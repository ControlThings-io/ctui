"""Project-scoped SQLite persistence for configs, history, and protocol records.

A catalog maps human names to UUID identities; each project has its own database
so snapshots can travel between installations of the same application. state.json
records the last selected UUID. aiosqlite moves SQL work off the event loop;
filesystem and JSON operations here are still synchronous. Individual SQL calls
are queued by the connection, not a blanket guarantee of isolation across
multi-call operations. Applications should coordinate project switches and
transactional maintenance with their active commands.

Service facades follow the backend's active connection. Command registration
adds confirmation and history policy around backend operations; calling a
backend method directly does not display a confirmation dialog.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Mapping, Sequence

import aiosqlite
from platformdirs import user_data_path

from ctui.path_completion import PathCompleter

from .commands import Argument, CommandError, CommandResult
from .services import HistoryEntry

SCHEMA_VERSION = 1

SCHEMA_STATEMENTS = (
    "CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE configs(
        name TEXT PRIMARY KEY, value TEXT NOT NULL,
        template INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE history(
        id INTEGER PRIMARY KEY, command TEXT NOT NULL, timestamp TEXT NOT NULL)""",
    """CREATE TABLE record_sessions(
        id INTEGER PRIMARY KEY, protocol TEXT NOT NULL, started_at TEXT NOT NULL,
        ended_at TEXT, metadata TEXT)""",
    """CREATE TABLE records(
        id INTEGER PRIMARY KEY, session_id INTEGER, timestamp TEXT NOT NULL,
        direction TEXT NOT NULL, protocol TEXT NOT NULL, payload BLOB NOT NULL,
        decoded TEXT, metadata TEXT,
        FOREIGN KEY(session_id) REFERENCES record_sessions(id))""",
    "CREATE INDEX records_timestamp ON records(timestamp)",
    "CREATE INDEX records_session ON records(session_id)",
)

# Each key is the version before its migration. Add version N migration statements
# under key N, then increment SCHEMA_VERSION to N + 1.
SCHEMA_MIGRATIONS: dict[int, tuple[str, ...]] = {
    0: tuple(
        statement.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1).replace(
            "CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1
        )
        for statement in SCHEMA_STATEMENTS
    ),
}

REQUIRED_PROJECT_TABLES = {
    "metadata",
    "configs",
    "history",
    "record_sessions",
    "records",
}
REQUIRED_PROJECT_COLUMNS = {
    "metadata": {"key", "value"},
    "configs": {"name", "value", "template"},
    "history": {"id", "command", "timestamp"},
    "record_sessions": {
        "id",
        "protocol",
        "started_at",
        "ended_at",
        "metadata",
    },
    "records": {
        "id",
        "session_id",
        "timestamp",
        "direction",
        "protocol",
        "payload",
        "decoded",
        "metadata",
    },
}


async def _connect(path, *, uri=False) -> aiosqlite.Connection:
    """Open a worker-thread-backed SQLite connection."""
    return await aiosqlite.connect(path, uri=uri)


@dataclass(frozen=True)
class ProjectInfo:
    """Immutable catalog identity, display name, and ISO-format timestamps.

    id is a UUID used for database filenames, so renaming a project does not
    change its identity. created_at and modified_at are stored as strings.
    """

    id: str
    name: str
    created_at: str
    modified_at: str


@dataclass(frozen=True)
class RecordEntry:
    """One stored protocol interaction returned by a record query.

    id and optional session_id belong to the project database. timestamp is a
    datetime decoded from the stored ISO value; payload retains raw bytes.
    decoded and metadata are JSON-decoded values or None. direction and protocol
    are application-supplied labels rather than framework enums.
    """

    id: int
    session_id: int | None
    timestamp: datetime
    direction: str
    protocol: str
    payload: bytes
    decoded: Any
    metadata: Any


def _now() -> str:
    """Return a timezone-aware local timestamp serialized as ISO text."""
    return datetime.now().astimezone().isoformat()


def _json(value: Any) -> str | None:
    """Encode compact JSON, using SQL NULL for a Python None value."""
    return None if value is None else json.dumps(value, separators=(",", ":"))


def _validate_name(name: str, label: str) -> str:
    """Return a usable user-facing name or raise a concise command error."""
    if not isinstance(name, str) or not name.strip():
        raise CommandError(f"{label} name cannot be empty")
    if name != name.strip() or any(character in name for character in "\r\n\0"):
        raise CommandError(f"{label} name contains unsupported whitespace")
    return name


