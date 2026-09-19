"""
Control Things User Interface, aka ctui.py

# Copyright (C) 2019  Justin Searle
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details at <http://www.gnu.org/licenses/>.
"""

from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import TextArea

from ctui.completion import CommandCompleter


class CtuiLayout:
    """Build and expose the standard ctui input and output layout."""

    def __init__(
        self,
        ctui=None,
        input_field=None,
        output_field=None,
        statusbar=None,
        root_container=None,
    ):
        """Build the standard input, output, completion, and status layout."""
        self.ctui = ctui

        self._completer = CommandCompleter(ctui.commands, ctui)

        self._history = InMemoryHistory()

        self._input_field = input_field or TextArea(
            height=1,
            prompt=self.ctui.prompt,
            style="class:input_field",
            completer=self.completer,
            history=self.history,
        )

        if input_field is None:
            self._input_field.buffer.on_completions_changed += self._restore_type_hint

        self._header_field = Window(height=1, char="-", style="class:line")

        self._output_field = output_field or TextArea(
            text="",
            style="class:output_field",
            wrap_lines=self.ctui.wrap_lines,
            scrollbar=True,
            read_only=True,
            focusable=False,
        )

        self._statusbar = statusbar or Window(
            content=FormattedTextControl(lambda: self.statusbar_text),
            height=1,
            style="class:statusbar",
        )

        self._body = FloatContainer(
            HSplit(
                [self.input_field, self.header_field, self.output_field, self.statusbar]
            ),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=16, scroll_offset=1),
                )
            ],
        )

        self._root_container = root_container or self._body

    def _restore_type_hint(self, buffer):
        """Keep non-inserting type aids that prompt-toolkit normally discards."""
        hint = self._completer.type_hint
        if buffer.complete_state is None and hint is not None:
            document, completion = hint
            if buffer.document == document:
                buffer.complete_state = CompletionState(document, [completion])

    @property
    def completer(self):
        """Return the command-aware prompt completer."""
        return self._completer

    @property
    def history(self):
        """Return prompt-toolkit's in-session editing history."""
        return self._history

    @property
    def input_field(self):
        """Return the single-line command input widget."""
        return self._input_field

    @property
    def header_field(self):
        """Return the separator between input and output."""
        return self._header_field

    @property
    def output_field(self):
        """Return the scrollable command output widget."""
        return self._output_field

    def set_output(self, text: str) -> None:
        """Replace read-only output through prompt-toolkit's safe bypass."""
        self._output_field.buffer.set_document(
            Document(text=text, cursor_position=len(text)),
            bypass_readonly=True,
        )

    @property
    def statusbar_text(self):
        """Resolve status text dynamically from the application."""
        return self.ctui._statusbar

    @property
    def statusbar(self):
        """Return the status-bar window."""
        return self._statusbar

    # Organization of windows
    @property
    def body(self):
        """Return the standard vertically arranged body container."""
        return self._body

    # Adding menus
    @property
    def root_container(self):
        """Return the root prompt-toolkit container used by default."""
        return self._root_container
