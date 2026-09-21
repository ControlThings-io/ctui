"""Combine typed paths, async commands, completion, and validation.

Run: uv run examples/filesystem.py
Try: ls
Try: ls examples --long
Try: ls README.md -l
Try: cd examples

A teaching example rather than a complete system ls implementation. Listing and
completion filesystem work runs in worker threads so it does not block the UI.
cd changes the process-wide directory; relative paths and the status callback
then use that directory. Quote paths containing spaces. Long listings report
numeric ownership and local modification time, without resolving account names.
"""

import asyncio
import os
import stat
from datetime import datetime
from pathlib import Path

from ctui import Argument, CommandError, CtuiApp, PathCompleter, command


def list_path(path, long):
    """Format one file or a sorted directory listing, optionally with metadata.

    Use lstat so symlink details describe the link; long mode includes its target.
    Raise a user-facing CommandError on filesystem failure. This synchronous
    helper is invoked in a worker by the async ls command.
    """
    try:
        items = sorted(path.iterdir()) if path.is_dir() else [path]
        lines = []
        for item in items:
            metadata = item.lstat()
            name = item.name
            if long:
                modified = datetime.fromtimestamp(metadata.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
                if item.is_symlink():
                    name += f" -> {os.readlink(item)}"
                lines.append(
                    f"{stat.filemode(metadata.st_mode)} {metadata.st_nlink:>3} "
                    f"{metadata.st_uid:>5} {metadata.st_gid:>5} "
                    f"{metadata.st_size:>10} {modified} {name}"
                )
            else:
                lines.append(name)
        return "\n".join(lines)
    except OSError as error:
        raise CommandError(f"Cannot list {path}: {error.strerror}") from error


class FilesystemApp(CtuiApp):
    """Browse directories using several ctui features together."""

    name, version, prompt = "Files", "1.0", "files> "
    description = (
        "A slightly more complex example of a ctui application with multiple commands."
    )

    def __init__(self):
        """Display the current process directory through a callable status value."""
        super().__init__()
        self.statusbar = lambda: f"CWD: {Path.cwd()}"

    @command(
        arguments={
            "path": Argument(
                help="File or directory to list", completer=PathCompleter()
            ),
            "long": Argument(
                flags=("-l", "--long"),
                help="Show permissions, links, numeric owner/group, size, and time",
            ),
        }
    )
    async def ls(self, path: Path = Path("."), long: bool = False) -> str:
        """List a file or directory; use -l or --long for details."""
        return await asyncio.to_thread(list_path, path, long)

    @command(
        arguments={
            "directory": Argument(
                help="Existing directory",
                completer=PathCompleter(directories_only=True),
                validator=lambda path: path.is_dir() or f"Not a directory: {path}",
            )
        }
    )
    def cd(self, directory: Path) -> str:
        """Change the working directory."""
        try:
            os.chdir(directory)
        except OSError as error:
            raise CommandError(
                f"Cannot change directory to {directory}: {error.strerror}"
            ) from error
        return f"Changed to {Path.cwd()}"


if __name__ == "__main__":
    FilesystemApp().run()
