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

    def __init__(self):
        self.output_field = 'bg:#000000 #ffffff'
        self.input_field = 'bg:#000000 #ffffff'
        self.line = '#004400'
        self.statusbar = 'bg:#AAAAAA'

    def get(self):
        # Colors of various style labels
        elements = [(k,v) for k,v in self.__dict__.items()]
        style = Style(elements)
        return style
