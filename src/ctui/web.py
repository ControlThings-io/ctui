"""Asyncio HTTP/WebSocket frontend for one live CtuiApp session.

Every connection shares widgets, commands and services; draft input, completion,
scrolling and dialogs are per-view. Concurrent commands preserve terminal mode's
completion-order behavior. Bounded outgoing queues coalesce UI snapshots, while
slow connections time out. Submitted commands survive view disconnection;
unanswered per-view dialogs are cancelled. Disconnection does not stop the session. Session exit cancels all work before
on_stop closes application resources.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import ipaddress
import json
import logging
import os
import secrets
import ssl
import sys
import traceback
from pathlib import Path
from urllib.parse import quote

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui.commands import CommandError, _HelpResult
from ctui.layout import CtuiLayout
from ctui.web_layout import WebLayout, plain

# Context propagates into tasks created by existing dialog convenience wrappers.
web_client = contextvars.ContextVar("ctui_web_client", default=None)
ASSETS = Path(__file__).with_name("web_assets")


def parse_web_options(arguments):
    """Parse web-only startup options; reject CLI batches and incomplete TLS.

    --web-host defaults to 127.0.0.1, --web-port to 8080 (0 selects a free port).
    Non-loopback binds require a certificate and key. --web-token-env selects an
    environment variable rather than exposing a supplied token in process args.
    Without it a random session token is generated and printed in the URL fragment.
    """
    options = {"host": "127.0.0.1", "port": 8080}
    values = {
        "--web-host": "host",
        "--web-port": "port",
        "--web-cert": "cert",
        "--web-key": "key",
        "--web-token-env": "token_env",
    }
    index = 0
    seen = set()
    while index < len(arguments):
        option, equals, value = arguments[index].partition("=")
        if option in seen:
            raise CommandError(f"Repeated web option: {option}")
        seen.add(option)
        if option == "--web" and not equals:
            index += 1
            continue
        if option not in values:
            raise CommandError(
                f"Invalid web option: {option}; web and CLI modes cannot be combined"
            )
        if not equals:
            index += 1
            if index >= len(arguments) or arguments[index].startswith("--"):
                raise CommandError(f"{option} requires a value")
            value = arguments[index]
        options[values[option]] = value
        index += 1
    try:
        options["port"] = int(options["port"])
        if not 0 <= options["port"] <= 65535:
            raise ValueError
    except ValueError as error:
        raise CommandError("--web-port must be between 0 and 65535") from error
    if not options["host"]:
        raise CommandError("--web-host cannot be empty")
    if bool(options.get("cert")) != bool(options.get("key")):
        raise CommandError("--web-cert and --web-key must be supplied together")
    if not is_loopback(options["host"]) and not options.get("cert"):
        raise CommandError("Remote web access requires --web-cert and --web-key")
    if "token_env" in options:
        token = os.environ.get(options.pop("token_env"), "")
        if len(token) < 24:
            raise CommandError(
                "The web token environment variable must contain at least 24 characters"
            )
        options["token"] = token
    return options


def is_loopback(host):
    """Recognize literal loopback addresses and localhost without DNS lookups."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class WebClient:
    """Own one view's bounded sender, pending dialogs and command tasks."""

    def __init__(self, session, socket):
        self.session, self.socket = session, socket
        self.updates = asyncio.Queue(maxsize=1)
        self.dialogs = {}
        self.dialog_buttons = {}
        self.dialog_lock = asyncio.Lock()
        self.tasks = set()
        self.send_lock = asyncio.Lock()
        self.completion_task = None

    async def send(self, message):
        """Serialize socket writes and detach clients that cannot keep up."""
        if self.socket.closed:
            return
        async with self.send_lock:
            await asyncio.wait_for(self.socket.send_json(message), timeout=10)

    def update(self, snapshot):
        """Replace stale queued state with the current complete snapshot."""
        if self.updates.full():
            self.updates.get_nowait()
        self.updates.put_nowait(snapshot)

    async def sender(self):
        """Stream coalesced snapshots independently of other views."""
        try:
            while True:
                await self.send(await self.updates.get())
        finally:
            await self.socket.close()

    async def dialog(
        self,
        title,
        text,
        buttons,
        *,
        input_field=None,
        options=None,
        validate=None,
        cancel=None,
    ):
        """Queue a modal for this view and retain edits on validation rejection.

        Validation is synchronous and server-side. Only DialogValidationError
        keeps the dialog open; other exceptions propagate. Cancellation, failure
        and disconnect remove pending answers and release the per-view queue.
        """
        from ctui.dialogs import DialogValidationError

        async with self.dialog_lock:
            if self.socket.closed:
                raise asyncio.CancelledError
            identifier = secrets.token_hex(12)
            self.dialog_buttons[identifier] = (len(buttons), cancel)
            try:
                future = asyncio.get_running_loop().create_future()
                self.dialogs[identifier] = future
                await self.send(
                    {
                        "type": "dialog",
                        "id": identifier,
                        "title": title,
                        "text": text,
                        "buttons": buttons,
                        "input": input_field,
                        "options": options or {},
                        "cancel": len(buttons) - 1 if cancel is None else cancel,
                    }
                )
                while True:
                    answer = await future
                    try:
                        return validate(answer) if validate else answer
                    except DialogValidationError as exc:
                        future = asyncio.get_running_loop().create_future()
                        self.dialogs[identifier] = future
                        await self.send(
                            {
                                "type": "dialog-error",
                                "id": identifier,
                                "text": str(exc),
                                "field": exc.field,
                            }
                        )
            finally:
                pending = self.dialogs.pop(identifier, None)
                if pending is not None and not pending.done():
                    pending.cancel()
                self.dialog_buttons.pop(identifier, None)
                await self.send({"type": "dialog-close", "id": identifier})

    async def show_dialog(self, dialog):
        """Display embedded ctui dialogs using their shared typed validation."""
        from ctui.dialogs import YesNoDialog

        title, text, buttons, input_field = dialog._web_dialog

        def result(answer):
            if hasattr(dialog, "_web_result"):
                return dialog._web_result(answer)
            return answer["button"] == 0 if isinstance(dialog, YesNoDialog) else None

        try:
            value = await self.dialog(
                plain(title),
                plain(text),
                buttons,
                input_field=input_field,
                options=getattr(dialog, "_web_options", None),
                validate=result,
                cancel=getattr(dialog, "_web_cancel", None),
            )
        except BaseException:
            dialog.future.cancel()
            raise
        if not dialog.future.done():
            dialog.future.set_result(value)
        return value

    def spawn(self, coroutine, *, persistent=False):
        """Track work and contain background transport/application failures."""

        context = contextvars.copy_context()
        context.run(web_client.set, self)
        task = asyncio.create_task(coroutine, context=context)
        owned = self.session.actions if persistent else self.tasks
        owned.add(task)

        def done(completed):
            owned.discard(completed)
            if not completed.cancelled() and completed.exception() is not None:
                error = completed.exception()
                logging.getLogger(__name__).error(
                    "Web view task failed",
                    exc_info=(type(error), error, error.__traceback__),
                )
                if not self.socket.closed:
                    self.session.create_background_task(self.socket.close())

        task.add_done_callback(done)
        return task

    async def command(self, text, identifier):
        """Confirm per view; notify the exiting view before stopping the session.

        The browser attempts to close only the tab submitting an accepted exit.
        Other views disconnect when the shared session shuts down.
        """
        try:
            self.session.ctui.output_text = self.session.ctui.layout.output_field.text

            async def confirm(message):
                value = await self.dialog("Confirm", message, ["Yes", "No"])
                return value.get("button") == 0

            result = await self.session.ctui.dispatch(text, confirm_callback=confirm)
            if not result.accepted:
                await self.send({"type": "rejected", "id": identifier, "text": text})
                return
            if isinstance(result, _HelpResult):
                await self.dialog(
                    "Help", self.session.ctui.format_ui_help(result.target), ["OK"]
                )
            elif result.dialog_title:
                await self.dialog(result.dialog_title, result.output, ["OK"])
            else:
                if result.exit_requested:
                    await self.send({"type": "session-ended", "close_tab": True})
                self.session.apply_result(result)
            await self.send({"type": "finished", "id": identifier})
        except Exception as error:
            await self.send(
                {
                    "type": "error",
                    "id": identifier,
                    "text": text,
                    "position": getattr(error, "position", len(text)),
                    "message": (
                        str(error)
                        if isinstance(error, CommandError)
                        else traceback.format_exc()
                    ),
                }
            )
        finally:
            self.session.invalidate()

    async def complete(self, message):
        """Use the same async providers and quote-aware replacements as the TUI."""
        text = message["text"]
        cursor = message.get("cursor", len(text))
        if not isinstance(cursor, int) or not 0 <= cursor <= len(text):
            return
        items = []
        async for item in self.session.ctui.layout.completer.get_completions_async(
            Document(text, cursor), CompleteEvent(completion_requested=True)
        ):
            items.append(
                {
                    "text": item.text,
                    "start": item.start_position,
                    "display": plain(item.display),
                    "help": plain(item.display_meta),
                }
            )
            if len(items) >= 100:
                break
        await self.send({"type": "completion", "id": message.get("id"), "items": items})

    async def handle(self, message):
        """Validate incoming actions before touching shared state."""
        if not isinstance(message, dict):
            raise ValueError("Messages must be objects")
        kind = message.get("type")
        if kind in ("command", "complete"):
            text = message.get("text")
            if not isinstance(text, str) or len(text) > 16384:
                raise ValueError("Command text must be at most 16384 characters")
            if kind == "command" and text.strip():
                if len(self.session.actions) >= 32:
                    await self.send(
                        {
                            "type": "error",
                            "id": message.get("id"),
                            "text": text,
                            "message": "Too many pending actions; wait for a command to finish.",
                        }
                    )
                else:
                    self.spawn(self.command(text, message.get("id")), persistent=True)
            elif kind == "complete":
                if self.completion_task:
                    self.completion_task.cancel()
                self.completion_task = self.spawn(self.complete(message))
        elif kind == "answer":
            future = self.dialogs.get(message.get("id"))
            button = message.get("button")
            count, cancel = self.dialog_buttons.get(message.get("id"), (0, None))
            if (
                future
                and not future.done()
                and type(button) is int
                and (0 <= button < count or button == cancel)
            ):
                text = message.get("text", "")
                if not isinstance(text, str) or len(text) > 16384:
                    raise ValueError("Invalid dialog input")
                future.set_result({**message, "text": text})
        elif kind == "clear":
            self.session.ctui.layout.set_output("")
            self.session.invalidate()
        elif kind == "exit":
            self.session.exit()
        elif kind == "shortcut":
            if len(self.session.actions) >= 32:
                return
            keys = message.get("keys")
            for registered, handler, _ in self.session.ctui.shortcuts:
                if list(registered) == keys:
                    self.spawn(self.session.invoke(handler), persistent=True)
                    break
        elif kind in ("button", "edit"):
            if len(self.session.actions) >= 32:
                return
            control = self.session.layout.controls.get(message.get("id"))
            if kind == "button" and control is not None and hasattr(control, "handler"):
                if control.handler:
                    self.spawn(self.session.invoke(control.handler), persistent=True)
            elif (
                kind == "edit"
                and control is not None
                and hasattr(control, "set_document")
            ):
                text = message.get("text")
                if isinstance(text, str) and len(text) <= 16384:
                    control.text = text
                    self.session.invalidate()


