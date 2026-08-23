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
    pass


class CommandValidationError(CommandError):
    pass


@dataclass(frozen=True)
class CompletionItem:
    value: str
    help: str = ""


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
    command: "Command"
    parameter: inspect.Parameter
    word: str
    arguments: Mapping[str, Any]
    app: Any = None


@dataclass
class CommandContext:
    app: Any
    command: "Command"
    raw_input: str
    arguments: Mapping[str, Any]

    async def emit(self, event: str, **data: Any) -> None:
        await self.app.events.emit(event, **data)


@dataclass(frozen=True)
class CommandResult:
    output: str | None = None
    clear_output: bool = False
    exit_requested: bool = False
    accepted: bool = True

    @classmethod
    def success(cls, output: str | None = None):
        return cls(output=output)

    @classmethod
    def rejected(cls):
        return cls(accepted=False)


def _name(func):
    value = func.__name__
    return (value[3:] if value.startswith("do_") else value).replace("_", " ")


def _convert(value: str, annotation: Any, name: str) -> Any:
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
    func: Callable[..., Any]
    name: str | None = None
    aliases: tuple[str, ...] = ()
    arguments: Mapping[str, Argument] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
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
        return [
            p
            for p in self.signature.parameters.values()
            if p.name not in ("self", "ctx")
        ]

    @property
    def help(self):
        args = " ".join(
            ("[" if p.default is not inspect.Parameter.empty else "<")
            + (self.arguments.get(p.name, Argument()).metavar or p.name.upper())
            + ("]" if p.default is not inspect.Parameter.empty else ">")
            for p in self.parameters
        )
        return f"{self.name} {args}\n\n{self.desc}".strip()

    def parse_args(self, text: str, partial: bool = False):
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
        call = dict(kwargs)
        if "ctx" in self.signature.parameters:
            call["ctx"] = CommandContext(app, self, raw_input, kwargs)
        result = self.func(**call)
        return await result if inspect.isawaitable(result) else result

    async def complete(self, text: str, word: str, app=None):
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


class Commands:
    def __init__(self):
        self.commands, self.aliases = {}, {}

    def register(
        self, func=None, *, name=None, aliases=(), arguments=None, description=""
    ):
        def decorate(target):
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
        return sorted(self.commands)

    @property
    def descriptions(self):
        return {k: v.desc for k, v in self.commands.items()}

    def resolve(self, text):
        stripped, all_names = text.strip(), {**self.commands, **self.aliases}
        for name in sorted(all_names, key=lambda x: len(x.split()), reverse=True):
            if stripped == name or stripped.startswith(name + " "):
                return all_names[name], stripped[len(name) :].lstrip()
        raise CommandNotFound(f"Unknown command: {stripped}")

    def extract(self, text):
        try:
            item, rest = self.resolve(text)
            return item, item.parse_args(rest)
        except CommandNotFound:
            return None, None

    def __iter__(self):
        return iter(self.commands.values())

    def __getitem__(self, key):
        return self.commands[key]


def command(func=None, *, name=None, aliases=(), arguments=None, description=""):
    """Mark a class method for registration by CtuiApp."""

    def decorate(target):
        target.__ctui_command__ = {
            "name": name,
            "aliases": tuple(aliases),
            "arguments": arguments or {},
            "description": description,
        }
        return target

    return decorate(func) if func else decorate


def register_default_commands(app):
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
