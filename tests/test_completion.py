import unittest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from ctui.commands import Argument, Commands
from ctui.completion import CommandCompleter


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
