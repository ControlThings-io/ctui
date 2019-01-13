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
import os

# Add your own commands by extending the Ctui class
class MyFsTerm(Ctui):
    name = 'filesystem'
    version = '0.1'
    description = 'Example filesystem application using ctui'
    prompt = 'fs> '
    help_text = 'Help menu for my ctui application'

    # Each function representing a command must:
    #     - start with a do_
    #     - accept (self, args, output_text) as params
    #         args:         is the text the user passed to your command
    #         output_text:  is the current text in the window
    #     - return a string to print, None, or False
    # Returning a False does nothing, forcing users to correct mistakes


    # Example of a command with no arguments
    def do_ls(self, args, output_text):
        """Help menu for ls."""     # <--- this will be used in help messages
        output_text += 'Directory contains:\n'
        # notice that we appended that text onto the existing output_text
        for item in os.listdir():
            output_text += ' ' + item + '\n'
        return output_text


    # Example of a command with 1 argument
    def do_cd(self, args, output_text):
        """Help menu for cd."""
        try:
            os.chdir(args)
        except:
            # Returning False on bad input forces users to edit their input
            return False
        output_text = output_text + 'Directory changed to ' + args + '\n'
        return output_text


myapp = MyFsTerm()
myapp.run()
