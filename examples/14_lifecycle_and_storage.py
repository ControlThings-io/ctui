"""Use persistent projects, configuration templates, and protocol records.

Run: uv run examples/14_lifecycle_and_storage.py
Try: configs list
Try: configs show local
Try: profile save lab 10.0.0.20 502
Try: traffic record sent 010300000001
Try: project

The stable app_id enables SQLite persistence in the platform user-data folder.
run() opens the backend before commands and closes it on shutdown. Register the
local template before startup; project activation fills missing templates without
overwriting saved profiles. Keep runtime sockets/clients on instance attributes,
profiles in configs, and payloads in records. These commands store example data;
they do not connect to a device.
"""

from ctui import Argument, CtuiApp, HexBytes, command


class SettingsTool(CtuiApp):
    """Persist connection profiles and protocol traffic by project."""

    app_id = "io.controlthings.ctui.storage-example"

    def __init__(self):
        """Register a copied default profile before the backend opens."""
        super().__init__()
        self.configs.register_template("local", {"host": "127.0.0.1", "port": 502})

    @command(
        name="profile save",
        arguments={
            "name": Argument(help="Profile name"),
            "host": Argument(help="Server hostname or address"),
            "port": Argument(help="Server port (default: 502)"),
        },
    )
    async def profile_save(self, name: str, host: str, port: int = 502) -> str:
        """Save a named connection profile in the active project."""
        await self.configs.save(name, {"host": host, "port": port})
        return f"Saved profile {name!r}."

    @command(
        name="traffic record",
        arguments={
            "direction": Argument(help="Traffic direction"),
            "payload": Argument(help="Frame bytes to record"),
        },
    )
    async def traffic_record(self, direction: str, payload: HexBytes) -> str:
        """Record one example protocol frame in the active project."""
        await self.records.append(
            direction=direction, protocol="example", payload=payload
        )
        return f"Recorded {len(payload)} bytes."


if __name__ == "__main__":
    SettingsTool().run()
