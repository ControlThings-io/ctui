"""Supported prompt-toolkit building blocks for CtuiApp.compose().

Vertical aliases HSplit (children stacked top to bottom); Horizontal aliases
VSplit (children placed side by side). The remaining exports are the upstream
Button, Frame, Label, ProgressBar, TextArea, and Window classes, not wrappers.
Reuse the application's command input in custom layouts so automatic focus and
bindings work. These exported aliases form part of ctui's supported 1.x surface;
internal layout and dialog modules do not gain that compatibility promise.
"""

from prompt_toolkit.layout.containers import HSplit as Vertical
from prompt_toolkit.layout.containers import VSplit as Horizontal
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.widgets import Button, Frame, Label, ProgressBar, TextArea

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
