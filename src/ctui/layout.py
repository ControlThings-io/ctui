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
from .base import TextArea
from .functions import show_help
from pathlib import Path
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import MenuContainer, MenuItem, SearchToolbar
from prompt_toolkit.completion import WordCompleter


class CtuiLayout(object):
    """Class to facility access to different layout elements"""

    def __init__(self, ctui, input_field=None, output_field=None, statusbar=None, root_container=None):
        """Stores layout of the app returns root_container"""
        completer = WordCompleter(ctui._commands(), meta_dict=ctui._meta_dict(), sentence=True, ignore_case=True)
        history = FileHistory("{}/.{}_history".format(Path.home(), ctui.name))
        search_field = SearchToolbar()

        self.input_field = TextArea(
            height=1,
            prompt=ctui.prompt,
            style='class:input_field',
            completer=completer,
            history=history)

        self.header_field = Window(
            height=1,
            char='-',
            style='class:line')

        self.output_field = TextArea(
            text='',
            # search_field=search_field,
            style='class:output_field',
            wrap_lines=ctui.wrap_lines,
            scrollbar=True )

        self.statusbar = Window(
            content = FormattedTextControl(self._get_statusbar_text(ctui)),
            height=1,
            style='class:statusbar'  )

        # Organization of windows
        self.body = FloatContainer(
            HSplit([
                self.input_field,
                self.header_field,
                self.output_field,
                search_field,
                self.statusbar ]),
            floats=[
                Float(xcursor=True,
                      ycursor=True,
                      content=CompletionsMenu(max_height=16, scroll_offset=1)) ] )

        # Adding menus
        self.root_container = MenuContainer(
            body=self.body,
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
                    MenuItem('Help', handler=show_help),
                    MenuItem('About'),  ]),  ],
            floats=[
                Float(xcursor=True,
                      ycursor=True,
                      content=CompletionsMenu(max_height=16, scroll_offset=1)),  ])


    def _get_statusbar_text(self, ctui):
        text = ctui.statusbar
        return text
