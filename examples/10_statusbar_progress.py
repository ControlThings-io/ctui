"""Show progress for concurrent commands in the status bar.

Run: uv run examples/10_statusbar_progress.py
Try ``download report.csv``, then ``download photo.jpg`` before it completes.
Finished downloads disappear from the status bar.
"""

import asyncio
import random

from ctui import CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Display progress for every active asynchronous download."""

    def __init__(self):
        super().__init__()
        self.progress: dict[str, int] = {}
        self.statusbar = self.progress_text
        self.on("progress", self.show_progress)

    def progress_text(self) -> str:
        """Format active downloads for the status bar."""
        if not self.progress:
            return "Ready"
        return " | ".join(
            f"{filename}: {percent}%" for filename, percent in self.progress.items()
        )

    def show_progress(self, filename: str, percent: int | None) -> None:
        """Update or remove one download and redraw the status bar."""
        if percent is None:
            self.progress.pop(filename, None)
        else:
            self.progress[filename] = percent
        if hasattr(self, "app"):
            self.app.invalidate()

    @command
    async def download(self, filename: str) -> CommandResult:
        """Simulate a download while reporting its percentage."""
        delay = random.randint(2, 10)
        try:
            await self.events.emit("progress", filename=filename, percent=0)
            for step in range(1, 21):
                await asyncio.sleep(delay / 20)
                await self.events.emit("progress", filename=filename, percent=step * 5)
        finally:
            await self.events.emit("progress", filename=filename, percent=None)
        return CommandResult.append(f"Completed {filename}")


if __name__ == "__main__":
    DownloadTool().run()
