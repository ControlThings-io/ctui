# ControlThings User Interface

`ctui` is an event-driven Python framework for command tools that work both as
full-screen terminal interfaces, traditional command-line programs, and optional
browser interfaces. Write
ordinary typed functions; ctui supplies parsing, validation, async execution,
completion, history, layout, and automatic CLI routing.

## Installation

ctui requires Python 3.11 or newer:

```bash
python -m pip install ctui
```

## Quick start

```python
from pathlib import Path
from typing import Literal
from ctui import Argument, CommandError, CtuiApp, command

class FileTool(CtuiApp):
    name = "files"
    prompt = "files> "

    @command(
        aliases=("ls",),
        arguments={"order": Argument(flags=("-o", "--order"))},
    )
    async def list_files(self, directory: Path = Path("."),
                         order: Literal["name", "size"] = "name") -> str:
        """List files in a directory."""
        if not directory.is_dir():
            raise CommandError(f"Not a directory: {directory}")
        key = (lambda item: item.stat().st_size) if order == "size" else None
        return "\n".join(item.name for item in sorted(directory.iterdir(), key=key))

FileTool().run()
```

Commands can be sync or async and return a string or `CommandResult`. Use
`CommandResult.success()` when there is no output. Applications already inside
an event loop can use `await app.run_async()`. Test without a terminal using
`await app.dispatch("list files . --order size")`.

## Automatic command-line mode

Every `CtuiApp` supports these terminal interfaces without application-specific argument
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
by generated help and exit with status 2. Command argument errors include the
submitted command and a caret pointing to the invalid argument:

```text
add wrong 2
    ^
Error: first must be float: 'wrong'
```

In the full-screen UI, an invalid command is restored to the input field and the
cursor moves to the beginning of the argument that needs correction.

Full-screen terminal mode protects Python stdout/stderr and existing logging
handlers targeting those streams. Diagnostics are printed safely outside the UI,
then the interface redraws. Logging levels, formatting, filters, and file handlers
are preserved; stream changes are scoped to the terminal lifecycle. Direct OS
file-descriptor writes and subprocess output require application-side routing.

## Browser frontend

Browser support is included in the standard installation. Serve the same
application's commands and supported custom widgets in a browser:

```bash
python -m pip install ctui
python my_tool.py --web
python my_tool.py --web --web-port 0
```

No flags still opens the full-screen terminal interface. `-c`/`--command` and
`-f`/`--file` still select CLI execution. `--web` selects browser-only mode and
cannot be combined with CLI batches. The terminal prints the browser address
and waits; Ctrl-C stops the server. Port 8080 is the default; port 0 chooses an
available port. Use different ports to start independent application sessions.

The startup URL includes a random session token in its fragment. Open that URL
to authenticate; the browser removes the fragment after exchanging it for an
HttpOnly session cookie. Treat the startup URL as a credential. Additional tabs
at the same address share app state and output. Draft commands, completion,
scrolling, focus, and confirmation/help dialogs belong to each tab. `help` opens
a scrollable popup and preserves the output window. `exit` or Ctrl-Q stops the
whole session. Closing all tabs leaves the server and submitted commands running;
other views receive completed results. Unanswered dialogs are cancelled when their
requesting tab disconnects.

The browser uses packaged HTML, CSS, and JavaScript with no frontend build step,
external assets, or JavaScript framework. WebSocket updates and commands run on
the same asyncio loop as app lifecycle hooks. Existing async commands can overlap;
append results use current output when each command finishes. Each view has a
bounded, coalescing update queue so a slow browser does not hold up other views.
Reconnecting views receive the current layout and output.

Typing `exit` asks for confirmation in both terminal and browser UIs. An approved
exit stops the shared application session. In browser mode, the submitting tab
attempts to close; if browser policy blocks it, a message tells you to close it
manually. Other tabs disconnect. Noninteractive CLI use requires `exit confirm`.

### Custom layouts and lifecycle

Reuse `compose()` and `ctui.widgets`: Vertical, Horizontal, Frame, Label, TextArea,
Window, Button, and ProgressBar. Shared buffer text, frame titles, callable
labels/footer text, visibility, and dimensions are translated into browser
widgets. Buttons invoke the same handlers; editable custom text areas update
shared state. Call `self.app.invalidate()` after changing application-owned
labels or progress. Text-buffer changes trigger web redraws automatically.

