"""Scoped Python stream protection for the full-screen terminal lifecycle."""

import asyncio
import io
import logging
import sys
import threading
from contextlib import asynccontextmanager

from prompt_toolkit.application import get_app_session, run_in_terminal


class _TerminalStream(io.TextIOBase):
    """Queue text from any thread; only the event loop writes to the terminal.

    Preserve partial writes and escape control sequences through Output.write.
    flush queues buffered text; the guard awaits delivery before restoration.
    Binary and direct file-descriptor writes are outside this stream contract.
    """

    def __init__(self, loop, queue, original):
        self.loop, self.queue, self.original = loop, queue, original
        self.lock = threading.RLock()
        self.pending = ""
        self.active = True

    @property
    def encoding(self):
        return getattr(self.original, "encoding", None) or "utf-8"

    def writable(self):
        return True

    def isatty(self):
        return self.original.isatty()

    def fileno(self):
        return self.original.fileno()

    def write(self, text):
        with self.lock:
            if not self.active:
                return self.original.write(text)
            self.pending += text
            if "\n" in self.pending:
                before, self.pending = self.pending.rsplit("\n", 1)
                self.loop.call_soon_threadsafe(self.queue.put_nowait, before + "\n")
        return len(text)

    def flush(self):
        with self.lock:
            if not self.active:
                self.original.flush()
                return
            if self.pending:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, self.pending)
                self.pending = ""


@asynccontextmanager
async def protect_terminal_output():
    """Protect stdout/stderr and existing standard-stream logging handlers.

    Keep handler formatting, levels and filters intact; do not add handlers or
    touch file/custom destinations. Changes are process-wide and scoped to one
    terminal lifecycle. Restore only streams still owned by this guard, respecting
    application reconfiguration. Await queued diagnostics on every exit path.
    Handlers created during the scope should resolve sys.stdout/sys.stderr;
    retained original streams and direct OS writes cannot be intercepted.
    """
    loop, queue = asyncio.get_running_loop(), asyncio.Queue()
    output = get_app_session().output  # Resolve before replacing system streams.
    original_stdout, original_stderr = sys.stdout, sys.stderr
    proxy = _TerminalStream(loop, queue, original_stdout)
    changed = []

    async def deliver():
        while True:
            text = await queue.get()
            if text is None:
                return

            def emit():
                output.enable_autowrap()
                output.write(text)
                output.flush()

            await run_in_terminal(emit)

    worker = asyncio.create_task(deliver())
    try:
        loggers = [
            logging.getLogger(),
            *logging.Logger.manager.loggerDict.copy().values(),
        ]
        handlers = {
            h
            for logger in loggers
            if isinstance(logger, logging.Logger)
            for h in logger.handlers
        }
        for handler in handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                descriptor = getattr(type(handler), "stream", None)
                if isinstance(descriptor, property) and descriptor.fset is None:
                    continue  # Dynamic stderr handlers already follow sys.stderr.
                if (
                    getattr(handler, "stream", None) is original_stdout
                    or getattr(handler, "stream", None) is original_stderr
                ):
                    old = handler.setStream(proxy)
                    changed.append((handler, old))
        sys.stdout = sys.stderr = proxy
        yield
    finally:
        for handler, stream in reversed(changed):
            if handler.stream is proxy:
                handler.setStream(stream)
        if sys.stdout is proxy:
            sys.stdout = original_stdout
        if sys.stderr is proxy:
            sys.stderr = original_stderr
        with proxy.lock:
            proxy.flush()
            proxy.active = False
        # Thread-safe puts registered by flush must precede the stop sentinel.
        await asyncio.sleep(0)
        queue.put_nowait(None)
        await asyncio.shield(worker)
