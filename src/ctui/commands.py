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

import shlex
import re
import time
from prompt_toolkit.application.current import get_app
from prompt_toolkit.document import Document
from .application import start_app
from tabulate import tabulate
from os.path import expanduser


class Ctui(object):
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

    def __init__(self):
        if self.welcome == '':
            self.welcome = 'Welcome to ' + self.name + ' ' + self.version + '\n' + self.description + '\n'
        if self.help_message == '':
            self.help_message = self.welcome + '\n' + 'Available commands are:' + '\n\n'


    def run(self):
        start_app(self)


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
        commands = [a[3:] for a in dir(self.__class__) if a.startswith('do_')]
        return commands


    def meta_dict(self):
        meta_dict = {}
        for command in self.commands():
            # TODO: find a better way to do this than eval
            meta_dict[command] = eval('self.do_' + command + '.__doc__')
        return meta_dict


    def do_clear(self, input_text, output_text, event):
        """Clear the screen."""
        return ''


    def do_help(self, input_text, output_text, event):
        """Print application help."""
        output_text += '==================== Help ====================\n'
        output_text += self.help_message
        table = []
        for key, value in self.meta_dict().items():
            table.append([key, value])
        output_text += tabulate(table, tablefmt='plain') + '\n'
        output_text += '==============================================\n'
        return output_text


    def do_history(self, input_text, output_text, event):
        """Print current history."""
        # output_text += str(get_app().history.all()) + '\n'
        output_text += tabulate(get_app().history.all(), headers='keys', tablefmt='plain')
        return output_text


    def do_exit(self, input_text, output_text, event):
        """Exit the application."""
        event.app.exit()
        output_text += 'Closing application.\n'
        return output_text