Web mode runs `on_start`, builds widgets and the runtime, then calls `on_ready`.
`self.app` supports `invalidate()`, `exit()`, and `create_background_task()`;
terminal renderer internals are unavailable. Shutdown cancels pending work
before `on_stop` and service cleanup. In an existing event loop, use
`await app.run_web(port=8080)` instead of `run()`.

CTUI's message, confirmation, text-input, button-choice, radio-list, checkbox-list
and dictionary-input dialogs work from browser-triggered commands and callbacks. Native browser keyboard reservations and text selection
still apply. Arbitrary third-party prompt-toolkit controls, custom floating
containers, and renderer-specific extensions need a browser adapter; unsupported
controls produce an explicit startup error rather than a partial interface.

Try the complete example:

```bash
uv run examples/15_web_frontend.py --web --web-port 0
```

### Optional remote access and HTTPS

Loopback HTTP is the default. To listen on other interfaces, explicitly specify
a bind address and supply a certificate and private key:

```bash
python my_tool.py --web --web-host 0.0.0.0 --web-port 8443 \
  --web-cert server-cert.pem --web-key server-key.pem
```

Open the printed address using the server's reachable hostname/IP in place of
localhost when binding all interfaces. Use a certificate trusted by the browser
and valid for that hostname/IP. HTTPS automatically uses secure WebSockets;
remote plaintext binds and incomplete certificate/key pairs are rejected.
Automatic certificate issuance and reverse-proxy configuration are not included.

To reuse a supplied token, set an environment variable containing at least 24
characters and pass `--web-token-env VARIABLE_NAME`. All connections still
require authentication. Browser origins are checked and loopback hosts are
validated. TLS encrypts traffic; the session token authorizes app access.

## Application dialogs

Import dialogs from `ctui.dialogs`. Constructors build embedded popups; await
`show_dialog(dialog)` to display them in the active terminal application or the
requesting browser tab. Dialogs queue, preserve application output, and restore
focus when dismissed. Use each instance once. Convenience functions
`button_dialog`, `radiolist_dialog`, `checkboxlist_dialog`, `dict_input_dialog`,
`input_dialog`, and `message_dialog` return scheduled tasks that can be awaited.
The existing `yes_no_dialog` convenience function invokes Yes/No callbacks.
Dialogs require an interactive UI; automatic CLI commands should collect values
through command arguments instead.

| Dialog | Inputs | Accepted result | Cancel / Escape |
| --- | --- | --- | --- |
| `MessageDialog` | Message text | `None` | Acknowledge (`None`) |
| `YesNoDialog` | Confirmation text | `True` / `False` | `False` |
| `TextInputDialog` | Text, optional `default`, completer/password | `str` | `None` |
| `ButtonDialog` | `buttons=[(label, value), ...]` | Button value | `None` |
| `RadioListDialog` | `values=[(value, label), ...]`, optional `default` | Selected value | `None` |
| `CheckboxListDialog` | `values=[(value, label), ...]`, optional `default_values` | List in entry order (possibly `[]`) | `None` |
| `DictInputDialog` | `values={key: value, ...}`, optional `fields` | New dictionary | `None` |

Button/selection values cannot be `None`; selection values must be unique.
Tab/Shift-Tab move between fields and buttons. Radio/checkbox lists use arrows
to move and Space to select. Enter on Ok accepts; Escape cancels. Dictionary
keys are fixed strings; values are limited to `str`, `int`, finite `float`, and
`bool`. Boolean fields use checkboxes. Empty strings are accepted; numeric fields
require values. Initial `None` needs a `DictField(value_type=...)` override.
The original dictionary is never modified and key order is preserved. Dictionary
fields use aligned label/value columns with a divider. Labels are read-only;
editable values have a contrasting background and focus highlight. Optional help
appears beneath its value, and booleans stay in the same value column.

