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

import sys
import time
# from .commands import Ctui
from .base import TextArea
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_focus
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.shortcuts.dialogs import message_dialog
from prompt_toolkit.search import start_search, SearchDirection
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import MenuContainer, MenuItem, ProgressBar, SearchToolbar #, TextArea
from prompt_toolkit.completion import WordCompleter
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage


class MyApplication(Application):
    """Application class"""
    prompt = '> '
    statusbar = {}
    statusbar_sep = '  -  '
    db = TinyDB(storage=MemoryStorage)
    settings = db.table('settings')
    trans = db.table('transactions')
    history = db.table('history')


def get_statusbar_text():
    sep = get_app().statusbar_sep
    statusbar = get_app().statusbar
    text = sep.join(['{}:{}'.format(k,v) for k,v in statusbar.items()])
    return text


# def start_app(session):
def start_app(ctui):
    """Text-based GUI application"""
    completer = WordCompleter(ctui.commands(), meta_dict=ctui.meta_dict(), ignore_case=True)
    history = InMemoryHistory()
    search_field = SearchToolbar()

    # Individual windows
    input_field = TextArea(
        height=1,
        prompt=ctui.prompt,
        style='class:input-field',
        completer=completer,
        history=history)

    output_field = TextArea(
        scrollbar=True,
        search_field=search_field,
        style='class:output-field',
        text='')

    statusbar = Window(
        content = FormattedTextControl(get_statusbar_text),
        height=1,
        style='class:statusbar'  )

    # Organization of windows
    body = FloatContainer(
        HSplit([
            input_field,
            Window(height=1, char='-', style='class:line'),
            output_field,
            search_field,
            statusbar ]),
        floats=[
            Float(xcursor=True,
                  ycursor=True,
                  content=CompletionsMenu(max_height=16, scroll_offset=1)) ] )

    # Adding menus
    root_container = MenuContainer(
        body=body,
        menu_items=[
            MenuItem('Session ', children=[
                MenuItem('Connect'),
                MenuItem('Disconnect'),
        #         MenuItem('Save'),
        #         MenuItem('Save as...'),
        #         MenuItem('-', disabled=True),
                MenuItem('Exit'),  ]),
            MenuItem('Edit ', children=[
                MenuItem('Copy'),
                MenuItem('Paste'),  ]),
            MenuItem('Help ', children=[
                MenuItem('Help'),
                MenuItem('About'),  ]),  ],
        floats=[
            Float(xcursor=True,
                  ycursor=True,
                  content=CompletionsMenu(max_height=16, scroll_offset=1)),  ])

    # The key bindings.
    kb = KeyBindings()

    @kb.add('tab')
    def _(event):
        try:
            event.app.layout.focus_next()
        except:
            pass

    @kb.add('s-tab')
    def _(event):
        try:
            event.app.layout.focus_previous()
        except:
            pass

    @kb.add('c-q')
    def _(event):
        " Pressing Ctrl-Q will exit the user interface. "
        ctui.do_exit(input_field.text, output_field.text, event)

    @kb.add('c-d')
    def _(event):
        """Press Ctrl-D to start the python debugger"""
        import pdb
        pdb.set_trace()

    # @kb.add('space')
    # def _(event):
    #     input_text = input_field.text
    #     cursor=len(input_text)
    #     input_updated = input_text[:cursor] + ' ' + input_text[cursor+1:]
    #     cursor += 1
    #     input_field.buffer.document = Document(
    #         text=input_updated, cursor_position=cursor)
    #     input_field.buffer.completer = WordCompleter([], ignore_case=True)


    # Input Field ONLY key bindings
    @kb.add('enter', filter=has_focus(input_field))
    def _(event):
        # Process commands on prompt after hitting enter key
        # tx_bytes = parse_command(input_field.text, event=event)
        input_field.buffer.completer = WordCompleter(ctui.commands(), meta_dict=ctui.meta_dict(), ignore_case=True)
        if len(input_field.text) == 0:
            return
        output_text = ctui.execute(input_field.text, output_field.text, event)
        input_field.buffer.reset(append_to_history=True)

        # For commands that do not have output_text
        if output_text == None:
            input_field.text = ''
            return
        # For invalid commands forcing users to correct them
        elif output_text == False:
            return
        # For invalid commands forcing users to correct them
        else:
            output_field.buffer.document = Document(
                text=output_text, cursor_position=len(output_text))
            input_field.text = ''

    @kb.add('c-c', filter=has_focus(input_field))
    def _(event):
        """Pressing Control-C will copy highlighted text to clipboard"""
        data = input_field.buffer.copy_selection()
        get_app().clipboard.set_data(data)

    @kb.add('c-p', filter=has_focus(input_field))
    def _(event):
        """Pressing Control-P will paste text from clipboard"""
        input_field.buffer.paste_clipboard_data(get_app().clipboard.get_data())


    # Output Field ONLY key bindings
    kb.add('pagedown', filter=has_focus(output_field))(scroll_page_down)
    kb.add('space', filter=has_focus(output_field))(scroll_page_down)
    kb.add('f', filter=has_focus(output_field))(scroll_page_down)
    kb.add('pageup')(scroll_page_up)
    kb.add('b')(scroll_page_up)

    @kb.add('q', filter=has_focus(output_field))
    def _(event):
        """Quit navigation back to input_field"""
        event.app.layout.focus_previous()

    @kb.add('/', filter=has_focus(output_field))
    def _(event):
        """Search and highlight strigs in output_field"""
        start_search(output_field.control)

    @kb.add('g', filter=has_focus(output_field))
    def _(event):
        """Goto beginning of output_field"""
        output_field.buffer.document = Document(
            text=output_field.text, cursor_position=0)

    @kb.add('G', filter=has_focus(output_field))
    def _(event):
        """Goto end of output_field"""
        output_field.buffer.document = Document(
            text=output_field.text, cursor_position=len(output_field.text))

    @kb.add('n', filter=has_focus(output_field))
    def _(event):
        """Goto next item in output_field search"""
        search_state = get_app().current_search_state
        cursor_position = output_field.buffer.get_search_position(
            search_state, include_current_position=False)
        output_field.buffer.cursor_position = cursor_position

    @kb.add('N', filter=has_focus(output_field))
    def _(event):
        """Goto previous item in output_field search"""
        search_state = get_app().current_search_state
        cursor_position = output_field.buffer.get_search_position(
            ~search_state, include_current_position=True)
        output_field.buffer.cursor_position = cursor_position

    @kb.add('c-c', filter=has_focus(output_field))
    def _(event):
        """Pressing Control-C will copy highlighted text to clipboard"""
        data = output_field.buffer.copy_selection()
        get_app().clipboard.set_data(data)

    @kb.add('<any>', filter=has_focus(output_field))
    @kb.add('enter', filter=has_focus(output_field))
    @kb.add('c-c', filter=has_focus(output_field))
    def _(event):
        """Prevent user from editing output_field"""
        pass

    # Colors of various style labels
    style = Style([
        # ('output-field', 'bg:#000000 #ffffff'),
        # ('input-field', 'bg:#000000 #ffffff'),
        ('line',        '#004400'),
        ('statusbar', 'bg:#AAAAAA')  ])

    # Run application.
    application = MyApplication(
        layout=Layout(root_container, focused_element=input_field),
        key_bindings=kb,
        style=style,
        # enable_page_navigation_bindings=True,
        mouse_support=True,
        full_screen=True  )
    application.run()
