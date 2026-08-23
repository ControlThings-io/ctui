"""Keep the interface responsive during asynchronous work.

Run: uv run examples/05_async_and_events.py
Try: download report.csv
While it runs, try: download photo.jpg
"""

import asyncio

from ctui import CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Report progress from an async command through the event bus."""

    def __init__(self):
        super().__init__()
        self.progress: dict[str, int] = {}
        self.statusbar = self.progress_text
        self.on("progress", self.show_progress)

    def progress_text(self) -> str:
        """Format every active or completed download for the status bar."""
        if not self.progress:
            return "Ready"
        return " | ".join(
            f"{filename}: {percent}%" for filename, percent in self.progress.items()
        )

    def show_progress(self, filename: str, percent: int) -> None:
        """Store one file's progress and request an immediate redraw."""
        self.progress[filename] = percent
        if hasattr(self, "app"):
            self.app.invalidate()

    @command
    async def download(self, filename: str) -> CommandResult:
        """Pretend to download a file in three asynchronous steps."""
        await self.events.emit("progress", filename=filename, percent=0)
        for percent in (11, 22, 33, 44, 55, 66, 77, 88, 99, 100):
            await asyncio.sleep(0.5)
            await self.events.emit("progress", filename=filename, percent=percent)
        return CommandResult.append(f"Downloaded {filename}")


if __name__ == "__main__":
    DownloadTool().run()
