"""Context-aware command and argument completion."""

from __future__ import annotations
import shlex
from prompt_toolkit.completion import Completer, Completion
from ctui.commands import CommandNotFound, Commands


class CommandCompleter(Completer):
    """Complete command names, options, and validated argument values."""
    def __init__(self, commands: Commands, app=None):
        """Bind completion to a command registry and optional application."""
        self.commands, self.app = commands, app

    def _command_completions(self, text):
        """Yield command and alias completions matching *text*."""
        for item in self.commands:
            if item.name.startswith(text):
                yield Completion(
                    item.name, start_position=-len(text), display_meta=item.desc
                )
        for alias, item in self.commands.aliases.items():
            if alias.startswith(text):
                yield Completion(
                    alias,
                    start_position=-len(text),
                    display_meta=f"Alias for {item.name}",
                )

    def get_completions(self, document, complete_event):
        """Yield synchronous command-name completions for prompt-toolkit."""
        text = document.text_before_cursor
        try:
            self.commands.resolve(text)
        except CommandNotFound:
            yield from self._command_completions(text.lstrip())

    async def get_completions_async(self, document, complete_event):
        """Yield command or asynchronously generated argument completions."""
        text = document.text_before_cursor
        try:
            item, argument_text = self.commands.resolve(text)
        except CommandNotFound:
            for result in self._command_completions(text.lstrip()):
                yield result
            return
        trailing = text.endswith(" ")
        try:
            tokens = shlex.split(argument_text)
        except ValueError:
            tokens = argument_text.split()
        word = "" if trailing or not tokens else tokens[-1]
        completion_text = (
            argument_text
            if trailing
            else argument_text[: max(0, len(argument_text) - len(word))]
        )
        for result in await item.complete(completion_text, word, self.app):
            yield Completion(
                result.value, start_position=-len(word), display_meta=result.help
            )


__all__ = ["CommandCompleter"]
