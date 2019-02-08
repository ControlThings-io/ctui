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
from ctui.dialogs import YesNoDialog, show_dialog, yes_no_dialog, message_dialog, input_dialog
from ctui.functions import show_help
from prompt_toolkit.eventloop import ensure_future, From
from prompt_toolkit.formatted_text import HTML, to_formatted_text
from pygments.lexers.python import PythonLexer
from tabulate import tabulate
from tinydb import TinyDB, Query
from pathlib import Path


class Command(object):
    """Contains command object elements"""

    def __init__(self, func):
        self.func_name = func.__name__
        if self.func_name.startswith('do_'):    # allow users to use do_ prefix to avoid keywords
            self.string = self.func_name[3:].replace('_', ' ')
        else:
            self.string = self.func_name.replace('_', ' ')    # allow users to use grouped commnands
        self.func = func
        self.desc = func.__doc__
        self.parts = self.string.split()

    def execute(self, ctui, args, output_text):
        return self.func(ctui, args, output_text)

    def __str__(self):
        return f'{self.string}: {self.desc}'



class Commands(object):
    """Registers and assembles all the commands"""

    def __init__(self):
        self.commands = {}

    def register(self, func):
        command = Command(func)
        self.commands[command.string] = command

    @property
    def strings(self):
        command_strings = []
        for command_string in sorted(self.commands.keys()):
            command_strings.append(command_string)
        return command_strings

    @property
    def descriptions(self):
        command_descriptions = {}
        for k,v in self.commands.items():
            command_descriptions[k] = v.desc
        return command_descriptions

    @property
    def func_names(self):
        command_func_names = {}
        for k,v in self.commands.items():
            command_func_names[k] = v.func_name
        return command_func_names

    @property
    def functions(self):
        command_functions = {}
        for k,v in self.commands.items():
            command_functions[k] = v.func
        return command_functions

    def __getitem__(self, key):
        return self.commands[key]

    def __iter__(self):
        for command in self.commands.values():
            yield command

    def __str__(self):
        return str(self.descriptions)

    def __repr__(self):
        return str(self.commands)




