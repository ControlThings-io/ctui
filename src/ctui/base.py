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

from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.layout.containers import Window, WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEventType


class Button:
    """
    Clickable button, copied from prompt_toolkit/widgets/base.py, fixed width bug.

    :param text: The caption for the button.
    :param handler: `None` or callable. Called when the button is clicked.
    :param width: Width of the button.
    """

    def __init__(self, text, handler=None, width=12):
        """Create a focusable button with a minimum display width."""
        assert isinstance(text, str)
        assert handler is None or callable(handler)
        assert isinstance(width, int)

        self.text = text
        self.handler = handler
        self.width = max(width, len(text) + 2)
        self.control = FormattedTextControl(
            self._get_text_fragments,
            key_bindings=self._get_key_bindings(),
            focusable=True,
        )

        def get_style():
            """Return the style class appropriate to the current focus state."""
            if get_app().layout.has_focus(self):
                return "class:button.focused"
            return "class:button"

        self.window = Window(
            self.control,
            align=WindowAlign.CENTER,
            height=1,
            width=self.width,
            style=get_style,
            dont_extend_width=True,
            dont_extend_height=True,
        )

    def _get_text_fragments(self):
        """Build styled text fragments and their mouse callback."""
        text = ("{:^%s}" % (self.width - 2)).format(self.text)

        def handler(mouse_event):
            """Invoke the button handler after a mouse-button release."""
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self.handler()

        return [
            ("class:button.arrow", "<", handler),
            ("[SetCursorPosition]", ""),
            ("class:button.text", text, handler),
            ("class:button.arrow", ">", handler),
        ]

    def _get_key_bindings(self):
        "Key bindings for the Button."
        kb = KeyBindings()

        @kb.add(" ")
        @kb.add("enter")
        def _(event):
            """Invoke the configured handler from the keyboard."""
            if self.handler is not None:
                self.handler()

        return kb

    def __pt_container__(self):
        """Expose the underlying window to prompt-toolkit."""
        return self.window
