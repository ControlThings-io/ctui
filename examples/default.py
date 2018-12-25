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

from ctui.commands import Ctui
# try:
#     import better_exceptions
# except ImportError as err:
#     pass

# Class MyApp(Application)
#     name = 'Example'
#     version = '0'
#     description = 'Please set description with get_app().descrition = ...'
#     prompt = '> '
#     statusbar = {}
#     statusbar_sep = '  -  '

myapp = Ctui()
myapp.name = 'My App'
myapp.version = '0'
myapp.description = 'This is my app'
myapp.prompt = 'MyApp> '
myapp.run()
