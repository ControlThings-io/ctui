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
from .dialogs import message_dialog
from .functions import show_help
from prompt_toolkit.application.current import get_app
from tabulate import tabulate
from os.path import expanduser


class Commands(object):
    """Superclass class that contains built-in ctui commands"""

    def do_clear(self, input_text, output_text, event):
        """Clear the screen."""
        return ''


    def do_help(self, input_text, output_text, event):
        """Print application help."""
        show_help()
        return None


    def do_history(self, input_text, output_text, event):
        """Print current history."""
        dialog = tabulate(get_app().history.all(), headers='keys', tablefmt='plain')
        message_dialog('History', dialog)
        return None


    def do_exit(self, input_text, output_text, event):
        """Exit the application."""
        event.app.exit()
        output_text += 'Closing application.\n'
        return output_text
