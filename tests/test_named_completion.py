import importlib.util
import unittest
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui.completion import CommandCompleter, _argument_state
from ctui.layout import CtuiLayout


class NamedCompletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "examples/04_named_arguments.py"
        spec = importlib.util.spec_from_file_location("named_example", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.app = module.DeployTool()

    async def collect(self, text):
        return [
            item
            async for item in CommandCompleter(
                self.app.commands, self.app
            ).get_completions_async(Document(text), CompleteEvent())
        ]

    async def test_type_aids_survive_buffer_completion(self):
        layout = CtuiLayout(self.app)
        buffer = layout.input_field.buffer
        for text, label in (
            ("deploy ", "<TARGET: str>"),
            ("deploy api --replicas ", "<REPLICAS: int>"),
            ("deploy api -r ", "<REPLICAS: int>"),
            ("deploy api --replicas=", "<REPLICAS: int>"),
        ):
            with self.subTest(text=text):
                buffer.set_document(Document(text), bypass_readonly=True)
                buffer.complete_state = None
                await buffer._create_completer_coroutine()()
                self.assertIsNotNone(buffer.complete_state)
                completion = buffer.complete_state.completions[0]
                self.assertIn(label, str(completion.display))
                buffer.apply_completion(completion)
                self.assertEqual(buffer.text, text)

    async def test_literal_prefixes_execute_and_allow_following_options(self):
        for argument in ("-e prod", "--environment prod", "--environment=prod"):
            text = "deploy api " + argument
            result = await self.app.dispatch(text)
            self.assertIn("production", result.output)
            suggestions = await self.collect(text + " ")
            self.assertIn("--replicas", [item.text for item in suggestions])
            suggestions = await self.collect(text + " --replicas ")
            self.assertIn("<REPLICAS: int>", str(suggestions[0].display))

    async def test_inline_literal_completion(self):
        items = await self.collect("deploy api --environment=pro")
        self.assertEqual([item.text for item in items], ["production"])
        self.assertEqual(items[0].start_position, -3)

    async def test_type_hint_never_deletes_partial_value(self):
        items = await self.collect("deploy api --replicas 2")
        self.assertEqual(items[0].text, "")
        self.assertEqual(items[0].start_position, 0)

    async def test_escaped_space_keeps_current_parameter(self):
        items = await self.collect("deploy api\\ ")
        self.assertIn("<TARGET: str>", str(items[0].display))
        items = await self.collect('deploy "api ')
        self.assertIn("<TARGET: str>", str(items[0].display))

    async def test_ambiguous_literal_is_not_guessed(self):
        from typing import Literal

        from ctui import Argument, CommandValidationError

        @self.app.commands.register(arguments={"mode": Argument(flags=("--mode",))})
        def choose(mode: Literal["production", "preview"]):
            return mode

        for value in ("--mode pr", "--mode=pr"):
            with self.assertRaises(CommandValidationError):
                await self.app.dispatch("choose " + value)
        self.assertEqual(
            (await self.app.dispatch("choose --mode=prev")).output, "preview"
        )

    def test_escaped_and_quoted_spaces_do_not_advance(self):
        self.assertEqual(_argument_state("api\\ "), ([], "api ", False))
        self.assertEqual(_argument_state('"api '), ([], "api ", False))
