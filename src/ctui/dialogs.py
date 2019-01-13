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
from .base import Button
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.layout.containers import Float, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.eventloop import Future, ensure_future, Return, From
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.widgets import Dialog, Label, TextArea


class YesNoDialog(object):
    def __init__(self, title='', text='', yes_text='Yes', no_text='No',
                 width=None, wrap_lines=True, scrollbar=False):
        self.future = Future()

        def yes_handler():
            self.future.set_result(True)

        def no_handler():
            self.future.set_result(False)

        text_width = len(max(text.split('\n'), key=len)) + 2

        self.text_area = TextArea(
            text = text,
            read_only = True,
            # focus_on_click = True,
            focusable = False,
            width = D(preferred=text_width),
            wrap_lines = wrap_lines,
            scrollbar = scrollbar )

        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=[
                Button(text=yes_text, width=1, handler=yes_handler),
                Button(text=no_text, width=1, handler=no_handler) ],
            with_background=True,
            modal=True)

    def __pt_container__(self):
        return self.dialog


class TextInputDialog(object):
    def __init__(self, title='', text='', ok_text='Ok',
                 width=None, wrap_lines=True, scrollbar=False):
        self.future = Future()

        def accept_text(buf):
            get_app().layout.focus(ok_button)
            buf.complete_state = None
            return True

        def accept():
            self.future.set_result(self.text_area.text)

        def cancel():
            self.future.set_result(None)

        text_width = len(max(text.split('\n'), key=len)) + 2

        self.text_area = TextArea(
            completer=completer,
            multiline=False,
            width = D(preferred=text_width),
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
            width = width,
            modal=True)

    def __pt_container__(self):
        return self.dialog


class MessageDialog(object):
    def __init__(self, title='', text='', ok_text='Ok', shadow=False,
                 width=None, wrap_lines=True, scrollbar=False):
        self.future = Future()

        def set_done():
            self.future.set_result(None)

        text_width = len(max(text.split('\n'), key=len)) + 2
        text_height = len(text.split('\n'))
        app_height = get_app().ctui.layout.output_field.window.render_info.window_height - 2

        def dynamic_scrollbar():
             if text_height > app_height:
                 return True

        self.text_area = TextArea(
            text = text,
            read_only = True,
            # focus_on_click = True,
            focusable = False,
            width = D(preferred=text_width),
            wrap_lines = wrap_lines,
            scrollbar = dynamic_scrollbar())

        ok_button = Button(text='OK', handler=(lambda: set_done()))

        self.dialog = Dialog(
            title=title,
            body=self.text_area,
            buttons=[ok_button],
            width=width,
            modal=True)

    def __pt_container__(self):
        return self.dialog


def show_dialog(dialog):
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



# Functions that use dialog classes and return results

def func_pass():
    pass

def yes_no_dialog(title='', text='', yes_text='Yes', yes_func=func_pass,
                  no_text='No', no_func=func_pass):
    """
    Display a Yes/No dialog.
    Execute a passed function.
    """
    def coroutine():
        dialog = YesNoDialog(title=title, text=text, yes_text=yes_text,
                             no_text=no_text)
        result = yield From(show_dialog(dialog))
        if result == True:
            yes_func()
        else:
            no_func()
    ensure_future(coroutine())


# def button_dialog(title='', text='', buttons=[], style=None):
#     """
#     Display a dialog with button choices (given as a list of tuples).
#     Return the value associated with button.
#     """


def input_dialog(title='', text='', ok_text='OK', cancel_text='Cancel',
                 completer=None, password=False):
    """
    Display a text input box.
    Return the given text, or None when cancelled.
    """
    output_text = ''
    def coroutine():
        global output_text
        open_dialog = TextInputDialog(title, text, completer)

        output_text = yield From(show_dialog(open_dialog))
    ensure_future(coroutine())
    return output_text


def message_dialog(title='', text='', ok_text='Ok',
                   width=None, wrap_lines=True, scrollbar=None):
    """
    Display a simple message box and wait until the user presses enter.
    """
    def coroutine():
        dialog = MessageDialog(title=title, text=text, ok_text=ok_text,
                               width=width, wrap_lines=wrap_lines,
                               scrollbar=scrollbar)
        yield From(show_dialog(dialog))
    ensure_future(coroutine())


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
