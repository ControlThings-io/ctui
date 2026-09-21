"""Typed command registration, parsing, validation, and completion.

Function annotations control conversion. Argument metadata adds help, choices,
validators, and explicitly opted-in flags; defaults alone never create options.
Command names derive from method names by replacing underscores with spaces.
The dispatcher in application.py adds confirmation, history, events, and result
normalization around these lower-level operations.
"""

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
    """An error safe to show to an application user.

    Raise this for expected application failures. The UI shows the message in a
    dialog; CLI execution prints it with command context and returns status 2.
    """


class CommandNotFound(CommandError):
    """Indicate that input did not match a registered command or alias."""

    pass


class CommandValidationError(CommandError):
    """Report invalid command input with an optional source offset.

    position is a zero-based character offset, initially relative to argument
    text and remapped to the full input by dispatch(). argument identifies the
    parameter when known. Presenters use the offset for the CLI caret or the
    restored UI input cursor.
    """

    def __init__(self, message, *, position=None, argument=None):
        """Store a user-facing message and optional source location."""
        super().__init__(message)
        self.position = position
        self.argument = argument

    def locate(self, position, argument=None):
        """Attach a source location unless one is already available."""
        if self.position is None:
            self.position = position
        if self.argument is None:
            self.argument = argument
        return self


class ConfirmationRequired(CommandError):
    """Request explicit approval before a destructive command executes.

    message is the command's confirmation template formatted with parsed
    arguments. Headless callers can retry with confirmed=True or supply a
    confirmation callback to dispatch().
    """

    def __init__(self, message: str):
        """Store the formatted message for a presenter or headless caller."""
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CompletionItem:
    """Describe a completion value, dropdown explanation, and optional label.

    value is the text inserted into input; help appears beside it and display
    can replace its visible label. The framework uses an empty value plus a
    label for non-inserting type hints, so selecting a hint preserves input.
    """

    value: str
    help: str = ""
    display: str | None = None


@dataclass(frozen=True)
class Argument:
    """Configure one parameter without duplicating its conversion annotation.

    help explains the parameter in completion and detailed command help.
    choices is an iterable of values or a value-to-description mapping; it
    constrains parsed values as well as supplying suggestions. completer accepts
    CompletionContext and returns strings or CompletionItems, directly or via
    an awaitable. Suggestions are converted and checked by the validator.
    A provider suggests candidates; it is not itself an execution allowlist.

    validator is synchronous and receives the converted value. False rejects
    with a generated message; any string rejects with that message; True or
    None accepts. metavar replaces the parameter label in usage and type aids.

    flags explicitly makes a parameter named: e.g. ('-n', '--count'). Without
    flags it remains positional even if it has a default, help, or choices.
    A named bool acts as a flag. Flags must be unique within the command; short
    flags have one alphanumeric character and long flags use alphanumerics and
    hyphens. No flags are inferred from Python names.
    """

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
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompletionContext:
    """Snapshot supplied to a sync or async completion provider.

    command is the resolved metadata, parameter is the argument being entered,
    word is its partial text, and arguments contains earlier parsed values.
    Omitted defaults need not be present. app is the application when supplied
    by the caller; providers can inspect application state without adding a
    hidden context parameter to command signatures.
    """

    command: "Command"
    parameter: inspect.Parameter
    word: str
    arguments: Mapping[str, Any]
    app: Any = None


@dataclass(frozen=True)
class CommandResult:
    """Describe acceptance and presentation of a completed command.

    output replaces UI output unless append_output is true; None leaves it
    unchanged. clear_output takes precedence over text in the UI. exit_requested
    asks the presenter to stop. CLI prints provided output sequentially.

    accepted=False suppresses history and command_finished and lets the UI
    restore the submission when it is still current. Use success() for commands
    with no output; returning Python None is not accepted by dispatch().
    The result is immutable and carries intent rather than a stale widget state.
    """

    output: str | None = None
    clear_output: bool = False
    append_output: bool = False
    exit_requested: bool = False
    accepted: bool = True

    @classmethod
    def success(cls, output: str | None = None):
        """Create an accepted result with optional output text."""
        return cls(output=output)

    @classmethod
    def append(cls, output: str):
        """Request an append to the output present when the command finishes.

        The UI applies this after awaiting execution, so overlapping async commands
        do not overwrite one another with snapshots captured at submission time.
        """
        return cls(output=output, append_output=True)

    @classmethod
    def rejected(cls):
        """Create a result that preserves the user's current input."""
        return cls(accepted=False)


