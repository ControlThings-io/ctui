"""Combine typed paths, async commands, completion, and validation.

Run: uv run examples/filesystem.py
Try: list
Try: change directory .
"""

import asyncio
import os
from pathlib import Path

from ctui import Argument, CommandError, CtuiApp, command


async def directory_names(_context):
    """Suggest directories found under the current working directory."""
    await asyncio.sleep(0)
    return [str(path) for path in Path.cwd().iterdir() if path.is_dir()]


class FilesystemApp(CtuiApp):
    """Browse directories using several ctui features together."""

    name, version, prompt = "files", "1.0", "files> "

    def __init__(self):
        super().__init__()
        self.statusbar = lambda: f"CWD: {Path.cwd()}"

    @command
    async def list(self, directory: Path = Path(".")) -> str:
        """List a directory without blocking the terminal UI."""
        await asyncio.sleep(0)
        if not directory.is_dir():
            raise CommandError(f"Not a directory: {directory}")
        return "\n".join(sorted(item.name for item in directory.iterdir()))

    @command(
        arguments={
            "directory": Argument(
                help="Existing directory",
                completer=directory_names,
                validator=lambda path: path.is_dir() or f"Not a directory: {path}",
            )
        }
    )
    def change_directory(self, directory: Path) -> str:
        """Change the working directory."""
        os.chdir(directory)
        return f"Changed to {Path.cwd()}"


if __name__ == "__main__":
    FilesystemApp().run()
