"""The event-driven ctui application."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, TextIO

from prompt_toolkit.application import Application
from prompt_toolkit.layout.layout import Layout

from ctui.commands import (
    CommandError,
    CommandResult,
    Commands,
    CommandValidationError,
    _token_starts,
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
    help_message = "Currently supported commands:"
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
        self.theme = theme
        self.statusbar = lambda: self.name
        self.output_text = ""
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
        """Resolve the current application-defined status-bar text."""
        value = self.statusbar() if callable(self.statusbar) else self.statusbar
        return str(value)

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

    def format_help(self):
        """Return application help shared by the UI and terminal modes."""
        return "\n".join(
            [self.welcome, "", self.help_message, ""]
            + [f"{item.name:<20} {item.desc}" for item in self.commands]
        )

    def format_cli_help(self, program=None):
        """Return terminal usage followed by the standard application help."""
        program = program or Path(sys.argv[0]).name
        usage = [
            f"Usage: {program} [help | -h | --help]",
            f"       {program} [-c COMMAND | --command COMMAND] ...",
            f"       {program} [-f FILE | --file FILE] ...",
            "",
            "Terminal options:",
            "  -c, --command COMMAND  Run a command; may be repeated.",
            "  -f, --file FILE        Run nonblank commands from a file in order.",
            "  -h, --help             Print this help page.",
            "",
        ]
        return "\n".join(usage) + "\n" + self.format_help()

    @staticmethod
    def format_command_error(text, error):
        """Format a command, source-position caret, and error message."""
        position = getattr(error, "position", None)
        position = 0 if position is None else max(0, min(position, len(text)))
        return f"{text}\n{' ' * position}^\nError: {error}"

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
        source_starts = _token_starts(text)
        argument_starts = source_starts[len(item.name.split()) :]
        try:
            argument_text = await item.expand_unique_arguments(argument_text, self)
            kwargs = item.parse_args(argument_text)
        except CommandValidationError as error:
            expanded_starts = _token_starts(argument_text)
            if error.position is not None and error.position >= len(argument_text):
                error.position = len(text)
            elif error.position is not None and argument_starts:
                token_number = sum(
                    start <= error.position for start in expanded_starts
                ) - 1
                token_number = max(0, min(token_number, len(argument_starts) - 1))
                error.position = argument_starts[token_number]
            elif error.position is not None:
                error.position = len(text)
            raise
        await self.events.emit("command_started", command=item, arguments=kwargs)
        try:
            raw = await item.execute(app=self, raw_input=text, **kwargs)
        except CommandError:
            await self.events.emit("command_failed", command=item)
            raise
        if isinstance(raw, CommandResult):
            result = raw
        elif isinstance(raw, str):
            result = CommandResult(output=str(raw))
        else:
            raise TypeError(
                f'Command "{item.name}" must return str or CommandResult, '
                f"not {type(raw).__name__}"
            )
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

    @staticmethod
    def _parse_cli_operations(arguments):
        """Parse ordered command and file operations without losing their order."""
        operations = []
        index = 0
        while index < len(arguments):
            token = arguments[index]
            if token in ("help", "-h", "--help"):
                return True, []
            if token.startswith("--command="):
                operations.append(("command", token.split("=", 1)[1]))
            elif token.startswith("--file="):
                operations.append(("file", token.split("=", 1)[1]))
            elif token in ("-c", "--command", "-f", "--file"):
                if index + 1 >= len(arguments):
                    raise CommandError(f"{token} requires a value")
                index += 1
                kind = "command" if token in ("-c", "--command") else "file"
                operations.append((kind, arguments[index]))
            else:
                raise CommandError(
                    f"Unknown terminal argument: {token!r}; use -c or --command"
                )
            index += 1
        return False, operations

    async def run_cli(self, arguments, *, stdout: TextIO | None = None,
                      stderr: TextIO | None = None, program=None):
        """Execute terminal arguments and return a conventional exit status."""
        stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
        try:
            show_help, operations = self._parse_cli_operations(list(arguments))
        except CommandError as error:
            print(f"Error: {error}\n", file=stderr)
            print(self.format_cli_help(program), file=stderr)
            return 2
        if show_help:
            print(self.format_cli_help(program), file=stdout)
            return 0
        commands = []
        try:
            for kind, value in operations:
                if kind == "command":
                    commands.append(value)
                    continue
                path = Path(value).expanduser()
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        commands.append(line)
        except OSError as error:
            print(f"Error: {error}\n", file=stderr)
            print(self.format_cli_help(program), file=stderr)
            return 2

        await self._hook(self.on_start)
        try:
            for text in commands:
                try:
                    result = await self.dispatch(text)
                except (CommandError, TypeError) as error:
                    print(f"{self.format_command_error(text, error)}\n", file=stderr)
                    print(self.format_cli_help(program), file=stderr)
                    return 2
                if result.output is not None:
                    print(result.output, file=stdout)
                if result.exit_requested:
                    break
            return 0
        finally:
            await self._hook(self.on_stop)
            self.storage.close()

    def run(self, argv=None):
        """Open the UI without arguments, otherwise run terminal operations."""
        import asyncio

        arguments = list(sys.argv[1:] if argv is None else argv)
        if not arguments:
            return asyncio.run(self.run_async())
        raise SystemExit(asyncio.run(self.run_cli(arguments)))

    def exit(self):
        """Request termination when the terminal application is running."""
        if hasattr(self, "app"):
            self.app.exit()
