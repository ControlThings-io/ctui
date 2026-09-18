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

from asyncio import Future, ensure_future

from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.layout.containers import Float, HSplit
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import Dialog, Label, TextArea

from .base import Button


def _text_width(text, scrollbar):
    """Allow space for the scrollbar and the buffer's trailing cursor cell."""
    plain = fragment_list_to_text(to_formatted_text(text))
    longest = max((get_cwidth(line) for line in plain.splitlines()), default=0)
    return D(preferred=longest + 1 + int(bool(scrollbar)))


def _scroll_buttons(text_area, buttons):
    """Scroll read-only text without moving focus away from dialog buttons."""
    # Import lazily: functions also exposes convenience dialog helpers.
    from .functions import (
        scroll_line_down,
        scroll_line_up,
        scroll_page_down,
        scroll_page_up,
    )

    for button in buttons:
        for key, handler in (
            ("up", scroll_line_up),
            ("down", scroll_line_down),
            ("pageup", scroll_page_up),
            ("pagedown", scroll_page_down),
        ):

            def scroll(event, handler=handler):
                handler(event, text_area)

            button.control.key_bindings.add(key)(scroll)


class YesNoDialog:
    """Display a modal confirmation with affirmative and negative actions."""

    def __init__(
        self,
        title="",
        text="",
        yes_text="Yes",
        no_text="No",
        width=None,
        wrap_lines=True,
        scrollbar=False,
    ):
        """Construct a confirmation dialog and its result future."""
        self.future = Future()

        def yes_handler():
            """Resolve the dialog with an affirmative result."""
            self.future.set_result(True)

        def no_handler():
            """Resolve the dialog with a negative result."""
            self.future.set_result(False)

        self.text_area = TextArea(
            text=text,
            read_only=True,
            # focus_on_click = True,
            focusable=False,
            width=_text_width(text, scrollbar),
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )

        buttons = [
            Button(text=yes_text, width=1, handler=yes_handler),
            Button(text=no_text, width=1, handler=no_handler),
        ]
        _scroll_buttons(self.text_area, buttons)
        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=buttons,
            with_background=True,
            modal=True,
            width=width,
        )

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog


class TextInputDialog:
    """Collect a single line of text in a modal dialog."""

    def __init__(
        self,
        title="",
        text="",
        ok_text="Ok",
        cancel_text="Cancel",
        completer=None,
        password=False,
        width=None,
    ):
        """Construct a text-input dialog and its result future."""
        self.future = Future()

        def accept_text(buf):
            """Move focus to confirmation after accepting the input buffer."""
            get_app().layout.focus(ok_button)
            buf.complete_state = None
            return True

        def accept():
            """Resolve the dialog with the entered text."""
            self.future.set_result(self.text_area.text)

        def cancel():
            """Resolve the dialog with ``None`` to indicate cancellation."""
            self.future.set_result(None)

        text_width = len(max(text.split("\n"), key=len)) + 2

        self.text_area = TextArea(
            completer=completer,
            multiline=False,
            width=D(preferred=text_width),
            accept_handler=accept_text,
            password=password,
        )

        ok_button = Button(text=ok_text, handler=accept)
        cancel_button = Button(text=cancel_text, handler=cancel)

        self.dialog = Dialog(
            title=title,
            body=HSplit([Label(text=text), self.text_area]),
            buttons=[ok_button, cancel_button],
            width=width,
            modal=True,
        )

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog


class MessageDialog:
    """Display read-only text in a modal dialog."""

    def __init__(
        self,
        title="",
        text="",
        ok_text="Ok",
        lexer=None,
        width=None,
        wrap_lines=True,
        scrollbar=False,
        focusable=False,
    ):
        """Construct a message dialog sized to its content."""
        self.future = Future()
        self.text = text

        def set_done():
            """Resolve the dialog result after acknowledgement."""
            self.future.set_result(None)

        def dynamic_vertical_scrollbar():
            """Enable scrolling when content exceeds the terminal height."""
            text_fragments = to_formatted_text(self.text)
            text = fragment_list_to_text(text_fragments)
            if text:
                text_height = len(self.text.splitlines())
                max_text_height = get_app().renderer.output.get_size().rows - 6
                if text_height > max_text_height:
                    return True
            return False

        scrollbar = dynamic_vertical_scrollbar() if scrollbar is None else scrollbar
        self.text_area = TextArea(
            text=text,
            lexer=lexer,
            read_only=True,
            focusable=focusable,
            width=_text_width(text, scrollbar),
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )

        ok_button = Button(text=ok_text, handler=set_done)
        _scroll_buttons(self.text_area, [ok_button])

        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=[ok_button],
            width=width,
            modal=True,
        )

    def __pt_container__(self):
        """Expose the underlying dialog to prompt-toolkit."""
        return self.dialog


async def show_dialog(dialog):
    """Display *dialog* as a modal float and return its result."""
    app = get_app()
    float_ = Float(content=dialog)
    app.layout.container.floats.insert(0, float_)
    focused_before = app.layout.current_window
    app.layout.focus(dialog)
    result = await dialog.future
    app.layout.focus(focused_before)

    if float_ in app.layout.container.floats:
        app.layout.container.floats.remove(float_)

    return result


# Functions that use dialog classes and return results


def func_pass():
    """Provide a no-operation default dialog callback."""


def yes_no_dialog(
    title="",
    text="",
    yes_text="Yes",
    yes_func=func_pass,
    no_text="No",
    no_func=func_pass,
):
    """
    Display a Yes/No dialog.
    Execute a passed function.
    """

    async def coroutine():
        """Show the confirmation and invoke the selected callback."""
        dialog = YesNoDialog(title=title, text=text, yes_text=yes_text, no_text=no_text)
        result = await show_dialog(dialog)
        if result is True:
            yes_func()
        else:
            no_func()

    return ensure_future(coroutine())


# def button_dialog(title='', text='', buttons=[], style=None):
#     """
#     Display a dialog with button choices (given as a list of tuples).
#     Return the value associated with button.
#     """


def input_dialog(
    title="",
    text="",
    ok_text="OK",
    cancel_text="Cancel",
    completer=None,
    password=False,
):
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """

    async def coroutine():
        """Show the input dialog and return its result."""
        open_dialog = TextInputDialog(
            title=title,
            text=text,
            ok_text=ok_text,
            cancel_text=cancel_text,
            completer=completer,
            password=password,
        )
        return await show_dialog(open_dialog)

    return ensure_future(coroutine())


def message_dialog(
    title="",
    text="",
    ok_text="Ok",
    lexer=None,
    width=None,
    wrap_lines=True,
    scrollbar=None,
):
    """
    Display a simple message box and wait until the user presses enter.
    """

    async def coroutine():
        """Show the message dialog until it is acknowledged."""
        dialog = MessageDialog(
            title=title,
            text=text,
            ok_text=ok_text,
            lexer=lexer,
            width=width,
            wrap_lines=wrap_lines,
            scrollbar=scrollbar,
        )
        await show_dialog(dialog)

    return ensure_future(coroutine())


# def radiolist_dialog(title='', text='', ok_text='Ok', cancel_text='Cancel',
#                      values=None, style=None):
#     """
#     Display a simple list of element the user can choose amongst.
#
#     Only one element can be selected at a time using Arrow keys and Enter.
#     The focus can be moved between the list and the Ok/Cancel button with tab.
#     """


# def progress_dialog(title='', text='', run_callback=None, style=None):
#     """
#     :param run_callback: A function that receives as input a `set_percentage`
#         function and it does the work.
#     """