@dataclass(frozen=True)
class _HelpResult(CommandResult):
    """Carry a help target to the interface presenter."""

    target: str = ""


def _name(func):
    """Derive a terminal command name from a Python function name."""
    value = func.__name__
    return value.replace("_", " ")


def _token_starts(text: str) -> list[int]:
    """Return source offsets for shell-like tokens, including quoted tokens."""
    starts = []
    quote = None
    escaped = False
    in_token = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            if not in_token:
                starts.append(index)
                in_token = True
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in ("'", '"'):
            if not in_token:
                starts.append(index)
                in_token = True
            quote = character
        elif character.isspace():
            in_token = False
        elif not in_token:
            starts.append(index)
            in_token = True
    return starts


def _convert(value: str, annotation: Any, name: str) -> Any:
    """Convert one textual value according to a parameter annotation.

    Raises:
        CommandValidationError: If conversion fails or a constrained value does
            not match its annotation.

    Boolean text accepts true/false, yes/no, on/off, and 1/0 case-insensitively.
    Optional values accept none/null. Lists, tuples, and sets split on commas;
    Path expands the home directory. Enum accepts a member name or stringified
    value. Other annotations are called with the text, enabling custom types.
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
    """Store a callable's metadata and handle arguments independently of the UI.

    Registration validates names, aliases, flags, and parameter configuration.
    Only user-entered parameters appear; bound self is excluded. Positional-only
    parameters, *args, and **kwargs are rejected because their terminal meaning
    is not defined. An explicit description overrides the docstring's first
    line as the summary; remaining docstring text appears in targeted help.

    parse_args handles complete values. Prefix expansion and dynamic completion
    are separate async operations. execute invokes the callable directly; use
    CtuiApp.dispatch for confirmation, events, history, and result normalization.
    """

    func: Callable[..., Any]
    name: str | None = None
    aliases: tuple[str, ...] = ()
    arguments: Mapping[str, Argument] = field(default_factory=dict)
    description: str = ""
    record_history: bool = True
    confirmation: str | None = None

    def __post_init__(self):
        """Derive command metadata and validate argument configuration."""
        self.name = _name(self.func) if self.name is None else self.name
        if (
            not isinstance(self.name, str)
            or not self.name
            or self.name != " ".join(self.name.split())
        ):
            raise ValueError(
                "Command names must be non-empty words separated by single spaces"
            )
        if any(
            not isinstance(alias, str) or not alias or alias != " ".join(alias.split())
            for alias in self.aliases
        ):
            raise ValueError(
                "Command aliases must be non-empty words separated by single spaces"
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
        unsupported = [
            parameter.name
            for parameter in self.parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        if unsupported:
            raise ValueError(
                f"Command {self.name!r} uses unsupported parameters: "
                f"{', '.join(unsupported)}"
            )
        seen_flags = set()
        for parameter in self.parameters:
            for flag in self.arguments.get(parameter.name, Argument()).flags:
                if not isinstance(flag, str):
                    raise ValueError(
                        f"Invalid flag for {parameter.name}: {flag!r}; "
                        "use '-x' or '--long-name'"
                    )
                if not (
                    flag.startswith("--")
                    and not flag.startswith("---")
                    and len(flag) > 2
                    and flag[2:].replace("-", "").isalnum()
                    or flag.startswith("-")
                    and len(flag) == 2
                    and flag[1].isalnum()
                ):
                    raise ValueError(
                        f"Invalid flag for {parameter.name}: {flag!r}; "
                        "use '-x' or '--long-name'"
                    )
                if flag in seen_flags:
                    raise ValueError(f"Duplicate argument flag: {flag}")
                seen_flags.add(flag)

    @property
    def parameters(self):
        """Return user-supplied parameters, excluding the bound ``self``."""
        return [p for p in self.signature.parameters.values() if p.name != "self"]

    @property
    def help(self):
        """Return a compact usage line followed by the command description."""
        parts = []
        for parameter in self.parameters:
            config = self.arguments.get(parameter.name, Argument())
            metavar = config.metavar or parameter.name.upper()
            if config.flags:
                label = "|".join(config.flags)
                annotation = self.hints.get(parameter.name, parameter.annotation)
                if annotation is not bool:
                    label += " " + metavar
                parts.append(
                    f"[{label}]"
                    if parameter.default is not inspect.Parameter.empty
                    else f"<{label}>"
                )
            else:
                parts.append(
                    f"[{metavar}]"
                    if parameter.default is not inspect.Parameter.empty
                    else f"<{metavar}>"
                )
        args = " ".join(parts)
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

        Tokenize with shell-like quoting. Declared options can appear around
        positional values as -n VALUE or --name=VALUE. A bare bool option means
        True; explicit equals syntax can set False. -- ends option recognition,
        allowing positional values beginning with a hyphen. Duplicate options,
        unknown flags, missing values, and excess arguments are errors. Omitted
        optional parameters stay absent from the returned mapping so Python applies
        the callable's defaults. Partial mode still requires valid token quoting
        and conversion, but skips complete arity, choices, and validator checks.
        """
        try:
            tokens = shlex.split(text)
        except ValueError as error:
            raise CommandValidationError(str(error), position=len(text)) from error
        starts = _token_starts(text)
        values, pending = {}, None
        options = {
            flag: parameter
            for parameter in self.parameters
            for flag in self.arguments.get(parameter.name, Argument()).flags
        }
        positional_parameters = [
            parameter
            for parameter in self.parameters
            if not self.arguments.get(parameter.name, Argument()).flags
        ]

        def convert_at(raw, parameter, token_index):
            """Convert and validate a token at its command-line position."""
            try:
                value = _convert(
                    raw,
                    self.hints.get(parameter.name, parameter.annotation),
                    parameter.name,
                )
            except CommandValidationError as error:
                error.locate(starts[token_index], parameter.name)
                raise
            if partial:
                return value
            config = self.arguments.get(parameter.name, Argument())
            choices = (
                config.choices.keys()
                if isinstance(config.choices, Mapping)
                else config.choices
            )
            if choices is not None and str(value) not in {str(x) for x in choices}:
                raise CommandValidationError(
                    f"{parameter.name} must be one of: {', '.join(map(str, choices))}",
                    position=starts[token_index],
                    argument=parameter.name,
                )
            if config.validator:
                valid = config.validator(value)
                if valid is False or isinstance(valid, str):
                    raise CommandValidationError(
                        (
                            valid
                            if isinstance(valid, str)
                            else f"Invalid {parameter.name}: {value}"
                        ),
                        position=starts[token_index],
                        argument=parameter.name,
                    )
            return value

        index = 0
        positional_index = 0
        options_enabled = True
        while index < len(tokens):
            token = tokens[index]
            if options_enabled and token == "--":
                options_enabled = False
            elif options_enabled and token.startswith("-"):
                option, equals, inline = token.partition("=")
                parameter = options.get(option)
                if not parameter:
                    if partial:
                        break
                    raise CommandValidationError(
                        f"Unknown option: {option}", position=starts[index]
                    )
                if parameter.name in values:
                    raise CommandValidationError(
                        f"Argument specified more than once: {parameter.name}",
                        position=starts[index],
                        argument=parameter.name,
                    )
                annotation = self.hints.get(parameter.name, parameter.annotation)
                if annotation is bool and not equals:
                    values[parameter.name] = convert_at("true", parameter, index)
                elif equals:
                    values[parameter.name] = convert_at(inline, parameter, index)
                elif index + 1 < len(tokens):
                    index += 1
                    values[parameter.name] = convert_at(tokens[index], parameter, index)
                elif not partial:
                    raise CommandValidationError(
                        f"Missing value for {option}",
                        position=len(text),
                        argument=parameter.name,
                    )
                else:
                    pending = parameter
            else:
                if positional_index >= len(positional_parameters):
                    if not partial:
                        raise CommandValidationError(
                            f"Too many arguments\n\n{self.help}",
                            position=starts[index],
                        )
                else:
                    parameter = positional_parameters[positional_index]
                    values[parameter.name] = convert_at(token, parameter, index)
                    positional_index += 1
            index += 1
        if not partial:
            for parameter in self.parameters:
                if (
                    parameter.name not in values
                    and parameter.default is inspect.Parameter.empty
                ):
                    raise CommandValidationError(
                        f"Missing argument: {parameter.name}\n\n{self.help}",
                        position=len(text),
                        argument=parameter.name,
                    )
            return values
        next_parameter = pending or (
            positional_parameters[positional_index]
            if positional_index < len(positional_parameters)
            else None
        )
        return values, next_parameter

    async def execute(self, app=None, raw_input="", **kwargs):
        """Call the command with parsed keyword arguments and await its result.

        No context argument is injected; app and raw_input are not passed to the
        callable. Sync commands run inline. Return the raw value without converting
        it to CommandResult; application dispatch owns that validation.
        """
        result = self.func(**kwargs)
        return await result if inspect.isawaitable(result) else result

    async def complete(self, text: str, word: str, app=None):
        """Return type-checked and validator-approved completion items.

        Args:
            text: Completed argument text before the current word.
            word: Partial word to complete.
            app: Optional application passed to dynamic providers.

        Providers may be sync or async; validators are synchronous. Candidate
        values are prefix-filtered, converted, and checked by the validator. If no
        candidates exist, return a display-only type aid rather than invented input.
        Completion providers can run during dispatch for unique-prefix expansion,
        so they should avoid side effects.
        """
        values, parameter = self.parse_args(text, partial=True)
        option_names = {
            flag: parameter
            for parameter in self.parameters
            for flag in self.arguments.get(parameter.name, Argument()).flags
        }
        try:
            completed_tokens = shlex.split(text)
        except ValueError:
            completed_tokens = []
        entering_option_value = bool(
            completed_tokens
            and completed_tokens[-1] in option_names
            and self.hints.get(
                option_names[completed_tokens[-1]].name,
                option_names[completed_tokens[-1]].annotation,
            )
            is not bool
        )
        if not entering_option_value and (word.startswith("-") or parameter is None):
            options = []
            for candidate in self.parameters:
                config = self.arguments.get(candidate.name, Argument())
                for option in config.flags:
                    if candidate.name not in values and option.startswith(word):
                        annotation = self.hints.get(
                            candidate.name, candidate.annotation
                        )
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
        options = {
            flag
            for parameter in self.parameters
            for flag in self.arguments.get(parameter.name, Argument()).flags
        }
        for token in tokens:
            if token in options:
                expanded.append(token)
                continue
            option, equals, value = token.partition("=")
            inline = bool(equals and option in options)
            prefix = shlex.join(expanded + ([option] if inline else []))
            if prefix:
                prefix += " "
            matches = [
                item.value
                for item in await self.complete(prefix, value if inline else token, app)
                if item.value
            ]
            if len(matches) == 1:
                token = f"{option}={matches[0]}" if inline else matches[0]
            expanded.append(token)
        return shlex.join(expanded)


