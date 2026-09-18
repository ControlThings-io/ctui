import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from prompt_toolkit.application.current import set_app
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui import Argument, CtuiApp, command
from ctui.commands import CommandNotFound, CommandValidationError
from ctui.completion import CommandCompleter
from ctui.dialogs import MessageDialog, show_dialog
from ctui.keybindings import get_key_bindings


class HelpApp(CtuiApp):
    @command
    def project(self):
        """Show project statistics."""
        return "stats"

    @command(
        aliases=("save",),
        arguments={
            "count": Argument(flags=("-n", "--count"), help="Records to export")
        },
    )
    def project_export(self, path: str, count: int = 5):
        """Export a project."""
        return path

    @command
    def project_list(self):
        """List projects."""
        return "projects"

    @command
    def profile_list(self):
        """List profiles."""
        return "profiles"


class HelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_hierarchy_and_details(self):
        app = HelpApp()
        root = app.format_help()
        self.assertNotIn("project export", root)
        self.assertNotIn("project list", root)
        self.assertIn("project", root)
        self.assertIn("profile", root)
        group = (await app.dispatch("help proj")).output
        self.assertIn("Usage: project", group)
        self.assertIn("export", group)
        self.assertIn("list", group)
        leaf = (await app.dispatch("help proj exp")).output
        self.assertIn("Usage: project export", leaf)
        self.assertIn("--count", leaf)
        self.assertIn("default: 5", leaf)
        self.assertIn("Records to export", leaf)
        self.assertEqual(leaf, (await app.dispatch("help save")).output)
        for target in ("pro", "missing", "project missing"):
            with self.assertRaises(CommandNotFound):
                await app.dispatch("help " + target)
        with self.assertRaises(CommandValidationError):
            await app.dispatch('help "')

    async def test_interface_guidance_and_cli_output(self):
        app = HelpApp()
        app.ui_help_intro = "Custom UI intro"
        app.cli_help_intro = "Custom CLI intro"
        app.add_shortcut("f2", handler=lambda: None, description="Show status")
        ui = app.format_ui_help()
        self.assertIn("Custom UI intro", ui)
        self.assertIn("Ctrl-A / Ctrl-E", ui)
        self.assertIn("Home / End", ui)
        self.assertIn("while input keeps focus", ui)
        self.assertIn("Show status", ui)
        output = io.StringIO()
        self.assertEqual(await app.run_cli(["-c", "help"], stdout=output), 0)
        self.assertIn("Custom CLI intro", output.getvalue())
        self.assertNotIn("Custom UI intro", output.getvalue())
        self.assertNotIn("Ctrl-A", output.getvalue())
        self.assertNotIn("Custom UI intro", app.format_ui_help("project"))
        output = io.StringIO()
        self.assertEqual(
            await app.run_cli(["help", "project", "export"], stdout=output), 0
        )
        self.assertIn("Usage: project export", output.getvalue())

    async def test_help_completion(self):
        completer = CommandCompleter(HelpApp().commands)
        for text, expected in (
            ("help ", "project"),
            ("help proj ", "export"),
            ("help proj e", "export"),
        ):
            matches = [
                item.text
                async for item in completer.get_completions_async(
                    Document(text), CompleteEvent()
                )
            ]
            self.assertIn(expected, matches)

    async def test_ui_help_preserves_output(self):
        app = HelpApp()
        app._build_application()
        app.layout.set_output("Keep this output")
        tasks = []
        seen = []

        async def display(dialog):
            seen.append(dialog)
            self.assertTrue(dialog.text_area.control.is_focusable())

        binding = next(
            binding
            for binding in get_key_bindings(app).bindings
            if str(binding.keys[0]) == "Keys.ControlM"
        )
        for text in ("help", "help project export"):
            app.layout.input_field.text = text
            with patch("ctui.keybindings.show_dialog", side_effect=display):
                binding.handler(
                    SimpleNamespace(
                        app=SimpleNamespace(
                            create_background_task=lambda coro: tasks.append(
                                asyncio.create_task(coro)
                            )
                        )
                    )
                )
                await tasks[-1]
            self.assertEqual(app.layout.output_field.text, "Keep this output")
        self.assertEqual(len(seen), 2)
        self.assertIn("Input window", seen[0].text)
        self.assertIn("Usage: project export", seen[1].text)

    async def test_dialog_restores_focus(self):
        app = HelpApp()
        app._build_application()
        dialog = MessageDialog(
            title="Help", text=app.format_ui_help(), scrollbar=True, focusable=True
        )
        with set_app(app.app):
            floats_before = list(app.app.layout.container.floats)
            before = app.app.layout.current_window
            task = asyncio.create_task(show_dialog(dialog))
            await asyncio.sleep(0)
            self.assertIsNot(app.app.layout.current_window, before)
            dialog.future.set_result(None)
            await task
            self.assertIs(app.app.layout.current_window, before)
            self.assertEqual(app.app.layout.container.floats, floats_before)
