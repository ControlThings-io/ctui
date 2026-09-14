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

import inspect
import traceback

from prompt_toolkit.filters import has_focus
from prompt_toolkit.key_binding import KeyBindings

from .commands import CommandError
from .dialogs import YesNoDialog, message_dialog, show_dialog
from .functions import (
    scroll_end,
    scroll_home,
    scroll_line_down,
    scroll_line_up,
    scroll_page_down,
    scroll_page_up,
)


def get_key_bindings(ctui):
    """Return keybinding object for application shortcut keys"""
    input_field = ctui.layout.input_field
    output_field = ctui.layout.output_field
    kb = KeyBindings()

    #######################
    # Global key bindings #
    #######################

    @kb.add("c-q")  # None-graceful shutdown, ctui.exit() is graceful
    def _(event):
        "Pressing Ctrl-Q will force quit the user interface."
        ctui.app.exit()

    #################################
    # Input Field ONLY key bindings #
    #################################

    @kb.add("enter", filter=has_focus(input_field))
    def _(event):
        """Schedule the current command without blocking terminal rendering."""
        if len(input_field.text) == 0:
            return
        submitted = input_field.text
        submission_id = getattr(ctui, "_submission_id", 0) + 1
        ctui._submission_id = submission_id
        # Clear immediately so another command can be entered while this one runs.
        input_field.buffer.reset(append_to_history=True)
        input_field.text = ""

        def restore_if_latest():
            """Restore rejected input only when no newer command replaced it."""
            if ctui._submission_id == submission_id and not input_field.text:
                input_field.text = submitted
                return True
            return False

        async def execute():
            """Dispatch input and apply its normalized result to the widgets."""
            try:
                ctui.output_text = output_field.text
                result = await ctui.dispatch(
                    submitted,
                    confirm_callback=lambda message: show_dialog(
                        YesNoDialog(title="Confirm", text=message)
                    ),
                )
            except CommandError as error:
                restored = restore_if_latest()
                if restored and getattr(error, "position", None) is not None:
                    input_field.buffer.cursor_position = min(
                        error.position, len(input_field.text)
                    )
                message_dialog(title="Error", text=str(error))
                return
            except Exception:
                restore_if_latest()
                message_dialog(
                    title="Error", text=traceback.format_exc(), scrollbar=True
                )
                return
            if not result.accepted:
                restore_if_latest()
                return
            if result.clear_output:
                ctui.layout.set_output("")
            elif result.output is not None:
                output = result.output
                if result.append_output and output_field.text:
                    output = f"{output_field.text.rstrip()}\n{output}"
                ctui.layout.set_output(output)
            if result.exit_requested:
                ctui.exit()

        event.app.create_background_task(execute())

    @kb.add("c-a", filter=has_focus(input_field))
    def _(event):
        """Move to the beginning of the input line."""
        input_field.buffer.cursor_position = 0

    @kb.add("c-e", filter=has_focus(input_field))
    def _(event):
        """Move to the end of the input line."""
        input_field.buffer.cursor_position = len(input_field.text)

    @kb.add("c-u", filter=has_focus(input_field))
    def _(event):
        """Delete input from the cursor back to the beginning."""
        input_field.buffer.delete_before_cursor(input_field.buffer.cursor_position)

    @kb.add("c-k", filter=has_focus(input_field))
    def _(event):
        """Delete input from the cursor through the end."""
        input_field.buffer.delete(
            len(input_field.text) - input_field.buffer.cursor_position
        )

    @kb.add("c-w", filter=has_focus(input_field))
    def _(event):
        """Delete the word immediately before the cursor."""
        word = input_field.buffer.document.get_word_before_cursor(WORD=True)
        input_field.buffer.delete_before_cursor(len(word))

    @kb.add("c-c", filter=has_focus(input_field))
    def _(event):
        """Cancel and clear the current input line."""
        input_field.buffer.reset()

    @kb.add("c-d", filter=has_focus(input_field))
    def _(event):
        """Delete one character, or exit when the input line is empty."""
        if input_field.text:
            input_field.buffer.delete(1)
        else:
            ctui.exit()

    @kb.add("c-l", filter=has_focus(input_field))
    def _(event):
        """Clear command output without changing the input line."""
        ctui.layout.set_output("")

    for keys, handler, _description in ctui.shortcuts:

        @kb.add(*keys)
        def _(event, shortcut_handler=handler):
            """Invoke a user-defined synchronous or asynchronous shortcut."""
            result = shortcut_handler()
            if inspect.isawaitable(result):
                event.app.create_background_task(result)

    #############################################
    # Key bindings that affect the output_field #
    #############################################

    @kb.add("home", filter=has_focus(input_field))
    def _(event):
        """Scroll the output field to its beginning."""
        scroll_home(event, output_field)

    @kb.add("end", filter=has_focus(input_field))
    def _(event):
        """Scroll the output field to its end."""
        scroll_end(event, output_field)

    @kb.add("pagedown", filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one page"""
        scroll_page_down(event, output_field)

    @kb.add("pageup", filter=has_focus(input_field))
    def _(event):
        """Scroll output_field up one page"""
        scroll_page_up(event, output_field)

    @kb.add("c-down", filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_line_down(event, output_field)

    @kb.add("c-up", filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_line_up(event, output_field)

    return kb
