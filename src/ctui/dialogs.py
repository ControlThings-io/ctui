"""
Control Things User Interface, aka ctui.py

# Copyright (C) 2017-2019  Justin Searle
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
from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.containers import Float, HSplit
from prompt_toolkit.eventloop import Future, ensure_future, Return, From
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.widgets import Button, Dialog, Label, TextArea


class TextInputDialog(object):
    def __init__(self, title='', text='', completer=None):
        self.future = Future()

        def accept_text(buf):
            get_app().layout.focus(ok_button)
            buf.complete_state = None
            return True

        def accept():
            self.future.set_result(self.text_area.text)

        def cancel():
            self.future.set_result(None)

        self.text_area = TextArea(
            completer=completer,
            multiline=False,
            width=D(preferred=40),
            accept_handler=accept_text)

        ok_button = Button(text='OK', handler=accept)
        cancel_button = Button(text='Cancel', handler=cancel)

        self.dialog = Dialog(
            title=title,
            body=HSplit([
                Label(text=text),
                self.text_area
            ]),
            buttons=[ok_button, cancel_button],
            width=D(preferred=60),
            modal=True)

    def __pt_container__(self):
        return self.dialog


class MessageDialog(object):
    def __init__(self, title='', text='', ok_text='Ok', style=None,
                 async_=False, wrap_lines=False, scrollbar=False):
        self.future = Future()

        def set_done():
            self.future.set_result(None)

        ok_button = Button(text='OK', handler=(lambda: set_done()))

        self.dialog = Dialog(
            title=title,
            body=HSplit([
                Label(text=text),
            ]),
            buttons=[ok_button],
            width=D(preferred=60),
            modal=True)

    def __pt_container__(self):
        return self.dialog


def show_dialog_as_float(dialog):
    " Coroutine. "
    app = get_app()
    float_ = Float(content=dialog)
    app.layout.container.floats.insert(0, float_)
    focused_before = app.layout.current_window
    app.layout.focus(dialog)
    result = yield dialog.future
    app.layout.focus(focused_before)

    if float_ in app.layout.container.floats:
        app.layout.container.floats.remove(float_)

    raise Return(result)


# def yes_no_dialog(title='', text='', yes_text='Yes', no_text='No', style=None,
#                   async_=False):
#     """
#     Display a Yes/No dialog.
#     Return a boolean.
#     """


# def button_dialog(title='', text='', buttons=[], style=None,
#                   async_=False):
#     """
#     Display a dialog with button choices (given as a list of tuples).
#     Return the value associated with button.
#     """


def input_dialog(title='', text='', ok_text='OK', cancel_text='Cancel',
                 completer=None, password=False, style=None, async_=False):
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """
    output_text = ''
    def coroutine():
        global output_text
        open_dialog = TextInputDialog(title, text, completer)

        output_text = yield From(show_dialog_as_float(open_dialog))
    ensure_future(coroutine())
    return output_text


def message_dialog(title='', text='', ok_text='Ok', style=None, async_=False):
    """
    Display a simple message box and wait until the user presses enter.
    """
    def coroutine():
        dialog = MessageDialog(title, text)
        yield From(show_dialog_as_float(dialog))
    ensure_future(coroutine())


# def radiolist_dialog(title='', text='', ok_text='Ok', cancel_text='Cancel',
#                      values=None, style=None, async_=False):
#     """
#     Display a simple list of element the user can choose amongst.
#
#     Only one element can be selected at a time using Arrow keys and Enter.
#     The focus can be moved between the list and the Ok/Cancel button with tab.
#     """


# def progress_dialog(title='', text='', run_callback=None, style=None, async_=False):
#     """
#     :param run_callback: A function that receives as input a `set_percentage`
#         function and it does the work.
#     """
