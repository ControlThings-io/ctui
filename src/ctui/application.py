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
from .keybindings import get_key_bindings
from .commands import Commands
from .layout import CtuiLayout
from .style import CtuiStyle
from prompt_toolkit.application import Application
from prompt_toolkit.layout.layout import Layout
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage


class Ctui(Commands):
    """Class with commands that users may use at the application prompt."""
    # Each function representing a command must:
    #     - start with a do_
    #     - accept self, input_text, output_text, and event as params
    #     - return a string to print, None, or False
    # Returning a False does nothing, forcing users to correct mistakes
    name = 'Nameless'
    version = '0.1'
    description = 'No description.'
    prompt = '> '
    welcome = ''
    help_message = ''
    statusbar = ''
    wrap_lines = False


    def __init__(self, layout=None):
        if self.welcome == '':
            self.welcome = 'Welcome to ' + self.name + ' ' + str(self.version) + '\n' + self.description + '\n'
        if self.help_message == '':
            self.help_message = self.welcome + '\n' + 'Available commands are:' + '\n\n'
        self.layout = CtuiLayout(self)
        self.style = CtuiStyle()


    def run(self):
        """Start the Ctui application"""
        layout = Layout(
            self.layout.root_container,
            focused_element=self.layout.input_field)
        application = CtuiApplication(
            layout=layout,
            key_bindings=get_key_bindings(self),
            style=self.style.get(),
            enable_page_navigation_bindings=False,
            mouse_support=True,
            full_screen=True)
        application.register_ctui(self)
        application.run()


    def execute(self, input_text, output_text, event):
        """Extract command and call appropriate function."""
        parts = input_text.strip().split(maxsplit=1)
        command = parts[0].lower()
        if len(parts) == 2:
            arg = parts[1]
        else:
            arg = ''
        try:
            func = getattr(self, 'do_' + command)
        except AttributeError:
            return False
        return func(arg, output_text, event)


    def commands(self):
        """Generate list of user commands from function names"""
        commands = [a[3:] for a in dir(self.__class__) if a.startswith('do_')]
        return commands


    def meta_dict(self):
        """Generate a dictionary of commands to populate Ctui completer"""
        meta_dict = {}
        for command in self.commands():
            # TODO: find a better way to do this than eval
            meta_dict[command] = eval('self.do_' + command + '.__doc__')
        return meta_dict




class CtuiApplication(Application):
    """Application class to maintate state objects"""
    db = TinyDB(storage=MemoryStorage)
    settings = db.table('settings')
    storage = db.table('storage')
    history = db.table('history')

    def register_ctui(self, ctui):
        self.ctui = ctui
        self.input_field = ctui.layout.input_field
        self.header_field = ctui.layout.header_field
        self.output_field = ctui.layout.output_field