class WebSession:
    """Async runtime facade supporting existing invalidate/exit/task calls.

    Not a running prompt-toolkit Application. on_ready runs after layout and this
    facade exist. Existing widgets remain available through CtuiApp.layout;
    custom code that accesses prompt-toolkit renderer internals is terminal-only.
    """

    is_running = False

    def __init__(
        self,
        ctui,
        *,
        host="127.0.0.1",
        port=8080,
        cert=None,
        key=None,
        token=None,
        stdout=None,
    ):
        self.ctui, self.host, self.port = ctui, host, port
        self.cert, self.key = cert, key
        self.access_token = token or secrets.token_urlsafe(32)
        self.cookie = secrets.token_urlsafe(32)
        self.cookie_name = "ctui_" + secrets.token_hex(8)
        self.stdout = stdout or sys.stdout
        self.clients, self.tasks, self.actions = set(), set(), set()
        self.dirty, self.stopped = asyncio.Event(), asyncio.Event()
        self.loop = asyncio.get_running_loop()
        self.layout = None
        self.url = None
        self.runner = None

    def invalidate(self):
        """Request a coalesced redraw, including from a worker thread."""
        self.loop.call_soon_threadsafe(self.dirty.set)

    def exit(self, *args, **kwargs):
        """Request graceful session shutdown for every attached view."""
        self.loop.call_soon_threadsafe(self.stopped.set)

    def create_background_task(self, coroutine):
        """Track application-owned background work for cancellation on shutdown."""
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)

        def done(completed):
            self.tasks.discard(completed)
            if not completed.cancelled() and completed.exception() is not None:
                error = completed.exception()
                logging.getLogger(__name__).error(
                    "Web background task failed",
                    exc_info=(type(error), error, error.__traceback__),
                )
                for client in tuple(self.clients):
                    client.update(
                        {
                            "type": "notice",
                            "message": f"Background task failed: {error}",
                        }
                    )

        task.add_done_callback(done)
        return task

    def apply_result(self, result):
        """Apply output at completion time, matching terminal append semantics."""
        if result.clear_output:
            self.ctui.layout.set_output("")
        elif result.output is not None:
            output = result.output
            current = self.ctui.layout.output_field.text
            if result.append_output and current:
                output = f"{current.rstrip()}\n{output}"
            self.ctui.layout.set_output(output)
        if result.exit_requested:
            self.exit()
        self.invalidate()

    async def invoke(self, handler):
        """Run widget/shortcut callbacks with async support and error containment."""
        try:
            result = handler()
            if inspect.isawaitable(result):
                await result
        except Exception as error:
            client = web_client.get()
            if client:
                await client.dialog(
                    "Error",
                    (
                        str(error)
                        if isinstance(error, CommandError)
                        else traceback.format_exc()
                    ),
                    ["OK"],
                )
            else:
                raise
        finally:
            self.invalidate()

    def snapshot(self):
        """Produce a complete state for new/reconnecting views and invalidations."""
        return {
            "type": "state",
            "name": self.ctui.name,
            "theme": self.ctui.theme,
            "layout": self.layout.snapshot(),
            "shortcuts": [list(keys) for keys, _, _ in self.ctui.shortcuts],
        }

    async def redraw(self):
        """Broadcast snapshots without blocking on individual socket writes."""
        while True:
            await self.dirty.wait()
            self.dirty.clear()
            await asyncio.sleep(0.02)
            try:
                snapshot = self.snapshot()
            except Exception:
                snapshot = {"type": "notice", "message": traceback.format_exc()}
            for client in tuple(self.clients):
                client.update(snapshot)

    async def start(self):
        """Build the shared layout and start the authenticated server."""
        from aiohttp import WSMsgType, web

        if bool(self.cert) != bool(self.key):
            raise CommandError("Web TLS requires both certificate and key")
        if not is_loopback(self.host) and not self.cert:
            raise CommandError("Remote web access requires a certificate and key")
        if len(self.access_token) < 24:
            raise CommandError("Web access tokens must contain at least 24 characters")
        context = None
        if self.cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.cert, self.key)
        self.ctui.layout = CtuiLayout(self.ctui)
        root = self.ctui.compose() or self.ctui.layout.root_container
        self.layout = WebLayout(self.ctui, root)
        self.ctui.app = self
        self.snapshot()  # Fail unsupported custom layouts before opening a port.

        @web.middleware
        async def security(request, handler):
            if is_loopback(self.host) and not is_loopback(request.url.host):
                raise web.HTTPForbidden(text="Invalid host")
            origin = request.headers.get("Origin")
            if origin and origin != f"{request.scheme}://{request.host}":
                raise web.HTTPForbidden(text="Invalid origin")
            response = await handler(request)
            if not isinstance(response, web.WebSocketResponse):
                response.headers.update(
                    {
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer",
                        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                    }
                )
            return response

        async def asset(request):
            name = request.match_info.get("asset", "index.html")
            if name not in ("index.html", "app.js", "style.css"):
                raise web.HTTPNotFound()
            return web.Response(
                body=(ASSETS / name).read_bytes(),
                content_type={
                    "index.html": "text/html",
                    "app.js": "application/javascript",
                    "style.css": "text/css",
                }[name],
            )

        async def login(request):
            try:
                data = await request.json()
            except (ValueError, UnicodeError):
                raise web.HTTPBadRequest(text="Invalid JSON") from None
            token = data.get("token") if isinstance(data, dict) else None
            if not isinstance(token, str) or not secrets.compare_digest(
                token.encode(), self.access_token.encode()
            ):
                raise web.HTTPUnauthorized(text="Invalid session token")
            response = web.json_response({"ok": True})
            response.set_cookie(
                self.cookie_name,
                self.cookie,
                httponly=True,
                secure=bool(context),
                samesite="Strict",
            )
            return response

        async def websocket(request):
            cookie = request.cookies.get(self.cookie_name, "")
            if not secrets.compare_digest(cookie.encode(), self.cookie.encode()):
                raise web.HTTPUnauthorized()
            socket = web.WebSocketResponse(heartbeat=30, max_msg_size=65536)
            await socket.prepare(request)
            client = WebClient(self, socket)
            self.clients.add(client)
            sender = asyncio.create_task(client.sender())
            client.update(self.snapshot())
            try:
                async for message in socket:
                    if message.type == WSMsgType.TEXT:
                        try:
                            await client.handle(json.loads(message.data))
                        except (ValueError, TypeError, KeyError):
                            await socket.close(code=1008, message=b"Invalid message")
                            break
            finally:
                self.clients.discard(client)
                for future in tuple(client.dialogs.values()):
                    future.cancel()
                pending = [sender, *client.tasks]
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            return socket

        server = web.Application(middlewares=[security], client_max_size=65536)
        server.router.add_get("/", asset)
        server.router.add_get("/{asset:app.js|style.css}", asset)
        server.router.add_post("/login", login)
        server.router.add_get("/ws", websocket)
        self.runner = web.AppRunner(server, access_log=None)
        await self.runner.setup()
        bind_host = "127.0.0.1" if self.host.lower() == "localhost" else self.host
        site = web.TCPSite(self.runner, bind_host, self.port, ssl_context=context)
        await site.start()
        self.port = self.runner.addresses[0][1]
        address = self.host
        if address in ("0.0.0.0", "::"):
            address = "localhost"
        if ":" in address:
            address = f"[{address}]"
        self.url = f"{'https' if context else 'http'}://{address}:{self.port}/"
        self.create_background_task(self.redraw())
        print(
            f"{self.ctui.name} web session: {self.url}#token={quote(self.access_token, safe='')}",
            file=self.stdout,
            flush=True,
        )
        print(
            "Open this address in a browser. Ctrl-C stops the session.",
            file=self.stdout,
            flush=True,
        )

    async def close(self):
        """Disconnect views and cancel runtime work before application cleanup."""
        for client in tuple(self.clients):
            for task in tuple(client.tasks):
                task.cancel()
            await client.socket.close(code=1001, message=b"Session stopped")
        pending = (*self.tasks, *self.actions)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if self.runner:
            await self.runner.cleanup()
        if self.layout:
            self.layout.close()
        if getattr(self.ctui, "app", None) is self:
            del self.ctui.app