Text/selection/dictionary dialogs accept an optional synchronous `validator`.
It receives the converted result; return `True` or `None` to accept, `False` or
an error string to reject. Rejections leave the dialog open and retain edits.
Unexpected validator exceptions propagate. `DictField` adds per-field labels,
help text, type overrides and validators; field checks run before the whole-form
validator. Both UIs use the same server-side validation. The caller applies or
persists an accepted result; the editor only collects values.

```python
from ctui.dialogs import DictField, DictInputDialog, show_dialog

edited = await show_dialog(DictInputDialog(
    title="Connection",
    values={"host": "localhost", "port": 502, "enabled": True},
    fields={"port": DictField(
        help="TCP port, 1–65535",
        validator=lambda value: 1 <= value <= 65535 or "Invalid port",
    )},
))
if edited is not None:
    self.profile = edited
```

See [the dialog tutorial](examples/16_dialogs.py) for button, radio, checkbox and
form examples. ctui composes upstream prompt-toolkit widgets inside its running
application; it does not start a separate application for each popup.

## Help and interface guidance

In the full-screen UI, `help` opens a scrollable popup and preserves the main
output. The introduction explains input editing, output navigation, clipboard
use, and exit shortcuts. Output scrolling shortcuts work while input retains
focus: Home/End move through output, while Ctrl-A/Ctrl-E move within input.
In help and confirmation popups, Up/Down scroll one line and Page Up/Page Down
scroll one page while the buttons retain focus. Press Enter on Ok to close help
and restore input focus. Tab or Left/Right selects confirmation buttons.

The main command reference lists only top-level commands and groups. Use
`help history` to see its usage and immediate subcommands, then
`help history export` for argument details. Help accepts aliases and unique
command prefixes, and its targets support completion. Detailed command help
includes additional docstring text, so commands can document examples there.

CLI help prints to the terminal, with invocation and batch-execution guidance:

```bash
python my_tool.py help history export
python my_tool.py -c "help history export"
```

Customize interface introductions independently on your application class:

```python
class MyTool(CtuiApp):
    ui_help_intro = "Enter a command below; results appear above."
    cli_help_intro = "Use -c for individual commands or -f for a command file."
```

The main help page starts with the welcome text (app name, version, and
description), followed by the interface introduction and guidance, then the
generated command reference. Targeted help omits the introduction.
Shortcuts registered with `add_shortcut(..., description="...")` also appear
in the UI guidance, using prompt-toolkit key names.

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
and validation, so the menu does not recommend invalid input. Arguments remain
positional even when they have `Argument` completion or validation metadata.
For `list[T]` arguments, including optional lists, completion continues after
commas without requiring spaces. Providers return individual elements and receive
an empty `context.word`; ctui excludes exact values already typed anywhere in the
list. Partial entries do not filter candidates. Selecting an item preserves earlier
comma-separated values and replaces the current entry. Without a provider, the
argument help or type hint remains visible. List values are parsed as typed rather
than automatically expanded from a single remaining suggestion.

For filesystem arguments, opt into the reusable `PathCompleter`:

```python
from pathlib import Path
from ctui import Argument, PathCompleter, command

@command(arguments={
    "path": Argument(help="File to read", completer=PathCompleter()),
})
def read(self, path: Path): ...
```

It lists files and directories in a worker thread, supports relative, absolute,
and `~/` paths, and quotes inserted values when needed. Directories include a
trailing separator for navigation. Suggestions preserve typed path separators,
including forward slashes on Windows. Use `PathCompleter(directories_only=True)`
for directory arguments, or `PathCompleter(file_filter=lambda p: p.suffix ==
".json")` to filter files while retaining directories. Filters affect suggestions,
not validation; new export filenames can still be typed. No completer is inferred
from a `Path` annotation. Built-in project/config import and export, and history
export, use this provider without restricting file extensions.

To make a parameter a named option, declare its short and/or long flags
explicitly:

```python
@command(arguments={
    "environment": Argument(flags=("-e", "--environment")),
    "verbose": Argument(flags=("-v", "--verbose")),
})
def deploy(self, target: str, environment: str = "dev", verbose: bool = False): ...
```

This accepts forms such as `deploy api -e prod`,
`deploy api --environment=prod`, and `deploy api --verbose`. Boolean named
arguments act as flags; all parameters without `flags` are positional.

