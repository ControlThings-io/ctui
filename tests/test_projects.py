import asyncio
import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import ctui.projects as projects_module
from ctui import CommandError, ConfirmationRequired, CtuiApp, SqliteProjectBackend


class ProjectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.app = CtuiApp(app_id="io.example.test", data_dir=Path(self.temporary.name))
        self.app.configs.register_template("local", {"host": "127.0.0.1"})
        await self.app.backend.open()

    async def asyncTearDown(self):
        await self.app.backend.close()
        self.temporary.cleanup()

    async def test_default_project_and_config_templates(self):
        self.assertEqual(self.app.backend.current.name, "default")
        self.assertEqual(await self.app.configs.get("local"), {"host": "127.0.0.1"})
        self.assertTrue((Path(self.temporary.name) / "state.json").exists())

    async def test_project_create_saveas_load_rename_and_delete(self):
        await self.app.dispatch("project create lab")
        await self.app.configs.save("device", {"port": 502})
        await self.app.dispatch("project saveas copied")
        self.assertEqual(await self.app.configs.get("device"), {"port": 502})
        await self.app.dispatch("project rename archive")
        await self.app.dispatch("project load lab")

        with self.assertRaises(ConfirmationRequired):
            await self.app.dispatch("project delete archive")
        await self.app.dispatch("project delete archive confirm")
        self.assertEqual(
            [item.name for item in await self.app.backend.list_projects()],
            ["default", "lab"],
        )

    async def test_history_search_clear_and_project_load_are_not_recorded(self):
        await self.app.dispatch("help")
        await self.app.dispatch("project create lab")
        await self.app.dispatch("project load default")
        entries = await self.app.history.all()
        self.assertEqual([entry.command for entry in entries], ["help"])
        result = await self.app.dispatch("history search help --since 7d --limit 5")
        self.assertEqual(result.output, "help")
        await self.app.dispatch("history clear confirm")
        self.assertEqual(await self.app.history.all(), [])

    async def test_config_json_and_project_snapshot_round_trip(self):
        await self.app.configs.save("remote", {"host": "10.0.0.2", "port": 502})
        root = Path(self.temporary.name)
        configs_path = root / "configs.json"
        await self.app.dispatch(f'configs export "{configs_path}"')
        document = json.loads(configs_path.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "ctui-configs")

        project_path = root / "shared.ctui-project"
        await self.app.dispatch(f'project export "{project_path}"')
        await self.app.dispatch(f'project import "{project_path}" --name imported')
        self.assertEqual(self.app.backend.current.name, "imported")
        self.assertEqual((await self.app.configs.get("remote"))["port"], 502)

    async def test_records_and_selective_reset(self):
        session = await self.app.records.start_session("modbus-tcp")
        await self.app.records.append(
            session=session,
            direction="sent",
            protocol="modbus-tcp",
            payload=b"request",
        )
        records = await self.app.records.query(direction="sent")
        self.assertEqual(records[0].payload, b"request")
        self.assertEqual((await self.app.backend.stats())["records"], 1)
        await self.app.dispatch("project reset records confirm")
        self.assertEqual((await self.app.backend.stats())["records"], 0)

    async def test_concurrent_record_writes_are_serialized(self):
        await asyncio.gather(
            *(
                self.app.records.append(
                    direction="received", protocol="tcp", payload=str(index).encode()
                )
                for index in range(50)
            )
        )
        self.assertEqual((await self.app.backend.stats())["records"], 50)

    async def test_slow_sqlite_work_does_not_block_the_event_loop(self):
        await self.app.backend.connection.create_function("delay", 1, time.sleep)
        query = asyncio.create_task(
            self.app.backend.connection.execute("SELECT delay(?)", (0.1,))
        )

        await asyncio.sleep(0.02)

        self.assertFalse(query.done())
        cursor = await query
        await cursor.fetchone()

    async def test_invalid_names_limits_and_config_documents_are_command_errors(self):
        for name in ("", " ", " trailing ", "bad\nname"):
            with self.subTest(name=name), self.assertRaises(CommandError):
                await self.app.backend.create(name)

        with self.assertRaisesRegex(CommandError, "history limit"):
            await self.app.history.search("anything", limit=-1)
        with self.assertRaisesRegex(CommandError, "record limit"):
            await self.app.records.query(limit=-1)

        invalid = Path(self.temporary.name) / "configs.json"
        invalid.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(CommandError, "JSON object"):
            await self.app.configs.import_file(invalid, self.app.app_id)

    async def _export_with_metadata(self, filename, **metadata):
        """Export a project and replace selected metadata values."""
        path = Path(self.temporary.name) / filename
        await self.app.backend.export_project(path)
        with closing(sqlite3.connect(path)) as connection, connection:
            for key, value in metadata.items():
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                    (key, str(value)),
                )
        return path

    async def test_older_schema_is_backed_up_and_migrated(self):
        await self.app.configs.save("device", {"port": 502})
        path = await self._export_with_metadata("legacy.ctui-project", schema_version=0)

        info = await self.app.backend.import_project(path, "migrated")

        cursor = await self.app.backend.connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        )
        self.assertEqual(
            (await cursor.fetchone())[0], str(projects_module.SCHEMA_VERSION)
        )
        self.assertEqual(await self.app.configs.get("device"), {"port": 502})
        database = self.app.backend._database_path(info.id)
        self.assertTrue(
            list(database.parent.glob(f"{database.name}.pre-migration-v0-tool1-*.bak"))
        )

    async def test_corrupt_incomplete_and_newer_imports_leave_no_orphans(self):
        root = Path(self.temporary.name)
        corrupt = root / "corrupt.ctui-project"
        corrupt.write_bytes(b"not a sqlite database")
        missing = root / "missing.ctui-project"
        with closing(sqlite3.connect(missing)):
            pass
        newer = await self._export_with_metadata(
            "newer.ctui-project", schema_version=projects_module.SCHEMA_VERSION + 1
        )
        wrong_app = await self._export_with_metadata(
            "wrong-app.ctui-project", app_id="io.example.somewhere-else"
        )
        incomplete = await self._export_with_metadata("incomplete.ctui-project")
        with closing(sqlite3.connect(incomplete)) as connection, connection:
            connection.execute("DROP TABLE records")

        before = await self.app.backend.list_projects()
        cases = (
            (corrupt, "Invalid project database"),
            (missing, "metadata table"),
            (newer, "newer than supported"),
            (wrong_app, "different application"),
            (incomplete, "missing required tables"),
        )
        for path, message in cases:
            with self.subTest(path=path), self.assertRaisesRegex(CommandError, message):
                await self.app.backend.import_project(path, f"import-{path.stem}")
            self.assertEqual(await self.app.backend.list_projects(), before)
            self.assertEqual(self.app.backend.current.name, "default")

    async def test_failed_migration_rolls_back_and_removes_failed_import(self):
        path = await self._export_with_metadata("legacy.ctui-project", schema_version=0)
        before = await self.app.backend.list_projects()
        files_before = {item.name for item in self.app.backend.databases_dir.iterdir()}

        with patch.dict(
            projects_module.SCHEMA_MIGRATIONS,
            {0: ("THIS IS NOT SQL",)},
            clear=True,
        ):
            with self.assertRaisesRegex(CommandError, "migration failed"):
                await self.app.backend.import_project(path, "broken-migration")

        self.assertEqual(await self.app.backend.list_projects(), before)
        self.assertEqual(self.app.backend.current.name, "default")
        self.assertEqual(
            {item.name for item in self.app.backend.databases_dir.iterdir()},
            files_before,
        )

    async def test_failed_load_keeps_the_current_project_available(self):
        bad = await self.app.backend.create("bad", activate=False)
        self.app.backend._database_path(bad.id).write_bytes(b"not sqlite")

        with self.assertRaises(CommandError):
            await self.app.backend.load("bad")

        self.assertEqual(self.app.backend.current.name, "default")
        self.assertEqual(await self.app.configs.get("local"), {"host": "127.0.0.1"})

    async def test_application_schema_requires_explicit_ordered_migrations(self):
        data_dir = Path(self.temporary.name) / "tool-migrations"
        original = SqliteProjectBackend(
            "io.example.migrations", data_dir=data_dir, tool_schema_version=1
        )
        await original.open()
        await original.connection.execute(
            "CREATE TABLE app_data(id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        await original.connection.execute(
            "INSERT INTO app_data(value) VALUES ('preserved')"
        )
        await original.connection.commit()
        await original.close()

        missing = SqliteProjectBackend(
            "io.example.migrations", data_dir=data_dir, tool_schema_version=2
        )
        with self.assertRaisesRegex(CommandError, "No application migration"):
            await missing.open()
        await missing.close()

        migrated = SqliteProjectBackend(
            "io.example.migrations",
            data_dir=data_dir,
            tool_schema_version=2,
            tool_migrations={
                1: ("ALTER TABLE app_data ADD COLUMN label TEXT NOT NULL DEFAULT ''",)
            },
        )
        await migrated.open()
        try:
            cursor = await migrated.connection.execute(
                "SELECT value, label FROM app_data"
            )
            self.assertEqual(await cursor.fetchone(), ("preserved", ""))
            cursor = await migrated.connection.execute(
                "SELECT value FROM metadata WHERE key = 'tool_schema_version'"
            )
            self.assertEqual((await cursor.fetchone())[0], "2")
            database = migrated._database_path(migrated.current.id)
            self.assertTrue(
                list(
                    database.parent.glob(
                        f"{database.name}.pre-migration-v1-tool1-*.bak"
                    )
                )
            )
        finally:
            await migrated.close()

    def test_application_migration_configuration_is_validated(self):
        for schema_version in (True, 0, -1, 1.5):
            with (
                self.subTest(schema_version=schema_version),
                self.assertRaisesRegex(ValueError, "positive integer"),
            ):
                SqliteProjectBackend(
                    "io.example.invalid", tool_schema_version=schema_version
                )

        invalid_migrations = ({0: ("SELECT 1",)}, {2: ("SELECT 1",)}, {1: "SQL"})
        for migrations in invalid_migrations:
            with self.subTest(migrations=migrations), self.assertRaises(ValueError):
                SqliteProjectBackend(
                    "io.example.invalid",
                    tool_schema_version=2,
                    tool_migrations=migrations,
                )
