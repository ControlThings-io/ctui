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
from datetime import datetime
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.layout import Layout
from tinydb import TinyDB

from ctui.commands import Commands, register_default_commands
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout
from ctui.style import CtuiStyle

from .dialogs import yes_no_dialog


class Ctui(object):
    """
    Class with commands that users may use at the application prompt.

    Each function representing a command must:
        - start with a do_
        - accept self, input_text, output_text, and event as params
        - return a string to print, None, or False
    Returning a False does nothing, forcing users to correct mistakes
    """

    # User setable variables
    name = "MyApp"
    version = "0.1.0"  # must be string
    description = "My App does something..."
    prompt = "> "
    help_message = "Commands go on top, results appear on the bottom."
    wrap_lines = False  # Wrap lines in main output window or not

    # sets various defaults if not overriden with subclass
    def __init__(self, layout=None):
        self.status_dict = {}
        self.commands = Commands()
        register_default_commands(ctui=self)
        self.project_name = "default"

    @property
    def welcome(self):
        return f"Welcome to {self.name}{self.version}\n\n{self.description}"

    @property
    def project_folder(self):
        return f"{Path.home()}/.{self.name}/projects/"

    @property
    def _project_path(self):
        return f"{self.project_folder}{self.project_name}.{self.name}"

    # TODO: Fix broken status bar
    @property
    def _statusbar(self):
        self.status_dict["Project"] = self.project_name
        return "  ".join([f"{k}: {v}" for k, v in self.status_dict.items()])

    def _init_db(self):
        """setup database storage"""
        self.db = TinyDB(self._project_path)
        self.settings = self.db.table("settings")
        self.storage = self.db.table("storage")
        self.history = self.db.table("history")

    def command(self, func):
        return self.commands.register(func)

    def run(self):
        """Start the python_prompt application with ctui's default settings"""
        Path(self.project_folder).mkdir(parents=True, exist_ok=True)
        if Path(
            self._project_path
        ).exists():  # start with clean default project at each start
            Path.unlink(Path(self._project_path))
        self._init_db()
        self.layout = CtuiLayout(self)
        self.style = CtuiStyle()
        self._mode = "term_ui"  # For future headless mode
        layout = Layout(
            self.layout.root_container, focused_element=self.layout.input_field
        )
        self.app = Application(
            layout=layout,
            key_bindings=get_key_bindings(self),
            style=self.style.dark_theme,
            enable_page_navigation_bindings=False,
            mouse_support=True,
            full_screen=True,
        )
        self.app.run()

    def _log_and_exit(self):
        date, time = str(datetime.today()).split()
        self.history.insert(
            {"Date": date, "Time": time.split(".")[0], "Command": "exit"}
        )
        self.db.close()
        get_app().exit()

    def exit(self):
        """Graceful shutdown of the prompt_toolkit application"""
        if self._mode == "term_ui" and self.project_name == "default":
            yes_no_dialog(
                title="Warning",
                text="Exit without saving project?",
                yes_func=self._log_and_exit,
            )
        else:
            self._log_and_exit()