Supported annotations include `str`, `int`, `float`, `bool`, `Path`, `Enum`,
`Literal`, `Optional`, and comma-separated collections. Normal Python
parameters are supported; positional-only parameters, `*args`, and `**kwargs`
are rejected during registration because their CLI meaning would be ambiguous.

Use `list[int]`, `tuple[int, ...]`, or `set[int]` for simple comma-separated
integers. Use `IntegerRanges` when an argument also accepts inclusive ranges:

```python
from ctui import IntegerRanges, command

@command
def scan(self, addresses: IntegerRanges):
    for span in addresses:
        print(span.start, span.count, span.stop)
```

`0-5,9,15-20` becomes an ordered immutable collection of `IntegerSpan`
objects. Each span stores `start` and `count`; `stop` follows Python convention
and is exclusive. `expand()` lazily yields values in the entered span order,
`sample()` selects unique integers from the merged union, and `sorted()`,
`unique()`, and `merged()` return new collections without changing the original.
Only non-negative integers and ascending ranges are accepted.

Use the included `HexBytes` annotation when a command accepts hexadecimal
binary data. It returns an immutable `bytes` subclass and accepts contiguous,
space-, colon-, hyphen-, or underscore-separated byte pairs, a whole-value
`0x` prefix, per-byte `0x` prefixes, and `\xNN` escapes. Quote representations
containing spaces or backslashes so they remain one shell-like argument.

Plain `HexBytes` hex input ignores whitespace even within byte pairs:
`"dead beef"`, `"deadbe ef"`, and `"dead   b e      ef"` all produce `de ad be ef`.
The total number of hex digits must be even.

Mixed-radix `HexBytes` uses an explicit prefix on every component: `0x` hex,
`0b` binary, `0o` octal, or `0d` decimal. Each component must fit 0..255.
For example, `"0xbe 0b10101100 0xef 0d10 0o377"` produces `be ac ef 0a ff`.
Bare `"10 20"` remains plain hex; `"0xbe 10 20"` is rejected. Binary, octal,
and hex components support Python-style underscores. Standalone `0xdeadbeef`
retains its contiguous multi-byte meaning. Single/double command quotes work.

Fuzzy hex also supports mixed-radix byte components: `0b1010_????`,
`0o[0-3]??`, and `0d[1-5,10-15,200-216,254,255]`. Decimal sets use inclusive
IntegerRanges syntax, allow interior whitespace, merge duplicates, and expand
in ascending order. Each component contributes one byte. Reject the entire
pattern if any possibility exceeds 255 (for example `0o???`). Decimal digit
wildcards are not supported. Fuzzy underscores separate complete atoms or
follow a prefix, never consecutive/trailing or inside classes/repetition counts.
Global expansion limits, exact counts, and unique sampling remain in effect.

`FuzzyHexPattern` and `FuzzyStringPattern` represent finite sets without
materializing them during command conversion. Both provide an exact `count`,
bounded lazy `expand()`, and unique `sample()` operations. Hex patterns support
`?`, nibble classes and ranges such as `[0-5a-f]`, negated classes such as
`[!0]`, and fixed repetition such as `?{4}`. Hex formatting follows `HexBytes`:
plain hex ignores whitespace between pattern elements, including individual
nibbles (`"d e a d ? ?"`). Whitespace inside classes (`[0 -3]`) or repetition
counts (`?{ 2 }`) is invalid. Other separators must consistently divide complete
bytes, while one leading `0x`,
per-byte `0x` prefixes, and `\xNN` notation may contain fuzzy nibbles. Repetition
is nibble-oriented, so `?{4}` produces four nibbles (two bytes). String patterns
additionally support ASCII wildcard classes (`\d`, `\h`, `\l`, `\u`, `\w`, and
`\s`), literal alternatives such as `{admin,user}`, escapes, Unicode literals,
and fixed repetition. Generated ranges and wildcard alphabets remain
ASCII-bounded; explicitly written Unicode characters are preserved.

Expansion is lazy but guarded by a default limit of 65,536 complete results:

