# Project decisions

Originally recorded 2026-09-18 from locally available ctui conversations and
Git history since August 22, 2026 (owner-approved cutoff). Private transcripts
and conversations on other laptops were not repository dependencies. Dates
below identify discussion/implementation. “Accepted” denotes explicit user
direction; “Implemented policy” denotes documented codebase policy. Later
entries supersede earlier choices where noted. Proposals remain in STATUS.

Read entries relevant to the task; this is durable rationale, not startup
reading in full. Personal submission preferences now live in the global
Codex instructions; their September 19 update is preserved in Git (`88df143`).

## D01 — A reusable, event-driven tool framework

Accepted, Aug 22–26; `46eb6a8`, `806187f`, `7a46034`.

Support tools such as Modbus clients/servers/proxies and network interaction
or testing applications. Prefer a Pythonic `CtuiApp` subclass with decorated
methods, sync/async commands, lifecycle hooks, events, and testable headless
dispatch. UI and CLI share the command engine. Keep service and layout
replacement possible. Examples should be short, ordered, and accessible to
new Python developers; use `self.events` rather than implicit `ctx` injection.

## D02 — Automatic CLI and deliberate pre-1.0 API cleanup

Accepted, Aug 23 and reaffirmed Sep 13; `806187f`, `bfe795c`.

Every application entry point supports full-screen and automatic CLI operation
through one dispatcher, avoiding a separate application-owned CLI parser.
Routing, batch ordering, lifecycle, and result contracts live in
[CtuiApp](../src/ctui/application.py); examples remain in the README.

The owner explicitly did not require compatibility with earlier ctui releases.
Historical `Ctui`, `do_` conventions, instance command registration, and special
legacy result handling were removed during the overhaul. Use current tutorials
rather than reviving old examples. Correction from implementation review on
Sep 18: commands return `str` or `CommandResult`; bare `None` is rejected by
current dispatch and its regression test. The earlier note saying it remained
valid was stale. Use `CommandResult.success()` for no-output success.

Implemented policy: documented top-level exports and `ctui.widgets` are the
supported 1.x surface; internal submodules are not generally stable. Follow
semantic versioning and document deprecations before future major removal.
The import boundary is documented in [__init__.py](../src/ctui/__init__.py).

## D03 — Positional by default; named options explicitly declared

Accepted, Sep 13; `b031e15`, `213043a`.

Keep positional parameters as the default; named options require explicit
`Argument(flags=...)` opt-in. Conversion follows function annotations, avoiding
a competing `Argument(type=...)` source of truth. Parameter help or completion
metadata alone does not change how users supply a value. See
[Argument, command, and Command.parse_args](../src/ctui/commands.py) for syntax,
validation, quoting, and error contracts.

This supersedes the Aug 26 preference against `--` options. Quoted Windows-path
regressions (`420daed`) preserve shell-like tokenization across platforms.

## D04 — Predictable completion and precise errors

Accepted, Aug 23–27; `9a7611c`, `d106e49`, `4aeb8e6`, `d307e0b`.

Completion should explain the argument currently being entered, advance only
at an explicit token boundary, and show subcommands alongside parent arguments.
Allow unique command/choice abbreviations while rejecting ambiguity. Put error
locations back in the original input so UI users can correct it and CLI users
can identify the bad argument.

Detailed contracts belong in [completion.py](../src/ctui/completion.py),
[commands.py](../src/ctui/commands.py), and
[application.py](../src/ctui/application.py). Sep 18 completion fixes retain
non-inserting hints through prompt-toolkit filtering and expand earlier named
choice prefixes; the local rationale is in completion/layout docstrings.

Accepted follow-up, September 21: report supplied-argument errors in command-line
order across positional and named arguments. Whole-line tokenization errors still
come first, and missing required arguments remain end-of-input errors.

