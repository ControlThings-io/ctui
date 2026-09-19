"""Combine typed paths, async commands, completion, and validation.

Run: uv run examples/filesystem.py
Try: ls
Try: ls examples --long
Try: ls README.md -l
Try: cd examples
"""

import asyncio
import os
import stat
from datetime import datetime
from pathlib import Path

from ctui import Argument, CommandError, CtuiApp, command


def matching_paths(word, directories_only=False):
    """Suggest relative, absolute, or home-relative paths one level at a time."""
    parent, prefix = os.path.split(word)
    try:
        return [
            os.path.join(parent, path.name) + (os.sep if path.is_dir() else "")
            for path in sorted(Path(parent or ".").expanduser().iterdir())
            if path.name.startswith(prefix) and (not directories_only or path.is_dir())
        ]
    except OSError:
        return []


async def path_names(context):
    """Suggest files and directories for ls."""
    return await asyncio.to_thread(matching_paths, context.word)


async def directory_names(context):
    """Suggest only directories for cd."""
    return await asyncio.to_thread(matching_paths, context.word, True)


def list_path(path, long):
    """List a file or directory, optionally including detailed metadata."""
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

    name, version, prompt = "files", "1.0", "files> "
    description = "A slightly more complex example of a ctui application with multiple commands."

    def __init__(self):
        super().__init__()
        self.statusbar = lambda: f"CWD: {Path.cwd()}"

    @command(
        arguments={
            "path": Argument(help="File or directory to list", completer=path_names),
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
                completer=directory_names,
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