class Commands:
    """Register commands and resolve input using longest-prefix matching."""

    def __init__(self):
        """Create an empty command and alias registry."""
        self.commands, self.aliases = {}, {}

    def register(
        self,
        func=None,
        *,
        name=None,
        aliases=(),
        arguments=None,
        description="",
        record_history=True,
        confirmation=None,
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

        record_history controls accepted-command recording by dispatch();
        confirmation supplies its formatted approval prompt. Reject name/alias
        collisions rather than silently replacing registered commands.
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
                meta.get("record_history", record_history),
                meta.get("confirmation", confirmation),
            )
            if item.name in self.commands or item.name in self.aliases:
                raise ValueError(f"Command already registered: {item.name}")
            duplicate_aliases = [
                alias
                for alias in item.aliases
                if alias in self.aliases or alias in self.commands or alias == item.name
            ]
            if len(set(item.aliases)) != len(item.aliases):
                duplicate_aliases.extend(
                    alias for alias in item.aliases if item.aliases.count(alias) > 1
                )
            if duplicate_aliases:
                raise ValueError(
                    f"Alias already registered: {sorted(set(duplicate_aliases))[0]}"
                )
            self.commands[item.name] = item
            for alias in item.aliases:
                self.aliases[alias] = item
            return target

        return decorate(func) if func else decorate

    @property
    def strings(self):
        """Return registered command names in alphabetical order."""
        return sorted(self.commands)

    def resolve(self, text):
        """Resolve exact names first, then unique word prefixes and aliases.

        Prefer the longest matching exact name. If no exact name matches, compare
        prefixes at each word and retain the deepest matching command. Multiple
        aliases for the same command are not ambiguity. Return the Command and its
        remaining argument text; raise CommandNotFound for no match, malformed
        quoting during prefix resolution, or multiple distinct matches.
        """
        stripped, all_names = text.lstrip(), {**self.commands, **self.aliases}
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
        if matches:
            longest = max(count for _, _, count in matches)
            matches = [match for match in matches if match[2] == longest]
        if len({id(item) for _, item, _ in matches}) == 1:
            _, item, count = max(matches, key=lambda match: match[2])
            return item, shlex.join(tokens[count:])
        if matches:
            names = ", ".join(sorted(name for name, _, _ in matches))
            raise CommandNotFound(f"Ambiguous command; matches: {names}")
        raise CommandNotFound(f"Unknown command: {stripped}")

    def __iter__(self):
        """Iterate over commands in registration order."""
        return iter(self.commands.values())

    def __getitem__(self, key):
        """Return the command registered under *key*."""
        return self.commands[key]