Accepted follow-up, September 21: provide a reusable, explicitly configured
`PathCompleter` rather than inferring filesystem completion from `Path` types.
Use it for built-in file arguments and the filesystem example. Keep directory
navigation available with file filters; suggestions do not restrict execution.
Project import does not filter by extension because snapshot suffixes are optional.

## D05 — Terminal-native selection and concurrent output

Accepted, Aug 23; `84679d3`, `1b53da9`.

Leave selection and clipboard operations to the terminal, with mouse capture
disabled by default and command input retaining focus. Earlier internal
copy/paste bindings and their example were deliberately removed. The temporary
request for Ctrl-C to exit was explicitly reversed: it clears input, while
Ctrl-L clears output. Binding details live in
[keybindings.py](../src/ctui/keybindings.py); focus-preserving scroll mechanics
live in [functions.py](../src/ctui/functions.py).

Apply output appends when commands finish to avoid overwriting concurrent
results with stale snapshots. See [CommandResult](../src/ctui/commands.py).
Progress tracking stays application-owned; the
[progress tutorial](../examples/11_statusbar_progress.py) explains updates and
cleanup. Custom layouts and application-wide shortcuts remain supported.

## D06 — Separate runtime state, configs, and records

Accepted, Aug 26; `7a46034`.

Runtime clients, sockets, servers, and tasks belong on application attributes.
Named persistent profiles belong in configs; sent/received protocol data belongs
in records, grouped by sessions. Generic storage remains injectable rather than
being the primary home for these distinct concepts.

A stable app_id enables default disk persistence, with replaceable service
implementations and platform-appropriate paths. Constructor defaults and service
contracts belong in [application.py](../src/ctui/application.py) and
[services.py](../src/ctui/services.py); the concrete backend is documented in
[projects.py](../src/ctui/projects.py).

## D07 — Portable per-project persistence and explicit destructive commands

Accepted, Aug 26; `7a46034`, `fd3e743`.

Use a SQLite database per project for portable snapshots, with UUID identity,
a catalog, and a separate active-selection file. Export profiles as versioned
JSON; TOML was discussed for display, not chosen for exchange. Allow application
config templates. Python 3.11 became the minimum.

Deletion is permanent by explicit preference. Destructive commands require a
formatted confirmation message so approval names the affected data. Command
history can be suppressed, especially for project switching and resets. Export
history as its own discoverable command producing a replayable UTF-8 file.
Protocol-specific record commands remain application-owned. Detailed service,
exchange, and command contracts live in [projects.py](../src/ctui/projects.py)
and [commands.py](../src/ctui/commands.py).

Unresolved implementation discrepancy, identified Sep 18: the Aug 26 request
preferred `project reset history` and explicitly omitted `history clear`.
Current registration nevertheless installs `history clear` for searchable
history backends, and `tests/test_projects.py` exercises it. No later acceptance
of that difference was found in available logs. This documentation review does
not remove it or treat its presence as a new user decision.

## D08 — Real asynchronous SQLite; recoverable migrations

Accepted, Sep 13; `7921344`, `f6b3b98`.

Use aiosqlite to keep SQL work off the event loop, superseding the Aug 26
standard-library workaround. The earlier observed hang is not an established
incompatibility or a reason to remove the tested async backend. Dependency
versions belong in packaging metadata and the lockfile; Python 3.11 remains
the baseline.

Protect persisted work through integrity/compatibility checks, explicit ordered
migrations, transactional updates, and backups before migration. Reject newer
schemas or missing migration paths rather than guessing. Keep an existing
project usable when candidate validation fails and clean failed imports out of
the catalog. Mechanisms and limits, including the scope of asynchronous I/O,
are documented in [SqliteProjectBackend](../src/ctui/projects.py).

## D09 — Compact, bounded protocol argument types

Accepted, Sep 13; `1cc1d8e`, `dfa4d88`, `64f813c`, `3fb8ff9`.

