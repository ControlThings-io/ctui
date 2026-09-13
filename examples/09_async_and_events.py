"""Run several asynchronous commands at the same time.

Run: uv run examples/09_async_and_events.py
Try ``download report.csv``, then ``download photo.jpg`` before it completes.
Each download randomly takes between 2 and 10 seconds.
"""

import asyncio
import random

from ctui import CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Demonstrate concurrent commands with immediate event messages."""

    def __init__(self):
        super().__init__()
        self.on("message", self.show_message)

    def show_message(self, text: str) -> None:
        """Append an event message immediately to either interface."""
        if not hasattr(self, "layout"):
            print(text)
            return
        previous = self.layout.output_field.text.rstrip()
        self.layout.set_output(f"{previous}\n{text}".lstrip())
        self.app.invalidate()

    @command
    async def download(self, filename: str) -> CommandResult:
        """Simulate an asynchronous file download."""
        delay = random.randint(2, 10)
        await self.events.emit("message", text=f"Started {filename} ({delay} seconds)")
        await asyncio.sleep(delay)
        await self.events.emit("message", text=f"Completed {filename}")
        return CommandResult.success()


if __name__ == "__main__":
    DownloadTool().run()
