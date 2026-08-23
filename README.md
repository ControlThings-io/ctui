# ControlThings User Interface

`ctui` is an event-driven Python framework for command tools that work both as
full-screen terminal interfaces and traditional command-line programs. Write
ordinary typed functions; ctui supplies parsing, validation, async execution,
completion, history, layout, and automatic CLI routing.

## Quick start

```python
from pathlib import Path
from typing import Literal
from ctui import CommandError, CtuiApp, command

class FileTool(CtuiApp):
    name = "files"
    prompt = "files> "

    @command(aliases=("ls",))
    async def list_files(self, directory: Path = Path("."),
                         order: Literal["name", "size"] = "name") -> str:
        """List files in a directory."""
        if not directory.is_dir():
            raise CommandError(f"Not a directory: {directory}")
        return "\n".join(item.name for item in directory.iterdir())

FileTool().run()
```

Commands can be sync or async. Applications already inside an event loop can
use `await app.run_async()`. Test without a terminal using
`await app.dispatch("list files . --order size")`.

## Automatic command-line mode

Every `CtuiApp` supports both interfaces without application-specific argument
parsing. Calling the program without arguments opens the full-screen UI:

```bash
python my_tool.py
```

Help is printed directly in the terminal with any standard help form:

```bash
python my_tool.py help
python my_tool.py -h
python my_tool.py --help
```

Use `-c` or `--command` to run commands without opening the UI. Repeat the
option to execute several commands sequentially:

```bash
python my_tool.py -c "list files ." -c "list files /tmp --order size"
```

Use `-f` or `--file` to read commands from a UTF-8 text file. Blank lines and
lines beginning with `#` are ignored. Command and file options may be mixed;
they execute in the order supplied:

```bash
python my_tool.py -c "list files ." --file nightly-commands.txt
```

Invalid terminal options, command names, and arguments print an error followed
by generated help and exit with status 2.

## Completion and validation

`Literal` and `Enum` annotations automatically produce completion choices. Use
`Argument` for tool-specific choices, validation, and sync or async providers:

```python
async def server_names(context):
    return ["web-1", "web-2", "db-1"]

@command(arguments={
    "environment": Argument(
        choices={"dev": "Development", "prod": "Production"},
        help="Deployment environment"),
    "server": Argument(
        completer=server_names,
        validator=lambda value: value != "db-1" or "db-1 is read-only"),
})
async def deploy(self, environment: str, server: str): ...
```

A provider receives `CompletionContext`: the command, current parameter,
partial word, parsed arguments, and app. It may return strings or
`CompletionItem` values with dropdown help. Results pass through type conversion
and validation, so the menu does not recommend invalid input. Named options
such as `--environment` are also completed.

Supported annotations include `str`, `int`, `float`, `bool`, `Path`, `Enum`,
`Literal`, `Optional`, and comma-separated collections.

Command names and constrained choices accept unique prefixes. For example,
`dep dev web-1` can select `deploy development web-1` when each prefix has one
match. Ambiguous prefixes produce validation help instead of guessing. Quote
free-form strings to include spaces: `greet "Ada Lovelace"`.

The dropdown stays on the current argument until an unquoted space is typed.
Free-form values show a typed aid such as `<NAME: str>` or `<COUNT: int>`;
typing a space advances the menu to the next argument.

## Events, lifecycle, and services

`on_start`, `on_ready`, and `on_stop` may be sync or async. The event bus emits
`command_submitted`, `command_started`, `command_finished`, and
`command_failed`. Commands defined as application methods can emit custom events
directly with `await self.events.emit("download_progress", percent=50)`.

History and storage are injected instead of automatically writing project files.
Memory and null implementations are included. Override `compose()` for a custom
prompt-toolkit container; stable component aliases are available in
`ctui.widgets`.

Return `CommandResult.append("Finished")` when output should be added below
previous command output instead of replacing it. This is safe for overlapping
async commands because the append is applied when each command finishes.

## Development

The [`examples`](examples/README.md) directory contains a progressive tutorial.
Each file is intentionally short and concentrates on one or two features.

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run examples/filesystem.py
```