Use dedicated parameter annotations for reusable conversion and validation,
keeping annotations the single source of type information (D03). Represent
patterns and integer ranges compactly so argument conversion cannot eagerly
allocate enormous result sets before application limits can run. Expansion is
explicit, lazy, and bounded; random sampling is a separate operation. Keep the
pattern language finite and predictable instead of adopting a general regex
engine. Align concrete and fuzzy hex formatting to avoid conflicting grammars.

Accepted documentation placement, Sep 18: keep per-type syntax, limits,
semantics, and local rationale in class and method docstrings in
[types.py](../src/ctui/types.py). Keep shared architectural rationale here;
[README](../README.md) and [tutorials](../examples/README.md) provide usage.

## D10 — Release checks, supported platforms, and prereleases

Accepted implementation, Sep 13–18; `63e4c81`, `b6ae3be`, `bfe795c`,
`c2b944f`, `351436a`, `1f9707d`, `dc6e1ef`, `7e4e971`.

CI targets Python 3.11–3.14 across Ubuntu x86-64, Ubuntu ARM64, Windows, and
macOS. Source checks use unittest, Black, and isort. Build and install-test
both wheel and sdist in isolated environments. A single portable Python
distribution serves the platforms; tests do not imply separate OS packages.

Use matching PEP 440 package versions and Git tags: `1.0.0rc1` / `v1.0.0rc1`.
The tag workflow validates the match, runs checks, builds and smoke-tests,
attests, publishes via trusted PyPI publishing, and creates a GitHub release.
Merging alone does not publish. Prereleases are marked accordingly and are
not the latest stable release. Notes combine curated changelog content and
generated GitHub notes; RC notes may fall back to the base-version section.

The overhaul was merged through PR #6 before the local RC tag was created.
See the release checklist for subsequent releases. Successful external
publication is a verification item, not implied by this decision.

Owner update, September 18: RC1 was successfully published to PyPI and is
functional. More testing and changes are required, so the next release will
be RC2. The specific changes/tests are still to be listed. A background-job
manager and `py.typed` remain optional ideas, not release requirements.

Implemented metadata policy: retain the repository's existing
`GPL-3.0-or-later` license and include LICENSE in distributions. Metadata was
aligned with existing license/header evidence, not a newly approved relicensing
decision. No license change was accepted in the reviewed conversations.

## D11 — Git-tracked cross-laptop context

Accepted, Sep 18.

Maintain root `AGENTS.md` for ctui-specific operating instructions, `docs/STATUS.md` for
current work/next steps, and this file for durable decisions and rationale.
Update them alongside meaningful work and transfer them with the working
branch. Keep the evidence and outstanding questions visible; neither a new
session nor another laptop should need the original private transcripts.

## D12 — Hierarchical help with interface-specific presentation

Accepted, September 18, during RC2 development.

UI help belongs in a scrollable popup that preserves output and restores focus;
CLI help prints normally. Use one hierarchical reference with separate,
customizable interface guidance so applications do not maintain two command
manuals. Main help starts with welcome text, then interface guidance, then
root commands/groups; targeted help omits the introduction.

Follow-up accepted Sep 18: read-only message/confirmation dialogs keep buttons
focused during scrolling, so Enter activates the selected button. This
supersedes the initial help-text focus and Tab-to-Ok interaction. Text-entry
dialogs continue to focus input. Detailed hierarchy, rendering, and focus
contracts live in [help.py](../src/ctui/help.py),
[application.py](../src/ctui/application.py), and
[dialogs.py](../src/ctui/dialogs.py).

## D13 — Retain reusable dialogs; remove unused legacy metadata

Accepted September 18: keep the dialog classes and convenience wrappers for
application developers, including text-input and callback-based dialogs.
Remove obsolete `functions.show_help`, unused `Commands.descriptions`, and
redundant `Command.string`, `string_parts`, and `func_name`. Keep active command
descriptions (`desc`/`description`) used by generated help and completion.
The obsolete helper was the only tabulate consumer, so remove that dependency.

## D14 — Keep implementation contracts beside the code

