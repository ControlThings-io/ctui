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

from tabulate import tabulate

from .dialogs import message_dialog


def _scroll_output(event, output_field, amount):
    """Move the output viewport by *amount* lines without changing focus."""
    window = output_field.window
    render_info = window.render_info
    if render_info is None:
        return
    maximum = max(0, render_info.ui_content.line_count - render_info.window_height)
    current = render_info.first_visible_line()
    target = min(maximum, max(0, current + amount))
    window.vertical_scroll = target

    # prompt-toolkit always recalculates scrolling to keep a buffer's cursor
    # visible. Keep the invisible output cursor inside the requested viewport,
    # otherwise the next render immediately jumps back to the bottom.
    cursor_row = target
    if amount > 0:
        cursor_row = min(
            render_info.ui_content.line_count - 1,
            target + render_info.window_height - 1,
        )
    output_field.buffer.cursor_position = (
        output_field.buffer.document.translate_row_col_to_index(cursor_row, 0)
    )
    event.app.invalidate()


def scroll_line_down(event, output_field):
    """Scroll the supplied output field down one line."""
    _scroll_output(event, output_field, 1)


def scroll_line_up(event, output_field):
    """Scroll the supplied output field up one line."""
    _scroll_output(event, output_field, -1)


def scroll_page_down(event, output_field):
    """Scroll the supplied output field down one page."""
    render_info = output_field.window.render_info
    if render_info is not None:
        _scroll_output(event, output_field, render_info.window_height)


def scroll_page_up(event, output_field):
    """Scroll the supplied output field up one page."""
    render_info = output_field.window.render_info
    if render_info is not None:
        _scroll_output(event, output_field, -render_info.window_height)


def scroll_home(event, output_field):
    """Scroll the supplied output field to its beginning."""
    render_info = output_field.window.render_info
    if render_info is not None:
        _scroll_output(event, output_field, -render_info.ui_content.line_count)


def scroll_end(event, output_field):
    """Scroll the supplied output field to its end."""
    render_info = output_field.window.render_info
    if render_info is not None:
        _scroll_output(event, output_field, render_info.ui_content.line_count)


def show_help(ctui):
    """Display a dialog listing top-level commands for *ctui*."""
    dialog = "{}\n\n{}\n\nAvaiable commands are:\n\n".format(
        ctui.welcome, ctui.help_message
    )
    table = []
    for command in ctui.commands:
        if len(command.string.split()) == 1:
            table.append((command.string, command.desc))
    dialog += tabulate(sorted(table), tablefmt="plain")
    message_dialog("Help", dialog)
