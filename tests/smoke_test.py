"""Exercise installed-package behavior against built distributions."""

import asyncio
import tempfile
from importlib.metadata import version
from pathlib import Path

from ctui import CtuiApp, FuzzyHexPattern, HexBytes, command


class SmokeApp(CtuiApp):
    """Small installed-package application used by artifact checks."""

    @command
    def add(self, first: int, second: int) -> str:
        """Add two integers."""
        return str(first + second)


async def smoke_test() -> None:
    """Verify public types, dispatch, and persistent project storage."""
    assert version("ctui")
    assert HexBytes("be:ef") == b"\xbe\xef"
    assert list(FuzzyHexPattern("f[0-1]").expand()) == [b"\xf0", b"\xf1"]

    app = SmokeApp(register_defaults=False)
    assert (await app.dispatch("add 20 22")).output == "42"

    with tempfile.TemporaryDirectory() as directory:
        project_app = CtuiApp(
            app_id="io.controlthings.ctui.smoke",
            data_dir=Path(directory),
            register_defaults=False,
        )
        await project_app.backend.open()
        try:
            await project_app.configs.save("connection", {"port": 502})
            assert await project_app.configs.get("connection") == {"port": 502}
        finally:
            await project_app.backend.close()


if __name__ == "__main__":
    asyncio.run(smoke_test())
