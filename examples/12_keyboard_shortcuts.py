"""Register an application-wide keyboard shortcut.

Run: uv run examples/12_keyboard_shortcuts.py
Press F2 several times and watch the status bar.

Register before run() constructs bindings. The zero-argument handler updates
ordinary application state and explicitly requests a redraw. Its description
appears in UI help; the shortcut applies application-wide.
"""

from ctui import CtuiApp


class ShortcutTool(CtuiApp):
    """Update application state from a custom F2 shortcut."""

    def __init__(self):
        """Set up the counter, dynamic status text, and global F2 binding."""
        super().__init__()
        self.presses = 0
        self.statusbar = lambda: f"F2 presses: {self.presses}"
        self.add_shortcut("f2", handler=self.record_press, description="Count a press")

    def record_press(self) -> None:
        """Count the key press and redraw the interface."""
        self.presses += 1
        self.app.invalidate()


if __name__ == "__main__":
    ShortcutTool().run()
