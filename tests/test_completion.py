import unittest

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui.commands import Argument, Commands
from ctui.completion import CommandCompleter, _argument_state


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, completer, text):
        return [
            item
            async for item in completer.get_completions_async(
                Document(text, cursor_position=len(text)), CompleteEvent()
            )
        ]

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

    async def test_empty_document_does_not_crash(self):
        completer = CommandCompleter(Commands())
        self.assertEqual(await self.collect(completer, ""), [])

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
