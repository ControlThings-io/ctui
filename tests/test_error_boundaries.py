import asyncio
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui import Argument, CommandError, CtuiApp
from ctui.completion import CommandCompleter
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout


class ErrorBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_example_value_errors_are_command_errors(self):
        for filename, cls, commands in (
            (
                "06_fuzzy_patterns.py",
                "PatternTool",
                ["hex sample ?? -n -1", "text sample [ab] -n -1"],
            ),
            (
                "07_integer_ranges.py",
                "RangeTool",
                ["expand 0-2000", "sample 0-9 -n -1"],
            ),
        ):
            path = Path(__file__).resolve().parents[1] / "examples" / filename
            spec = importlib.util.spec_from_file_location("example", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            app = getattr(module, cls)()
            for command in commands:
                with self.assertRaises(CommandError):
                    await app.dispatch(command)

    async def test_sync_and_async_shortcut_failures_show_dialogs(self):
        def sync():
            raise CommandError("expected")

        async def async_failure():
            raise RuntimeError("unexpected")

        for handler, text in ((sync, "expected"), (async_failure, "unexpected")):
            app = CtuiApp()
            app.layout = CtuiLayout(app)
            app.add_shortcut("f2", handler=handler)
            binding = next(
                b for b in get_key_bindings(app).bindings if str(b.keys[0]) == "Keys.F2"
            )
            tasks = []
            event = SimpleNamespace(
                app=SimpleNamespace(
                    create_background_task=lambda coro: tasks.append(
                        asyncio.create_task(coro)
                    )
                )
            )
            with patch("ctui.keybindings.message_dialog") as dialog:
                binding.handler(event)
                await tasks[0]
                self.assertIn(text, dialog.call_args.kwargs["text"])

    async def test_completion_failure_is_contained(self):
        app = CtuiApp()
        app.app = SimpleNamespace(is_running=True)

        def provider(context):
            raise RuntimeError("provider failed")

        @app.commands.register(arguments={"value": Argument(completer=provider)})
        def demo(value: str):
            return value

        with patch("ctui.dialogs.message_dialog") as dialog:
            results = [
                item
                async for item in CommandCompleter(
                    app.commands, app
                ).get_completions_async(Document("demo "), CompleteEvent())
            ]
            self.assertEqual(results, [])
            self.assertIn("provider failed", dialog.call_args.kwargs["text"])

    async def test_project_io_error_is_translated(self):
        from ctui.projects import register_project_commands

        app = CtuiApp()

        async def export(path):
            raise PermissionError("read-only destination")

        app.backend = SimpleNamespace(export_project=export)
        register_project_commands(app)
        with self.assertRaisesRegex(CommandError, "read-only destination"):
            await app.dispatch("project export test.ctui-project")
