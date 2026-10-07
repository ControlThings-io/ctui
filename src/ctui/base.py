"""Internal upstream-based button adapter for content-sized dialog captions."""

from prompt_toolkit.filters import to_filter
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import Button as ToolkitButton


class Button(ToolkitButton):
    """Use upstream navigation/mouse handling with a minimum display-cell width."""

    def __init__(self, text: str, handler=None, width: int = 12):
        super().__init__(text, handler=handler, width=max(width, get_cwidth(text) + 2))
        self.window.dont_extend_width = to_filter(True)
