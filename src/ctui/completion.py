"""Quote-aware, incremental completion for the shared command registry.

Suggest one command word at a time, retaining parent arguments alongside child
commands. Advance to the next argument only after unquoted, unescaped whitespace.
Dynamic providers and unique choice prefixes use the command parsing layer so
UI suggestions and dispatch share conversion rules.
Acceptance is separate from menu previews: finish scalar arguments with a
separator, but retain editable directory and comma-separated list values.
"""

from __future__ import annotations

import logging
import os
import shlex
import traceback
from typing import TypedDict

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from ctui.commands import (
    CommandError,
    CommandNotFound,
    Commands,
    CommandValidationError,
    _list_annotation,
)
from ctui.path_completion import PathCompleter


def _argument_state(text: str) -> tuple[list[str], str, bool]:
    """Return completed tokens, the current word, and whether input ends at a boundary.

    Tolerate an unfinished quote while editing. Spaces inside quotes or escaped
    spaces stay in the current word; a trailing separator advances completion.
    This tracks editing state, while shlex performs final command parsing.
    """
    completed, word, boundary, _ = _argument_details(text)
    return completed, word, boundary


def _argument_details(text):
    """Track the raw token span as well as its shell-decoded editing value."""
    completed, current, quote, escaped = [], [], None, False
    start = 0
    boundary = False
    for index, character in enumerate(text):
        boundary = False
        if escaped:
            if quote == '"' and character not in ('"', "\\"):
                current.append("\\")
            current.append(character)
            escaped = False
        elif character == "\\" and quote != "'":
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
            if index > start:
                completed.append("".join(current))
                current = []
            start = index + 1
        else:
            current.append(character)
    return completed, "" if boundary else "".join(current), boundary, start


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

    def show_menu_first(self, document: Document) -> bool:
        """Whether Tab must reveal a hidden command menu before accepting it.

        Empty/whitespace-only input and unquoted command-word boundaries use
        this policy, including help targets. Partial words, argument values,
        quoted/escaped spaces and the start of existing text retain immediate
        acceptance. Both frontends use this decision only while no menu is shown.
        """
        text = document.text_before_cursor
        if not text.strip():
            return not document.text.strip()
        if not _argument_state(text)[2]:
            return False
        target = text.lstrip()
        try:
            item, arguments = self.commands.resolve(text)
        except CommandNotFound:
            pass
        else:
            if getattr(item.func, "__ctui_help__", False):
                target = arguments + " "
        return any(self._command_completions(target))

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
            yield _InputCompletion(
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
        """Contain provider failures at the interactive completion boundary."""
        try:
            async for item in self._get_completions_async(document, complete_event):
                yield item
        except Exception as error:
            self.type_hint = None
            from ctui.web import web_client

            if self.app is not None and (
                web_client.get() is not None
                or getattr(getattr(self.app, "app", None), "is_running", False)
            ):
                from ctui.dialogs import message_dialog

                message_dialog(
                    title="Completion error",
                    text=(
                        str(error)
                        if isinstance(error, CommandError)
                        else traceback.format_exc()
                    ),
                    scrollbar=True,
                )
            else:
                logging.getLogger(__name__).exception("Completion failed")

    async def _get_completions_async(self, document, complete_event):
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
            # Group suggestions were already emitted above.
            return
        if getattr(item.func, "__ctui_help__", False):
            target = argument_text + (" " if text[-1:].isspace() else "")
            for result in self._command_completions(target):
                yield result
            return
        _, _, input_at_boundary = _argument_state(text)
        if input_at_boundary:
            argument_text += " "
        completed, word, _, token_start = _argument_details(argument_text)
        raw_length = len(argument_text) - token_start
        completion_text = shlex.join(completed)
        if completion_text:
            completion_text += " "
        option, equals, value = word.partition("=")
        inline_option = option + "=" if equals and option.startswith("-") else ""
        if inline_option and argument_text[token_start:].startswith(inline_option):
            raw_length -= len(inline_option)
            inline_option = ""
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
            _, parameter = item.parse_args(completion_text, partial=True)
            config = item.arguments.get(parameter.name) if parameter else None
            annotation = (
                item.hints.get(parameter.name, parameter.annotation)
                if parameter
                else None
            )
            list_argument = _list_annotation(annotation) is not None
        except CommandValidationError:
            return
        for result in results:
            value = inline_option + result.value
            completion = _InputCompletion(
                _preview_value(document, raw_length, value) if result.value else "",
                start_position=-raw_length if result.value else 0,
                display=result.display or result.value,
                display_meta=result.help,
                value=value,
                finish=not list_argument or word.startswith("-"),
                directory=bool(
                    config
                    and isinstance(config.completer, PathCompleter)
                    and result.value.endswith(
                        tuple(x for x in (os.sep, os.altsep) if x)
                    )
                ),
            )
            if not result.value and result.display:
                self.type_hint = (document, completion)
            yield completion


class _InputCompletion(Completion):
    """Keep acceptance policy separate from prompt-toolkit's menu preview text.

    value is decoded input; directory continues the configured PathCompleter's
    navigation, while finish=False keeps a comma-separated list editable. Plain
    Completion providers retain their insertion text and default to finishing.
    """

    def __init__(self, text, *, value=None, finish=True, directory=False, **kwargs):
        super().__init__(text, **kwargs)
        self.value = value
        self.finish = finish
        self.directory = directory


def _token_end(text: str, start: int) -> int:
    """Find the end of a shell token, including any closing quote after the cursor."""
    quote, escaped = None, False
    for index in range(start, len(text)):
        character = text[index]
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in ("'", '"'):
            quote = character
        elif character.isspace():
            return index
    return len(text)


def _quote_value(value: str, original: str) -> str:
    """Preserve an explicitly started quote style and escape for shlex, not a shell."""
    if original.startswith('"'):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if original.startswith("'"):
        return "'" + value.replace("'", "'\"'\"'") + "'"
    return shlex.quote(value)


def _preview_value(document: Document, raw_length: int, value: str) -> str:
    """Quote a menu preview, reusing a closing quote immediately after the cursor.

    prompt-toolkit only replaces text before the cursor during arrow navigation.
    Keep the original quote style and omit the preview's closing quote when the
    untouched suffix already supplies it. Accepted edits still replace the whole
    token through completion_edit using the decoded value.
    """
    cursor = document.cursor_position
    start = cursor - raw_length
    end = _token_end(document.text, start)
    inserted = _quote_value(value, document.text[start:end])
    if (
        end == cursor + 1
        and inserted[:1] in ("'", '"')
        and document.text[cursor:end] == inserted[:1] == inserted[-1:]
    ):
        return inserted[:-1]
    return inserted


class _CompletionEdit(TypedDict):
    """One accepted input snapshot with code-point cursor and quote positions."""

    text: str
    cursor: int
    quote: int | None


def completion_edit(document: Document, completion: Completion) -> _CompletionEdit:
    """Return accepted input, cursor and owned closing-quote position for both UIs.

    Replace the whole current token, preserving subsequent arguments. Final
    values gain one separating space (reuse existing whitespace). Directories
    and list values remain editable, inside a closing quote when necessary.
    An empty type aid is a no-op. Positions count Python Unicode code points;
    the browser converts them to/from its UTF-16 selection offsets.
    """
    text, cursor = document.text, document.cursor_position
    if not completion.text:
        return {"text": text, "cursor": cursor, "quote": None}
    start = cursor + completion.start_position
    end = _token_end(text, start)
    value = getattr(completion, "value", None)
    inserted = (
        _quote_value(value, text[start:end]) if value is not None else completion.text
    )
    continuing = getattr(completion, "directory", False) or not getattr(
        completion, "finish", True
    )
    suffix = text[end:]
    position = start + len(inserted)
    quote_position = None
    if continuing:
        if inserted.startswith(("'", '"')) and inserted[-1:] == inserted[:1]:
            position -= 1
            quote_position = position
    elif suffix[:1].isspace():
        position += 1
    else:
        inserted += " "
        position += 1
    return {
        "text": text[:start] + inserted + suffix,
        "cursor": position,
        "quote": quote_position,
    }


def move_completion_quote(before: str, after: str, position: int | None) -> int | None:
    """Track an inserted closing quote across edits strictly before it; drop on removal.

    Comparing the changed span preserves ownership when users type path children,
    without treating arbitrary manually entered closing quotes as completion-owned.
    """
    if position is None or before == after:
        return position
    first = 0
    while first < min(len(before), len(after)) and before[first] == after[first]:
        first += 1
    old_end, new_end = len(before), len(after)
    while (
        old_end > first
        and new_end > first
        and before[old_end - 1] == after[new_end - 1]
    ):
        old_end -= 1
        new_end -= 1
    if first <= position and old_end <= position:
        return position + len(after) - len(before)
    return None


__all__ = ["CommandCompleter"]
