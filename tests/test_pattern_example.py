import asyncio
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ctui import CommandError
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout


class PatternExampleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "examples/06_fuzzy_patterns.py"
        spec = importlib.util.spec_from_file_location("pattern_example", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.app = module.PatternTool()

    async def test_default_boundary_and_override(self):
        for command in ("hex expand 0[0-3]??", "text expand [ab]{10}"):
            result = await self.app.dispatch(command)
            self.assertEqual(result.output.splitlines()[0], "1,024 possibilities")
        for command in ("hex expand ????", "text expand [ab]{11}"):
            with self.assertRaisesRegex(CommandError, "expansion limit is 1,024"):
                await self.app.dispatch(command)
        result = await self.app.dispatch("text expand [ab]{11} --limit 2048")
        self.assertTrue(result.output.startswith("2,048 possibilities"))

    async def test_overflow_opens_error_dialog_and_preserves_output(self):
        self.app.layout = CtuiLayout(self.app)
        self.app.layout.set_output("Keep output")
        binding = next(
            b
            for b in get_key_bindings(self.app).bindings
            if str(b.keys[0]) == "Keys.ControlM"
        )
        tasks = []
        event = SimpleNamespace(
            app=SimpleNamespace(
                create_background_task=lambda coro: tasks.append(
                    asyncio.create_task(coro)
                )
            )
        )
        for text in ("hex expand ????", "text expand [ab]{11}"):
            self.app.layout.input_field.text = text
            with patch("ctui.keybindings.message_dialog") as dialog:
                binding.handler(event)
                await tasks[-1]
                dialog.assert_called_once()
                self.assertEqual(dialog.call_args.kwargs["title"], "Error")
                self.assertIn(
                    "expansion limit is 1,024", dialog.call_args.kwargs["text"]
                )
                self.assertNotIn("Traceback", dialog.call_args.kwargs["text"])
            self.assertEqual(self.app.layout.input_field.text, text)
            self.assertEqual(self.app.layout.output_field.text, "Keep output")
