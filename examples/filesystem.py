# Copyright (C) 2018  Justin Searle
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details at <http://www.gnu.org/licenses/>.

from ctui.application import Ctui
from ctui.types import *
import os

# Add your own commands by extending the Ctui class
myapp = Ctui()

myapp.name = 'ctui_filesystem'
myapp.version = '0.1'
myapp.description = 'Example filesystem application using ctui'
myapp.prompt = 'fs> '
myapp.help_text = 'Help menu for my ctui application'

# Each function representing a command must:
#     - start with a do_
#     - accept (self, args, output_text) as params
#         args:         is the text the user passed to your command
#         output_text:  is the current text in the window
#     - return a string to print, None, or False
# Returning a False does nothing, forcing users to correct mistakes


# Example of a command with no arguments
@myapp.command
def do_ls():
    """Help menu for ls."""     # <--- this will be used in help messages
    output_text = myapp.output_text           # Grab existing output text
    output_text += 'Directory contains:\n'
    # notice that we appended that text onto the existing output_text
    for item in os.listdir():
        output_text += ' ' + item + '\n'
    return output_text


# Example of a command with 1 argument
@myapp.command
def do_cd(dir:str):
    """Help menu for cd.

    :PARAM dir: Directory to change into
    """
    try:
        os.chdir(dir)
    except:
        # Returning False on bad input forces users to edit their input
        return False
    output_text = myapp.output_text           # Grab existing output text
    output_text = output_text + 'Directory changed to ' + dir + '\n'
    return output_text


myapp.run()
