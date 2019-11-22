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
from ctui.completion import CommandCompleter
from ctui.functions import show_help
from pathlib import Path
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import MenuContainer, MenuItem, SearchToolbar, TextArea


class CtuiLayout(object):
    """Class to facilitate editing and accessing different layout elements"""

    def __init__(self, ctui=None, input_field=None, output_field=None,
                 statusbar=None, root_container=None):
        self.ctui = ctui

        self._completer = CommandCompleter(ctui.commands)

        self._history = FileHistory(
            "{}/.{}_history".format(Path.home(), self.ctui.name))

        self._input_field = TextArea(
            height = 1,
            prompt = self.ctui.prompt,
            style = 'class:input_field',
            completer = self.completer,
            history = self.history)

        self._header_field = Window(
            height = 1,
            char = '-',
            style = 'class:line')

        self._output_field = TextArea(
            text = '',
            style = 'class:output_field',
            wrap_lines = self.ctui.wrap_lines,
            scrollbar = True )

        self._statusbar = Window(
            content = FormattedTextControl(self.statusbar_text),
            height = 1,
            style = 'class:statusbar'  )

        self._body = FloatContainer(

            HSplit([
                self.input_field,
                self.header_field,
                self.output_field,
                self.statusbar ]),
            floats = [Float(xcursor=True, ycursor=True,
                content=CompletionsMenu(max_height=16, scroll_offset=1) )] )

        self._root_container = MenuContainer(
            body = self.body,
            menu_items = [
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
                    MenuItem('Help', handler=show_help),
                    MenuItem('About'),  ]),  ],
            floats = [
                Float(xcursor=True,
                      ycursor=True,
                      content=CompletionsMenu(max_height=16, scroll_offset=1)),  ])


    @property
    def completer(self):
        return self._completer


    @property
    def history(self):
        return self._history


    @property
    def input_field(self):
        return self._input_field


    @property
    def header_field(self):
        return self._header_field


    @property
    def output_field(self):
        return self._output_field


    @property
    def statusbar_text(self):
        return self.ctui._statusbar


    @property
    def statusbar(self):
        return self._statusbar


    # Organization of windows
    @property
    def body(self):
        return self._body


    # Adding menus
    @property
    def root_container(self):
        return self._root_container
