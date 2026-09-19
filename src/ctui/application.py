"""Application lifecycle and the shared UI/CLI command dispatcher.

CtuiApp owns registration and services; presentation delegates to layout,
keybindings, and help. Headless dispatch uses the same parsing and validation
path as either interface, enabling terminal-free application tests.
"""

from __future__ import annotations

import inspect
import shlex
import sys
from pathlib import Path
from typing import TextIO

from prompt_toolkit.application import Application
from prompt_toolkit.layout.layout import Layout

from ctui.commands import (
    CommandError,
    CommandResult,
    Commands,
    CommandValidationError,
    ConfirmationRequired,
    _token_starts,
    register_default_commands,
)
from ctui.events import EventBus
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout
from ctui.services import MemoryHistory, NullStorage
from ctui.style import CtuiStyle


class CtuiApp:
    """Base class for synchronous or asynchronous terminal applications.

    Define commands with @command on ordinary methods; use self.events for custom
    events and ordinary instance attributes for clients, sockets, and running tasks.
    Named persistent profiles belong in configs and protocol traffic in records.
    A stable app_id enables the default SQLite project backend; individual services
    remain replaceable. Construction registers commands but does not open databases
    or create terminal resources.

    run() automatically selects full-screen or CLI mode. Call run_async() or
    run_cli() inside an existing event loop, or dispatch() for headless execution.
    Override sync or async lifecycle hooks for resources owned by your application.
    Commands must return str or CommandResult; use CommandResult.success() when
    there is no output. Sync handlers execute on the calling event loop, so move
    blocking work to a worker explicitly.

    Set statusbar to text or a zero-argument callable returning text. It is read
    on redraw rather than polled on a timer; call self.app.invalidate() after
    background state changes while the UI is running. Mouse capture defaults off
    so terminal selection and clipboard shortcuts work while input keeps focus.
    Customize name, version, description, prompt, interface help introductions,
    and compose() on the subclass.
    """

    name, version, prompt = "MyApp", "0.1.0", "> "
    description = "MyApp description (make sure to set name, version, and description"
    cli_help_intro = "Run without arguments to open the interactive UI."
    ui_help_intro = (
        "Type commands in the input window; results appear in the output window."
    )
    help_message = "Currently supported commands:"
    wrap_lines = False
    mouse_support = False
    app_id = None
    project_schema_version = 1
    project_migrations = {}

    def __init__(
        self,
        *,
        name=None,
        version=None,
        description=None,
        prompt=None,
        history=None,
        storage=None,
        backend=None,
        configs=None,
        records=None,
        app_id=None,
        app_author=None,
        data_dir=None,
        theme="dark",
        register_defaults=True,
    ):
        """Configure services, register commands, and initialize app state.

        Args:
            name: Optional instance-specific application name.
            version: Optional instance-specific version string.
            description: Optional description shown in help.
            prompt: Text displayed before command input.
            history: Override project history, or in-memory history without a backend.
            storage: Key-value backend; defaults to discarded storage.
            backend: Optional project backend; SQLite is used when app_id is set.
            configs: Optional named-configuration repository override.
            records: Optional protocol-record repository override.
            app_id: Stable identifier used for default project storage.
            app_author: Optional platform-specific application author.
            data_dir: Optional project-data directory override.
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
        if app_id is not None:
            self.app_id = app_id
        self.commands, self.events = Commands(), EventBus()
        self.backend = backend
        if self.backend is None and self.app_id:
            from ctui.projects import SqliteProjectBackend

            self.backend = SqliteProjectBackend(
                self.app_id,
                app_author=app_author,
                data_dir=data_dir,
                tool_version=self.version,
                tool_schema_version=self.project_schema_version,
                tool_migrations=self.project_migrations,
            )
        self.history = (
            history
            if history is not None
            else (self.backend.history if self.backend is not None else MemoryHistory())
        )
        self.configs = (
            configs
            if configs is not None
            else (self.backend.configs if self.backend is not None else None)
        )
        self.records = (
            records
            if records is not None
            else (self.backend.records if self.backend is not None else None)
        )
        self.storage = storage if storage is not None else NullStorage()
        self.theme = theme
        self.statusbar = lambda: self.name
        self.output_text = ""
        self.shortcuts = []
        if register_defaults:
            register_default_commands(self)
            if self.backend is not None:
                from ctui.projects import register_project_commands

                register_project_commands(self)
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
        """Resolve the current application-defined status-bar text.

        Evaluate callables on each access; return their value as text. This getter
        does not schedule refreshes or await asynchronous providers.
        """
        value = self.statusbar() if callable(self.statusbar) else self.statusbar
        return str(value)

    def on(self, event, handler=None):
        """Register an event listener, directly or as a decorator."""
        return self.events.on(event, handler)

    def add_shortcut(self, *keys, handler, description=""):
        """Register an application-wide keyboard shortcut.

        Args:
            *keys: One or more prompt-toolkit key names, such as ``"f2"`` or
                ``"c-t"``. Multiple values form a key sequence.
            handler: Synchronous or asynchronous zero-argument callable.
            description: Optional human-readable explanation.

        Register before the UI is built. Bindings apply application-wide, including
        while a dialog is focused. Descriptions appear in UI help. Awaitable handler
        results are scheduled as prompt-toolkit background tasks.
        """
        if not keys:
            raise ValueError("A shortcut requires at least one key")
        if not callable(handler):
            raise TypeError("A shortcut handler must be callable")
        self.shortcuts.append((tuple(keys), handler, description))

    async def _hook(self, func):
        """Call a lifecycle hook and await it when necessary."""
        result = func()
        return await result if inspect.isawaitable(result) else result

    async def on_start(self):
        """Initialize application resources after the project backend opens.

        Called in UI and CLI execution before any commands. May be sync or async.
        The framework closes services if this hook fails, but calls on_stop only
        when on_start has completed successfully.
        """
        pass

    async def on_ready(self):
        """Initialize UI-dependent resources after layout and app are constructed.

        Called only in full-screen mode, before the prompt-toolkit run loop begins.
        May be sync or async; CLI execution does not create widgets or call this hook.
        """
        pass

    async def on_stop(self):
        """Release application resources before framework services close.

        Called in either execution mode if on_start completed, including after a
        later failure. May be sync or async. Storage and an opened project backend
        are still closed if this hook raises.
        """
        pass

    def compose(self):
        """Return a prompt-toolkit root container, or None for the standard UI.

        self.layout already exists here. Reuse its input_field so the framework can
        focus command input. ctui.widgets supplies supported building blocks, and
        self.layout.body includes the default panes and completion float. Dialogs
        require a root container exposing a floats list to show_dialog().
        """
        return None

    def format_help(self, target=""):
        """Return the shared reference for a command or its immediate children.

        An empty target lists root commands/groups. Targets accept names, aliases,
        and unique prefixes; invalid or ambiguous targets raise CommandNotFound.
        This reference excludes welcome text and interface guidance.
        """
        from ctui.help import command_help

        return command_help(self, target)

    def format_ui_help(self, target=""):
        """Return welcome text, UI guidance, and the shared command reference.

        A nonempty target returns only detailed command help. The UI presenter puts
        this text in a modal popup, preserving the main output.
        """
        from ctui.help import ui_guidance

        reference = self.format_help(target)
        if target:
            return reference
        return (
            f"{self.welcome}\n\n{self.ui_help_intro}\n\n"
            f"{ui_guidance(self)}\n\n{reference}"
        )

    def format_cli_help(self, program=None, target=""):
        """Return welcome text, CLI usage and guidance, then the command reference.

        program controls the executable name in usage examples. A nonempty target
        returns only detailed command help, without the welcome or introduction.
        """
        if target:
            return self.format_help(target)
        program = program or Path(sys.argv[0]).name
        usage = [
            self.welcome,
            "",
            f"Usage: {program} [help | -h | --help]",
            f"       {program} [-c COMMAND | --command COMMAND] ...",
            f"       {program} [-f FILE | --file FILE] ...",
            "",
            self.cli_help_intro,
            "",
            "Terminal options:",
            "  -c, --command COMMAND  Run a command; may be repeated.",
            "  -f, --file FILE        Run nonblank commands from a file in order.",
            "  -h, --help             Print this help page.",
            f'  Example: {program} -c "help history export"',
            "",
        ]
        return "\n".join(usage) + "\n" + self.format_help()

    @staticmethod
    def format_command_error(text, error):
        """Format a command, source-position caret, and error message."""
        position = getattr(error, "position", None)
        position = 0 if position is None else max(0, min(position, len(text)))
        return f"{text}\n{' ' * position}^\nError: {error}"

    async def dispatch(self, text, *, confirmed=False, confirm_callback=None):
        """Parse and execute one command without requiring a terminal.

        text is the complete command line. This method does not open services or
        run lifecycle hooks; callers using a persistent backend must open it first.
        Aliases and unique command/choice prefixes resolve before typed conversion.
        Argument error offsets are mapped back to the originally submitted text.

        Confirmation uses the command's format string and parsed arguments. Pass
        confirmed=True, append a trailing ``confirm`` token, or supply a sync/async
        confirm_callback(message). Without approval machinery, raise
        ConfirmationRequired. A declined callback returns CommandResult.rejected()
        without executing or recording the command.

        Emit command_submitted(text=...) before resolution, then
        command_started(command=..., arguments=...) after validation and approval.
        Normalize str to CommandResult; other return values besides CommandResult
        raise TypeError. Accepted results are recorded when record_history is true,
        then emit command_finished(command=..., result=...). Rejected results do
        neither. Exceptions from the execution/result/history/finished-event stage
        emit command_failed(command=...) and propagate; parse and confirmation
        failures occur before that stage. Listener errors also propagate.

        Return the normalized result. Presentation, including output updates and
        exit requests, belongs to the caller; this method does not serialize
        concurrent calls or render widgets.
        """
        await self.events.emit("command_submitted", text=text)
        item, argument_text = self.commands.resolve(text)
        if item.confirmation:
            tokens = argument_text.rsplit(None, 1)
            if tokens and tokens[-1] == "confirm":
                argument_text = tokens[0] if len(tokens) == 2 else ""
                confirmed = True
        source_starts = _token_starts(text)
        argument_starts = source_starts[len(item.name.split()) :]
        try:
            if getattr(item.func, "__ctui_help__", False):
                try:
                    kwargs = {"target": " ".join(shlex.split(argument_text))}
                except ValueError as error:
                    raise CommandValidationError(str(error)) from error
            else:
                argument_text = await item.expand_unique_arguments(argument_text, self)
                kwargs = item.parse_args(argument_text)
        except CommandValidationError as error:
            expanded_starts = _token_starts(argument_text)
            if error.position is not None and error.position >= len(argument_text):
                error.position = len(text)
            elif error.position is not None and argument_starts:
                token_number = (
                    sum(start <= error.position for start in expanded_starts) - 1
                )
                token_number = max(0, min(token_number, len(argument_starts) - 1))
                error.position = argument_starts[token_number]
            elif error.position is not None:
                error.position = len(text)
            raise
        if item.confirmation and not confirmed:
            try:
                message = item.confirmation.format(**kwargs)
            except (KeyError, ValueError, IndexError, AttributeError) as error:
                raise CommandError(f"Invalid confirmation template: {error}") from error
            if confirm_callback is None:
                raise ConfirmationRequired(message)
            approved = confirm_callback(message)
            approved = await approved if inspect.isawaitable(approved) else approved
            if not approved:
                return CommandResult.rejected()
        try:
            await self.events.emit("command_started", command=item, arguments=kwargs)
            raw = await item.execute(app=self, raw_input=text, **kwargs)
            if isinstance(raw, CommandResult):
                result = raw
            elif isinstance(raw, str):
                result = CommandResult(output=raw)
            else:
                raise TypeError(
                    f'Command "{item.name}" must return str or CommandResult, '
                    f"not {type(raw).__name__}"
                )
            if result.accepted:
                if item.record_history:
                    appended = self.history.append(text)
                    if inspect.isawaitable(appended):
                        await appended
                await self.events.emit("command_finished", command=item, result=result)
            return result
        except Exception:
            await self.events.emit("command_failed", command=item)
            raise

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
            mouse_support=self.mouse_support,
            full_screen=True,
        )

    async def _close_runtime(self, backend_opened):
        """Close configured services, preserving backend cleanup on failure."""
        try:
            closed = self.storage.close()
            if inspect.isawaitable(closed):
                await closed
        finally:
            if backend_opened:
                await self.backend.close()

    async def run_async(self):
        """Run the full-screen application in the caller's event loop.

        Open the backend, call on_start, build the UI, call on_ready, and await the
        terminal application. On exit or failure, call on_stop if startup completed,
        then close storage and the opened backend. Return prompt-toolkit's result.
        """
        backend_opened = False
        started = False
        try:
            if self.backend is not None:
                backend_opened = True
                await self.backend.open()
            await self._hook(self.on_start)
            started = True
            self._build_application()
            await self._hook(self.on_ready)
            return await self.app.run_async()
        finally:
            try:
                if started:
                    await self._hook(self.on_stop)
            finally:
                await self._close_runtime(backend_opened)

    @staticmethod
    def _parse_cli_operations(arguments):
        """Parse ordered command and file operations without losing their order."""
        operations = []
        index = 0
        while index < len(arguments):
            token = arguments[index]
            if token == "help" and index + 1 < len(arguments):
                return False, [
                    ("command", "help " + shlex.join(arguments[index + 1 :]))
                ]
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

    async def run_cli(
        self,
        arguments,
        *,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        program=None,
    ):
        """Execute terminal arguments sequentially and return an exit status.

        Accept help/-h/--help, targeted ``help COMMAND``, and repeatable -c/--command
        or -f/--file operations in supplied order, including long-option equals
        forms. Files are UTF-8; skip blank lines and lines beginning with #.
        Read all command files before starting execution. Main help returns without
        opening services; command execution opens the backend and runs on_start and
        on_stop, but never on_ready.

        Print non-None result output to stdout. Stop at an exit request or the first
        error. Return 0 on success, 2 for command/argument/type or file-opening
        errors, and 1 for unexpected exceptions during dispatch. Startup/shutdown
        exceptions propagate. Command errors include a source caret and help on
        stderr. Streams and the displayed program name can be supplied for testing.
        """
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

        backend_opened = False
        started = False
        try:
            if self.backend is not None:
                backend_opened = True
                await self.backend.open()
            await self._hook(self.on_start)
            started = True
            for text in commands:
                try:
                    result = await self.dispatch(text)
                except (CommandError, TypeError) as error:
                    print(f"{self.format_command_error(text, error)}\n", file=stderr)
                    print(self.format_cli_help(program), file=stderr)
                    return 2
                except Exception as error:  # Application code failed unexpectedly.
                    print(
                        f"Error: Unexpected {type(error).__name__}: {error}",
                        file=stderr,
                    )
                    return 1
                if result.output is not None:
                    print(result.output, file=stdout)
                if result.exit_requested:
                    break
            return 0
        finally:
            try:
                if started:
                    await self._hook(self.on_stop)
            finally:
                await self._close_runtime(backend_opened)

    def run(self, argv=None):
        """Open the UI without arguments, otherwise run terminal operations.

        Use sys.argv[1:] when argv is omitted. This synchronous entry point owns an
        event loop via asyncio.run; use run_async/run_cli inside an existing loop.
        UI mode returns the terminal result; CLI mode raises SystemExit with its
        status so application scripts need no separate argument parser.
        """
        import asyncio

        arguments = list(sys.argv[1:] if argv is None else argv)
        if not arguments:
            return asyncio.run(self.run_async())
        raise SystemExit(asyncio.run(self.run_cli(arguments)))

    def exit(self):
        """Request termination when the terminal application is running."""
        if hasattr(self, "app"):
            self.app.exit()
