"""Pythonic, typed and asynchronous command dispatch."""

from __future__ import annotations

import inspect
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import (
    Any,
    Awaitable,
    Callable,
    Iterable,
    Literal,
    Mapping,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)


class CommandError(Exception):
    """An error safe to show to an application user."""


class CommandNotFound(CommandError):
    """Indicate that input did not match a registered command or alias."""
    pass


class CommandValidationError(CommandError):
    """Indicate that command arguments could not be parsed or validated."""
    pass


@dataclass(frozen=True)
class CompletionItem:
    """Describe insertable completion text and its dropdown help message."""
    value: str
    help: str = ""
    display: str | None = None


@dataclass(frozen=True)
class Argument:
    """Completion and validation configuration for one parameter."""

    help: str = ""
    choices: Iterable[Any] | Mapping[Any, str] | None = None
    completer: (
        Callable[
            ["CompletionContext"],
            Iterable[str | CompletionItem] | Awaitable[Iterable[str | CompletionItem]],
        ]
        | None
    ) = None
    validator: Callable[[Any], bool | str | None] | None = None
    metavar: str | None = None


@dataclass(frozen=True)
class CompletionContext:
    """Describe the command-line state supplied to a completion provider."""
    command: "Command"
    parameter: inspect.Parameter
    word: str
    arguments: Mapping[str, Any]
    app: Any = None


@dataclass
class CommandContext:
    """Expose application state and event publication to a running command."""
    app: Any
    command: "Command"
    raw_input: str
    arguments: Mapping[str, Any]

    async def emit(self, event: str, **data: Any) -> None:
        """Publish a custom application event with keyword payload data."""
        await self.app.events.emit(event, **data)


@dataclass(frozen=True)
class CommandResult:
    """Describe how a completed command should affect the user interface."""
    output: str | None = None
    clear_output: bool = False
    exit_requested: bool = False
    accepted: bool = True

    @classmethod
    def success(cls, output: str | None = None):
        """Create an accepted result with optional output text."""
        return cls(output=output)

    @classmethod
    def rejected(cls):
        """Create a result that preserves the user's current input."""
        return cls(accepted=False)


def _name(func):
    """Derive a terminal command name from a Python function name."""
    value = func.__name__
    return (value[3:] if value.startswith("do_") else value).replace("_", " ")


def _convert(value: str, annotation: Any, name: str) -> Any:
    """Convert one textual value according to a parameter annotation.

    Raises:
        CommandValidationError: If conversion fails or a constrained value does
            not match its annotation.
    """
    if annotation in (inspect.Parameter.empty, Any, str):
        return value
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, UnionType) and type(None) in args:
        if value.lower() in ("none", "null"):
            return None
        annotation = next(arg for arg in args if arg is not type(None))
        origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        for choice in args:
            if _convert(value, type(choice), name) == choice:
                return choice
        raise CommandValidationError(
            f"{name} must be one of: {', '.join(map(str, args))}"
        )
    if origin in (list, tuple, set):
        subtype = args[0] if args else str
        return origin(_convert(item, subtype, name) for item in value.split(","))
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        for member in annotation:
            if value in (member.name, str(member.value)):
                return member
        raise CommandValidationError(
            f"{name} must be one of: {', '.join(x.name for x in annotation)}"
        )
    if annotation is bool:
        values = {
            "true": True,
            "yes": True,
            "on": True,
            "1": True,
            "false": False,
            "no": False,
            "off": False,
            "0": False,
        }
        if value.lower() in values:
            return values[value.lower()]
        raise CommandValidationError(f"{name} must be true or false")
    try:
        return Path(value).expanduser() if annotation is Path else annotation(value)
    except (TypeError, ValueError) as error:
        raise CommandValidationError(
            f"{name} must be {getattr(annotation, '__name__', annotation)}: {value!r}"
        ) from error


