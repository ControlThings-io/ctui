"""Run several asynchronous commands at the same time.

Run: uv run examples/10_async_and_events.py
Try ``download report.csv``, then ``download photo.jpg`` before it completes.
Each download randomly takes between 2 and 10 seconds.

This is a simulation: no files are downloaded. UI submissions overlap because
the handler awaits asyncio.sleep; CLI batches remain sequential. Commands access
the event bus through self rather than a hidden context parameter. A no-output
CommandResult.success() avoids replacing messages already displayed by listeners.
"""

import asyncio
import random

from ctui import Argument, CommandResult, CtuiApp, command


class DownloadTool(CtuiApp):
    """Demonstrate concurrent commands with immediate event messages."""

    def __init__(self):
        """Register a synchronous message listener before either interface starts."""
        super().__init__()
        self.on("message", self.show_message)

    def show_message(self, text: str) -> None:
        """Present a message immediately rather than waiting for a command result.

        Print in CLI mode, where no layout exists. In UI mode append to current
        read-only output through set_output and request a redraw.
        """
        if not hasattr(self, "layout"):
            print(text)
            return
        previous = self.layout.output_field.text.rstrip()
        self.layout.set_output(f"{previous}\n{text}".lstrip())
        self.app.invalidate()

    @command(arguments={"filename": Argument(help="File to download")})
    async def download(self, filename: str) -> CommandResult:
        """Simulate an asynchronous file download."""
        delay = random.randint(2, 10)
        await self.events.emit("message", text=f"Started {filename} ({delay} seconds)")
        await asyncio.sleep(delay)
        await self.events.emit("message", text=f"Completed {filename}")
        return CommandResult.success()


if __name__ == "__main__":
    DownloadTool().run()
