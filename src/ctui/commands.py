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
from .dialogs import YesNoDialog, show_dialog, yes_no_dialog, message_dialog, input_dialog
from .functions import show_help
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.eventloop import ensure_future, From
from tabulate import tabulate
from tinydb import TinyDB, Query
from pathlib import Path


class Commands(object):
    """Superclass class that contains built-in ctui commands"""

    def do_clear(self, args, output_text):
        """Clear the screen."""
        return ''


    def do_help(self, args, output_text):
        """Print application help."""
        show_help()
        return None


    def do_history(self, args, output_text):
        """Print history of commands entered."""
        if len(args) > 0:
            assert (args.isdigit()), 'History only accepts a NUM of historys to grab'
            num = int(args)
            message = tabulate(self.history.all()[-num:], headers='keys', tablefmt='simple')
        else:
            message = tabulate(self.history.all(), headers='keys', tablefmt='simple')
        message_dialog(title='History', text=message)
        return None


    def do_history_clear(self, args, output_text):
        """Clear history of commands entered."""
        self.db.purge_table('history')
        self.history = self.db.table('history')
        return None


    def do_history_search(self, args, output_text):
        """Search history of commands entered using regex."""
        History = Query()
        search_results = self.history.search(History.Command.matches('.*' + args))
        message = tabulate(search_results, headers='keys', tablefmt='simple')
        message_dialog(title='History Search Results', text=message)
        return None


    def do_project(self, args, output_text):
        """Information about the current project"""
        message =  '  Project Name:  {}\n'.format(self.project_name)
        message += '  Project Path:  {}\n'.format(self.project_path)
        message += '     File Size:  {} KB\n'.format(Path(self.project_path).stat().st_size)
        message += ' History Count:  {} records\n'.format(len(self.history))
        message += 'Settings Count:  {} records\n'.format(len(self.settings))
        message += ' Storage Count:  {} records'.format(len(self.storage))
        message_dialog(title='Project Information', text=message)
        return None


    def do_project_delete(self, args, output_text):
        """Delete a saved project."""
        assert (args != self.project_name), 'Cannot delete current project'
        project_name = '{}.{}'.format(args, self.name)
        project_path = Path(self.project_folder + project_name).expanduser()
        assert (project_path.exists()), 'Project does not exist'

        yes_no_dialog(
            title = 'Confirmation',
            text = 'Delete {} project?'.format(args),
            yes_func = lambda: Path.unlink(Path(project_path)) )

        return None


    def do_project_export(self, args, output_text):
        """Export the current project to a file."""
        export_file = Path('{}.{}'.format(args, self.name)).expanduser()

        def yes_func():
            export_file.write_bytes(Path(self.project_path).read_bytes())

        if export_file.exists():
            yes_no_dialog(
                title = 'File Already Exists',
                text = 'Overwrite file?',
                yes_func = yes_func )
        else:
            yes_func()
            message_dialog(
                title = 'Success',
                text = 'Project exported as "{}"'.format(args))

        return None


    def do_project_import(self, args, output_text):
        """Import from an exported project file."""
        import_file = Path(args).expanduser()
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
        self._init_db()

        message_dialog(
            title = 'Success',
            text = 'Project imported as "{}"'.format(self.project_name))

        return None


    def do_project_list(self, args, output_text):
        """List saved projects"""
        lines = []
        for file in list(Path(self.project_folder).glob('*.{}'.format(self.name))):
            lines.append({'Project': file.stem, 'Size (KB)': file.stat().st_size})
        message = tabulate(lines, headers='keys', tablefmt='simple')
        message_dialog(title='Saved Projects', text=message, scrollbar=True)
        return None


    def do_project_load(self, args, output_text, envent):
        """Load saved project"""
        project_name = args
        project_path = '{}{}.{}'.format(self.project_folder, project_name, self.name)
        assert (Path(project_path).exists()), '{} is not a valid project'.format(project_name)

        self.db.close()
        self.project_name = project_name
        self.project_path = project_path
        self._init_db()

        message_dialog(
            title = 'Success',
            text = '{} project loaded.'.format(project_name))

        return None


    def do_project_reset(self, args, output_text):
        """Reset the current project file."""
        def project_reset():
            self.db.close()
            Path.unlink(Path(self.project_path))
            self._init_db()

        yes_no_dialog(
            title='Warning',
            text='Current project history and data will be deleted!',
            yes_text = 'Ok',
            yes_func = project_reset,
            no_text = 'Cancel' )

        return None


    def do_project_saveas(self, args, output_text):
        """Save current project as $name."""
        # TODO: confirm before overrite existing project
        project_name = args
        project_path = '{}{}.{}'.format(self.project_folder, project_name, self.name)

        def project_saveas():
            self.db.close()
            old_project = Path(self.project_path)
            self.project_name = args
            self.project_path = '{}{}.{}'.format(self.project_folder, self.project_name, self.name)
            Path(self.project_path).write_bytes(old_project.read_bytes())
            self._init_db()
            message_dialog(text = 'Project saved as "{}"'.format(self.project_name))

        if Path(project_path).exists():
            yes_no_dialog(
                title='Warning',
                text='{} project already exists!  Overwrite?'.format(project_name),
                yes_func = project_saveas )
        else:
            project_saveas()

        return None


    def do_exit(self, args, output_text):
        """Exit the application."""
        self.exit()
        # Return False to prevent history write since db is already closed
        return False
