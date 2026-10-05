"""Real HTTP/WebSocket regressions for shared sessions, security and lifecycle.

Always bind ephemeral loopback
ports, capture the credential URL, and close sockets/tasks. No external service
or terminal is required. aiohttp is a required package dependency.
"""

import asyncio
import io
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import ClientSession, CookieJar, WSServerHandshakeError

from ctui import CommandError, CommandResult, CtuiApp, command
from ctui.dialogs import MessageDialog, TextInputDialog, show_dialog
from ctui.web import WebClient, WebSession, parse_web_options
from ctui.widgets import Button, Frame, Horizontal, Label, ProgressBar, Vertical


def nodes(tree):
    yield tree
    for child in tree.get("children", []):
        yield from nodes(child)


class BrowserApp(CtuiApp):
    """A reusable existing-style app exercising custom widgets and async commands."""

    def __init__(self):
        super().__init__()
        self.progress = ProgressBar()
        self.clicks = 0
        self.hooks = []
        self.cancelled = asyncio.Event()
        self.statusbar = lambda: f"Clicks: {self.clicks}"
        self.add_shortcut("f2", handler=self.increment, description="Increment counter")

    def compose(self):
        return Vertical(
            [
                Label(lambda: "Dashboard"),
                Frame(self.layout.body, title="Commands"),
                Horizontal(
                    [self.progress, Button("Increment", handler=self.increment)]
                ),
            ]
        )

    def increment(self):
        self.clicks += 1
        self.app.invalidate()

    async def on_start(self):
        self.hooks.append("start")

    async def on_ready(self):
        self.hooks.append("ready")

    async def on_stop(self):
        self.hooks.append("stop")

    @command
    async def echo(self, text: str) -> CommandResult:
        """Append text."""
        await asyncio.sleep(0)
        return CommandResult.append(text)

    @command(confirmation="Erase data?")
    def erase(self) -> str:
        """Exercise explicit confirmation."""
        return "erased"

    @command
    async def ask(self) -> str:
        """Exercise an existing text-input dialog."""
        return (
            await show_dialog(
                TextInputDialog(title="Name", text="Your name?", password=True)
            )
            or "cancelled"
        )

    @command
    async def message(self) -> str:
        """Exercise an existing message dialog."""
        await show_dialog(MessageDialog(title="Notice", text="Hello"))
        return "acknowledged"

    @command
    async def wait(self) -> str:
        """Wait until cancellation."""
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()
        return "never"


class WebOptionsTests(unittest.TestCase):
    def test_defaults_and_explicit_port(self):
        self.assertEqual(
            parse_web_options(["--web"]), {"host": "127.0.0.1", "port": 8080}
        )
        self.assertEqual(parse_web_options(["--web", "--web-port=0"])["port"], 0)

    def test_invalid_and_mixed_options(self):
        for arguments in (
            ["--web", "-c", "help"],
            ["--web", "--web-port=-1"],
            ["--web", "--web-cert", "cert"],
            ["--web", "--web-host", "0.0.0.0"],
            ["--web", "--web-port"],
            ["--web", "--web-port=1", "--web-port=2"],
        ):
            with self.subTest(arguments=arguments), self.assertRaises(CommandError):
                parse_web_options(arguments)

    def test_web_route_and_default_cli_are_exclusive(self):
        app = CtuiApp()
        with patch("asyncio.run", return_value=0) as run:
            with self.assertRaises(SystemExit):
                app.run(["--web", "--web-port", "0"])
        coroutine = run.call_args.args[0]
        self.assertEqual(coroutine.cr_code.co_name, "_run_web_arguments")
        coroutine.close()


class WebTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = BrowserApp()
        self.session = WebSession(self.app, port=0, stdout=io.StringIO())
        await self.session.start()
        self.http = ClientSession(cookie_jar=CookieJar(unsafe=True))
        self.sockets = []

    async def asyncTearDown(self):
        for socket in self.sockets:
            await socket.close()
        await self.http.close()
        await self.session.close()

    async def login(self):
        async with self.http.post(
            self.session.url + "login", json={"token": self.session.access_token}
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("HttpOnly", response.headers["Set-Cookie"])
            self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])

    async def connect(self):
        socket = await self.http.ws_connect(self.session.url + "ws")
        self.sockets.append(socket)
        state = await self.receive(socket, "state")
        return socket, state

    async def receive(self, socket, kind, predicate=lambda message: True):
        async with asyncio.timeout(3):
            while True:
                message = await socket.receive_json()
                if message.get("type") == kind and predicate(message):
                    return message

    async def output(self, socket, expected):
        return await self.receive(
            socket,
            "state",
            lambda m: any(n.get("text") == expected for n in nodes(m["layout"])),
        )

    async def test_static_assets_and_authentication_boundaries(self):
        for name in ("", "app.js", "style.css"):
            async with self.http.get(self.session.url + name) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(
                    "frame-ancestors 'none'",
                    response.headers["Content-Security-Policy"],
                )
        with self.assertRaises(WSServerHandshakeError):
            await self.http.ws_connect(self.session.url + "ws")
        async with self.http.post(
            self.session.url + "login", json={"token": "wrong"}
        ) as response:
            self.assertEqual(response.status, 401)
        async with self.http.post(
            self.session.url + "login",
            json={"token": self.session.access_token},
            headers={"Origin": "https://other.example"},
        ) as response:
            self.assertEqual(response.status, 403)
        async with self.http.get(
            self.session.url, headers={"Host": "attacker.example"}
        ) as response:
            self.assertEqual(response.status, 403)
        await self.login()
        with self.assertRaises(WSServerHandshakeError):
            await self.http.ws_connect(
                self.session.url + "ws", headers={"Origin": "https://other.example"}
            )

    async def test_two_tabs_share_output_and_reconnect_snapshot(self):
        await self.login()
        first, state = await self.connect()
        second, _ = await self.connect()
        self.assertTrue(
            any(
                n["kind"] == "frame" and n["title"] == "Commands"
                for n in nodes(state["layout"])
            )
        )
        await first.send_json({"type": "command", "text": "echo one", "id": 1})
        await self.output(first, "one")
        await self.output(second, "one")
        await second.send_json({"type": "command", "text": "echo two", "id": 2})
        await self.output(first, "one\ntwo")
        await self.output(second, "one\ntwo")
        await first.close()
        third, state = await self.connect()
        self.assertTrue(
            any(n.get("text") == "one\ntwo" for n in nodes(state["layout"]))
        )
        await third.send_json({"type": "clear"})
        await self.output(second, "")

    async def test_completion_errors_and_help_preserve_output(self):
        await self.login()
        socket, _ = await self.connect()
        await socket.send_json({"type": "complete", "text": "ec", "id": 3})
        completion = await self.receive(socket, "completion")
        self.assertEqual(completion["items"][0]["text"], "echo")
        await socket.send_json({"type": "command", "text": "echo preserved", "id": 4})
        await self.output(socket, "preserved")
        await socket.send_json({"type": "command", "text": "unknown", "id": 5})
        error = await self.receive(socket, "error")
        self.assertEqual(error["id"], 5)
        await socket.send_json({"type": "command", "text": "help echo", "id": 6})
        dialog = await self.receive(socket, "dialog")
        self.assertEqual(dialog["title"], "Help")
        await socket.send_json({"type": "answer", "id": dialog["id"], "button": 0})
        await self.receive(socket, "finished")
        self.assertEqual(self.app.layout.output_field.text, "preserved")

    async def test_exit_confirms_and_notifies_only_submitting_tab(self):
        await self.login()
        socket, _ = await self.connect()
        other, _ = await self.connect()
        await socket.send_json({"type": "command", "text": "exit", "id": 1})
        dialog = await self.receive(socket, "dialog")
        self.assertEqual(dialog["text"], "Exit the application?")
        await socket.send_json({"type": "answer", "id": dialog["id"], "button": 1})
        await self.receive(socket, "rejected")
        self.assertFalse(self.session.stopped.is_set())
        await socket.send_json({"type": "command", "text": "exit", "id": 2})
        dialog = await self.receive(socket, "dialog")
        await socket.send_json({"type": "answer", "id": dialog["id"], "button": 0})
        ended = await self.receive(socket, "session-ended")
        self.assertTrue(ended["close_tab"])
        await self.receive(socket, "finished")
        await asyncio.wait_for(self.session.stopped.wait(), 1)
        await self.session.close()
        async for message in other:
            if message.type.name == "TEXT":
                self.assertNotEqual(message.json()["type"], "session-ended")

    async def test_confirmation_and_existing_dialogs(self):
        await self.login()
        socket, _ = await self.connect()
        await socket.send_json({"type": "command", "text": "erase", "id": 1})
        dialog = await self.receive(socket, "dialog")
        self.assertEqual(dialog["text"], "Erase data?")
        await socket.send_json({"type": "answer", "id": dialog["id"], "button": 1})
        await self.receive(socket, "rejected")
        self.assertEqual(self.app.layout.output_field.text, "")
        await socket.send_json({"type": "command", "text": "erase", "id": 2})
        dialog = await self.receive(socket, "dialog")
        await socket.send_json({"type": "answer", "id": dialog["id"], "button": 0})
        await self.output(socket, "erased")
        for command_text, expected in (("ask", "Alice"), ("message", "acknowledged")):
            await socket.send_json({"type": "command", "text": command_text, "id": 3})
            dialog = await self.receive(socket, "dialog")
            if command_text == "ask":
                self.assertTrue(dialog["input"]["password"])
            await socket.send_json(
                {"type": "answer", "id": dialog["id"], "button": 0, "text": "Alice"}
            )
            await self.output(socket, expected)

    async def test_custom_button_progress_and_invalidation(self):
        await self.login()
        socket, state = await self.connect()
        button = next(n for n in nodes(state["layout"]) if n["kind"] == "button")
        await socket.send_json({"type": "button", "id": button["id"]})
        await self.receive(
            socket,
            "state",
            lambda m: any(
                n.get("fragments") == [["", "Clicks: 1"]] for n in nodes(m["layout"])
            ),
        )
        self.app.progress.percentage = 37
        self.app.app.invalidate()
        await self.receive(
            socket,
            "state",
            lambda m: any(n.get("value") == 37 for n in nodes(m["layout"])),
        )

    async def test_disconnect_keeps_commands_running_until_session_shutdown(self):
        await self.login()
        socket, _ = await self.connect()
        await socket.send_json({"type": "command", "text": "wait", "id": 1})
        await asyncio.sleep(0.05)
        await socket.close()
        await asyncio.sleep(0.05)
        self.assertFalse(self.app.cancelled.is_set())
        self.assertFalse(self.session.stopped.is_set())
        await self.connect()
        await self.session.close()
        await asyncio.wait_for(self.app.cancelled.wait(), 3)

    async def test_disconnected_command_result_reaches_other_tab(self):
        release = asyncio.Event()
        started = asyncio.Event()

        @self.app.commands.register
        async def delayed():
            started.set()
            await release.wait()
            return CommandResult.append("completed after disconnect")

        await self.login()
        first, _ = await self.connect()
        second, _ = await self.connect()
        await first.send_json({"type": "command", "text": "delayed", "id": 1})
        await asyncio.wait_for(started.wait(), 3)
        await first.close()
        release.set()
        await self.output(second, "completed after disconnect")

    async def test_disconnection_cancels_unanswered_confirmation(self):
        await self.login()
        socket, _ = await self.connect()
        await socket.send_json({"type": "command", "text": "erase", "id": 1})
        await self.receive(socket, "dialog")
        await socket.close()
        await asyncio.sleep(0.05)
        self.assertEqual(self.app.layout.output_field.text, "")
        self.assertFalse(self.session.actions)

    async def test_outgoing_state_queue_is_bounded_and_latest_wins(self):
        client = WebClient(self.session, None)
        for index in range(100):
            client.update({"index": index})
        self.assertEqual(client.updates.qsize(), 1)
        self.assertEqual(await client.updates.get(), {"index": 99})

    async def test_malformed_message_disconnects_only_its_view(self):
        await self.login()
        socket, _ = await self.connect()
        await socket.send_json(["invalid"])
        await asyncio.wait_for(socket.receive(), 3)
        self.assertFalse(self.session.stopped.is_set())
        await self.connect()

    async def test_second_process_style_session_has_independent_state(self):
        other = WebSession(CtuiApp(), port=0, stdout=io.StringIO())
        try:
            await other.start()
            self.assertNotEqual(other.port, self.session.port)
            self.assertNotEqual(other.cookie, self.session.cookie)
            self.app.layout.set_output("private")
            self.assertEqual(other.ctui.layout.output_field.text, "")
        finally:
            await other.close()

    async def test_https_and_secure_websocket_with_certificate(self):
        fixtures = Path(__file__).with_name("fixtures")
        certificate = fixtures / "web-test-cert.pem"
        secure = WebSession(
            CtuiApp(),
            host="0.0.0.0",
            port=0,
            cert=certificate,
            key=fixtures / "web-test-key.pem",
            stdout=io.StringIO(),
        )
        try:
            await secure.start()
            url = f"https://127.0.0.1:{secure.port}/"
            context = ssl.create_default_context(cafile=str(certificate))
            async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as http:
                async with http.post(
                    url + "login", json={"token": secure.access_token}, ssl=context
                ) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.cookies[secure.cookie_name]["secure"])
                async with http.ws_connect(url + "ws", ssl=context) as socket:
                    self.assertEqual((await socket.receive_json())["type"], "state")
        finally:
            await secure.close()

    async def test_authentication_cookies_do_not_collide_across_ports(self):
        other = WebSession(CtuiApp(), port=0, stdout=io.StringIO())
        try:
            await other.start()
            await self.login()
            async with self.http.post(
                other.url + "login", json={"token": other.access_token}
            ) as response:
                self.assertEqual(response.status, 200)
            async with self.http.ws_connect(other.url + "ws") as socket:
                self.assertEqual((await socket.receive_json())["type"], "state")
            await self.connect()
        finally:
            await other.close()

    async def test_run_web_lifecycle_and_startup_failure_cleanup(self):
        app = BrowserApp()

        async def ready():
            app.hooks.append("ready")
            app.exit()

        app.on_ready = ready
        await asyncio.wait_for(app.run_web(port=0, stdout=io.StringIO()), 3)
        self.assertEqual(app.hooks, ["start", "ready", "stop"])
        self.assertFalse(hasattr(app, "app"))
        failing = BrowserApp()
        with self.assertRaises(CommandError):
            await failing.run_web(host="0.0.0.0", stdout=io.StringIO())
        self.assertEqual(failing.hooks, ["start", "stop"])
