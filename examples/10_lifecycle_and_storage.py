"""Use persistent projects, configuration templates, and protocol records.

Run: uv run examples/10_lifecycle_and_storage.py
Try: configs list
Try: configs show local
Try: profile save lab 10.0.0.20 502
Try: traffic record sent 010300000001
Try: project
"""

from ctui import CtuiApp, command


class SettingsTool(CtuiApp):
    """Persist connection profiles and protocol traffic by project."""

    app_id = "io.controlthings.ctui.storage-example"

    def __init__(self):
        super().__init__()
        self.configs.register_template("local", {"host": "127.0.0.1", "port": 502})

    @command(name="profile save")
    async def profile_save(self, name: str, host: str, port: int = 502) -> str:
        """Save a named connection profile in the active project."""
        await self.configs.save(name, {"host": host, "port": port})
        return f"Saved profile {name!r}."

    @command(name="traffic record")
    async def traffic_record(self, direction: str, hexadecimal: str) -> str:
        """Record one example protocol frame in the active project."""
        payload = bytes.fromhex(hexadecimal)
        await self.records.append(
            direction=direction, protocol="example", payload=payload
        )
        return f"Recorded {len(payload)} bytes."


if __name__ == "__main__":
    SettingsTool().run()
