"""Default prompt-toolkit panes, completion float, and dynamic status text.

The output pane is read-only and non-focusable, leaving input focused while the
terminal handles mouse selection. Framework writes bypass read-only protection
through set_output(); assigning to the buffer document directly would fail.

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
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import TextArea

from ctui.completion import CommandCompleter, completion_edit, move_completion_quote


class CtuiLayout:
    """Build input, separator, output, and status panes with a completion float.

    Accept injected widgets or a root container for customization. The default
    body is a FloatContainer, allowing dialogs to add modal floats. Its editing
    history belongs to prompt-toolkit and is separate from accepted-command
    history in CtuiApp. compose() can reuse the body or individual widgets.
    """

    def __init__(
        self,
        ctui=None,
        input_field=None,
        output_field=None,
        statusbar=None,
        root_container=None,
    ):
        """Build widgets for a configured CtuiApp without starting the UI loop.

        ctui supplies commands, prompt, wrapping, and status text. Optional widgets
        replace their defaults; a custom input widget owns its own completion setup.
        Install the non-inserting type-hint restoration hook only on default input.
        """
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
        self._completion_quote = None
        self._completion_text = self._input_field.text

        if input_field is None:
            self._input_field.buffer.on_completions_changed += self._restore_type_hint
            self._input_field.buffer.on_text_changed += self._track_completion_quote

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

    def _track_completion_quote(self, buffer):
        """Keep ownership of an inserted closing quote while its contents change."""
        self._completion_quote = move_completion_quote(
            self._completion_text, buffer.text, self._completion_quote
        )
        self._completion_text = buffer.text

    def accept_completion(self, completion: Completion, document: Document) -> None:
        """Apply one highlighted suggestion and request the next context's menu.

        document is the menu's original input, before arrow-key previews. Type
        aids do not insert anything. Only the default command completer uses
        this acceptance policy; injected input widgets retain their own setup.
        """
        if not completion.text:
            return
        edit = completion_edit(document, completion)
        buffer = self.input_field.buffer
        # A directory/list preview can already equal the accepted edit. Explicitly
        # dismiss its menu even when assigning the Document changes nothing.
        buffer.complete_state = None
        buffer.document = Document(edit["text"], edit["cursor"])
        self._completion_text = buffer.text
        self._completion_quote = edit["quote"]
        buffer.start_completion()

    def completion_quote_at_cursor(self, character: str | None = None) -> bool:
        """Whether input is immediately before a completion-owned closing quote."""
        buffer = self.input_field.buffer
        position = self._completion_quote
        return (
            position is not None
            and buffer.cursor_position == position
            and not buffer.selection_state
            and buffer.text[position : position + 1] in ("'", '"')
            and (character is None or buffer.text[position] == character)
        )

    def finish_completion_quote(self, space: bool = False) -> None:
        """Step over the owned quote, optionally inserting/reusing a separator."""
        buffer = self.input_field.buffer
        position = buffer.cursor_position + 1
        self._completion_quote = None
        buffer.cursor_position = position
        if space:
            if buffer.text[position : position + 1].isspace():
                buffer.cursor_position += 1
            else:
                buffer.insert_text(" ")
            buffer.start_completion()

    def _restore_type_hint(self, buffer):
        """Restore a discarded no-op completion only for its original Document.

        prompt-toolkit can remove hints whose insertion changes nothing, notably
        just after a separating space. Keep the aid visible without resurrecting
        stale suggestions after another edit or altering submitted text.
        """
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
        """Replace output using the buffer's explicit read-only bypass.

        Place its invisible cursor at the start of the final line to follow new
        output vertically without scrolling past the first column. Reset horizontal
        scrolling on replacement; long lines remain intact.
        This does not append, update CtuiApp.output_text, or explicitly invalidate
        the application; callers choose presentation and redraw behavior.
        """
        self._output_field.buffer.set_document(
            Document(text=text, cursor_position=text.rfind("\n") + 1),
            bypass_readonly=True,
        )
        self._output_field.window.horizontal_scroll = 0

    @property
    def statusbar_text(self):
        """Resolve application text on redraw, evaluating a callable if configured.

        Return text rather than printing it, which would interfere with terminal
        rendering. Background updates should invalidate the running application;
        this property does not poll or schedule a refresh timer.
        """
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
