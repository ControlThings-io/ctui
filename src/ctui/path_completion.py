"""Reusable filesystem suggestions for explicitly configured arguments."""

import asyncio
import os
from pathlib import Path
from typing import Callable


class PathCompleter:
    """Suggest existing paths without restricting values accepted by a command.

    Resolve relative paths against the process working directory and expand ~
    for lookup, preserving the typed prefix in suggestions. Include directories
    with a trailing separator for navigation, even when file_filter excludes
    files. file_filter receives an expanded Path and runs in the worker thread.
    Missing or inaccessible directories produce no suggestions. No filesystem
    work runs on the UI loop. New destination names can still be typed freely.
    """

    def __init__(
        self,
        *,
        directories_only: bool = False,
        file_filter: Callable[[Path], bool] | None = None,
    ):
        self.directories_only = directories_only
        self.file_filter = file_filter

    async def __call__(self, context):
        """Return matching paths for a CompletionContext's partial word."""
        return await asyncio.to_thread(self._matches, context.word)

    def _matches(self, word):
        """List one directory, preserving relative, absolute, and home prefixes."""
        parent, prefix = os.path.split(word)
        try:
            matches = []
            for path in sorted(Path(parent or ".").expanduser().iterdir()):
                if not path.name.startswith(prefix):
                    continue
                directory = path.is_dir()
                if not directory and (
                    self.directories_only
                    or (self.file_filter is not None and not self.file_filter(path))
                ):
                    continue
                matches.append(
                    os.path.join(parent, path.name) + (os.sep if directory else "")
                )
            return matches
        except (OSError, RuntimeError):
            return []