def command(
    func=None,
    *,
    name=None,
    aliases=(),
    arguments=None,
    description="",
    record_history=True,
    confirmation=None,
):
    """Mark a class method for automatic registration by CtuiApp.

    Support @command and @command(...) while leaving the function directly
    callable. name overrides the method name (underscores otherwise become
    spaces); aliases adds alternate names. arguments maps parameter names to
    Argument metadata. description overrides the docstring's first-line summary.
    Use the remaining docstring for user-facing details shown by targeted help.

    Parameters are positional unless Argument.flags opts them into named syntax.
    Conversion follows annotations; command methods access the app through self.
    Return str or CommandResult, synchronously or asynchronously.

    record_history=False suppresses accepted-command history, useful when
    switching projects or exporting/resetting state. confirmation is a format
    string interpolated with parsed arguments, such as "Delete {name}?".
    Dispatch requires a callback, confirmed=True, or a trailing confirm token
    before executing such a command. A boolean is not a confirmation template.
    """

    def decorate(target):
        """Attach declarative command metadata to *target*."""
        target.__ctui_command__ = {
            "name": name,
            "aliases": tuple(aliases),
            "arguments": arguments or {},
            "description": description,
            "record_history": record_history,
            "confirmation": confirmation,
        }
        return target

    return decorate(func) if func else decorate