@dataclass
class Command:
    """Store callable metadata and perform parsing, execution, and completion."""
    func: Callable[..., Any]
    name: str | None = None
    aliases: tuple[str, ...] = ()
    arguments: Mapping[str, Argument] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        """Derive command metadata and validate argument configuration."""
        self.name = self.name or _name(self.func)
        self.string, self.string_parts, self.func_name = (
            self.name,
            self.name.split(),
            self.func.__name__,
        )
        self.desc = (
            self.description
            or ((inspect.getdoc(self.func) or "").splitlines() or [""])[0]
        )
        self.signature = inspect.signature(self.func)
        try:
            self.hints = get_type_hints(self.func)
        except (NameError, TypeError):
            self.hints = {}
        unknown = set(self.arguments) - set(self.signature.parameters)
        if unknown:
            raise ValueError(f"Unknown arguments for {self.name}: {', '.join(unknown)}")

    @property
    def parameters(self):
        """Return user-supplied parameters, excluding ``self`` and ``ctx``."""
        return [
            p
            for p in self.signature.parameters.values()
            if p.name not in ("self", "ctx")
        ]

    @property
    def help(self):
        """Return a compact usage line followed by the command description."""
        args = " ".join(
            ("[" if p.default is not inspect.Parameter.empty else "<")
            + (self.arguments.get(p.name, Argument()).metavar or p.name.upper())
            + ("]" if p.default is not inspect.Parameter.empty else ">")
            for p in self.parameters
        )
        return f"{self.name} {args}\n\n{self.desc}".strip()

    def parse_args(self, text: str, partial: bool = False):
        """Parse and validate command arguments.

        Args:
            text: Argument text following the resolved command name.
            partial: Permit missing or unfinished arguments for completion.

        Returns:
            Parsed keyword arguments. In partial mode, returns those arguments
            together with the parameter currently being entered.

        Raises:
            CommandValidationError: If syntax, conversion, arity, choices, or a
                custom validator rejects the input.
        """
        try:
            tokens = shlex.split(text)
        except ValueError as error:
            raise CommandValidationError(str(error)) from error
        values, positional, pending = {}, [], None
        options = {"--" + p.name.replace("_", "-"): p for p in self.parameters}
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.startswith("--"):
                option, equals, inline = token.partition("=")
                parameter = options.get(option)
                if not parameter:
                    if partial:
                        break
                    raise CommandValidationError(f"Unknown option: {option}")
                annotation = self.hints.get(parameter.name, parameter.annotation)
                if annotation is bool and not equals:
                    values[parameter.name] = True
                elif equals:
                    values[parameter.name] = _convert(
                        inline, annotation, parameter.name
                    )
                elif index + 1 < len(tokens):
                    index += 1
                    values[parameter.name] = _convert(
                        tokens[index], annotation, parameter.name
                    )
                else:
                    pending = parameter
            else:
                positional.append(token)
            index += 1
        available = [p for p in self.parameters if p.name not in values]
        for raw, parameter in zip(positional, available):
            values[parameter.name] = _convert(
                raw,
                self.hints.get(parameter.name, parameter.annotation),
                parameter.name,
            )
        if len(positional) > len(available) and not partial:
            raise CommandValidationError(f"Too many arguments\n\n{self.help}")
        if not partial:
            for parameter in self.parameters:
                if (
                    parameter.name not in values
                    and parameter.default is inspect.Parameter.empty
                ):
                    raise CommandValidationError(
                        f"Missing argument: {parameter.name}\n\n{self.help}"
                    )
                if parameter.name in values:
                    config, value = (
                        self.arguments.get(parameter.name, Argument()),
                        values[parameter.name],
                    )
                    choices = (
                        config.choices.keys()
                        if isinstance(config.choices, Mapping)
                        else config.choices
                    )
                    if choices is not None and str(value) not in {
                        str(x) for x in choices
                    }:
                        raise CommandValidationError(
                            f"{parameter.name} must be one of: {', '.join(map(str, choices))}"
                        )
                    if config.validator:
                        valid = config.validator(value)
                        if valid is False or isinstance(valid, str):
                            raise CommandValidationError(
                                valid
                                if isinstance(valid, str)
                                else f"Invalid {parameter.name}: {value}"
                            )
            return values
        next_parameter = pending or (
            available[len(positional)] if len(positional) < len(available) else None
        )
        return values, next_parameter

    async def execute(self, app=None, raw_input="", **kwargs):
        """Invoke the command and resolve synchronous or awaitable results."""
        call = dict(kwargs)
        if "ctx" in self.signature.parameters:
            call["ctx"] = CommandContext(app, self, raw_input, kwargs)
        result = self.func(**call)
        return await result if inspect.isawaitable(result) else result

    async def complete(self, text: str, word: str, app=None):
        """Return type-checked and validator-approved completion items.

        Args:
            text: Completed argument text before the current word.
            word: Partial word to complete.
            app: Optional application passed to dynamic providers.
        """
        values, parameter = self.parse_args(text, partial=True)
        if word.startswith("--"):
            options = []
            for candidate in self.parameters:
                option = "--" + candidate.name.replace("_", "-")
                if candidate.name not in values and option.startswith(word):
                    config = self.arguments.get(candidate.name, Argument())
                    annotation = self.hints.get(candidate.name, candidate.annotation)
                    type_name = getattr(annotation, "__name__", str(annotation))
                    options.append(
                        CompletionItem(
                            option, config.help or f"{candidate.name}: {type_name}"
                        )
                    )
            return options
        if not parameter:
            return []
        config, annotation = self.arguments.get(
            parameter.name, Argument()
        ), self.hints.get(parameter.name, parameter.annotation)
        items: list[Any] = []
        if isinstance(config.choices, Mapping):
            items += [CompletionItem(str(k), v) for k, v in config.choices.items()]
        elif config.choices is not None:
            items += list(config.choices)
        elif get_origin(annotation) is Literal:
            items += list(get_args(annotation))
        elif inspect.isclass(annotation) and issubclass(annotation, Enum):
            items += [CompletionItem(x.name, str(x.value)) for x in annotation]
        if config.completer:
            generated = config.completer(
                CompletionContext(self, parameter, word, values, app)
            )
            items += list(
                await generated if inspect.isawaitable(generated) else generated
            )
        normalized = [
            x if isinstance(x, CompletionItem) else CompletionItem(str(x))
            for x in items
        ]
        if not normalized and not word.startswith("--"):
            type_name = getattr(annotation, "__name__", str(annotation))
            label = config.metavar or parameter.name.upper()
            detail = config.help or (
                "quoted text may contain spaces" if annotation is str else type_name
            )
            return [CompletionItem("", detail, f"<{label}: {type_name}>")]
        valid = []
        for item in normalized:
            if not item.value.startswith(word):
                continue
            try:
                converted = _convert(item.value, annotation, parameter.name)
            except CommandValidationError:
                continue
            if config.validator:
                verdict = config.validator(converted)
                if verdict is False or isinstance(verdict, str):
                    continue
            valid.append(item)
        return valid

    async def expand_unique_arguments(self, text: str, app=None) -> str:
        """Expand unique prefixes for constrained argument values.

        Free-form strings and numbers remain unchanged. Choices supplied by
        annotations, configuration, or completion providers participate.
        """
        try:
            tokens = shlex.split(text)
        except ValueError as error:
            raise CommandValidationError(str(error)) from error
        expanded: list[str] = []
        for token in tokens:
            prefix = shlex.join(expanded)
            if prefix:
                prefix += " "
            matches = [
                item.value
                for item in await self.complete(prefix, token, app)
                if item.value
            ]
            if len(matches) == 1:
                token = matches[0]
            expanded.append(token)
        return shlex.join(expanded)