Accepted, September 18, extending the type-docstring work in D09.

Class, method, and module docstrings own syntax, return values, limits, lifecycle
and error contracts, and the rationale for locally surprising behavior. This
log retains shared architecture, accepted historical choices, superseded
alternatives, and unresolved discrepancies. README/tutorials retain usage;
release procedures remain in the release checklist and workflow documentation.

Decorated command docstrings are also generated user help, so keep developer
implementation details on framework objects or tutorial module docstrings.
Test documentation explains fixture scope and regression intent without
repeating self-explanatory test names. Reconcile session suggestions against
explicit approval and current code; do not turn proposed features into promises.

Accepted follow-up, September 21: give user-facing positional arguments brief
completion/help descriptions once tutorial 04 has introduced `Argument` metadata.
Keep examples 01–03 focused on their earlier concepts instead of using argument
configuration before the tutorial explains it.

## HexBytes whitespace and mixed radix (September 19)

Accepted: plain hex ignores whitespace anywhere between digits, with an even
total digit count. When any whitespace-separated component has a 0x/0b/0o
prefix, parse each component as a single byte; bare components are decimal.
Binary underscores follow Python placement rules. Reject malformed syntax
and values outside 0..255. Preserve standalone contiguous 0x multi-byte input
and existing separate byte-separator and escape formats. Command input may
use either quote style. Fuzzy pattern parsing is unchanged.

The implicit decimal rule above is superseded by explicit mixed-radix byte
patterns below.

## Command errors and UI containment (September 19)

Accepted: convert expected user-facing failures at command boundaries to
CommandError. Preserve ordinary exceptions for reusable Python APIs and
programmer mistakes. Interactive execution, completion, and shortcut boundaries
contain unexpected exceptions and show diagnostics without reclassifying
cancellation or process-exit signals as command failures.

Accepted follow-up, September 21: when failed input is restored, keep precise
validation-error positions at the offending argument. For a CommandError or
unexpected exception without a position, place the cursor at the end of the
restored command so editing can resume from a predictable location.

## Flexible plain fuzzy-hex whitespace (September 19)

Accepted: ignore whitespace between plain FuzzyHexPattern elements, including
nibbles, complete classes, and repetition expressions. Reject whitespace inside
classes or repetition counts and require complete bytes after normalization.
Keep prefixed/escaped and colon/hyphen/underscore formats unchanged. Do not add
mixed-radix fuzzy syntax. FuzzyStringPattern preserves literal whitespace.
Example 06 displays expanded and sampled hex without separators.

The earlier exclusion of mixed-radix fuzzy syntax is superseded by the next
decision; plain-pattern whitespace behavior remains.

## Explicit mixed-radix byte patterns (September 19)

Accepted: both HexBytes and mixed FuzzyHexPattern require 0x/0b/0o/0d
prefixes on every component. This supersedes implicit bare decimal bytes.
Fuzzy binary/octal components support radix-specific digits, wildcards, classes,
and digit repetition. Underscores separate atoms or follow prefixes, never
consecutive/trailing or inside constructs. Decimal 0d sets reuse IntegerRanges
syntax, sort and deduplicate choices, and validate bounds before expansion.
Every possible component value must fit 0..255; reject rather than filter.
Plain fuzzy hex and standalone contiguous 0x multi-byte notation remain.

## D15 — Separate personal instructions and task-specific context

Accepted scope, September 19: move reusable operating preferences to
`~/.codex/AGENTS.md` and keep repository instructions specific to ctui, balancing
quality with context cost. The global file is machine-local and must be copied
separately when moving laptops; it does not travel with this repository.

Implementation choice: keep STATUS as a current snapshot with dated validation
and open work; retain detailed chronology in Git. Read decision headings and
relevant entries per task, broadening for architectural work. Preserve decision
rationale and supersession history instead of compressing away API constraints.
This refines D11's instruction placement and startup reading, not its requirement
for durable project continuity.
