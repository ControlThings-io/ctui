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
from .dialogs import message_dialog, input_dialog
from .functions import show_help
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import PathCompleter
from tabulate import tabulate
from tinydb import TinyDB, Query
from pathlib import Path
import datetime


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
        """Print history of commands entered."""
        if len(input_text) > 0:
            assert (input_text.isdigit()), 'History only accepts a NUM of historys to grab'
            num = int(input_text)
            message = tabulate(self.history.all()[-num:], headers='keys', tablefmt='plain')
        else:
            message = tabulate(self.history.all(), headers='keys', tablefmt='plain')
        message_dialog(title='History', text=message)
        return None


    def do_history_clear(self, input_text, output_text, event):
        """Clear history of commands entered."""
        self.db.purge_table('history')
        self.history = self.db.table('history')
        return None


    def do_history_search(self, input_text, output_text, event):
        """Search history of commands entered using regex."""
        History = Query()
        search_results = self.history.search(History.Command.matches('.*' + input_text))
        message = tabulate(search_results, headers='keys', tablefmt='plain')
        message_dialog(title='History Search Results', text=message)
        return None


    def do_project(self, input_text, output_text, event):
        """Information about the current project"""
        message = 'Project Name: {}\n'.format(self.project_name)
        message += 'Project Path: {}\n'.format(self.project_path)
        message += 'File Size: {} KB\n'.format(Path(self.project_path).stat().st_size)
        message += 'History Count: {} records\n'.format(len(self.history))
        message += 'Settings Count: {} records\n'.format(len(self.settings))
        message += 'Storage Count: {} records'.format(len(self.storage))
        message_dialog(title='Project Information', text=message)
        return None


    def do_project_export(self, input_text, output_text, event):
        """Export the current project to a file."""
        export_file = Path('{}.{}'.format(input_text, self.name)).expanduser()
        if export_file.exists():
            pass # TODO
            # if yes_no_dialog(title='File Exsists', test='Overwrite file?') = False:
            #     return False
        export_file.write_bytes(Path(self.project_path).read_bytes())
        message_dialog(title = 'Success',
                       text = 'Project exported as "{}"'.format(input_text))
        return None


    def do_project_import(self, input_text, output_text, event):
        """Import from an exported project file."""
        import_file = Path(input_text).expanduser()
        assert (import_file.exists()), 'File does not exist'
        with open(import_file) as f:
            assert (f.read(12) == '{"_default":'), 'Invald project file'

        self.db.close()
        if import_file.suffix == self.name:
            self.project_name = import_file.stem
        else:
            self.project_name = import_file.name
        self.project_path = '{}{}.{}'.format(self.project_folder, self.project_name, self.name)
        Path(self.project_path).write_bytes(import_file.read_bytes())
        self.init_db()
        message_dialog(title = 'Success',
                       text = 'Project imported as "{}"'.format(self.project_name))
        return None


    def do_project_reset(self, input_text, output_text, event):
        """Reset the current project file."""
        self.db.close()
        Path.unlink(Path(self.project_path))
        self.db.init()


    def do_project_saveas(self, input_text, output_text, event):
        """Save current project as $name."""
        self.db.close()
        old_project = Path(self.project_path)
        self.project_name = input_text
        self.project_path = '{}{}.{}'.format(self.project_folder, self.project_name, self.name)
        Path(self.project_path).write_bytes(old_project.read_bytes())
        self.init_db()
        message_dialog(text = 'Project saved as "{}"'.format(self.project_name))
        return None


    def do_exit(self, input_text, output_text, event):
        """Exit the application."""
        # TODO:
        # if self.project_name == 'default'
        #     if yes_no_dialog(title='Warning', text='Quit without saving?') == False:
        #         return False
        # Log exit in history before quitting app, which closes db
        date, time = str(datetime.datetime.today()).split()
        # Get original exit command entered
        command = self.layout.input_field.text
        try:
            event.app.history.insert({'Date': date, 'Time': time, 'Command': command})
        except:
            pass
        self.quit()
        # Return False to prevent history write after db closed
        return False