class Commands:
    """Register commands and resolve input using longest-prefix matching."""
    def __init__(self):
        """Create an empty command and alias registry."""
        self.commands, self.aliases = {}, {}

    def register(
        self, func=None, *, name=None, aliases=(), arguments=None, description=""
    ):
        """Register a callable, directly or as a configurable decorator.

        Args:
            func: Callable to register when used without parentheses.
            name: Explicit terminal name; otherwise derived from the callable.
            aliases: Alternative names accepted by the resolver.
            arguments: Per-parameter completion and validation configuration.
            description: Explicit help summary overriding the docstring.

        Returns:
            The original callable, allowing normal decorator behavior.
        """
        def decorate(target):
            """Create and store command metadata for a decorated callable."""
            meta = getattr(target, "__ctui_command__", {})
            item = Command(
                target,
                name or meta.get("name"),
                tuple(aliases or meta.get("aliases", ())),
                arguments or meta.get("arguments", {}),
                description or meta.get("description", ""),
            )
            if item.name in self.commands:
                raise ValueError(f"Command already registered: {item.name}")
            self.commands[item.name] = item
            for alias in item.aliases:
                if alias in self.aliases or alias in self.commands:
                    raise ValueError(f"Alias already registered: {alias}")
                self.aliases[alias] = item
            return target

        return decorate(func) if func else decorate

    @property
    def strings(self):
        """Return registered command names in alphabetical order."""
        return sorted(self.commands)

    @property
    def descriptions(self):
        """Map registered command names to their help summaries."""
        return {k: v.desc for k, v in self.commands.items()}

    def resolve(self, text):
        """Return the matching command and its unparsed argument text.

        Raises:
            CommandNotFound: If no registered command or alias matches.
        """
        stripped, all_names = text.strip(), {**self.commands, **self.aliases}
        for name in sorted(all_names, key=lambda x: len(x.split()), reverse=True):
            if stripped == name or stripped.startswith(name + " "):
                return all_names[name], stripped[len(name) :].lstrip()
        try:
            tokens = shlex.split(stripped)
        except ValueError as error:
            raise CommandNotFound(str(error)) from error
        matches = []
        for name, item in all_names.items():
            parts = name.split()
            if len(tokens) >= len(parts) and all(
                part.startswith(token) for token, part in zip(tokens, parts)
            ):
                matches.append((name, item, len(parts)))
        if len({id(item) for _, item, _ in matches}) == 1:
            _, item, count = max(matches, key=lambda match: match[2])
            return item, shlex.join(tokens[count:])
        if matches:
            names = ", ".join(sorted(name for name, _, _ in matches))
            raise CommandNotFound(f"Ambiguous command; matches: {names}")
        raise CommandNotFound(f"Unknown command: {stripped}")

    def extract(self, text):
        """Compatibility helper returning a command and parsed arguments."""
        try:
            item, rest = self.resolve(text)
            return item, item.parse_args(rest)
        except CommandNotFound:
            return None, None

    def __iter__(self):
        """Iterate over commands in registration order."""
        return iter(self.commands.values())

    def __getitem__(self, key):
        """Return the command registered under *key*."""
        return self.commands[key]


def command(func=None, *, name=None, aliases=(), arguments=None, description=""):
    """Mark a class method for automatic registration by ``CtuiApp``.

    The decorator supports both ``@command`` and ``@command(...)`` forms and
    leaves the decorated function callable outside the framework.
    """

    def decorate(target):
        """Attach declarative command metadata to *target*."""
        target.__ctui_command__ = {
            "name": name,
            "aliases": tuple(aliases),
            "arguments": arguments or {},
            "description": description,
        }
        return target

    return decorate(func) if func else decorate


def register_default_commands(app):
    """Install the standard clear, help, history, and exit commands."""
    @app.command
    def clear():
        """Clear the output."""
        return CommandResult(clear_output=True)

    @app.command
    def help():
        """Show application help."""
        return "\n".join(
            [app.welcome, "", app.help_message, ""]
            + [f"{c.name:<20} {c.desc}" for c in app.commands]
        )

    @app.command
    def history(count: int = 0):
        """Show recent command history."""
        entries = app.history.all()
        entries = entries[-count:] if count else entries
        return "\n".join(x.command for x in entries)

    @app.command
    async def exit():
        """Exit the application."""
        return CommandResult(exit_requested=True)
