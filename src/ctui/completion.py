"""Quote-aware, incremental completion for the shared command registry.

Suggest one command word at a time, retaining parent arguments alongside child
commands. Advance to the next argument only after unquoted, unescaped whitespace.
Dynamic providers and unique choice prefixes use the command parsing layer so
UI suggestions and dispatch share conversion rules.
"""

from __future__ import annotations

import shlex

from prompt_toolkit.completion import Completer, Completion

from ctui.commands import CommandNotFound, Commands, CommandValidationError


def _argument_state(text: str) -> tuple[list[str], str, bool]:
    """Return completed tokens, the current word, and whether input ends at a boundary.

    Tolerate an unfinished quote while editing. Spaces inside quotes or escaped
    spaces stay in the current word; a trailing separator advances completion.
    This tracks editing state, while shlex performs final command parsing.
    """
    completed, current, quote, escaped = [], [], None, False
    boundary = False
    for character in text:
        boundary = False
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
            boundary = True
            if current:
                completed.append("".join(current))
                current = []
        else:
            current.append(character)
    return completed, "" if boundary else "".join(current), boundary


class CommandCompleter(Completer):
    """Complete command words, explicit options, and validated argument values.

    The asynchronous path supports sync/async providers and typed hints; the
    synchronous fallback suggests command names only. type_hint retains the
    originating Document and a non-inserting completion so CtuiLayout can restore
    hints prompt-toolkit discards without applying them to newer input.
    """

    def __init__(self, commands: Commands, app=None):
        """Bind completion to a command registry and optional application."""
        self.commands, self.app = commands, app
        self.type_hint = None

    def _command_completions(self, text):
        """Yield one next word per matching command or alias, deduplicating words.

        Honor abbreviations in already entered command words. A parent with its own
        arguments can also expose child commands rather than hiding them behind
        its next argument's type aid.
        """
        boundary = bool(text) and text[-1].isspace()
        parts = text.split()
        completed = parts if boundary else parts[:-1]
        word = "" if boundary or not parts else parts[-1]
        candidates = {}

        def collect(name, item, *, alias=False):
            """Collect a next word only when all entered command prefixes match."""
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
        """Yield suggestions for text before the cursor without changing the input.

        Handle help targets as command paths. For arguments, expand earlier unique
        choices before parsing later values and support both --option VALUE and
        --option=VALUE. Invalid partial conversions suppress suggestions; type aids
        use an empty insertion so selecting them never erases the current value.
        """
        self.type_hint = None
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
        if getattr(item.func, "__ctui_help__", False):
            target = argument_text + (" " if text[-1:].isspace() else "")
            for result in self._command_completions(target):
                yield result
            return
        _, _, input_at_boundary = _argument_state(text)
        if input_at_boundary:
            argument_text += " "
        completed, word, _ = _argument_state(argument_text)
        completion_text = shlex.join(completed)
        if completion_text:
            completion_text += " "
        option, equals, value = word.partition("=")
        if equals and option.startswith("-"):
            completion_text += option + " "
            word = value
        try:
            completion_text = await item.expand_unique_arguments(
                completion_text, self.app
            )
            if completion_text:
                completion_text += " "
            results = await item.complete(completion_text, word, self.app)
        except CommandValidationError:
            return
        for result in results:
            completion = Completion(
                result.value,
                start_position=-len(word) if result.value else 0,
                display=result.display or result.value,
                display_meta=result.help,
            )
            if not result.value and result.display:
                self.type_hint = (document, completion)
            yield completion


__all__ = ["CommandCompleter"]
