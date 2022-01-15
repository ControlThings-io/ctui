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
from ctui.types import *
import shlex
from ctui.dialogs import YesNoDialog, show_dialog, yes_no_dialog, message_dialog, input_dialog
from ctui.functions import show_help
#from ctui.application import Ctui
from prompt_toolkit.formatted_text import HTML, to_formatted_text
from pygments.lexers.python import PythonLexer
from tabulate import tabulate
from tinydb import TinyDB, Query
from pathlib import Path
from typing import get_type_hints
from inspect import getfullargspec


class KwArgs(object):
    """Defines the elements of each command argument"""
    def __init__(self, kwarg, argtype, argdesc):
        self.name = kwarg
        self.type = argtype
        self.desc = argdesc

    def to_type(self, value:str):
        assert (type(value) == str)
        return to_type(value, self)

    def __repr__(self):
        return {'name': self.name, 'type': self.type, 'desc': self.desc}

    def __str__(self):
        return f'{self.name}: {self.desc}'


class Command(object):
    """Defines the elements of each command"""

    def __init__(self, func):
        """Called by @commands property, registreing passed function as a ctui command"""
        self.func_name = func.__name__          # used to track original function name
        if self.func_name.startswith('do_'):    # allow users to use do_ prefix to avoid keywords
            self.string = self.func_name[3:].replace('_', ' ')  # used to match multi-word commands
        else:
            self.string = self.func_name.replace('_', ' ')      # used to match multi-word commands
        self.string_parts = self.string.split()
        self.func = func                        # used to call the function
        doc_lines = func.__doc__.split('\n')
        if doc_lines[0] == '':
            self.desc = doc_lines[1].strip()    # used for completion description
        else:
            self.desc = doc_lines[0].strip()    # used for completion description
        self.kwargs = self.register_args(getfullargspec(func), doc_lines)
        # Determine if command supports infinite arguments (greedy final arg)
        if self.kwargs and is_greedy(self.kwargs[-1].type):
            self.greedy = True
        else:
            self.greedy = False

    @property
    def kwarg_descriptions(self):
        descriptions = {}
        for key, kwarg in self.kwargs.items():
            descriptions[key] = kwarg.desc
        return descriptions

    @property
    def help(self):
        output = f'Help for command "{self.string}"\n'
        output += f'  {self.desc}\n\nArguments\n'
        if self.kwargs:
            output += '\n'.join([f'  {kwarg}' for kwarg in self.kwargs])
        else:
            output += '  None'
        return output

    def register_args(self, argspec, doc_lines):
        kwargs = []                             # used to track args to function
        argdesc = ''
        self.req_args = len(argspec.args or []) - len(argspec.defaults or [])
        for kwarg in argspec.args:
            if kwarg in argspec.annotations:
                argtype = argspec.annotations[kwarg]
            else:
                argtype = None
            for line in doc_lines[1:]:
                kwarg_offset = line.find(kwarg)
                if kwarg_offset >= 0:
                    argdesc = line[kwarg_offset + len(kwarg) + 1:].strip()
                    break
            kwargs.append(KwArgs(kwarg, argtype, argdesc))
        return kwargs

    def parse_args(self, arg_string):
        args = shlex.split(arg_string)
        # assert False, f'{self.req_args}, {len(args)}, {len(self.kwargs)}'
        assert (self.req_args <= len(args) and len(self.kwargs) >= len(args)
                or self.req_args <= len(args) and self.greedy
                ), f'Wrong number of arguments\n\n{self.help}'
        kwargs = {}
        pairs = min(len(self.kwargs), len(args))
        for argnum in range(pairs):
            kwarg = self.kwargs[argnum]
            if argnum < pairs - 1:
                kwargs[kwarg.name] = kwarg.to_type(args[argnum])
            elif argnum == pairs - 1:
                if self.req_args > len(args):
                    greedy_str = ' '.join(args[argnum:])    # Minor bug, will loose mupti-spaces
                    kwargs[kwarg.name] = kwarg.to_type(greedy_str)
                else:
                    kwargs[kwarg.name] = kwarg.to_type(args[argnum])
        return kwargs

    def execute(self, **kwargs):
        return self.func(**kwargs)


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
        for key, command in self.commands.items():
            command_descriptions[key] = command.desc
        return command_descriptions

    @property
    def func_names(self):
        command_func_names = {}
        for key, command in self.commands.items():
            command_func_names[key] = command.func_name
        return command_func_names

    @property
    def functions(self):
        command_functions = {}
        for key, command in self.commands.items():
            command_functions[key] = command.func
        return command_functions

    def extract(self, input_text):
        """Extract command arguments from user text."""
        parts = input_text.split()
        # try the the longest combination of parts to the smallest combination
        for i in range(len(parts),0,-1):
            for command in self:
                # if command exists, parse and type-convert command arguments
                if command.string == ' '.join(parts[:i]):
                    if i == len(parts):
                        return command, {}
                    kwargs = command.parse_args(input_text.split(maxsplit=i)[i])
                    return command, kwargs
        return None, None

    def __getitem__(self, key):
        return self.commands[key]

    def __iter__(self):
        for command in self.commands.values():
            yield command

    def __str__(self):
        return str(self.descriptions)

    def __repr__(self):
        return str(self.commands)




