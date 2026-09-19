"""Show progress for concurrent commands in the status bar.

Run: uv run examples/11_statusbar_progress.py
Try ``download report.csv``, then ``download photo.jpg`` before it completes.
Finished downloads disappear from the status bar.

This is application-owned progress state, not a framework job manager. Use
unique filenames here because the dictionary keys identify concurrent downloads.
The status callable returns text when rendered; progress listeners invalidate the
UI to request a redraw. finally removes entries on success, failure, or task
cancellation, while completion output uses an append result.
"""

import asyncio
import random

from ctui import CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Display progress for every active asynchronous download."""

    def __init__(self):
        """Create transient progress state and register its status/event callbacks."""
        super().__init__()
        self.progress: dict[str, int] = {}
        self.statusbar = self.progress_text
        self.on("progress", self.show_progress)

    def progress_text(self) -> str:
        """Return Ready or one percentage per active filename without printing."""
        if not self.progress:
            return "Ready"
        return " | ".join(
            f"{filename}: {percent}%" for filename, percent in self.progress.items()
        )

    def show_progress(self, filename: str, percent: int | None) -> None:
        """Update one filename's progress and request a UI redraw when available.

        None removes an entry; no framework job registration or persistence occurs.
        """
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