def register_defaults(ctui):

    @ctui.command
    def do_clear(ctui, args, output_text):
        """Clear the screen"""
        return ''


    @ctui.command
    def do_help(ctui, args, output_text):
        """Print application help"""
        show_help(ctui)


    @ctui.command
    def do_history(ctui, args, output_text):
        """Print history of commands entered"""
        if len(args) > 0:
            assert (args.isdigit()), 'History only accepts a NUM of historys to grab'
            num = int(args)
            message = tabulate(ctui.history.all()[-num:], headers='keys', tablefmt='simple')
        else:
            message = tabulate(ctui.history.all(), headers='keys', tablefmt='simple')
        message_dialog(title='History', text=message)


    @ctui.command
    def do_history_clear(ctui, args, output_text):
        """Clear history of commands entered"""
        ctui.db.purge_table('history')
        ctui.history = ctui.db.table('history')


    @ctui.command
    def do_history_search(ctui, args, output_text):
        """Search history of commands entered using regex"""
        History = Query()
        search_results = ctui.history.search(History.Command.matches('.*' + args))
        message = tabulate(search_results, headers='keys', tablefmt='simple')
        message_dialog(title='History Search Results', text=message)


    @ctui.command
    def do_project(ctui, args, output_text):
        """Information about the current project"""
        if args != '':
            return False
        message =  '  Project Name:  {}\n'.format(ctui.project_name)
        message += '  Project Path:  {}\n'.format(ctui._project_path)
        message += '     File Size:  {} KB\n'.format(Path(ctui._project_path).stat().st_size)
        message += ' History Count:  {} records\n'.format(len(ctui.history))
        message += 'Settings Count:  {} records\n'.format(len(ctui.settings))
        message += ' Storage Count:  {} records'.format(len(ctui.storage))
        message_dialog(title='Project Information', text=message)


    @ctui.command
    def do_project_delete(ctui, args, output_text):
        """Delete a saved project"""
        assert (args != ctui.project_name), 'Cannot delete current project'
        project_to_delete = '{}.{}'.format(args, ctui.name)
        project_to_delete_path = Path(ctui._project_folder + project_to_delete).expanduser()
        assert (project_to_delete_path.is_file()), 'Project does not exist'

        yes_no_dialog(
            title = 'Confirmation',
            text = 'Delete {} project?'.format(args),
            yes_func = lambda: Path.unlink(Path(project_to_delete_path)) )


    @ctui.command
    def do_project_export(ctui, args, output_text):
        """Export the current project to a file"""
        export_file = Path('{}.{}'.format(args, ctui.name)).expanduser()

        def project_export():
            export_file.write_bytes(Path(ctui._project_path).read_bytes())

        if export_file.is_file():
            yes_no_dialog(
                title = 'File Already Exists',
                text = 'Overwrite file?',
                yes_func = project_export )
        else:
            project_export()
            message_dialog(
                title = 'Success',
                text = 'Project exported as:\n"{}"'.format(export_file) )


    @ctui.command
    def do_project_import(ctui, args, output_text):
        """Import from an exported project file"""
        project_to_import_path = Path(args).expanduser()
        if project_to_import_path.is_file() == False:
            project_to_import_path = Path(str(project_to_import_path) + f'.{ctui.name}')
        assert (project_to_import_path.is_file()), 'File does not exist'
        with open(project_to_import_path) as f:
            assert (f.read(14) == '{"_default": {'), 'Invald or corrupted project file'

        # build new project name and path
        if project_to_import_path.suffix[1:] == ctui.name:
            ctui.project_name = project_to_import_path.stem
        else:
            ctui.project_name = project_to_import_path.name

        def project_import():
            ctui.db.close()
            Path(ctui._project_path).write_bytes(project_to_import_path.read_bytes())
            ctui._init_db()

        if Path(ctui._project_path).is_file():
            yes_no_dialog(
                title = 'WARNING',
                text = 'Project already exists.\nOverwrite project?',
                yes_func = project_import )
            # TODO: use input_dialog to request new project name
        else:
            project_import()
            message_dialog(
                title = 'Success',
                text = 'Project imported as "{}"'.format(ctui.project_name) )


    @ctui.command
    def do_project_list(ctui, args, output_text):
        """List saved projects"""
        lines = []
        for file in list(Path(ctui._project_folder).glob('*.{}'.format(ctui.name))):
            lines.append({'Project': file.stem, 'Size (KB)': file.stat().st_size})
        message = tabulate(lines, headers='keys', tablefmt='simple')
        message_dialog(title='Saved Projects', text=message, scrollbar=True)


    @ctui.command
    def do_project_load(ctui, args, output_text):
        """Load saved project"""
        project_to_load = args
        project_to_load_path = '{}{}.{}'.format(ctui._project_folder, project_to_load, ctui.name)
        assert (Path(project_to_load_path).is_file()), '{} is not a valid project'.format(project_to_load)

        ctui.db.close()
        ctui.project_name = project_to_load
        # ctui.project_path = project_path
        ctui._init_db()

        message_dialog(
            title = 'Success',
            text = '{} project loaded.'.format(project_to_load))


    @ctui.command
    def do_project_reset(ctui, args, output_text):
        """Reset the current project file"""
        def project_reset():
            ctui.db.close()
            Path.unlink(Path(ctui.project_path))
            ctui._init_db()

        yes_no_dialog(
            title='Warning',
            text='Current project history and data will be deleted!',
            yes_text = 'Ok',
            yes_func = project_reset,
            no_text = 'Cancel' )


    @ctui.command
    def do_project_saveas(ctui, args, output_text):
        """Save current project as $name"""
        project_to_save = args
        project_to_save_path = '{}{}.{}'.format(ctui._project_folder, project_to_save, ctui.name)

        def project_saveas():
            ctui.db.close()
            old_project = Path(ctui._project_path)
            ctui.project_name = args
            Path(ctui._project_path).write_bytes(old_project.read_bytes())
            ctui._init_db()

        if Path(project_to_save_path).is_file():
            yes_no_dialog(
                title='Warning',
                text='{} project already exists!  Overwrite?'.format(project_to_save),
                yes_func = project_saveas )
        else:
            project_saveas()
            message_dialog(text = 'Project saved as "{}"'.format(ctui.project_name))


    @ctui.command
    def do_exit(ctui, args, output_text):
        """Exit the application"""
        ctui.exit()
        # Return False to prevent history write since db is already closed
        return False


    @ctui.command
    def do_python(ctui, args, output_text):
        """Run python command"""
        if args == '':
            return False
        def _dict(_object):
            template = '<style fg="ansibrightcyan">{}</style> = {}'
            return tabulate(_object.__dict__.items(), tablefmt='simple')
            # output_list = ['{} = {}'.format(k,v) for k,v in _object.__dict__.items()]
            # return '\n'.join(output_list)
            # output_list = [template.format(k,v) for k,v in _object.__dict__.items()]
            # return to_formatted_text(HTML('\n'.join(output_list)))
        message = str(eval(args))
        message_dialog(
            title = 'Python Response',
            text = message,
            lexer = PythonLexer(),
            scrollbar = True )


    @ctui.command
    def do_system(ctui, args, output_text):
        """Run system command"""
        if args == '':
            return False
        ctui.app.run_system_command(args)
