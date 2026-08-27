"""Context-aware command and argument completion."""

from __future__ import annotations

from prompt_toolkit.completion import Completer, Completion

from ctui.commands import CommandNotFound, Commands


def _argument_state(text: str) -> tuple[list[str], str, bool]:
    """Split partial input while preserving quoted spaces and cursor state."""
    completed, current, quote, escaped = [], [], None, False
    for character in text:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
            else:
                current.append(character)
        elif character in ("'", '"'):
            quote = character
        elif character.isspace():
            if current:
                completed.append("".join(current))
                current = []
        else:
            current.append(character)
    boundary = bool(text) and text[-1].isspace() and quote is None
    return completed, "" if boundary else "".join(current), boundary


class CommandCompleter(Completer):
    """Complete command names, options, and validated argument values."""

    def __init__(self, commands: Commands, app=None):
        """Bind completion to a command registry and optional application."""
        self.commands, self.app = commands, app

    def _command_completions(self, text):
        """Yield only the next matching word of commands and aliases."""
        boundary = bool(text) and text[-1].isspace()
        parts = text.split()
        completed = parts if boundary else parts[:-1]
        word = "" if boundary or not parts else parts[-1]
        candidates = {}

        def collect(name, item, *, alias=False):
            name_parts = name.split()
            if len(name_parts) < len(completed) or any(
                not actual.startswith(typed)
                for typed, actual in zip(completed, name_parts)
            ):
                return
            if len(name_parts) <= len(completed):
                return
            candidate = name_parts[len(completed)]
            if not candidate.startswith(word):
                return
            help_text = f"Alias for {item.name}" if alias else item.desc
            candidates.setdefault(candidate, help_text)

        for item in self.commands:
            collect(item.name, item)
        for alias, item in self.commands.aliases.items():
            collect(alias, item, alias=True)
        for candidate, help_text in candidates.items():
            yield Completion(
                candidate,
                start_position=-len(word),
                display_meta=help_text,
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
        stripped = text.lstrip()
        command_matches = list(self._command_completions(stripped))
        if command_matches and not text.endswith(tuple(" \t\r\n")):
            for result in command_matches:
                yield result
            return
        for result in command_matches:
            yield result
        try:
            item, argument_text = self.commands.resolve(text)
        except CommandNotFound:
            for result in self._command_completions(text.lstrip()):
                yield result
            return
        _, _, input_at_boundary = _argument_state(text)
        if input_at_boundary:
            argument_text += " "
        completed, word, _ = _argument_state(argument_text)
        import shlex

        completion_text = shlex.join(completed)
        if completion_text:
            completion_text += " "
        for result in await item.complete(completion_text, word, self.app):
            yield Completion(
                result.value,
                start_position=-len(word),
                display=result.display or result.value,
                display_meta=result.help,
            )


__all__ = ["CommandCompleter"]
