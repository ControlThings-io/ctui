import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from ctui import ConfirmationRequired, CtuiApp


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
        result = await self.app.dispatch("history search help since 7d limit 5")
        self.assertEqual(result.output, "help")
        await self.app.dispatch("history clear confirm")
        self.assertEqual(await self.app.history.all(), [])

    async def test_config_json_and_project_snapshot_round_trip(self):
        await self.app.configs.save("remote", {"host": "10.0.0.2", "port": 502})
        root = Path(self.temporary.name)
        configs_path = root / "configs.json"
        await self.app.dispatch(f"configs export {configs_path}")
        document = json.loads(configs_path.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "ctui-configs")

        project_path = root / "shared.ctui-project"
        await self.app.dispatch(f"project export {project_path}")
        await self.app.dispatch(f"project import {project_path} name imported")
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
