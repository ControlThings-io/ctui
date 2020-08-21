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
import time
from prompt_toolkit.filters import has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.search import start_search, SearchDirection
from prompt_toolkit.shortcuts.dialogs import message_dialog
from prompt_toolkit.document import Document
from tabulate import tabulate
import datetime

def scroll_line_down(event):
    """Scroll output_field down one line, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        line_index =  w.render_info.last_visible_line() + 1
        b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
        b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
        w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def scroll_line_up(event):
    """Scroll output_field up one line, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        if w.render_info.first_visible_line() != 0:
            line_index = w.render_info.last_visible_line() - 1
            b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
            b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
            w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def scroll_page_down(event):
    """Scroll output_field down one page, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        line_index =  w.render_info.last_visible_line() + w.render_info.window_height
        b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
        b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
        w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def scroll_page_up(event):
    """Scroll output_field up one page, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        if w.render_info.first_visible_line() != 0:
            line_index = max(w.render_info.first_visible_line() - 1, w.render_info.window_height - 1)
            b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
            b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
            w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def scroll_end(event):
    """Scroll output_field to first page, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        line_index = w.render_info.ui_content.line_count - 1
        b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
        b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
        w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def scroll_home(event):
    """Scroll output_field to last page, leaving cursor at bottom"""
    event.app.layout.focus(event.app.output_field)
    w = event.app.layout.current_window
    b = event.app.current_buffer
    if w and w.render_info:
        line_index = 0
        b.cursor_position = b.document.translate_row_col_to_index(line_index, 0)
        b.cursor_position += b.document.get_start_of_line_position(after_whitespace=True)
        w.vertical_scroll = 0
    event.app.layout.focus(event.app.input_field)

def show_help(ctui):
    dialog = ctui._help_message
    table = []
    for command in ctui.commands:
        if len(command.string.split()) == 1:
            table.append((command.string, command.desc))
    dialog += tabulate(sorted(table), tablefmt='plain')
    message_dialog('Help', dialog)
