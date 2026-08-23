"""Wrap the standard command interface in a custom layout.

Run: uv run examples/09_custom_layout.py
Try: system status
"""

from ctui import CtuiApp, command
from ctui.widgets import Frame, Label, Vertical


class DashboardTool(CtuiApp):
    """Add a title and frame around ctui's reusable standard body."""

    def compose(self):
        """Return a prompt-toolkit container containing the command input."""
        return Vertical(
            [
                Label(" ControlThings demonstration dashboard "),
                Frame(self.layout.body, title="Commands and output"),
            ]
        )

    @command
    def system_status(self) -> str:
        """Show a small dashboard-style status report."""
        return "Controller: online\nDevices: 4\nWarnings: 0"


if __name__ == "__main__":
    DashboardTool().run()
