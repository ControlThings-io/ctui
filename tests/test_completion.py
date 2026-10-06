"""Dropdown progression and partial-input tokenization regressions.

Keep suggestions on the current word until a separating space is entered, allow
child commands beside parent argument hints, and retain quoted spaces. These
tests inspect completer results; real Buffer behavior is covered separately in
test_named_completion.py.
"""

import shlex
import unittest
from typing import Literal

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui.commands import Argument, Commands
from ctui.completion import CommandCompleter, _argument_state


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    """Collect asynchronous suggestions without requiring a terminal application."""

    async def collect(self, completer, text):
        """Materialize completions for a Document whose cursor is at the end."""
        return [
            item
            async for item in completer.get_completions_async(
                Document(text, cursor_position=len(text)), CompleteEvent()
            )
        ]

    async def test_list_completion_filters_exact_elements_and_preserves_prefix(self):
        commands, words = Commands(), []

        def available(context):
            words.append(context.word)
            return ["alpha", "beta", "gamma"]

        @commands.register(arguments={"names": Argument(completer=available)})
        def read(names: list[str] | None = None):
            return names

        @commands.register(
            arguments={"names": Argument(flags=("--names",), completer=available)}
        )
        def named(names: list[str] | None = None):
            return names

        completer = CommandCompleter(commands)
        for text in ("read alpha,be", "named --names=alpha,be", 'read "alpha,be'):
            with self.subTest(text=text):
                matches = await self.collect(completer, text)
                self.assertEqual([c.display_text for c in matches], ["beta", "gamma"])
                buffer = Buffer(document=Document(text))
                buffer.apply_completion(matches[0])
                item, arguments = commands.resolve(buffer.text)
                self.assertEqual(item.parse_args(arguments)["names"], ["alpha", "beta"])
        matches = await self.collect(completer, "read alpha,beta,")
        self.assertEqual([c.display_text for c in matches], ["gamma"])
        matches = await self.collect(completer, "read alpha,beta")
        self.assertEqual([c.display_text for c in matches], ["gamma"])
        self.assertTrue(words)
        self.assertEqual(set(words), {""})
        item, arguments = commands.resolve("read alpha,beta")
        self.assertEqual(
            await item.expand_unique_arguments(arguments), shlex.join(["alpha,beta"])
        )

    async def test_list_hints_and_element_choices_after_comma(self):
        commands = Commands()

        @commands.register(arguments={"names": Argument(help="Names to read")})
        def read(names: list[str] | None = None):
            pass

        @commands.register
        def numbers(numbers: list[Literal[1, 2, 3]]):
            pass

        completer = CommandCompleter(commands)
        hint = (await self.collect(completer, "read first,"))[0]
        self.assertEqual(hint.text, "")
        self.assertEqual(hint.start_position, 0)
        self.assertIn("Names to read", str(hint.display_meta))
        matches = await self.collect(completer, "numbers 1,")
        self.assertEqual([c.display_text for c in matches], ["2", "3"])
        buffer = Buffer(document=Document("numbers 1,"))
        buffer.apply_completion(matches[0])
        item, arguments = commands.resolve(buffer.text)
        self.assertEqual(item.parse_args(arguments)["numbers"], [1, 2])

    async def test_command_and_argument_dropdowns(self):
        commands = Commands()

        @commands.register(
            arguments={
                "environment": Argument(
                    choices={
                        "development": "Safe sandbox",
                        "production": "Live systems",
                    }
                )
            }
        )
        def deploy(environment: str):
            pass

        completer = CommandCompleter(commands)
        commands_found = await self.collect(completer, "dep")
        self.assertEqual(commands_found[0].text, "deploy")
        values = await self.collect(completer, "deploy prod")
        self.assertEqual(values[0].text, "production")
        self.assertEqual(
            str(values[0].display_meta), "FormattedText([('', 'Live systems')])"
        )

    async def test_group_without_parent_command_suggests_children_once(self):
        commands = Commands()

        @commands.register(name="hex expand")
        def expand(pattern: str):
            return pattern

        @commands.register(name="hex sample")
        def sample(pattern: str):
            return pattern

        completer = CommandCompleter(commands)
        for text in ("hex ", "he ", "hex  ", "hex\t"):
            with self.subTest(text=text):
                results = await self.collect(completer, text)
                self.assertEqual([item.text for item in results], ["expand", "sample"])

    async def test_empty_document_does_not_crash(self):
        completer = CommandCompleter(Commands())
        self.assertEqual(await self.collect(completer, ""), [])

    async def test_subcommands_and_parent_arguments_share_dropdown(self):
        commands = Commands()

        @commands.register(name="history")
        def history(count: int = 0):
            pass

        @commands.register(name="history export")
        def history_export(path: str):
            pass

        @commands.register(name="history search")
        def history_search(keyword: str):
            pass

        completer = CommandCompleter(commands)
        top_level = await self.collect(completer, "history")
        self.assertEqual([item.text for item in top_level], ["history"])

        results = await self.collect(completer, "history ")
        self.assertEqual(
            [item.text for item in results],
            ["export", "search", ""],
        )

        partial = await self.collect(completer, "history e")
        self.assertEqual([item.text for item in partial], ["export"])

        abbreviated_parent = await self.collect(completer, "hist ")
        self.assertEqual(
            [item.text for item in abbreviated_parent],
            ["export", "search", ""],
        )

    async def test_arguments_wait_for_space_after_command(self):
        commands = Commands()

        @commands.register(
            arguments={"environment": Argument(choices=("development", "production"))}
        )
        def deploy(environment: str):
            pass

        completer = CommandCompleter(commands)
        without_space = await self.collect(completer, "deploy")
        self.assertEqual([item.text for item in without_space], ["deploy"])
        with_space = await self.collect(completer, "deploy ")
        self.assertEqual(
            [item.text for item in with_space], ["development", "production"]
        )

    async def test_next_argument_waits_for_unquoted_space(self):
        commands = Commands()

        @commands.register(
            arguments={
                "environment": Argument(choices=("development", "production")),
                "server": Argument(choices=("web-1", "web-2")),
            }
        )
        def deploy(environment: str, server: str):
            pass

        completer = CommandCompleter(commands)
        current = await self.collect(completer, "deploy development")
        self.assertEqual([item.text for item in current], ["development"])
        following = await self.collect(completer, "deploy development ")
        self.assertEqual([item.text for item in following], ["web-1", "web-2"])

    async def test_free_form_arguments_always_show_a_typed_aid(self):
        commands = Commands()

        @commands.register
        def repeat(message: str, count: int):
            pass

        completer = CommandCompleter(commands)
        string_aid = await self.collect(completer, "repeat hello")
        self.assertEqual(
            str(string_aid[0].display), "FormattedText([('', '<MESSAGE: str>')])"
        )
        int_aid = await self.collect(completer, "repeat hello ")
        self.assertEqual(
            str(int_aid[0].display), "FormattedText([('', '<COUNT: int>')])"
        )

    def test_partial_tokenizer_keeps_quoted_spaces_in_one_argument(self):
        self.assertEqual(_argument_state('"Ada Lovelace'), ([], "Ada Lovelace", False))
        self.assertEqual(
            _argument_state('"Ada Lovelace" '), (["Ada Lovelace"], "", True)
        )
