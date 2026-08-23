"""The event-driven ctui application."""

from __future__ import annotations
import inspect
from typing import Any
from prompt_toolkit.application import Application
from prompt_toolkit.layout.layout import Layout
from ctui.commands import (
    CommandError,
    CommandResult,
    Commands,
    register_default_commands,
)
from ctui.events import EventBus
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout
from ctui.services import MemoryHistory, NullStorage
from ctui.style import CtuiStyle


class CtuiApp:
    """Base class for synchronous or asynchronous terminal applications."""

    name, version, description = "MyApp", "0.1.0", "My App does something..."
    prompt = "> "
    help_message = "Commands go on top, results appear on the bottom."
    wrap_lines = False

    def __init__(
        self,
        *,
        name=None,
        version=None,
        description=None,
        prompt=None,
        history=None,
        storage=None,
        theme="dark",
        register_defaults=True,
    ):
        """Configure services, register commands, and initialize app state.

        Args:
            name: Optional instance-specific application name.
            version: Optional instance-specific version string.
            description: Optional description shown in help.
            prompt: Text displayed before command input.
            history: History backend; defaults to in-memory history.
            storage: Key-value backend; defaults to discarded storage.
            theme: Built-in theme name, either ``"dark"`` or ``"light"``.
            register_defaults: Whether to install standard commands.
        """
        if name is not None:
            self.name = name
        if version is not None:
            self.version = version
        if description is not None:
            self.description = description
        if prompt is not None:
            self.prompt = prompt
        self.commands, self.events = Commands(), EventBus()
        self.history = history if history is not None else MemoryHistory()
        self.storage = storage if storage is not None else NullStorage()
        self.theme, self.project_name = theme, "default"
        self.footer, self.statusbar, self.output_text = "", None, ""
        if register_defaults:
            register_default_commands(self)
        self._register_class_commands()

    def _register_class_commands(self):
        """Register decorated methods inherited by this application."""
        discovered = {}
        for cls in reversed(type(self).mro()):
            for name, value in vars(cls).items():
                if hasattr(value, "__ctui_command__"):
                    discovered[name] = value.__ctui_command__
        for name, meta in discovered.items():
            self.commands.register(getattr(self, name), **meta)

    @property
    def welcome(self):
        """Return the generated application welcome text."""
        return f"Welcome to {self.name} {self.version}\n\n{self.description}"

    @property
    def _statusbar(self):
        """Resolve the current status-bar text, including legacy footers."""
        if self.statusbar is not None:
            value = self.statusbar() if callable(self.statusbar) else self.statusbar
            return str(value)
        value = self.footer() if callable(self.footer) else self.footer
        return f"Project: {self.project_name}" + (f"  {value}" if value else "")

    def command(self, func=None, **options):
        """Register a function as a command, directly or as a decorator."""
        return self.commands.register(func, **options)

    def on(self, event, handler=None):
        """Register an event listener, directly or as a decorator."""
        return self.events.on(event, handler)

    async def _hook(self, func):
        """Call a lifecycle hook and await it when necessary."""
        result = func()
        return await result if inspect.isawaitable(result) else result

    async def on_start(self):
        """Run before terminal resources are constructed."""
        pass

    async def on_ready(self):
        """Run after terminal resources are ready and before input begins."""
        pass

    async def on_stop(self):
        """Run during shutdown before the storage backend closes."""
        pass

    def compose(self):
        """Return a prompt_toolkit root container, or None for the standard UI."""
        return None

    async def dispatch(self, text):
        """Parse and execute one command without requiring a terminal.

        Args:
            text: Complete command line, including arguments.

        Returns:
            The normalized :class:`~ctui.commands.CommandResult`.

        Raises:
            CommandNotFound: If no command or alias matches the input.
            CommandValidationError: If argument conversion or validation fails.
            CommandError: If the command reports another user-facing failure.
        """
        await self.events.emit("command_submitted", text=text)
        item, argument_text = self.commands.resolve(text)
        kwargs = item.parse_args(argument_text)
        await self.events.emit("command_started", command=item, arguments=kwargs)
        try:
            raw = await item.execute(app=self, raw_input=text, **kwargs)
        except CommandError:
            await self.events.emit("command_failed", command=item)
            raise
        if isinstance(raw, CommandResult):
            result = raw
        elif raw is False:
            result = CommandResult.rejected()
        elif raw is None:
            result = CommandResult()
        else:
            result = CommandResult(output=str(raw))
        if result.accepted:
            self.history.append(text)
            await self.events.emit("command_finished", command=item, result=result)
        return result

    def _build_application(self):
        """Construct prompt-toolkit layout, bindings, style, and application."""
        self.layout = CtuiLayout(self)
        root = self.compose() or self.layout.root_container
        style = CtuiStyle()
        style.theme = self.theme
        self.app = Application(
            layout=Layout(root, focused_element=self.layout.input_field),
            key_bindings=get_key_bindings(self),
            style=style.theme,
            enable_page_navigation_bindings=False,
            mouse_support=True,
            full_screen=True,
        )

    async def run_async(self):
        """Run the terminal application in the caller's event loop."""
        await self._hook(self.on_start)
        self._build_application()
        await self._hook(self.on_ready)
        try:
            return await self.app.run_async()
        finally:
            await self._hook(self.on_stop)
            self.storage.close()

    def run(self):
        """Create an event loop and run the application synchronously."""
        import asyncio

        return asyncio.run(self.run_async())

    def exit(self):
        """Request termination when the terminal application is running."""
        if hasattr(self, "app"):
            self.app.exit()


Ctui = CtuiApp
