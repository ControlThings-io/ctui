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
from __future__ import unicode_literals

from six import string_types
from ctui.commands import Commands
from prompt_toolkit.completion import Completer, Completion

__all__ = [
    'CommandCompleter',
    ]


class CommandCompleter(Completer):
    """
    Simple autocompletion on a list of ctui commands.

    :param commands: A ctui Commands object
    """
    def __init__(self, commands):
        assert isinstance(commands, Commands)
        self.commands = commands

    def get_completions(self, document, complete_event):
        parts_before_cursor = document.text_before_cursor.split()    # clean up spaces
        text_before_cursor = ' '.join(parts_before_cursor)
        current_index = len(parts_before_cursor) - 1
        current_part = parts_before_cursor[current_index]
        next_part = False
        if document.text_before_cursor[-1] == ' ':    # re-add trailing space if present
            next_part = True

        def previous_parts_match(command_parts):
            if current_index == 0:
                return True
            if len(command_parts) == len(parts_before_cursor):
                for i in range(current_index):
                    if command_parts[i] == parts_before_cursor[i]:
                        return True

        def last_part_full_match(command_parts):
            if next_part and len(command_parts) >= current_index + 2:
                if command_parts[current_index] == current_part:
                    return True

        def last_part_partial_match(command_parts):
            if len(command_parts) == current_index + 1:
                if command_parts[current_index] != (current_part):
                    return command_parts[current_index].startswith(current_part)

        # After command matches, suggest next argument, if any.
        def suggest_next_argument(command, command_len):
            arg_index = current_index - command_len
            if len(command.kwargs) ==
            yield Completion('', 0, display=command.kwargs[arg_index].name,
                             display_meta=command.kwargs[arg_index].desc)
            if len(command.kwargs) == 0:
                yield Completion('', 0, display='<enter>',
                                 display_meta=command.desc)
            # for arg_part in parts_before_cursor[command_len:]:
            #     if [validate_type] == False:
            #         break
            # else:
            #     yield Completion('', 0, display='<enter>',
            #                      display_meta=command.desc)

        # Check all commands for matches
        for command in self.commands:

            # If all command parts exactly match, suggest the user can hit enter
            if command.string_parts == parts_before_cursor[:command_len]:
                command_len = len(command.string_parts)
                suggest_next_argument(command, command_len)

            elif previous_parts_match(command.string_parts):

                # Suggest next parts (words) for commands that match so far
                if last_part_full_match(command.string_parts):
                    yield Completion(command.string_parts[current_index + 1],
                                     0, display_meta=command.desc)

                # Keep suggesting the parts (words) for commands that still match
                elif last_part_partial_match(command.string_parts):
                    yield Completion(command.string_parts[current_index],
                                     -len(current_part),
                                     display_meta=command.desc)
