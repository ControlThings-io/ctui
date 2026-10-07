"""Collect values in embedded terminal and browser dialogs.

Run: uv run examples/16_dialogs.py
Or:  uv run examples/16_dialogs.py --web --web-port 0
Try: choose
Try: edit

Dictionary labels and values share rows; field help appears beneath its value.
Tab moves between fields and buttons. Escape cancels; no changes are applied
until a result is accepted. These commands require an interactive UI, not CLI.
"""

from ctui import CtuiApp, command
from ctui.dialogs import (
    ButtonDialog,
    CheckboxListDialog,
    DictField,
    DictInputDialog,
    RadioListDialog,
    show_dialog,
)


def valid_port(value: int) -> bool | str:
    """Reject ports outside the TCP range with a useful inline message."""
    return 1 <= value <= 65535 or "Port must be between 1 and 65535."


class DialogTool(CtuiApp):
    """Select choices and edit a small in-memory connection profile."""

    def __init__(self):
        super().__init__()
        self.profile = {
            "host": "localhost",
            "port": 502,
            "timeout": 2.0,
            "enabled": True,
        }

    @command
    async def choose(self) -> str:
        """Choose buttons, a radio value, and any number of checkbox values."""
        action = await show_dialog(
            ButtonDialog(
                title="Action",
                text="Choose an action.",
                buttons=[("Read", "read"), ("Write", "write"), ("Inspect", "inspect")],
            )
        )
        if action is None:
            return "Cancelled."
        transport = await show_dialog(
            RadioListDialog(
                title="Transport",
                values=[("tcp", "TCP"), ("serial", "Serial")],
                default="tcp",
            )
        )
        if transport is None:
            return "Cancelled."
        options = await show_dialog(
            CheckboxListDialog(
                title="Options",
                values=[("debug", "Debug logging"), ("retry", "Retry requests")],
                default_values=["retry"],
            )
        )
        if options is None:
            return "Cancelled."
        return f"Selected {action}, {transport}, options={options}."

    @command
    async def edit(self) -> str:
        """Edit profile values; keep keys and validate the TCP port."""
        result = await show_dialog(
            DictInputDialog(
                title="Connection profile",
                text="Edit values, then select Ok.",
                values=self.profile,
                fields={
                    "port": DictField(
                        label="TCP port", help="1–65535", validator=valid_port
                    )
                },
            )
        )
        if result is None:
            return "Cancelled; profile kept."
        self.profile = result
        return f"Updated profile: {self.profile}"


if __name__ == "__main__":
    DialogTool().run()
