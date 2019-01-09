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
from pathlib import Path
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.layout import Layout
from tinydb import TinyDB, Query


class Ctui(Commands):
    """Class with commands that users may use at the application prompt."""
    # Each function representing a command must:
    #     - start with a do_
    #     - accept self, input_text, output_text, and event as params
    #     - return a string to print, None, or False
    # Returning a False does nothing, forcing users to correct mistakes
    name = 'ctui'
    version = ''
    description = ''
    prompt = '> '
    welcome = ''
    help_message = ''
    statusbar = ''
    wrap_lines = False
    project_folder = ''

    # sets various defaults if not overriden with subclass
    def __init__(self, layout=None):
        if self.welcome == '':
            self.welcome = 'Welcome to ' + self.name + ' ' + str(self.version) + '\n' + self.description + '\n'
        if self.help_message == '':
            self.help_message = self.welcome + '\n' + 'Available commands are:' + '\n\n'

        # Set up database storage
        if self.project_folder == '':
            self.project_folder = "{}/.{}/projects/".format(Path.home(), self.name)
        Path(self.project_folder).mkdir(parents=True, exist_ok=True)
        self.project_name = 'default'
        self.statusbar = 'Project: {}'.format(self.project_name)
        # start with clean default project at each start
        self.project_path = '{}{}.{}'.format(self.project_folder, self.project_name, self.name)
        if Path(self.project_path).exists():
            Path.unlink(Path(self.project_path))
        self.init_db()

        # Setup python_prompt applction elements
        self.layout = CtuiLayout(self)
        self.style = CtuiStyle()

    def init_db(self):
        """setup database storage"""
        self.db = TinyDB(self.project_path)
        self.settings = self.db.table('settings')
        self.storage = self.db.table('storage')
        self.history = self.db.table('history')


    def run(self):
        """Start the python_prompt application with ctui's default settings"""
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


    def quit(self):
        self.db.close()
        get_app().exit()




class CtuiApplication(Application):
    """Extends python_prompt application so ctui apps can append to it"""

    def register_ctui(self, ctui):
        """Expose various objects from ctui to get_app() for convenience"""
        self.ctui = ctui
        self.input_field = ctui.layout.input_field
        self.header_field = ctui.layout.header_field
        self.output_field = ctui.layout.output_field
        project_file = None
        self.db = ctui.db
        self.settings = ctui.settings
        self.storage = ctui.storage
        self.history = ctui.history
