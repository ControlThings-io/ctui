"""Run several asynchronous commands at the same time.

Run: uv run examples/05_async_and_events.py
Try: download report.csv
Before it completes, try: download photo.jpg

Each simulated download randomly takes between 2 and 10 seconds. The immediate
Started and Completed messages make it easy to see that commands overlap.
"""

import asyncio
import random

from ctui import CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Demonstrate concurrent commands using async functions and events."""

    def __init__(self):
        super().__init__()
        self.on("message", self.show_message)

    def show_message(self, text: str) -> None:
        """Append an event message immediately to the UI or command line."""
        if not hasattr(self, "layout"):
            print(text)
            return
        previous = self.layout.output_field.text.rstrip()
        self.layout.output_field.text = f"{previous}\n{text}".lstrip()
        self.app.invalidate()

    @command
    async def download(self, filename: str) -> CommandResult:
        """Simulate an asynchronous file download."""
        delay = random.randint(2, 10)
        await self.events.emit(
            "message", text=f"Started {filename} ({delay} seconds)"
        )
        await asyncio.sleep(delay)
        await self.events.emit("message", text=f"Completed {filename}")
        return CommandResult.success()


if __name__ == "__main__":
    DownloadTool().run()
