from __future__ import unicode_literals

from six import string_types
from ctui.commands import Commands
from prompt_toolkit.completion import Completer, Completion

__all__ = [
    'WordCompleter',
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
        current_part = len(parts_before_cursor) - 1
        next_part = False
        if document.text_before_cursor[-1] == ' ':    # re-add trailing space if present
            next_part = True

        def previous_parts_match(command_parts):
            if current_part == 0:
                return True
            if len(command_parts) == len(parts_before_cursor):
                for i in range(current_part):
                    if command_parts[i] == parts_before_cursor[i]:
                        return True

        def last_part_full_match(command_parts):
            if next_part and len(command_parts) >= current_part + 2:
                if command_parts[current_part] == parts_before_cursor[current_part]:
                    return True

        def last_part_partial_match(command_parts):
            if len(command_parts) == current_part + 1:
                if command_parts[current_part] != (parts_before_cursor[current_part]):
                    return command_parts[current_part].startswith(parts_before_cursor[current_part])

        for command in self.commands:
            if command.parts == parts_before_cursor:
                yield Completion('', 0, display='<enter>', display_meta=command.desc)
            elif previous_parts_match(command.parts):
                if last_part_full_match(command.parts):
                    yield Completion(command.parts[current_part+1], 0, display_meta=command.desc)
                elif last_part_partial_match(command.parts):
                    yield Completion(command.parts[current_part], 0, display_meta=command.desc)
