import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ctui import CommandError, CommandResult, ConfirmationRequired, CtuiApp, command
from ctui.commands import Argument, CommandNotFound, CommandValidationError
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout
from ctui.services import MemoryHistory, MemoryStorage, NullHistory


class Demo(CtuiApp):
    def __init__(self, **kwargs):
        self.lifecycle = []
        super().__init__(register_defaults=False, **kwargs)

    @command(arguments={"name": Argument(choices=("Ada", "Grace"))})
    async def greet(self, name: str):
        await self.events.emit("greeted", name=name)
        return f"Hello {name}"

    async def on_start(self):
        self.lifecycle.append("start")

    async def on_ready(self):
        self.lifecycle.append("ready")

    async def on_stop(self):
        self.lifecycle.append("stop")


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_class_commands_dispatch_history_and_events(self):
        history, seen = MemoryHistory(), []
        app = Demo(history=history)
        app.on("greeted", lambda name: seen.append(name))
        result = await app.dispatch("greet Ada")
        self.assertEqual(result.output, "Hello Ada")
        self.assertEqual(history.all()[0].command, "greet Ada")
        self.assertEqual(seen, ["Ada"])

    async def test_string_and_structured_results(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def clear():
            return CommandResult(clear_output=True)

        self.assertTrue((await app.dispatch("clear")).clear_output)
        appended = CommandResult.append("next line")
        self.assertTrue(appended.append_output)
        self.assertEqual(appended.output, "next line")

    async def test_confirmation_and_history_suppression(self):
        history = MemoryHistory()
        app = CtuiApp(register_defaults=False, history=history)
        called = []

        @app.commands.register(confirmation="Delete {name}?", record_history=False)
        def delete(name: str):
            called.append(name)
            return "deleted"

        with self.assertRaisesRegex(ConfirmationRequired, "Delete old"):
            await app.dispatch("delete old")
        self.assertEqual(called, [])
        result = await app.dispatch("delete old", confirm_callback=lambda _: True)
        self.assertEqual(result.output, "deleted")
        self.assertEqual(history.all(), [])

        result = await app.dispatch("delete other confirm")
        self.assertEqual(result.output, "deleted")
        self.assertEqual(called, ["old", "other"])

    async def test_history_exports_all_or_recent_commands(self):
        app = CtuiApp()
        await app.dispatch("help")
        await app.dispatch("clear")
        with tempfile.TemporaryDirectory() as folder:
            all_path = Path(folder) / "all.txt"
            recent_path = Path(folder) / "recent.txt"

            result = await app.dispatch(f"history export {all_path}")
            self.assertIn("Exported 2 commands", result.output)
            self.assertEqual(all_path.read_text(encoding="utf-8"), "help\nclear\n")

            result = await app.dispatch(f"history export {recent_path} --count 2")
            self.assertIn("Exported 2 commands", result.output)
            self.assertEqual(
                recent_path.read_text(encoding="utf-8"),
                f"clear\nhistory export {all_path}\n",
            )

            self.assertIn("history export", app.format_help())

    async def test_unknown_command(self):
        with self.assertRaises(CommandNotFound):
            await Demo().dispatch("missing")

    async def test_unique_command_and_argument_prefixes(self):
        app = Demo()
        result = await app.dispatch("gr Ad")
        self.assertEqual(result.output, "Hello Ada")

    async def test_ambiguous_command_prefix_is_rejected(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def deploy():
            return "deploy"

        @app.commands.register
        def delete():
            return "delete"

        with self.assertRaisesRegex(CommandNotFound, "Ambiguous command"):
            await app.dispatch("de")

    async def test_quoted_string_arguments_can_contain_spaces(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def echo(message: str):
            return message

        result = await app.dispatch('ec "hello new developer"')
        self.assertEqual(result.output, "hello new developer")

    async def test_unsupported_command_result_is_rejected(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def invalid():
            return None

        with self.assertRaisesRegex(TypeError, "must return str or CommandResult"):
            await app.dispatch("invalid")

    async def test_all_execution_failures_emit_command_failed(self):
        app = CtuiApp(register_defaults=False)
        failed = []
        app.on("command_failed", lambda command: failed.append(command.name))

        @app.commands.register
        def crashes():
            raise RuntimeError("broken")

        @app.commands.register
        def invalid_result():
            return None

        with self.assertRaisesRegex(RuntimeError, "broken"):
            await app.dispatch("crashes")
        with self.assertRaisesRegex(TypeError, "must return"):
            await app.dispatch("invalid result")
        self.assertEqual(failed, ["crashes", "invalid result"])

    async def test_malformed_confirmation_template_is_a_command_error(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register(confirmation="Delete {name!invalid}?")
        def delete(name: str):
            return name

        with self.assertRaisesRegex(CommandError, "Invalid confirmation"):
            await app.dispatch("delete old")

    async def test_validation_error_points_to_argument_start(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def add(first: int, second: int):
            return str(first + second)

        with self.assertRaises(CommandValidationError) as raised:
            await app.dispatch("add 10 wrong")
        self.assertEqual(raised.exception.argument, "second")
        self.assertEqual(raised.exception.position, len("add 10 "))

    async def test_missing_argument_points_to_end_of_input(self):
        app = CtuiApp(register_defaults=False)

        @app.commands.register
        def add(first: int, second: int):
            return str(first + second)

        with self.assertRaises(CommandValidationError) as raised:
            await app.dispatch("add 10")
        self.assertEqual(raised.exception.position, len("add 10"))

    def test_constructor_and_optional_services(self):
        storage = MemoryStorage()
        app = Demo(name="Demo", prompt="demo> ", history=NullHistory(), storage=storage)
        self.assertEqual((app.name, app.prompt), ("Demo", "demo> "))
        storage.set("answer", 42)
        self.assertEqual(storage.get("answer"), 42)

    def test_shortcut_registration_validates_and_stores_handler(self):
        app = Demo()

        def handler():
            return "handled"

        app.add_shortcut("f2", handler=handler, description="Example")
        self.assertEqual(app.shortcuts, [(("f2",), handler, "Example")])
        with self.assertRaises(ValueError):
            app.add_shortcut(handler=handler)
        with self.assertRaises(TypeError):
            app.add_shortcut("f3", handler=None)

    def test_registered_shortcut_is_added_to_terminal_bindings(self):
        app = Demo()
        app.add_shortcut("f2", handler=lambda: None)
        app.layout = CtuiLayout(app)
        bindings = get_key_bindings(app).bindings
        self.assertTrue(any(str(binding.keys[0]) == "Keys.F2" for binding in bindings))

    def test_terminal_mouse_capture_is_disabled_by_default(self):
        self.assertFalse(CtuiApp.mouse_support)

    async def test_startup_failure_still_closes_storage_and_open_backend(self):
        calls = []

        class Backend:
            history = MemoryHistory()
            configs = None
            records = None

            async def open(self):
                calls.append("backend open")

            async def close(self):
                calls.append("backend close")

        class Storage(MemoryStorage):
            def close(self):
                calls.append("storage close")

        class FailingApp(CtuiApp):
            async def on_start(self):
                calls.append("start")
                raise RuntimeError("startup failed")

            async def on_stop(self):
                calls.append("stop")

        app = FailingApp(backend=Backend(), storage=Storage(), register_defaults=False)
        with self.assertRaisesRegex(RuntimeError, "startup failed"):
            await app.run_cli([])
        self.assertEqual(
            calls,
            ["backend open", "start", "storage close", "backend close"],
        )

    def test_standard_input_editing_keys_are_registered(self):
        app = Demo()
        app.layout = CtuiLayout(app)
        bindings = get_key_bindings(app).bindings
        registered = {str(binding.keys[0]) for binding in bindings}
        expected = {
            "Keys.Home",
            "Keys.End",
            "Keys.ControlA",
            "Keys.ControlE",
            "Keys.ControlU",
            "Keys.ControlK",
            "Keys.ControlW",
            "Keys.ControlC",
            "Keys.ControlD",
            "Keys.ControlL",
        }
        self.assertTrue(expected.issubset(registered))

    def test_control_c_clears_current_input(self):
        app = Demo()
        app.layout = CtuiLayout(app)
        app.layout.input_field.text = "unfinished command"
        binding = next(
            binding
            for binding in get_key_bindings(app).bindings
            if str(binding.keys[0]) == "Keys.ControlC"
        )

        binding.handler(SimpleNamespace())

        self.assertEqual(app.layout.input_field.text, "")

    def test_control_l_clears_output(self):
        app = Demo()
        app.layout = CtuiLayout(app)
        app.layout.set_output("old output")
        app.layout.input_field.text = "unfinished command"
        binding = next(
            binding
            for binding in get_key_bindings(app).bindings
            if str(binding.keys[0]) == "Keys.ControlL"
        )

        binding.handler(SimpleNamespace())

        self.assertEqual(app.layout.output_field.text, "")
        self.assertEqual(app.layout.input_field.text, "unfinished command")
