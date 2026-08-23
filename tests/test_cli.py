import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ctui import CtuiApp, command


class CliApp(CtuiApp):
    """Small application used to verify automatic terminal mode."""

    name = "CLI Tests"

    @command
    def echo(self, text: str) -> str:
        """Print text."""
        return text

    @command
    def add(self, first: int, second: int) -> str:
        """Add two integers."""
        return str(first + second)


class CliTests(unittest.IsolatedAsyncioTestCase):
    async def test_help_flag_prints_cli_and_application_help(self):
        output = io.StringIO()
        status = await CliApp().run_cli(["--help"], stdout=output, program="tool")
        self.assertEqual(status, 0)
        self.assertIn("Usage: tool", output.getvalue())
        self.assertIn("echo", output.getvalue())

    async def test_repeated_commands_run_in_order(self):
        output = io.StringIO()
        status = await CliApp().run_cli(
            ["-c", "echo first", "--command", "add 2 3", "-c", "echo last"],
            stdout=output,
        )
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue().splitlines(), ["first", "5", "last"])

    async def test_file_commands_run_where_file_option_appears(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            command_file = Path(folder) / "commands.txt"
            command_file.write_text("# comment\necho from-file\nadd 10 5\n", encoding="utf-8")
            status = await CliApp().run_cli(
                ["-c", "echo before", "-f", str(command_file), "-c", "echo after"],
                stdout=output,
            )
        self.assertEqual(status, 0)
        self.assertEqual(
            output.getvalue().splitlines(),
            ["before", "from-file", "15", "after"],
        )

    async def test_invalid_command_prints_error_and_help(self):
        output, errors = io.StringIO(), io.StringIO()
        status = await CliApp().run_cli(
            ["-c", "add wrong 2"], stdout=output, stderr=errors, program="tool"
        )
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "")
        lines = errors.getvalue().splitlines()
        self.assertEqual(lines[0], "add wrong 2")
        self.assertEqual(lines[1], "    ^")
        self.assertIn("Error: first must be int", lines[2])
        self.assertIn("Usage: tool", errors.getvalue())

    async def test_missing_file_prints_error_and_help(self):
        errors = io.StringIO()
        status = await CliApp().run_cli(
            ["--file", "/definitely/missing/ctui-commands.txt"],
            stderr=errors,
            program="tool",
        )
        self.assertEqual(status, 2)
        self.assertIn("Error:", errors.getvalue())
        self.assertIn("Usage: tool", errors.getvalue())


class RunRoutingTests(unittest.TestCase):
    def test_no_arguments_select_full_screen_ui(self):
        app = CliApp()
        with patch("asyncio.run", return_value="ui-result") as run:
            self.assertEqual(app.run(argv=[]), "ui-result")
        run.call_args.args[0].close()

    def test_arguments_select_cli_and_exit_with_its_status(self):
        app = CliApp()
        with patch("asyncio.run", return_value=2) as run:
            with self.assertRaises(SystemExit) as raised:
                app.run(argv=["--help"])
        run.call_args.args[0].close()
        self.assertEqual(raised.exception.code, 2)
