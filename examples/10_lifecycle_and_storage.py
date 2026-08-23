"""Initialize an application with lifecycle hooks and shared storage.

Run: uv run examples/10_lifecycle_and_storage.py
Try: set color blue
Try: get color
Try: get missing
"""

from ctui import CtuiApp, MemoryStorage, command


class SettingsTool(CtuiApp):
    """Share in-memory values between commands."""

    def __init__(self):
        super().__init__(storage=MemoryStorage())

    async def on_start(self) -> None:
        """Install a default value before either interface starts."""
        self.storage.set("color", "green")

    @command
    def set(self, name: str, value: str) -> str:
        """Store a setting for this application session."""
        self.storage.set(name, value)
        return f"Stored {name}={value}"

    @command
    def get(self, name: str) -> str:
        """Read a setting, showing an error popup when it does not exist."""
        value = self.storage.get(name)
        return f"{name}={value}"


if __name__ == "__main__":
    SettingsTool().run()
