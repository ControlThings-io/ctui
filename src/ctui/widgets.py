"""Supported prompt-toolkit building blocks for CtuiApp.compose().

Vertical aliases HSplit (children stacked top to bottom); Horizontal aliases
VSplit (children placed side by side). Label, TextArea, and Window are upstream
classes. Button, Frame, and ProgressBar
are compatible subclasses retaining widget identity for browser rendering.
Reuse the application's command input in custom layouts so automatic focus and
bindings work. These exported aliases form part of ctui's supported 1.x surface;
internal layout and dialog modules do not gain that compatibility promise.
"""

from prompt_toolkit.layout.containers import HSplit as Vertical
from prompt_toolkit.layout.containers import VSplit as Horizontal
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.widgets import Button as _Button
from prompt_toolkit.widgets import Frame as _Frame
from prompt_toolkit.widgets import Label
from prompt_toolkit.widgets import ProgressBar as _ProgressBar
from prompt_toolkit.widgets import TextArea


class Frame(_Frame):
    """Upstream frame retaining its identity for the browser layout adapter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.container._ctui_widget = self


class Button(_Button):
    """Upstream button with the same callback in terminal and browser views."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window._ctui_widget = self


class ProgressBar(_ProgressBar):
    """Upstream progress bar exposing its percentage to both renderers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.container._ctui_widget = self


__all__ = [
    "Button",
    "Frame",
    "Horizontal",
    "Label",
    "ProgressBar",
    "TextArea",
    "Vertical",
    "Window",
]