class ProjectHistory:
    """Async command history following the currently active project.

    Facades retain the backend rather than a connection snapshot, so project
    switches also switch history. append() commits and updates modification
    metadata. History-suppressing command metadata prevents project-management
    commands from polluting the outgoing or incoming project.
    """

    def __init__(self, backend: "SqliteProjectBackend"):
        """Bind history operations to the backend without opening a database."""
        self.backend = backend

    async def append(self, command: str) -> None:
        """Append an accepted command to the active project."""
        db = self.backend.connection
        await db.execute(
            "INSERT INTO history(command, timestamp) VALUES (?, ?)",
            (command, _now()),
        )
        await db.commit()
        await self.backend.touch()

    async def all(self) -> list[HistoryEntry]:
        """Return active-project history in insertion order."""
        cursor = await self.backend.connection.execute(
            "SELECT command, timestamp FROM history ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [HistoryEntry(row[0], datetime.fromisoformat(row[1])) for row in rows]

    async def search(
        self, keyword: str, *, limit: int = 0, since: str | None = None
    ) -> list[HistoryEntry]:
        """Return matching history in insertion order, optionally by age and count.

        Match keyword with SQL LIKE, so % and _ retain wildcard meanings. since
        accepts non-negative integer durations such as 7d, 12h, or 30m. A positive
        limit selects the most recent matches before restoring their insertion
        order; zero means unlimited and negative limits raise CommandError.
        """
        if limit < 0:
            raise CommandError("history limit cannot be negative")
        sql = "SELECT command, timestamp FROM history WHERE command LIKE ?"
        values: list[Any] = [f"%{keyword}%"]
        if since:
            cutoff = _parse_since(since)
            sql += " AND timestamp >= ?"
            values.append(cutoff.isoformat())
        sql += " ORDER BY id DESC"
        if limit:
            sql += " LIMIT ?"
            values.append(limit)
        cursor = await self.backend.connection.execute(sql, values)
        rows = await cursor.fetchall()
        rows.reverse()
        return [HistoryEntry(row[0], datetime.fromisoformat(row[1])) for row in rows]

    async def clear(self) -> None:
        """Remove all history from the active project."""
        await self.backend.connection.execute("DELETE FROM history")
        await self.backend.connection.commit()
        await self.backend.touch()


class ProjectConfigs:
    """Async named JSON profiles with application-registered templates.

    Templates are copied at registration, inserted when missing on project
    activation, and restored on reset. Saving a profile does not mutate the
    registered template. Runtime clients and sockets belong on the app, not in
    these serialized values. Import/export uses versioned JSON rather than TOML.
    """

    def __init__(self, backend: "SqliteProjectBackend"):
        """Bind config operations and create an empty in-process template registry."""
        self.backend = backend
        self.templates: dict[str, dict[str, Any]] = {}

    def register_template(self, name: str, values: dict[str, Any]) -> None:
        """Snapshot a JSON-compatible default profile for future initialization.

        Require a nonblank name and JSON-serializable values. Copy through JSON so
        later caller mutations do not affect the template. Registration does not
        write the active database; initialization fills missing profiles and reset
        restores their registered values.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("A config template requires a name")
        json.dumps(values)
        self.templates[name] = json.loads(json.dumps(values))

    async def initialize_templates(self) -> None:
        """Add any missing registered templates to the active project."""
        for name, values in self.templates.items():
            await self.backend.connection.execute(
                "INSERT OR IGNORE INTO configs(name, value, template) VALUES (?, ?, 1)",
                (name, _json(values)),
            )
        await self.backend.connection.commit()

    async def list(self) -> dict[str, Any]:
        """Return all configs in the active project, ordered by name."""
        cursor = await self.backend.connection.execute(
            "SELECT name, value FROM configs ORDER BY name"
        )
        return {row[0]: json.loads(row[1]) for row in await cursor.fetchall()}

    async def get(self, name: str) -> Any:
        """Return one named config or raise ``CommandError``."""
        cursor = await self.backend.connection.execute(
            "SELECT value FROM configs WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise CommandError(f"Unknown config: {name!r}")
        return json.loads(row[0])

    async def save(self, name: str, values: Any) -> None:
        """Create or replace a JSON-compatible named config."""
        _validate_name(name, "Config")
        encoded = _json(values)
        await self.backend.connection.execute(
            """INSERT INTO configs(name, value, template) VALUES (?, ?, 0)
               ON CONFLICT(name) DO UPDATE SET value=excluded.value""",
            (name, encoded),
        )
        await self.backend.connection.commit()
        await self.backend.touch()

    async def delete(self, name: str) -> None:
        """Delete a named config when it exists."""
        await self.backend.connection.execute(
            "DELETE FROM configs WHERE name = ?", (name,)
        )
        await self.backend.connection.commit()
        await self.backend.touch()

    async def reset(self) -> None:
        """Delete configs and restore registered templates."""
        await self.backend.connection.execute("DELETE FROM configs")
        await self.initialize_templates()
        await self.backend.touch()

    async def export_file(self, path: Path, app_id: str) -> None:
        """Write a UTF-8 JSON config document, replacing the destination contents.

        Include format ctui-configs, version 1, app_id, and all named configs.
        This exports profiles only, not history, sessions, or raw protocol records.
        Filesystem errors propagate to the caller.
        """
        document = {
            "format": "ctui-configs",
            "version": 1,
            "app_id": app_id,
            "configs": await self.list(),
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    async def import_file(self, path: Path, app_id: str) -> int:
        """Merge a compatible JSON config document and return its profile count.

        Require format ctui-configs, version 1, matching app_id, and a configs
        object. Replace values for matching names and retain unrelated profiles.
        Apply the merge in a transaction with rollback on failure. Invalid files
        or compatibility metadata raise CommandError; this method does not prompt.
        """
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Cannot import configs: {error}") from error
        if not isinstance(document, dict):
            raise CommandError("Config export must contain a JSON object")
        if document.get("format") != "ctui-configs" or document.get("version") != 1:
            raise CommandError("Unsupported config export format")
        if document.get("app_id") != app_id:
            raise CommandError(
                f"Configs belong to {document.get('app_id')!r}, not {app_id!r}"
            )
        configs = document.get("configs")
        if not isinstance(configs, dict):
            raise CommandError("Config export must contain a configs object")
        await self.backend.connection.execute("BEGIN")
        try:
            for name, value in configs.items():
                await self.backend.connection.execute(
                    """INSERT INTO configs(name, value, template) VALUES (?, ?, 0)
                       ON CONFLICT(name) DO UPDATE SET value=excluded.value""",
                    (name, _json(value)),
                )
            await self.backend.connection.commit()
        except Exception:
            await self.backend.connection.rollback()
            raise
        await self.backend.touch()
        return len(configs)


class ProjectRecords:
    """Append and query raw or decoded traffic in the active project.

    Sessions group related interactions but are optional. Store payload as a
    SQLite BLOB and decoded/metadata values as JSON. The framework supplies no
    protocol-specific record commands; applications decide how to inspect traffic.
    """

    def __init__(self, backend: "SqliteProjectBackend"):
        """Bind record operations to the backend without opening a database."""
        self.backend = backend

    async def start_session(self, protocol: str, metadata: Any = None) -> int:
        """Create a recording session and return its project-local integer id.

        Record protocol, current time, and optional JSON-compatible metadata. Pass
        the returned id explicitly to append(); there is no implicit active session.
        """
        cursor = await self.backend.connection.execute(
            "INSERT INTO record_sessions(protocol, started_at, metadata) VALUES (?, ?, ?)",
            (protocol, _now(), _json(metadata)),
        )
        await self.backend.connection.commit()
        return cursor.lastrowid

    async def end_session(self, session_id: int) -> None:
        """Set a session's end timestamp; an unknown id updates no rows.

        This records metadata only; it does not prevent later appends to that id.
        """
        await self.backend.connection.execute(
            "UPDATE record_sessions SET ended_at = ? WHERE id = ?",
            (_now(), session_id),
        )
        await self.backend.connection.commit()

    async def append(
        self,
        *,
        direction: str,
        protocol: str,
        payload: bytes = b"",
        session: int | None = None,
        decoded: Any = None,
        metadata: Any = None,
    ) -> int:
        """Commit one protocol interaction and return its project-local id.

        Supply direction and protocol labels, raw payload bytes, and optional
        JSON-compatible decoded data or metadata. session may be omitted; when
        provided it must reference an existing session under SQLite foreign keys.
        Timestamp automatically and update the project's modification metadata.
        """
        cursor = await self.backend.connection.execute(
            """INSERT INTO records
               (session_id, timestamp, direction, protocol, payload, decoded, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session,
                _now(),
                direction,
                protocol,
                payload,
                _json(decoded),
                _json(metadata),
            ),
        )
        await self.backend.connection.commit()
        await self.backend.touch()
        return cursor.lastrowid

    async def query(
        self,
        *,
        session: int | None = None,
        direction: str | None = None,
        protocol: str | None = None,
        limit: int = 0,
    ) -> list[RecordEntry]:
        """Return matching RecordEntry values in ascending insertion order.

        Combine provided session, direction, and protocol filters with equality and
        AND. A positive limit returns the earliest matching entries; zero means all.
        Negative limits raise CommandError. Querying materializes the returned list.
        """
        if limit < 0:
            raise CommandError("record limit cannot be negative")
        clauses, values = [], []
        for column, value in (
            ("session_id", session),
            ("direction", direction),
            ("protocol", protocol),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        sql = (
            "SELECT id, session_id, timestamp, direction, protocol, payload, "
            "decoded, metadata FROM records"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        if limit:
            sql += " LIMIT ?"
            values.append(limit)
        cursor = await self.backend.connection.execute(sql, values)
        return [
            RecordEntry(
                row[0],
                row[1],
                datetime.fromisoformat(row[2]),
                row[3],
                row[4],
                row[5],
                json.loads(row[6]) if row[6] else None,
                json.loads(row[7]) if row[7] else None,
            )
            for row in await cursor.fetchall()
        ]


class SqliteProjectBackend:
    """Manage a catalog and one asynchronous SQLite database per project.

    Use a stable app_id to isolate application data and validate imports. The
    default root comes from platformdirs; data_dir overrides it. Store the
    catalog at projects/catalog.sqlite3, UUID databases at projects/databases,
    and active selection in state.json. history, configs, and records facades
    always follow the current connection.

    Await open() before using services and close() after use; CtuiApp's runtime
    entry points manage this automatically. Active connections enable foreign
    keys, WAL journaling, a five-second busy timeout, and NORMAL synchronous
    mode. SQLite backup APIs produce consistent snapshots, including WAL data.

    Framework and application schemas are versioned separately. Existing
    projects are checked for identity, integrity, supported versions, required
    columns/tables, and record-session references before activation. Older
    schemas need ordered migrations; retain a pre-migration backup and apply
    framework/application migration statements in one transaction. Reject
    newer schemas and missing migration paths rather than guessing changes.

    Backend methods perform no interactive confirmation. Built-in commands add
    that policy. Coordinate project switching with active application work;
    facades are not permanently bound to the project active at their creation.
    """

    def __init__(
        self,
        app_id: str,
        *,
        app_author: str | None = None,
        data_dir: Path | None = None,
        tool_version: str = "",
        tool_schema_version: int = 1,
        tool_migrations: Mapping[int, Sequence[str]] | None = None,
    ):
        """Configure identity, storage paths, migration policy, and service facades.

        app_author is passed to platformdirs when no data_dir is supplied.
        tool_version is descriptive metadata; tool_schema_version is a positive
        integer used for compatibility. tool_migrations maps each prior positive
        version N to SQL statements advancing it to N+1. Reject invalid keys or
        empty/non-string statements. Database connections open later in open().
        New projects receive the current framework schema and tool version metadata;
        application migrations are for existing projects, not a new-schema hook.
        """
        if (
            isinstance(tool_schema_version, bool)
            or not isinstance(tool_schema_version, int)
            or tool_schema_version < 1
        ):
            raise ValueError("tool_schema_version must be a positive integer")
        migrations = tool_migrations or {}
        for version, statements in migrations.items():
            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
                or version >= tool_schema_version
            ):
                raise ValueError(
                    "tool migration keys must be positive versions below "
                    "tool_schema_version"
                )
            if isinstance(statements, str) or not all(
                isinstance(statement, str) and statement.strip()
                for statement in statements
            ):
                raise ValueError("tool migrations must contain non-empty SQL strings")
        self.app_id = app_id
        self.tool_version = tool_version
        self.tool_schema_version = tool_schema_version
        self.tool_migrations = {
            version: tuple(statements) for version, statements in migrations.items()
        }
        self.root = (
            Path(data_dir)
            if data_dir
            else user_data_path(app_id, app_author, ensure_exists=True)
        )
        self.projects_dir = self.root / "projects"
        self.databases_dir = self.projects_dir / "databases"
        self.catalog_path = self.projects_dir / "catalog.sqlite3"
        self.state_path = self.root / "state.json"
        self.catalog: aiosqlite.Connection | None = None
        self.connection: aiosqlite.Connection | None = None
        self.current: ProjectInfo | None = None
        self.history = ProjectHistory(self)
        self.configs = ProjectConfigs(self)
        self.records = ProjectRecords(self)

    async def open(self) -> None:
        """Open the catalog and activate the saved, first, or default project.

        Read the selected UUID from state.json. Missing or malformed state falls
        back to the first catalog project in name order; an empty catalog creates
        default. Activation validates/migrates the database and adds missing config
        templates. Call close() even if opening fails partway through.
        """
        self.databases_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = await _connect(self.catalog_path)
        await self.catalog.execute("PRAGMA foreign_keys = ON")
        await self.catalog.execute("PRAGMA busy_timeout = 5000")
        await self.catalog.execute("""CREATE TABLE IF NOT EXISTS projects(
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL, modified_at TEXT NOT NULL)""")
        await self.catalog.commit()
        projects = await self.list_projects()
        wanted = self._read_state()
        selected = next((p for p in projects if p.id == wanted), None)
        if selected is None:
            selected = (
                projects[0]
                if projects
                else await self.create("default", activate=False)
            )
        await self.load(selected.name)

    async def close(self) -> None:
        """Close active-project and catalog database connections."""
        if self.connection:
            await self.connection.close()
            self.connection = None
        if self.catalog:
            await self.catalog.close()
            self.catalog = None

    def _database_path(self, project_id: str) -> Path:
        """Derive the database filename from UUID identity, never the display name."""
        return self.databases_dir / f"{project_id}.sqlite3"

    def _read_state(self) -> str | None:
        """Read the saved project UUID; ignore missing or malformed selection files."""
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")).get(
                "active_project"
            )
        except (OSError, json.JSONDecodeError, AttributeError):
            return None

    def _write_state(self) -> None:
        """Replace state.json atomically with the currently selected project UUID."""
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"active_project": self.current.id}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    async def _open_project(self, info: ProjectInfo) -> None:
        """Validate and prepare a candidate before replacing the active connection.

        Close the candidate on preparation failure, preserving the previous active
        connection. Once validation succeeds, switch, close the previous connection,
        persist the selected UUID, and initialize missing config templates.
        """
        path = self._database_path(info.id)
        is_new = not path.exists() or path.stat().st_size == 0
        candidate = await _connect(path)
        try:
            await candidate.execute("PRAGMA foreign_keys = ON")
            await candidate.execute("PRAGMA busy_timeout = 5000")
            if is_new:
                await self._initialize_schema(candidate, info)
            else:
                await self._prepare_existing_schema(candidate, path, info)
            await candidate.execute("PRAGMA journal_mode = WAL")
            await candidate.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            await candidate.close()
            raise

        previous = self.connection
        self.connection, self.current = candidate, info
        if previous:
            await previous.close()
        self._write_state()
        await self.configs.initialize_templates()

    async def _initialize_schema(
        self, connection: aiosqlite.Connection, info: ProjectInfo
    ) -> None:
        """Create the current schema transactionally for a new project."""
        await connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in SCHEMA_STATEMENTS:
                await connection.execute(statement)
            await self._write_project_metadata(connection, info, include_identity=True)
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise

    async def _inspect_schema(
        self, connection: aiosqlite.Connection
    ) -> tuple[int, int]:
        """Validate database integrity and return ctui and tool schema versions."""
        try:
            cursor = await connection.execute("PRAGMA quick_check")
            check = await cursor.fetchone()
            if check is None or check[0] != "ok":
                raise CommandError(f"Project database integrity check failed: {check}")
            cursor = await connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}
            if "metadata" not in tables:
                raise CommandError("Project database is missing its metadata table")
            cursor = await connection.execute("SELECT key, value FROM metadata")
            metadata = dict(await cursor.fetchall())
        except sqlite3.Error as error:
            raise CommandError(f"Invalid project database: {error}") from error

        if metadata.get("app_id") != self.app_id:
            raise CommandError("Project file belongs to a different application")
        try:
            schema = int(metadata["schema_version"])
            tool_schema = int(metadata.get("tool_schema_version", "1"))
        except (KeyError, TypeError, ValueError) as error:
            raise CommandError(
                "Project database has invalid schema metadata"
            ) from error
        if schema < 0 or tool_schema < 0:
            raise CommandError("Project database has invalid schema metadata")
        if schema > SCHEMA_VERSION:
            raise CommandError(
                f"Project uses ctui schema {schema}, newer than supported schema "
                f"{SCHEMA_VERSION}"
            )
        if tool_schema > self.tool_schema_version:
            raise CommandError(
                f"Project schema {tool_schema} is newer than supported schema "
                f"{self.tool_schema_version}"
            )
        return schema, tool_schema

    async def _prepare_existing_schema(
        self,
        connection: aiosqlite.Connection,
        path: Path,
        info: ProjectInfo,
    ) -> None:
        """Validate, migrate when needed, and refresh project metadata."""
        schema, tool_schema = await self._inspect_schema(connection)
        if schema < SCHEMA_VERSION or tool_schema < self.tool_schema_version:
            await self._backup_before_migration(connection, path, schema, tool_schema)
            await self._migrate_schemas(connection, schema, tool_schema)
        await self._validate_required_schema(connection)
        await self._write_project_metadata(connection, info)
        await connection.commit()

    async def _validate_required_schema(self, connection: aiosqlite.Connection) -> None:
        """Verify required tables, columns, and foreign-key consistency."""
        cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        missing_tables = REQUIRED_PROJECT_TABLES - tables
        if missing_tables:
            raise CommandError(
                "Project database is missing required tables: "
                + ", ".join(sorted(missing_tables))
            )
        for table, required in REQUIRED_PROJECT_COLUMNS.items():
            cursor = await connection.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in await cursor.fetchall()}
            missing_columns = required - columns
            if missing_columns:
                raise CommandError(
                    f"Project database table {table!r} is missing columns: "
                    + ", ".join(sorted(missing_columns))
                )
        cursor = await connection.execute("PRAGMA foreign_key_check")
        violation = await cursor.fetchone()
        if violation is not None:
            raise CommandError(
                "Project database contains invalid record-session references"
            )

    async def _backup_before_migration(
        self,
        connection: aiosqlite.Connection,
        path: Path,
        schema: int,
        tool_schema: int,
    ) -> Path:
        """Create a timestamped pre-migration SQLite backup beside the database.

        Include old framework/tool versions in the name for recovery. Use SQLite's
        backup API for consistency; remove a partially created backup on failure.
        Successful backups remain on disk for manual recovery.
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        backup_path = path.with_name(
            f"{path.name}.pre-migration-v{schema}-tool{tool_schema}-{timestamp}.bak"
        )
        try:
            destination = await _connect(backup_path)
            try:
                await connection.backup(destination)
            finally:
                await destination.close()
        except Exception:
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass
            raise
        return backup_path

    async def _migrate_schemas(
        self,
        connection: aiosqlite.Connection,
        start_version: int,
        tool_start_version: int,
    ) -> None:
        """Apply ordered framework and application migrations in one transaction.

        Keys identify the version before each step. Update version metadata after
        each step, validate the required schema, then commit. Roll back on any error;
        missing paths and failed statements become user-facing CommandError values.
        The caller creates the backup before entering this transaction.
        """
        await connection.execute("BEGIN IMMEDIATE")
        try:
            version = start_version
            while version < SCHEMA_VERSION:
                statements = SCHEMA_MIGRATIONS.get(version)
                if statements is None:
                    raise CommandError(
                        f"No migration exists from ctui schema {version}"
                    )
                for statement in statements:
                    await connection.execute(statement)
                version += 1
                await connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    (str(version),),
                )
            tool_version = tool_start_version
            while tool_version < self.tool_schema_version:
                statements = self.tool_migrations.get(tool_version)
                if statements is None:
                    raise CommandError(
                        f"No application migration exists from schema {tool_version}"
                    )
                for statement in statements:
                    await connection.execute(statement)
                tool_version += 1
                await connection.execute(
                    "UPDATE metadata SET value = ? "
                    "WHERE key = 'tool_schema_version'",
                    (str(tool_version),),
                )
            await self._validate_required_schema(connection)
            await connection.commit()
        except Exception as error:
            await connection.rollback()
            if isinstance(error, CommandError):
                raise
            raise CommandError(f"Project schema migration failed: {error}") from error

    async def _write_project_metadata(
        self,
        connection: aiosqlite.Connection,
        info: ProjectInfo,
        *,
        include_identity: bool = False,
    ) -> None:
        """Write framework, application, and catalog identity metadata."""
        if include_identity:
            metadata = {
                "schema_version": str(SCHEMA_VERSION),
                "app_id": self.app_id,
            }
        else:
            metadata = {}
        metadata = {
            **metadata,
            "tool_version": self.tool_version,
            "tool_schema_version": str(self.tool_schema_version),
            "project_id": info.id,
            "project_name": info.name,
            "project_created_at": info.created_at,
        }
        for key, value in metadata.items():
            await connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (key, value),
            )

    async def list_projects(self) -> list[ProjectInfo]:
        """Return catalog projects ordered by name."""
        cursor = await self.catalog.execute(
            "SELECT id, name, created_at, modified_at FROM projects ORDER BY name"
        )
        return [ProjectInfo(*row) for row in await cursor.fetchall()]

    async def find(self, name: str) -> ProjectInfo:
        """Return a project by exact name or raise ``CommandError``."""
        cursor = await self.catalog.execute(
            "SELECT id, name, created_at, modified_at FROM projects WHERE name = ?",
            (name,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise CommandError(f"Unknown project: {name!r}")
        return ProjectInfo(*row)

    async def create(self, name: str, *, activate: bool = True) -> ProjectInfo:
        """Create a project and optionally make it active."""
        _validate_name(name, "Project")
        project_id, now = str(uuid.uuid4()), _now()
        try:
            await self.catalog.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?)",
                (project_id, name, now, now),
            )
            await self.catalog.commit()
        except sqlite3.IntegrityError as error:
            raise CommandError(f"A project named {name!r} already exists") from error
        info = ProjectInfo(project_id, name, now, now)
        try:
            if activate:
                await self._open_project(info)
            else:
                db = await _connect(self._database_path(project_id))
                await db.close()
        except Exception:
            await self._discard_project(info)
            raise
        return info

    async def load(self, name: str) -> ProjectInfo:
        """Make an existing project active."""
        info = await self.find(name)
        await self._open_project(info)
        return info

    async def rename(self, name: str) -> ProjectInfo:
        """Rename the active project."""
        _validate_name(name, "Project")
        try:
            await self.catalog.execute(
                "UPDATE projects SET name = ?, modified_at = ? WHERE id = ?",
                (name, _now(), self.current.id),
            )
            await self.catalog.commit()
        except sqlite3.IntegrityError as error:
            raise CommandError(f"A project named {name!r} already exists") from error
        self.current = await self.find(name)
        await self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('project_name', ?)",
            (name,),
        )
        await self.connection.commit()
        return self.current

    async def delete(self, name: str) -> None:
        """Permanently delete an inactive project and its associated database files.

        Reject the active project; callers must switch first. Remove its catalog
        entry, database, journals, and migration backups. No trash or confirmation
        exists at this layer; the built-in command requires explicit approval.
        """
        info = await self.find(name)
        if info.id == self.current.id:
            raise CommandError(
                "Load another project before deleting the active project"
            )
        await self.catalog.execute("DELETE FROM projects WHERE id = ?", (info.id,))
        await self.catalog.commit()
        self._remove_database_files(info.id)

    async def _discard_project(self, info: ProjectInfo) -> None:
        """Remove a failed catalog insertion and every partial database file."""
        await self.catalog.execute("DELETE FROM projects WHERE id = ?", (info.id,))
        await self.catalog.commit()
        self._remove_database_files(info.id)

    def _remove_database_files(self, project_id: str) -> None:
        """Remove SQLite, journal, and migration files for one project id."""
        database = self._database_path(project_id)
        for path in database.parent.glob(f"{database.name}*"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    async def saveas(self, name: str) -> ProjectInfo:
        """Clone the current database under a new UUID/name and activate the copy.

        Use a consistent SQLite backup, retaining configs, history, sessions, and
        records. Reject duplicate names. Remove the new catalog entry and partial
        files if copying or preparing the clone fails.
        """
        _validate_name(name, "Project")
        project_id, now = str(uuid.uuid4()), _now()
        try:
            await self.catalog.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?)",
                (project_id, name, now, now),
            )
            await self.catalog.commit()
        except sqlite3.IntegrityError as error:
            raise CommandError(f"A project named {name!r} already exists") from error
        try:
            destination = await _connect(self._database_path(project_id))
            try:
                await self.connection.backup(destination)
            finally:
                await destination.close()
            info = ProjectInfo(project_id, name, now, now)
            await self._open_project(info)
        except Exception:
            await self._discard_project(ProjectInfo(project_id, name, now, now))
            raise
        return info

    async def export_project(self, path: Path) -> None:
        """Write a consistent SQLite snapshot of the active project.

        Use the backup API rather than copying a live WAL database file. The usual
        exchange suffix is .ctui-project, but no suffix is enforced. This includes
        all database contents and metadata, not the catalog or state.json.
        """
        destination = await _connect(path)
        try:
            await self.connection.backup(destination)
        finally:
            await destination.close()

    async def import_project(self, path: Path, name: str | None = None) -> ProjectInfo:
        """Copy and activate a compatible snapshot under a fresh project UUID.

        Open the source read-only and check integrity, app_id, and supported schema
        versions. Use the supplied name, embedded project name, or filename stem;
        reject catalog name conflicts. Copy with SQLite backup and prepare/migrate
        the copy before activation, preserving the source file. Validation/import
        failures remove the new catalog entry and partial files.
        """
        if not path.is_file():
            raise CommandError(f"Project file does not exist: {path}")
        source = None
        info = None
        try:
            source = await _connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            await self._inspect_schema(source)
            cursor = await source.execute(
                "SELECT value FROM metadata WHERE key = 'project_name'"
            )
            row = await cursor.fetchone()
            project_name = name or (row[0] if row else None) or path.stem
            info = await self.create(project_name, activate=False)
            destination = await _connect(self._database_path(info.id))
            try:
                await source.backup(destination)
            finally:
                await destination.close()
            await self._open_project(info)
            return info
        except CommandError:
            if info is not None:
                await self._discard_project(info)
            raise
        except (OSError, sqlite3.Error, ValueError) as error:
            if info is not None:
                await self._discard_project(info)
            raise CommandError(f"Cannot import project: {error}") from error
        finally:
            if source is not None:
                await source.close()

    async def reset(self, section: str) -> None:
        """Clear configs, records, history, or all data in the current project.

        Delete records before their sessions to respect foreign keys. Table deletion
        is transactional; configs/all then restore registered config templates.
        Keep project identity and schema. Unknown sections raise CommandError.
        Confirmation belongs to the command layer, not this method.
        """
        tables = {
            "history": ("history",),
            "records": ("records", "record_sessions"),
            "configs": ("configs",),
            "all": ("records", "record_sessions", "history", "configs"),
        }
        if section not in tables:
            raise CommandError("Reset must be one of: configs, records, history, all")
        await self.connection.execute("BEGIN")
        try:
            for table in tables[section]:
                await self.connection.execute(f"DELETE FROM {table}")
            await self.connection.commit()
        except Exception:
            await self.connection.rollback()
            raise
        if section in ("configs", "all"):
            await self.configs.initialize_templates()
        await self.touch()

    async def stats(self) -> dict[str, Any]:
        """Return counts, payload size, and path for the active project."""
        values = {}
        for key, table in (
            ("configs", "configs"),
            ("sessions", "record_sessions"),
            ("records", "records"),
            ("history", "history"),
        ):
            cursor = await self.connection.execute(f"SELECT COUNT(*) FROM {table}")
            values[key] = (await cursor.fetchone())[0]
        cursor = await self.connection.execute(
            "SELECT COALESCE(SUM(length(payload)), 0) FROM records"
        )
        values["record_bytes"] = (await cursor.fetchone())[0]
        values["path"] = self._database_path(self.current.id)
        return values

    async def touch(self) -> None:
        """Update modification metadata for the active project."""
        now = _now()
        await self.catalog.execute(
            "UPDATE projects SET modified_at = ? WHERE id = ?", (now, self.current.id)
        )
        await self.catalog.commit()
        self.current = ProjectInfo(
            self.current.id, self.current.name, self.current.created_at, now
        )
        await self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) "
            "VALUES ('project_modified_at', ?)",
            (now,),
        )
        await self.connection.commit()


def _parse_since(value: str) -> datetime:
    """Parse compact relative durations such as 7d, 12h, or 30m."""
    if len(value) < 2 or not value[:-1].isdigit() or value[-1] not in "dhm":
        raise CommandError("since must be a duration such as 7d, 12h, or 30m")
    amount = int(value[:-1])
    delta = {
        "d": timedelta(days=amount),
        "h": timedelta(hours=amount),
        "m": timedelta(minutes=amount),
    }[value[-1]]
    return datetime.now().astimezone() - delta


def register_project_commands(app: Any) -> None:
    """Install project/config commands around the configured backend and services.

    These commands suppress history, especially when switching projects or
    resetting history. Create, saveas, load, and import emit project_changed
    with previous/current metadata; create uses previous=None. Delete and reset
    commands require formatted confirmation. Config exchange uses JSON; project
    exchange uses SQLite. Record-specific commands remain application-owned.
    """

    backend = app.backend

    def register(*args, **kwargs):
        """Translate operational failures at the built-in command boundary."""

        def decorate(func):
            @wraps(func)
            async def guarded(*values, **options):
                try:
                    return await func(*values, **options)
                except CommandError:
                    raise
                except (OSError, UnicodeError, sqlite3.Error) as error:
                    raise CommandError(
                        f"{func.__name__.replace('_', ' ')}: {error}"
                    ) from error

            return app.commands.register(*args, **kwargs)(guarded)

        return decorate

    @register(name="project", record_history=False)
    async def project_status():
        """Show statistics for the active project."""
        info, stats = backend.current, await backend.stats()
        return CommandResult.success(
            "\n".join(
                (
                    f"Project: {info.name}",
                    f"Created: {info.created_at}",
                    f"Modified: {info.modified_at}",
                    "",
                    f"Configs: {stats['configs']}",
                    f"Record sessions: {stats['sessions']}",
                    f"Records: {stats['records']}",
                    f"Record data: {stats['record_bytes']} bytes",
                    f"History: {stats['history']}",
                    f"Database: {stats['path']}",
                )
            )
        )

    @register(
        name="project create",
        record_history=False,
        arguments={"name": Argument(help="Name for the new project")},
    )
    async def project_create(name: str):
        """Create and activate an empty project."""
        info = await backend.create(name)
        await app.events.emit("project_changed", previous=None, current=info)
        return f"Created and loaded project {name!r}."

    @register(
        name="project saveas",
        record_history=False,
        arguments={"name": Argument(help="Name for the project copy")},
    )
    async def project_saveas(name: str):
        """Clone the active project and activate the copy."""
        previous = backend.current
        info = await backend.saveas(name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Saved and loaded project {name!r}."

    @register(name="project list", record_history=False)
    async def project_list():
        """List stored projects."""
        projects = await backend.list_projects()
        return "\n".join(
            ("* " if item.id == backend.current.id else "  ") + item.name
            for item in projects
        )

    async def project_names(_context):
        """Suggest every project in the same catalog order as project list."""
        return [item.name for item in await backend.list_projects()]

    @register(
        name="project load",
        record_history=False,
        arguments={
            "name": Argument(help="Project to activate", completer=project_names)
        },
    )
    async def project_load(name: str):
        """Load a different project."""
        previous = backend.current
        info = await backend.load(name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Loaded project {name!r}."

    @register(
        name="project rename",
        record_history=False,
        arguments={"name": Argument(help="New name for the active project")},
    )
    async def project_rename(name: str):
        """Rename the active project."""
        old = backend.current.name
        await backend.rename(name)
        return f"Renamed project {old!r} to {name!r}."

    @register(
        name="project delete",
        record_history=False,
        confirmation="Permanently delete project {name} and all of its data?",
        arguments={"name": Argument(help="Inactive project to permanently delete")},
    )
    async def project_delete(name: str):
        """Permanently delete an inactive project."""
        await backend.delete(name)
        return f"Deleted project {name!r}."

    @register(
        name="project export",
        record_history=False,
        arguments={
            "path": Argument(
                help="Destination project snapshot file", completer=PathCompleter()
            )
        },
    )
    async def project_export(path: Path):
        """Export a consistent snapshot of the active project."""
        await backend.export_project(path)
        return f"Exported project to {path}."

    @register(
        name="project import",
        record_history=False,
        arguments={
            "path": Argument(
                help="Project snapshot file to import", completer=PathCompleter()
            ),
            "name": Argument(flags=("-n", "--name")),
        },
    )
    async def project_import(path: Path, name: str | None = None):
        """Import and activate a project snapshot."""
        previous = backend.current
        info = await backend.import_project(path, name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Imported and loaded project {info.name!r}."

    @register(
        name="project reset",
        record_history=False,
        confirmation="Reset {section} in the active project?",
        arguments={
            "section": Argument(
                help="Project data to reset",
                choices=("configs", "records", "history", "all"),
            )
        },
    )
    async def project_reset(section: str):
        """Reset configs, records, history, or all project data."""
        await backend.reset(section)
        return f"Reset project {section}."

    @register(name="configs", record_history=False)
    @register(name="configs list", record_history=False)
    async def configs_list():
        """List named configurations."""
        configs = await app.configs.list()
        return "\n".join(configs) if configs else "No configs."

    @register(
        name="configs show",
        record_history=False,
        arguments={"name": Argument(help="Configuration to display")},
    )
    async def configs_show(name: str):
        """Show one configuration as JSON."""
        return json.dumps(await app.configs.get(name), indent=2)

    @register(
        name="configs export",
        record_history=False,
        arguments={
            "path": Argument(help="Destination JSON file", completer=PathCompleter())
        },
    )
    async def configs_export(path: Path):
        """Export configurations as versioned JSON."""
        await app.configs.export_file(path, app.app_id)
        return f"Exported configs to {path}."

    @register(
        name="configs import",
        record_history=False,
        arguments={
            "path": Argument(
                help="Versioned JSON file to import", completer=PathCompleter()
            )
        },
    )
    async def configs_import(path: Path):
        """Import configurations from versioned JSON."""
        count = await app.configs.import_file(path, app.app_id)
        return f"Imported {count} configs."

    @register(
        name="configs reset",
        record_history=False,
        confirmation="Reset all configurations to application templates?",
    )
    async def configs_reset():
        """Reset configurations to registered application templates."""
        await app.configs.reset()
        return "Reset configs to application templates."
