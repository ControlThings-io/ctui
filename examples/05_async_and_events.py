"""Keep the interface responsive during asynchronous work.

Run: uv run examples/05_async_and_events.py
Try: download report.csv
"""

import asyncio

from ctui import CommandContext, CtuiApp, command


class DownloadTool(CtuiApp):
    """Report progress from an async command through the event bus."""

    def __init__(self):
        super().__init__()
        self.progress = "Ready"
        self.footer = lambda: self.progress
        self.on("progress", self.show_progress)

    def show_progress(self, percent: int) -> None:
        """Update text that the status bar reads dynamically."""
        self.progress = f"Downloading: {percent}%"

    @command
    async def download(self, ctx: CommandContext, filename: str) -> str:
        """Pretend to download a file in three asynchronous steps."""
        for percent in (11, 22, 33, 44, 55, 66, 77, 88, 99, 100):
            await asyncio.sleep(0.5)
            await ctx.emit("progress", percent=percent)
        return f"Downloaded {filename}"


if __name__ == "__main__":
    DownloadTool().run()