```python
from ctui import FuzzyHexPattern, FuzzyStringPattern, command

@command
def scan(self, pattern: FuzzyHexPattern):
    for payload in pattern.expand(limit=1_000):
        send(payload)

@command
def examples(self, pattern: FuzzyStringPattern):
    return "\n".join(pattern.sample(20, seed=42))
```

Command names and constrained choices accept unique prefixes. For example,
`dep dev web-1` can select `deploy development web-1` when each prefix has one
match. Ambiguous prefixes produce validation help instead of guessing. Quote
free-form strings to include spaces: `greet "Ada Lovelace"`.

The dropdown stays on the current argument until an unquoted space is typed.
Free-form values show a typed aid such as `<NAME: str>` or `<COUNT: int>`;
typing an unquoted, unescaped space advances the menu to the next argument.
Typed aids appear immediately, including after named options such as
`--replicas ` or `--replicas=`. Selecting an aid preserves your input.
Unique choice prefixes also work in `--option=value` form and when continuing
to later arguments.

History and project commands (including `project configs`) show successful
results in scrollable dialogs in terminal and browser modes, preserving
application output. Actions finish before results appear; output can continue
updating while a dialog is open. Result dialogs queue, and browser results appear
only in the submitting tab. CLI mode prints the same messages normally. `clear`
still clears output; help and exit retain their existing behavior.

Application commands can opt into this presentation with
`@command(result_title="Operation complete")`. Return a string or a
`CommandResult` containing output as usual. Closing a result dialog does not
undo the completed action.

## Events, lifecycle, and services

`on_start`, `on_ready`, and `on_stop` may be sync or async. The event bus emits
`command_submitted`, `command_started`, `command_finished`, and
`command_failed`. Commands defined as application methods can emit custom events
directly with `await self.events.emit("download_progress", percent=50)`.

History and storage remain injectable. An application with a stable `app_id`
also receives a default SQLite project backend in the platform-appropriate user
data directory. Each project has its own database containing named configs,
command history, record sessions, and raw or decoded protocol records. Every
startup opens `default`, creating it if needed. Existing data in `default`
persists across runs and can be reset like any project with `project reset`.
Load saved projects explicitly with `project load NAME`.  Create a new project
with `project create NAME` or fork an current proeject with `project saveas NAME`.


```python
class ModbusTool(CtuiApp):
    app_id = "io.example.modbus"

    def __init__(self):
        super().__init__()
        self.configs.register_template(
            "local", {"host": "127.0.0.1", "port": 502}
        )
```

Runtime objects such as clients, sockets, servers, and tasks remain ordinary
application attributes. Use `await self.configs.save(...)` for named profiles
and `await self.records.append(...)` for protocol traffic. Pass a custom
`backend`, `configs`, `records`, or `history` service to replace the defaults.

Project databases are versioned and checked for integrity when opened or
imported. Increase `project_schema_version` when application-owned database
objects change, and provide SQL statements keyed by the version they migrate
from:

```python
class ModbusTool(CtuiApp):
    app_id = "io.example.modbus"
    project_schema_version = 2
    project_migrations = {
        1: (
            "ALTER TABLE device_data ADD COLUMN label TEXT NOT NULL DEFAULT ''",
        ),
    }
```

Framework and application migrations run together in a transaction. Before a
database is changed, ctui creates a timestamped `pre-migration` backup beside
it. Missing migrations, newer schemas, corrupt databases, and incompatible
imports are rejected without replacing the active project or leaving an orphan
in the project catalog.

Built-in project commands create, clone, list, load, rename, permanently delete,
import, export, and selectively reset projects. `project` shows active-project
statistics. Named configurations are managed through `project configs` (or
`project configs list`), `project configs show NAME`, `project configs export PATH`,
`project configs import PATH`, and `project configs reset`. These replace the
unreleased top-level `configs` commands without aliases. Application code continues
using `self.configs`; its service API and persistence remain unchanged.
Configs export as versioned JSON, while whole projects export as
consistent `.ctui-project` SQLite snapshots. Destructive commands show a UI
confirmation dialog; noninteractive execution requires a trailing `confirm`.

Application command options use explicitly declared Linux-style flags, for
example `history search timeout --limit 50 --since 7d`. Decorated commands can
opt out of history and require a formatted confirmation message.