def register_default_commands(app):
    """Install the standard clear, help, history, and exit commands.

    History export is a separate command so it is discoverable alongside the
    parent history command and produces replayable UTF-8 command files. History
    search/clear are installed only when the history service exposes search.
    The project backend exposes search, so it also receives history clear in
    addition to project reset history. Help returns a private result so UI and CLI can
    present the same reference differently.
    """

    @app.commands.register
    def clear():
        """Clear the output."""
        return CommandResult(clear_output=True)

    @app.commands.register
    def help(target: str = ""):
        """Show help; use help <command> for subcommands and arguments."""
        return _HelpResult(output=app.format_cli_help(target=target), target=target)

    help.__ctui_help__ = True

    @app.commands.register(
        arguments={
            "count": Argument(
                help="Maximum number of recent commands to show; 0 shows all (default)"
            )
        }
    )
    async def history(count: int = 0):
        """Show recent command history."""
        entries = app.history.all()
        entries = await entries if inspect.isawaitable(entries) else entries
        entries = entries[-count:] if count else entries
        return CommandResult.success("\n".join(x.command for x in entries))

    @app.commands.register(
        name="history export",
        arguments={"count": Argument(flags=("-n", "--count"))},
    )
    async def history_export(path: Path, count: int = 0):
        """Export all or the most recent commands to a text file."""
        entries = app.history.all()
        entries = await entries if inspect.isawaitable(entries) else entries
        entries = entries[-count:] if count else entries
        try:
            path.write_text(
                "".join(f"{entry.command}\n" for entry in entries),
                encoding="utf-8",
            )
        except OSError as error:
            raise CommandError(f"Cannot export history: {error}") from error
        return CommandResult.success(
            f"Exported {len(entries)} command"
            f"{'s' if len(entries) != 1 else ''} to {path}."
        )

    if hasattr(app.history, "search"):

        @app.commands.register(
            name="history search",
            record_history=False,
            arguments={
                "limit": Argument(flags=("-n", "--limit")),
                "since": Argument(flags=("-s", "--since")),
            },
        )
        async def history_search(
            keyword: str, limit: int = 0, since: str | None = None
        ):
            """Search command history by keyword, limit, and relative age."""
            entries = await app.history.search(keyword, limit=limit, since=since)
            return CommandResult.success("\n".join(x.command for x in entries))

        @app.commands.register(
            name="history clear",
            record_history=False,
            confirmation="Clear all command history in the active project?",
        )
        async def history_clear():
            """Clear command history without recording this command."""
            await app.history.clear()
            return CommandResult.success("Cleared command history.")

    @app.commands.register
    async def exit():
        """Exit the application."""
        return CommandResult(exit_requested=True)
