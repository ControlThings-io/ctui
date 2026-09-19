"""Exercise an installed wheel or source distribution in an isolated environment.

Run via the release checklist's uv --isolated --no-project --with ARTIFACT command
so imports come from the artifact rather than the editable repository package.
Check public imports, installed version, custom type parsing, headless dispatch,
and temporary project persistence. Passing locally is artifact evidence, not
proof of remote CI success or publication.
"""

import asyncio
import tempfile
from importlib.metadata import version
from pathlib import Path

from ctui import CtuiApp, FuzzyHexPattern, HexBytes, __version__, command


class SmokeApp(CtuiApp):
    """Small installed-package application used by artifact checks."""

    @command
    def add(self, first: int, second: int) -> str:
        """Add two integers."""
        return str(first + second)


async def smoke_test() -> None:
    """Verify representative installed-package behavior without opening a terminal.

    Use a temporary project root and explicitly close the backend in finally.
    Assertion failures make the script fail for use in build/release workflows.
    """
    assert __version__ == version("ctui")
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