Export all history, or only the most recent commands, as a reusable command
file:

```text
history export commands.txt
history export recent-commands.txt --count 5
```

The resulting UTF-8 file can be executed later with `-f` or `--file`.

```python
@command(
    record_history=False,
    confirmation="Permanently delete {name}?",
)
async def delete(self, name: str):
    ...
```

Memory and null implementations remain included. Override `compose()` for a
custom prompt-toolkit container; stable component aliases are available in
`ctui.widgets`.

Register application-wide keyboard shortcuts with
`app.add_shortcut("f2", handler=callback)`. Ctui leaves mouse selection and the
clipboard to your terminal. Drag across output to select it, then use your
terminal's copy and paste shortcuts (commonly Ctrl-Shift-C/Ctrl-Shift-V on Linux
and Windows, or Command-C/Command-V on macOS). The command input keeps focus.

The input line includes familiar terminal editing shortcuts:

- Ctrl-A / Ctrl-E: move to the beginning / end of the input line.
- Ctrl-U / Ctrl-K: delete to the beginning / end.
- Ctrl-W: delete the previous word.
- Ctrl-C: cancel and clear the current input.
- Ctrl-D: delete the next character, or exit on an empty line.
- Ctrl-L: clear the output pane.
- Home / End: jump to the beginning / end of the output.
- Page Up / Page Down and Ctrl-Up / Ctrl-Down: scroll output vertically.
- Alt+Left / Alt+Right: scroll long, unwrapped output horizontally while input
  keeps focus. New terminal output returns to the first column and final line.

Return `CommandResult.append("Finished")` when output should be added below
previous command output instead of replacing it. This is safe for overlapping
async commands because the append is applied when each command finishes.

## Public API and compatibility

ctui follows semantic versioning. Within the 1.x series, documented top-level
imports from `ctui` are the supported compatibility surface:

- Application and commands: `CtuiApp`, `command`, `Argument`, `CommandResult`,
  `CommandError`, `CommandNotFound`, `CommandValidationError`,
  `ConfirmationRequired`, `CompletionContext`, `CompletionItem`, and `PathCompleter`.
- Parameter types: `HexBytes`, `FuzzyHexPattern`, `FuzzyStringPattern`,
  `IntegerRanges`, and `IntegerSpan`.
- Service interfaces and implementations: `HistoryStore`, `Storage`,
  `ConfigStore`, `RecordStore`, `HistoryEntry`, `MemoryHistory`, `NullHistory`,
  `MemoryStorage`, `NullStorage`, and `StorageKeyError`.
- Project storage: `SqliteProjectBackend`, `ProjectInfo`, and `RecordEntry`.
- Package metadata: `__version__`.

The reusable names exported by `ctui.widgets` are also supported for custom
layouts. Other submodules and names beginning with an underscore are
implementation details and may change between minor releases. Deprecations to
the supported API will be documented before removal in a future major release.

Detailed API contracts and implementation rationale live in the class and method
docstrings in [application.py](src/ctui/application.py),
[commands.py](src/ctui/commands.py), [types.py](src/ctui/types.py),
[services.py](src/ctui/services.py), and [projects.py](src/ctui/projects.py).
The [decision log](docs/DECISIONS.md) records shared architectural choices and
historical context; it is not a duplicate API reference.

## Development

The [`examples`](examples/README.md) directory contains a progressive tutorial.
Each file is intentionally short and concentrates on one or two features.

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run examples/filesystem.py
```

## Browser verification for contributors

The portable unittest suite includes real HTTP/WebSocket integration tests. Additional Playwright checks exercise browser behavior
and all 16 tutorial apps through their actual `--web` entry points:

```bash
uv run --with playwright python -m playwright install firefox
CTUI_BROWSER=firefox uv run --with playwright tests/browser_smoke.py
CTUI_BROWSER=firefox uv run --with playwright tests/browser_tutorials.py
```

Use `CTUI_BROWSER=chromium` for Chromium; `CTUI_CHROMIUM_EXECUTABLE` can select
a system installation. To repeat one tutorial, append its filename, such as
`15_web_frontend.py`, to `browser_tutorials.py`. These checks use temporary
application storage and close their servers; they do not require real devices.
