"""Persistent project services backed by one SQLite database per project."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from platformdirs import user_data_path

from .commands import Argument, CommandError, CommandResult
from .services import HistoryEntry

SCHEMA_VERSION = 1


class _Cursor:
    """Async facade over a sqlite cursor owned by one connection."""

    def __init__(self, connection: "_Connection", cursor: sqlite3.Cursor):
        self.connection, self.cursor = connection, cursor

    @property
    def lastrowid(self):
        """Return the row identifier produced by the last insert."""
        return self.cursor.lastrowid

    async def fetchone(self):
        """Fetch one result row without blocking the event loop."""
        return await self.connection._run(self.cursor.fetchone)

    async def fetchall(self):
        """Fetch all remaining result rows without blocking the event loop."""
        return await self.connection._run(self.cursor.fetchall)


class _Connection:
    """Serialize sqlite3 work off the event loop for one database connection."""

    def __init__(self, raw: sqlite3.Connection):
        self.raw = raw
        self.lock = asyncio.Lock()

    async def _run(self, function, *args):
        async with self.lock:
            return function(*args)

    async def execute(self, sql, parameters=()):
        """Execute one SQL statement and return its cursor facade."""
        return _Cursor(self, await self._run(self.raw.execute, sql, parameters))

    async def executescript(self, script):
        """Execute a SQL script and return its cursor facade."""
        return _Cursor(self, await self._run(self.raw.executescript, script))

    async def commit(self):
        """Commit the current transaction."""
        await self._run(self.raw.commit)

    async def rollback(self):
        """Roll back the current transaction."""
        await self._run(self.raw.rollback)

    async def close(self):
        """Close the underlying SQLite connection."""
        await self._run(self.raw.close)

    async def backup(self, destination: "_Connection"):
        """Copy this database into *destination*."""
        await self._run(self.raw.backup, destination.raw)


async def _connect(path, *, uri=False) -> _Connection:
    raw = sqlite3.connect(path, uri=uri, check_same_thread=False)
    return _Connection(raw)


@dataclass(frozen=True)
class ProjectInfo:
    """Describe a project registered in the application catalog."""

    id: str
    name: str
    created_at: str
    modified_at: str


@dataclass(frozen=True)
class RecordEntry:
    """Represent one stored protocol interaction."""

    id: int
    session_id: int | None
    timestamp: datetime
    direction: str
    protocol: str
    payload: bytes
    decoded: Any
    metadata: Any


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, separators=(",", ":"))


def _validate_name(name: str, label: str) -> str:
    """Return a usable user-facing name or raise a concise command error."""
    if not isinstance(name, str) or not name.strip():
        raise CommandError(f"{label} name cannot be empty")
    if name != name.strip() or any(character in name for character in "\r\n\0"):
        raise CommandError(f"{label} name contains unsupported whitespace")
    return name


class ProjectHistory:
    """Store command history in the currently active project."""

    def __init__(self, backend: "SqliteProjectBackend"):
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
        """Find history containing *keyword*, optionally by age and count."""
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
    """Manage named JSON-compatible configurations and app templates."""

    def __init__(self, backend: "SqliteProjectBackend"):
        self.backend = backend
        self.templates: dict[str, dict[str, Any]] = {}

    def register_template(self, name: str, values: dict[str, Any]) -> None:
        """Register a JSON-compatible config populated in every project."""
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
        """Write configs to a versioned UTF-8 JSON document."""
        document = {
            "format": "ctui-configs",
            "version": 1,
            "app_id": app_id,
            "configs": await self.list(),
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    async def import_file(self, path: Path, app_id: str) -> int:
        """Merge a compatible config document and return its item count."""
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
    """Append and query protocol records in the active project."""

    def __init__(self, backend: "SqliteProjectBackend"):
        self.backend = backend

    async def start_session(self, protocol: str, metadata: Any = None) -> int:
        """Start a recording session and return its database identifier."""
        cursor = await self.backend.connection.execute(
            "INSERT INTO record_sessions(protocol, started_at, metadata) VALUES (?, ?, ?)",
            (protocol, _now(), _json(metadata)),
        )
        await self.backend.connection.commit()
        return cursor.lastrowid

    async def end_session(self, session_id: int) -> None:
        """Mark a recording session as ended."""
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
        """Append a protocol interaction and return its database identifier."""
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
        """Query records using generic fields understood by Ctui."""
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
    """Manage a catalog and a separate SQLite database for each project."""

    def __init__(
        self,
        app_id: str,
        *,
        app_author: str | None = None,
        data_dir: Path | None = None,
        tool_version: str = "",
        tool_schema_version: int = 1,
    ):
        """Configure project identity, storage location, and service facades."""
        self.app_id = app_id
        self.tool_version = tool_version
        self.tool_schema_version = tool_schema_version
        self.root = (
            Path(data_dir)
            if data_dir
            else user_data_path(app_id, app_author, ensure_exists=True)
        )
        self.projects_dir = self.root / "projects"
        self.databases_dir = self.projects_dir / "databases"
        self.catalog_path = self.projects_dir / "catalog.sqlite3"
        self.state_path = self.root / "state.json"
        self.catalog: _Connection | None = None
        self.connection: _Connection | None = None
        self.current: ProjectInfo | None = None
        self.history = ProjectHistory(self)
        self.configs = ProjectConfigs(self)
        self.records = ProjectRecords(self)

    async def open(self) -> None:
        """Open the catalog and activate the last-used or default project."""
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
        return self.databases_dir / f"{project_id}.sqlite3"

    def _read_state(self) -> str | None:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")).get(
                "active_project"
            )
        except (OSError, json.JSONDecodeError, AttributeError):
            return None

    def _write_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"active_project": self.current.id}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    async def _open_project(self, info: ProjectInfo) -> None:
        if self.connection:
            await self.connection.close()
        self.connection = await _connect(self._database_path(info.id))
        await self.connection.execute("PRAGMA journal_mode = WAL")
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.execute("PRAGMA busy_timeout = 5000")
        await self.connection.execute("PRAGMA synchronous = NORMAL")
        self.current = info
        await self._create_schema()
        self._write_state()
        await self.configs.initialize_templates()

    async def _create_schema(self) -> None:
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS configs(
                name TEXT PRIMARY KEY, value TEXT NOT NULL, template INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY, command TEXT NOT NULL, timestamp TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS record_sessions(
                id INTEGER PRIMARY KEY, protocol TEXT NOT NULL, started_at TEXT NOT NULL,
                ended_at TEXT, metadata TEXT);
            CREATE TABLE IF NOT EXISTS records(
                id INTEGER PRIMARY KEY, session_id INTEGER, timestamp TEXT NOT NULL,
                direction TEXT NOT NULL, protocol TEXT NOT NULL, payload BLOB NOT NULL,
                decoded TEXT, metadata TEXT,
                FOREIGN KEY(session_id) REFERENCES record_sessions(id));
            CREATE INDEX IF NOT EXISTS records_timestamp ON records(timestamp);
            CREATE INDEX IF NOT EXISTS records_session ON records(session_id);
            """)
        await self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        await self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('app_id', ?)",
            (self.app_id,),
        )
        metadata = {
            "tool_version": self.tool_version,
            "tool_schema_version": str(self.tool_schema_version),
            "project_id": self.current.id,
            "project_name": self.current.name,
            "project_created_at": self.current.created_at,
        }
        for key, value in metadata.items():
            await self.connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (key, value),
            )
        await self.connection.commit()

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
        if activate:
            await self._open_project(info)
        else:
            db = await _connect(self._database_path(project_id))
            await db.close()
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
        """Permanently delete an inactive project and its database files."""
        info = await self.find(name)
        if info.id == self.current.id:
            raise CommandError(
                "Load another project before deleting the active project"
            )
        await self.catalog.execute("DELETE FROM projects WHERE id = ?", (info.id,))
        await self.catalog.commit()
        database = self._database_path(info.id)
        for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    async def saveas(self, name: str) -> ProjectInfo:
        """Clone the active project under *name* and activate the clone."""
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
        destination = await _connect(self._database_path(project_id))
        try:
            await self.connection.backup(destination)
        finally:
            await destination.close()
        info = ProjectInfo(project_id, name, now, now)
        await self._open_project(info)
        return info

    async def export_project(self, path: Path) -> None:
        """Export a consistent SQLite snapshot of the active project."""
        destination = await _connect(path)
        try:
            await self.connection.backup(destination)
        finally:
            await destination.close()

    async def import_project(self, path: Path, name: str | None = None) -> ProjectInfo:
        """Import and activate a compatible project snapshot."""
        if not path.is_file():
            raise CommandError(f"Project file does not exist: {path}")
        source = await _connect(f"file:{path}?mode=ro", uri=True)
        try:
            cursor = await source.execute(
                "SELECT value FROM metadata WHERE key = 'app_id'"
            )
            row = await cursor.fetchone()
            if row is None or row[0] != self.app_id:
                raise CommandError("Project file belongs to a different application")
            cursor = await source.execute(
                "SELECT key, value FROM metadata WHERE key IN "
                "('project_name', 'tool_schema_version')"
            )
            metadata = dict(await cursor.fetchall())
            schema = int(metadata.get("tool_schema_version", "1"))
            if schema > self.tool_schema_version:
                raise CommandError(
                    f"Project schema {schema} is newer than supported schema "
                    f"{self.tool_schema_version}"
                )
            project_name = name or metadata.get("project_name") or path.stem
            info = await self.create(project_name, activate=False)
            destination = await _connect(self._database_path(info.id))
            try:
                await source.backup(destination)
            finally:
                await destination.close()
        finally:
            await source.close()
        await self._open_project(info)
        return info

    async def reset(self, section: str) -> None:
        """Clear one data section, restoring templates when appropriate."""
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
    """Install built-in project and config commands for a project backend."""

    backend = app.backend

    @app.commands.register(name="project", record_history=False)
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

    @app.commands.register(name="project create", record_history=False)
    async def project_create(name: str):
        """Create and activate an empty project."""
        info = await backend.create(name)
        await app.events.emit("project_changed", previous=None, current=info)
        return f"Created and loaded project {name!r}."

    @app.commands.register(name="project saveas", record_history=False)
    async def project_saveas(name: str):
        """Clone the active project and activate the copy."""
        previous = backend.current
        info = await backend.saveas(name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Saved and loaded project {name!r}."

    @app.commands.register(name="project list", record_history=False)
    async def project_list():
        """List stored projects."""
        projects = await backend.list_projects()
        return "\n".join(
            ("* " if item.id == backend.current.id else "  ") + item.name
            for item in projects
        )

    @app.commands.register(name="project load", record_history=False)
    async def project_load(name: str):
        """Load a different project."""
        previous = backend.current
        info = await backend.load(name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Loaded project {name!r}."

    @app.commands.register(name="project rename", record_history=False)
    async def project_rename(name: str):
        """Rename the active project."""
        old = backend.current.name
        await backend.rename(name)
        return f"Renamed project {old!r} to {name!r}."

    @app.commands.register(
        name="project delete",
        record_history=False,
        confirmation="Permanently delete project {name} and all of its data?",
    )
    async def project_delete(name: str):
        """Permanently delete an inactive project."""
        await backend.delete(name)
        return f"Deleted project {name!r}."

    @app.commands.register(name="project export", record_history=False)
    async def project_export(path: Path):
        """Export a consistent snapshot of the active project."""
        await backend.export_project(path)
        return f"Exported project to {path}."

    @app.commands.register(
        name="project import",
        record_history=False,
        arguments={"name": Argument(flags=("-n", "--name"))},
    )
    async def project_import(path: Path, name: str | None = None):
        """Import and activate a project snapshot."""
        previous = backend.current
        info = await backend.import_project(path, name)
        await app.events.emit("project_changed", previous=previous, current=info)
        return f"Imported and loaded project {info.name!r}."

    @app.commands.register(
        name="project reset",
        record_history=False,
        confirmation="Reset {section} in the active project?",
        arguments={
            "section": Argument(choices=("configs", "records", "history", "all"))
        },
    )
    async def project_reset(section: str):
        """Reset configs, records, history, or all project data."""
        await backend.reset(section)
        return f"Reset project {section}."

    @app.commands.register(name="configs", record_history=False)
    @app.commands.register(name="configs list", record_history=False)
    async def configs_list():
        """List named configurations."""
        configs = await app.configs.list()
        return "\n".join(configs) if configs else "No configs."

    @app.commands.register(name="configs show", record_history=False)
    async def configs_show(name: str):
        """Show one configuration as JSON."""
        return json.dumps(await app.configs.get(name), indent=2)

    @app.commands.register(name="configs export", record_history=False)
    async def configs_export(path: Path):
        """Export configurations as versioned JSON."""
        await app.configs.export_file(path, app.app_id)
        return f"Exported configs to {path}."

    @app.commands.register(name="configs import", record_history=False)
    async def configs_import(path: Path):
        """Import configurations from versioned JSON."""
        count = await app.configs.import_file(path, app.app_id)
        return f"Imported {count} configs."

    @app.commands.register(
        name="configs reset",
        record_history=False,
        confirmation="Reset all configurations to application templates?",
    )
    async def configs_reset():
        """Reset configurations to registered application templates."""
        await app.configs.reset()
        return "Reset configs to application templates."
