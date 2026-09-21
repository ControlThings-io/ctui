"""Hierarchical help, interface introductions, and modal presentation tests.

Keep shared references independent from welcome/guidance, resolve aliases and
prefixes, and preserve existing UI output when help opens. Mock dialog display
for command presentation, then separately verify normal focus restoration.
"""

import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import DummyOutput

from ctui import Argument, CtuiApp, command
from ctui.commands import CommandNotFound, CommandValidationError
from ctui.completion import CommandCompleter
from ctui.dialogs import MessageDialog, show_dialog
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout


class HelpApp(CtuiApp):
    """Fixture with executable parents, child commands, aliases, and similar roots."""

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
    """Protect targeted help and the welcome-guidance-reference ordering."""

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

    async def test_main_help_orders_welcome_guidance_and_commands(self):
        app = HelpApp(
            name="Order Test", version="2.0", description="Unique description"
        )
        for text, guidance in (
            (app.format_ui_help(), app.ui_help_intro),
            (app.format_cli_help(), "Usage:"),
        ):
            self.assertTrue(text.startswith(app.welcome))
            self.assertEqual(text.count(app.welcome), 1)
            self.assertLess(text.index("Unique description"), text.index(guidance))
            self.assertLess(text.index(guidance), text.index(app.help_message))
        self.assertNotIn(app.welcome, app.format_help())
        self.assertNotIn(app.welcome, app.format_ui_help("project"))
        self.assertNotIn(app.welcome, app.format_cli_help(target="project"))

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

    async def test_history_count_completion_explains_zero(self):
        completer = CommandCompleter(HelpApp().commands)
        matches = [
            item
            async for item in completer.get_completions_async(
                Document("history "), CompleteEvent()
            )
        ]
        count = next(item for item in matches if item.text == "")
        self.assertEqual(
            str(count.display_meta),
            "FormattedText([('', 'Maximum number of recent commands to show; "
            "0 shows all')])",
        )

    async def test_ui_help_preserves_output(self):
        app = HelpApp()
        app._build_application()
        app.layout.set_output("Keep this output")
        tasks = []
        seen = []

        async def display(dialog):
            seen.append(dialog)
            self.assertFalse(dialog.text_area.control.is_focusable())

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

    async def test_help_redraws_after_async_history(self):
        """A delayed SQLite write must not leave an invisible modal focused."""
        with tempfile.TemporaryDirectory() as root:
            app = CtuiApp(app_id="io.example.help", data_dir=Path(root))
            await app.backend.open()
            running = None
            try:
                app.layout = CtuiLayout(app)
                history_written = asyncio.Event()
                release_history = asyncio.Event()
                help_rendered = asyncio.Event()
                append = app.history.append

                async def delayed_append(text):
                    await append(text)
                    history_written.set()
                    await release_history.wait()

                def after_render(terminal):
                    screen = terminal.renderer.last_rendered_screen
                    if screen is not None:
                        text = "\n".join(
                            "".join(row[x].char for x in sorted(row))
                            for row in screen.data_buffer.values()
                        )
                        if "Help" in text:
                            help_rendered.set()

                with create_pipe_input() as input_pipe:
                    terminal = Application(
                        layout=Layout(
                            app.layout.root_container,
                            focused_element=app.layout.input_field,
                        ),
                        key_bindings=get_key_bindings(app),
                        input=input_pipe,
                        output=DummyOutput(),
                        full_screen=True,
                        after_render=after_render,
                    )
                    app.app = terminal
                    with patch.object(app.history, "append", delayed_append):
                        running = asyncio.create_task(terminal.run_async())
                        await asyncio.sleep(0)
                        input_pipe.send_text("help\r")
                        await asyncio.wait_for(history_written.wait(), 2)
                        # Let the input-triggered redraw finish before dispatch returns.
                        await asyncio.sleep(0.1)
                        self.assertFalse(help_rendered.is_set())
                        release_history.set()
                        await asyncio.wait_for(help_rendered.wait(), 2)
                        input_pipe.send_text("\r")
                        await asyncio.sleep(0.1)
                        self.assertTrue(
                            terminal.layout.has_focus(app.layout.input_field)
                        )
                        input_pipe.send_text("history")
                        await asyncio.sleep(0.1)
                        self.assertEqual(app.layout.input_field.text, "history")
                        terminal.exit()
                        await asyncio.wait_for(running, 2)
            finally:
                if running is not None and not running.done():
                    running.cancel()
                    await asyncio.gather(running, return_exceptions=True)
                await app.backend.close()

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
            self.assertEqual(
                len(app.app.layout.container.floats), len(floats_before) + 1
            )
            dialog.future.set_result(None)
            await task
            self.assertIs(app.app.layout.current_window, before)
            self.assertEqual(app.app.layout.container.floats, floats_before)
