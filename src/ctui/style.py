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
from prompt_toolkit.styles import Style

class CtuiStyle(object):
    """Class to expose individual style values to ctui"""
    dark_theme = Style.from_dict({
        # Main windows.
        'input_field':                              'bg:#101010 #e0e0e0',
        'input_field last-line':                    'nounderline',
        'line':                                     'bg:#202020 ansibrightcyan',
        'output_field':                             'bg:#202020 ansicyan',
        'output_field scrollbar.background':         '',
        'output_field scrollbar.button':             'bg:#000000',
        'output_field scrollbar.arrow':              '',
        'output_field scrollbar.start':              'nounderline',
        'output_field scrollbar.end':                'nounderline',
        'line last-line':                           'nounderline',
        'statusbar':                                'bg:#AAAAAA',

        # Dialog windows.
        'dialog':                                   'bg:#4444ff',
        'dialog frame.label':                       '#ansibrightyellow bold',
        'dialog.body':                              'bg:#111111 ansiyellow',
        'dialog.body text-area':                    'bg:#111111 ansiyellow',
        'dialog.body text-area last-line':          'nounderline',
        'dialog.body scrollbar.background':         '',
        'dialog.body scrollbar.button':             'bg:#000000',
        'dialog.body scrollbar.arrow':              '',
        'dialog.body scrollbar.start':              'nounderline',
        'dialog.body scrollbar.end':                'nounderline',
        'button':                                   '',
        'button.arrow':                             'bold',
        'button.focused':                           'bg:ansibrightyellow #101010',

        # Menu bars.
        'menu-bar':                                 'bg:#aaaaaa #000000',
        'menu-bar.selected-item':                   'bg:#ffffff #000000',
        'menu':                                     'bg:#888888 #ffffff',
        'menu.border':                              '#aaaaaa',
        'menu.border shadow':                       '#444444',

        # Shadows.
        'dialog shadow':                            'bg:#000088',
        'dialog.body shadow':                       'bg:#aaaaaa',

        # Progress-bars.
        'progress-bar':                             'bg:#000088',
        'progress-bar.used':                        'bg:#ff0000',
        })
