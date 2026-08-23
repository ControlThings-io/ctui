import unittest
from ctui import CtuiApp, CommandResult, command
from ctui.commands import Argument, CommandNotFound, CommandValidationError
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