def register_default_commands(ctui):

    @ctui.command
    def do_clear():
        """Clear the screen"""
        return ''


    @ctui.command
    def do_help():
        """Print application help"""
        show_help(ctui)


    @ctui.command
    def do_history(count:int=0):
        """
        Print history of commands entered

        :PARAM count: Optional number of last histories to print
        """
        message = tabulate(ctui.history.all()[-count:], headers='keys', tablefmt='simple')
        message_dialog(title='History', text=message)


    @ctui.command
    def do_history_clear():
        """Clear history of commands entered"""
        ctui.db.purge_table('history')
        ctui.history = ctui.db.table('history')


    @ctui.command
    def do_history_search(query:str):
        """
        Search history of commands ...

        :PARAM query: Regex string to search in history
        """
        History = Query()
        search_results = ctui.history.search(History.Command.matches('.*' + query))
        message = tabulate(search_results, headers='keys', tablefmt='simple')
        message_dialog(title='History Search Results', text=message)


    @ctui.command
    def do_macro_set(name:str, command:GreedyStr):
        """
        Create a new macro

        :PARAM name: Name of new macro
        :PARAM command: Cammand to run and its arguments
        """
        ctui.settings.insert({name: date})



    @ctui.command
    def do_project():
        """Information about the current project"""
        message =  f'  Project Name:  {ctui.project_name}\n'
        message += f'  Project Path:  {ctui._project_path}\n'
        message += f'     File Size:  {Path(ctui._project_path).stat().st_size} KB\n'
        message += f' History Count:  {len(ctui.history)} records\n'
        message += f'Settings Count:  {len(ctui.settings)} records\n'
        message += f' Storage Count:  {len(ctui.storage)} records'
        message_dialog(title='Project Information', text=message)


    @ctui.command
    def do_project_delete(name:str):
        """
        Delete saved project ...

        :PARAM name: Name of project to deleted
        """
        assert (name != ctui.project_name), 'Cannot delete current project'
        project_to_delete = f'{name}.{ctui.name}'
        project_to_delete_path = Path(ctui._project_folder + project_to_delete).expanduser()
        assert (project_to_delete_path.is_file()), 'Project does not exist'

        yes_no_dialog(
            title = 'Confirmation',
            text = f'Delete {name} project?',
            yes_func = lambda: Path.unlink(Path(project_to_delete_path)) )


    @ctui.command
    def do_project_export(filename:str):
        """
        Export the current project to ...

        :PARAM filename: Filename of file to export current project
        """
        export_file = Path(f'{filename}.{ctui.name}').expanduser()

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
                text = f'Project exported as:\n"{export_file}"')


    @ctui.command
    def do_project_import(filename:str):
        """
        Import exported project from ...

        :PARAM filename: Exported filename to import
        """
        project_to_import_path = Path(filename).expanduser()
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
                text = f'Project imported as "{ctui.project_name}"')


    @ctui.command
    def do_project_list():
        """List saved projects"""
        lines = []
        for file in list(Path(ctui._project_folder).glob(f'*.{ctui.name}')):
            lines.append({'Project': file.stem, 'Size (KB)': file.stat().st_size})
        message = tabulate(lines, headers='keys', tablefmt='simple')
        message_dialog(title='Saved Projects', text=message, scrollbar=True)


    @ctui.command
    def do_project_load(name:str):
        """
        Load saved project ...

        :PARAM name: Name of project to load
        """
        project_to_load_path = f'{ctui._project_folder}{name}.{ctui.name}'
        assert (Path(project_to_load_path).is_file()), f'"{name}" is not a valid project'

        ctui.db.close()
        ctui.project_name = name
        ctui._init_db()

        message_dialog(
            title = 'Success',
            text = f'{name} project loaded.')


    @ctui.command
    def do_project_reset():
        """Reset the current project file"""
        def project_reset():
            ctui.db.close()
            Path.unlink(Path(ctui._project_path))
            ctui._init_db()

        yes_no_dialog(
            title='Warning',
            text='Current project history and data will be deleted!',
            yes_text = 'Ok',
            yes_func = project_reset,
            no_text = 'Cancel' )


    @ctui.command
    def do_project_saveas(name:str):
        """
        Save current project as ...

        :PARAM name: New name of project you are saving
        """
        project_to_save_path = f'{ctui._project_folder}{name}.{ctui.name}'

        def project_saveas():
            ctui.db.close()
            old_project = Path(ctui._project_path)
            ctui.project_name = name
            Path(ctui._project_path).write_bytes(old_project.read_bytes())
            ctui._init_db()

        if Path(project_to_save_path).is_file():
            yes_no_dialog(
                title = 'Warning',
                text = f'Project "{name}" already exists!  Overwrite?',
                yes_func = project_saveas )
        else:
            project_saveas()
            message_dialog(text = f'Project saved as "{name}".')


    @ctui.command
    def do_exit():
        """Exit the application"""
        ctui.exit()
        # Return False to prevent history write since db is already closed
        return False


    # @ctui.command
    # def do_python(py_cmd:GreedyStr):
    #     """
    #     Run python command
    #
    #     :PARAM py_cmd: Python command to run
    #     """
    #     def _dict(_object):
    #         template = '<style fg="ansibrightcyan">{}</style> = {}'
    #         return tabulate(_object.__dict__.items(), tablefmt='simple')
    #         # output_list = ['{} = {}'.format(k,v) for k,v in _object.__dict__.items()]
    #         # return '\n'.join(output_list)
    #         # output_list = [template.format(k,v) for k,v in _object.__dict__.items()]
    #         # return to_formatted_text(HTML('\n'.join(output_list)))
    #     message = str(eval(py_cmd))
    #     message_dialog(
    #         title = 'Python Response',
    #         text = message,
    #         lexer = PythonLexer(),
    #         scrollbar = True )
    #     return None
    #
    #
    # @ctui.command
    # def do_system(sys_cmd:GreedyStr):
    #     """
    #     Run system command
    #
    #     :PARAM sys_cmd: System command to run
    #     """
    #     ctui.app.run_system_command(sys_cmd)
    #     return None
