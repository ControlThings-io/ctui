"""Terminal diagnostics preserve logging configuration and stream ownership."""

import asyncio
import io
import logging
import sys
import unittest
from unittest.mock import patch

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from ctui import CommandError, CtuiApp, command
from ctui.dialogs import message_dialog
from ctui.terminal_output import protect_terminal_output


class RecordingOutput(DummyOutput):
    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class TerminalOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_handler_and_streams_deliver_once_and_restore(self):
        original = io.StringIO()
        handler = logging.StreamHandler(original)
        handler.setFormatter(logging.Formatter("LOG: %(message)s"))
        logger = logging.getLogger("ctui.test.output")
        old_handlers, old_propagate, old_level = (
            logger.handlers,
            logger.propagate,
            logger.level,
        )
        logger.handlers, logger.propagate, logger.level = (
            [handler],
            False,
            logging.WARNING,
        )
        output = RecordingOutput()
        try:
            with (
                patch.object(sys, "stdout", original),
                patch.object(sys, "stderr", original),
            ):
                with (
                    create_pipe_input() as pipe,
                    create_app_session(input=pipe, output=output),
                ):
                    async with protect_terminal_output():
                        terminal = Application(output=output, input=pipe)

                        async def produce():
                            while not terminal.is_running:
                                await asyncio.sleep(0)
                            print("stdout message")
                            sys.stderr.write("stderr message\n")
                            await asyncio.to_thread(logger.warning, "warning message")
                            await asyncio.sleep(0.05)
                            terminal.exit()

                        task = asyncio.create_task(produce())
                        await terminal.run_async()
                        await task
                        sys.stdout.write("partial tail")
                        retained = logging.StreamHandler(sys.stderr)
                    self.assertIs(sys.stdout, original)
                    self.assertIs(sys.stderr, original)
                    self.assertIs(handler.stream, original)
                    retained.handle(
                        logging.LogRecord(
                            "late", logging.WARNING, "", 0, "late warning", (), None
                        )
                    )
                    retained.close()
            text = "".join(output.messages)
            for message in (
                "stdout message",
                "stderr message",
                "LOG: warning message",
                "partial tail",
            ):
                self.assertEqual(text.count(message), 1)
            self.assertEqual(original.getvalue(), "late warning\n")
            self.assertEqual(handler.formatter._fmt, "LOG: %(message)s")
        finally:
            logger.handlers, logger.propagate, logger.level = (
                old_handlers,
                old_propagate,
                old_level,
            )
            handler.close()

    async def test_command_error_popup_and_input_survive_background_diagnostics(self):
        output = RecordingOutput()
        checks = []

        class NoisyApp(CtuiApp):
            @command
            def noisy(self):
                print("command stdout")
                sys.stderr.write("command stderr\n")
                raise CommandError("connection failed")

            async def on_ready(self):
                async def exercise():
                    while not self.app.is_running:
                        await asyncio.sleep(0)
                    before = len(self.app.layout.container.floats)
                    pipe.send_text("noisy\r")
                    for _ in range(100):
                        if len(self.app.layout.container.floats) > before:
                            break
                        await asyncio.sleep(0.01)
                    checks.append(len(self.app.layout.container.floats) > before)
                    checks.append(self.layout.input_field.text == "noisy")
                    print("background while dialog open")
                    await asyncio.sleep(0.05)
                    checks.append(len(self.app.layout.container.floats) > before)
                    self.app.exit()

                self.driver = asyncio.create_task(exercise())

        app = NoisyApp(register_defaults=False)
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=output):
            with patch(
                "ctui.keybindings.message_dialog", wraps=message_dialog
            ) as popup:
                await asyncio.wait_for(app.run_async(), 5)
                await app.driver
                popup.assert_called_once_with(title="Error", text="connection failed")
        self.assertEqual(checks, [True, True, True])
        text = "".join(output.messages)
        self.assertIn("command stdout", text)
        self.assertIn("command stderr", text)
        self.assertIn("background while dialog open", text)

    async def test_failure_and_cancellation_restore_streams(self):
        stdout, stderr = sys.stdout, sys.stderr
        for error in (RuntimeError("failed"), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__):
                output = RecordingOutput()
                with (
                    create_pipe_input() as pipe,
                    create_app_session(input=pipe, output=output),
                ):
                    with self.assertRaises(type(error)):
                        async with protect_terminal_output():
                            print("before failure")
                            raise error
                self.assertIs(sys.stdout, stdout)
                self.assertIs(sys.stderr, stderr)
                self.assertIn("before failure", "".join(output.messages))
