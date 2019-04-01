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
from .dialogs import message_dialog
from .functions import scroll_end, scroll_home, scroll_page_down, scroll_page_up
from .functions import scroll_line_down, scroll_line_up
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import HTML, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.search import start_search, SearchDirection
from datetime import datetime
import traceback


def get_key_bindings(ctui):
    """Return keybinding object for application shortcut keys"""
    input_field = ctui.layout.input_field
    output_field = ctui.layout.output_field
    kb = KeyBindings()


    #######################
    # Global key bindings #
    #######################

    @kb.add('c-q')      # None-graceful shutdown, ctui.exit() is graceful
    def _(event):
        " Pressing Ctrl-Q will force quit the user interface. "
        # ctui.do_exit(input_field.text, output_field.text, event)
        ctui.app.exit()


    @kb.add('c-d')
    def _(event):
        """Press Ctrl-D to start the python debugger"""
        import pdb
        pdb.set_trace()


    #################################
    # Input Field ONLY key bindings #
    #################################

    @kb.add('enter', filter=has_focus(input_field))
    def _(event):
        if len(input_field.text) == 0:
            return
        # Process commands on prompt after hitting enter key
        # do_function, args = ctui._extract_do_function(input_field.text)
        #
        # if do_function:
        #     try:
        #         output_text = ctui._execute(do_function, args, output_field.text)
        #     except AssertionError as error:
        #         message_dialog(title='Error', text=str(error))
        #     except:
        #         message_dialog(title='Error', text=traceback.format_exc(),
        #                        scrollbar=True)


        try:
            command, kwargs = ctui.commands.extract(input_field.text)
            if command:
                ctui.output_text = output_field.text
                output_text = command.execute(**kwargs)
        except AssertionError as error:
            message_dialog(title='Error', text=str(error))
        except:
            message_dialog(title='Error', text=traceback.format_exc(),
                           scrollbar=True)

        # For invalid commands forcing users to correct them
        if 'output_text' not in locals() or output_text == False:
            return

        date, time = str(datetime.today()).split()
        ctui.history.insert({'Date': date, 'Time': time.split('.')[0], 'Command': input_field.text})
        input_field.buffer.reset(append_to_history=True)

        # For commands that do not have output_text
        if output_text == None:
            input_field.text = ''
            return
        else:
            output_field.buffer.document = Document(
                text=output_text, cursor_position=len(output_text))
            input_field.text = ''

    @kb.add('c-c', filter=has_focus(input_field))
    def _(event):
        """Pressing Control-C will copy highlighted text to clipboard"""
        data = input_field.buffer.copy_selection()
        ctui.app.clipboard.set_data(data)

    @kb.add('c-p', filter=has_focus(input_field))
    def _(event):
        """Pressing Control-P will paste text from clipboard"""
        input_field.buffer.paste_clipboard_data(ctui.app.clipboard.get_data())


    #############################################
    # Key bindings that affect the output_field #
    #############################################

    @kb.add('pagedown', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one page"""
        scroll_page_down(event)

    @kb.add('pageup', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field up one page"""
        scroll_page_up(event)

    @kb.add('c-j', filter=has_focus(input_field))
    @kb.add('c-down', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_line_down(event)

    @kb.add('c-k', filter=has_focus(input_field))
    @kb.add('c-up', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_line_up(event)

    @kb.add('end', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_end(event)

    @kb.add('home', filter=has_focus(input_field))
    def _(event):
        """Scroll output_field down one line"""
        scroll_home(event)





    # kb.add('pagedown', filter=has_focus(output_field))(scroll_page_down)
    # kb.add('space', filter=has_focus(output_field))(scroll_page_down)
    # kb.add('f', filter=has_focus(output_field))(scroll_page_down)
    # kb.add('pageup')(scroll_page_up)
    # kb.add('b')(scroll_page_up)
    #
    # @kb.add('q', filter=has_focus(output_field))
    # def _(event):
    #     """Quit navigation back to input_field"""
    #     ctui.app.layout.focus_previous()
    #
    # @kb.add('/', filter=has_focus(output_field))
    # def _(event):
    #     """Search and highlight strigs in output_field"""
    #     start_search(output_field.control)
    #
    # @kb.add('g', filter=has_focus(output_field))
    # def _(event):
    #     """Goto beginning of output_field"""
    #     output_field.buffer.document = Document(
    #         text=output_field.text, cursor_position=0)
    #
    # @kb.add('G', filter=has_focus(output_field))
    # def _(event):
    #     """Goto end of output_field"""
    #     output_field.buffer.document = Document(
    #         text=output_field.text, cursor_position=len(output_field.text))
    #
    # @kb.add('n', filter=has_focus(output_field))
    # def _(event):
    #     """Goto next item in output_field search"""
    #     search_state = ctui.app.current_search_state
    #     cursor_position = output_field.buffer.get_search_position(
    #         search_state, include_current_position=False)
    #     output_field.buffer.cursor_position = cursor_position
    #
    # @kb.add('N', filter=has_focus(output_field))
    # def _(event):
    #     """Goto previous item in output_field search"""
    #     search_state = ctui.app.current_search_state
    #     cursor_position = output_field.buffer.get_search_position(
    #         ~search_state, include_current_position=True)
    #     output_field.buffer.cursor_position = cursor_position
    #
    # @kb.add('c-c', filter=has_focus(output_field))
    # def _(event):
    #     """Pressing Control-C will copy highlighted text to clipboard"""
    #     data = output_field.buffer.copy_selection()
    #     ctui.app.clipboard.set_data(data)
    #
    # @kb.add('<any>', filter=has_focus(output_field))
    # @kb.add('enter', filter=has_focus(output_field))
    # @kb.add('c-c', filter=has_focus(output_field))
    # def _(event):
    #     """Prevent user from editing output_field"""
    #     pass

    return kb
