# ControlThings User Interface

`ctui` is an event-driven Python framework for full-screen command tools. Write
ordinary typed functions; ctui supplies parsing, validation, async execution,
completion, history, layout, and terminal rendering.

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

## Events, lifecycle, and services

`on_start`, `on_ready`, and `on_stop` may be sync or async. The event bus emits
`command_submitted`, `command_started`, `command_finished`, and
`command_failed`. A command with a `ctx: CommandContext` parameter can emit
custom events with `await ctx.emit("download_progress", percent=50)`.

History and storage are injected instead of automatically writing project files.
Memory and null implementations are included. Override `compose()` for a custom
prompt-toolkit container; stable component aliases are available in
`ctui.widgets`.

The historical `Ctui` name, `do_` prefix, instance `@app.command` decorator,
and string/`None`/`False` results remain supported.

## Development

The [`examples`](examples/README.md) directory contains a progressive tutorial.
Each file is intentionally short and concentrates on one or two features.

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run examples/filesystem.py
```
