# Project decisions

Recorded 2026-09-18 from the local conversations and Git history described in
[STATUS.md](STATUS.md). Dates below are discussion/implementation dates.
“Accepted” means explicit user direction supported by the implementation;
“Implemented policy” identifies a documented codebase policy. Later decisions
supersede earlier ones where noted. New proposals belong in STATUS until accepted.

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

Every application's normal entry point opens the full-screen UI without
arguments; `help`, `-h`, and `--help` print help. Repeatable `-c`/`--command`
and `-f`/`--file` run commands sequentially in supplied order. Users should
not need to write a separate CLI parser.

The owner explicitly did not require compatibility with earlier ctui releases.
Historical `Ctui`, `do_` conventions, instance command registration, and
special legacy result handling were removed during the overhaul. Use current
README/tutorials rather than reviving old examples. Strings and `None` remain
valid current command results; structured `CommandResult` expresses behavior
such as appending output.

Implemented policy: documented top-level exports and `ctui.widgets` are the
supported 1.x surface; internal submodules are not generally stable. Follow
semantic versioning and document deprecations before future major removal.

## D03 — Positional by default; named options explicitly declared

Accepted, Sep 13; `b031e15`, `213043a`.

Function parameters are positional unless `Argument(flags=(...))` explicitly
declares short/long flags. Completion or validation metadata alone does not
make an option named. Support Linux-style `-e value`, `--environment value`,
`--environment=value`, and boolean flags. Conversion follows annotations;
avoid adding a competing `Argument(type=...)` convention.

This supersedes the Aug 26 preference for bare keyword/value arguments without
`--`. Do not restore that syntax based on the earlier discussion. Quote paths
and other values appropriately for the shell-like parser, especially Windows
paths (`420daed`).

## D04 — Predictable completion and precise errors

Accepted, Aug 23–27; `9a7611c`, `d106e49`, `4aeb8e6`, `d307e0b`.

Suggest one command word or argument at a time; advance only after an unquoted
space. Keep typed aids visible for free-form input, honor quoted spaces, and
allow unique prefixes for command words and constrained choices. Reject
ambiguity instead of guessing. At a command with subcommands and arguments,
show the valid next alternatives. Abbreviations such as `conf l` must work
for both execution and completion.

UI argument errors restore input and place the cursor at the offending value;
CLI errors show the command, a caret, and an explanatory message. Missing
storage keys without an explicit default raise `StorageKeyError`, allowing
normal command error handling and a UI popup.

## D05 — Terminal-native selection and concurrent output

Accepted, Aug 23; `84679d3`, `1b53da9`.

Leave mouse selection and clipboard operations to the terminal; disable mouse
capture by default and keep command input focused. The earlier internal
copy/paste bindings and example were deliberately removed.

Final shortcut preference: Ctrl-C clears/cancels input, Ctrl-L clears output,
Ctrl-A/Ctrl-E move within input, Home/End move through output, and Page Up/Down
and Ctrl-Up/Down scroll output. The temporary request for Ctrl-C to exit was
explicitly reversed. Ctrl-C clearing input is not a background-job cancellation
API.

Use `CommandResult.append(...)` to apply output appends when commands finish,
avoiding stale snapshots of existing output during overlapping async work.
Concurrent progress examples track individual operations and remove completed
ones from the status bar. Custom layouts and app-wide shortcuts remain supported.

## D06 — Separate runtime state, configs, and records

Accepted, Aug 26; `7a46034`.

Clients, sockets, servers, and tasks belong on ordinary application attributes.
Named persistent profiles belong in `self.configs`; sent/received raw or decoded
protocol data belongs in `self.records`, grouped by sessions. Generic `storage`
remains injectable, but is not the primary home for these distinct concepts.

An application with a stable `app_id` gets default disk persistence; retain
replaceable backend/config/record/history interfaces and memory/null options.
Without a project backend, defaults include memory history and null storage.
Use platform-appropriate data paths and dependencies available through uv/pip.

## D07 — Portable per-project persistence and explicit destructive commands

Accepted, Aug 26; `7a46034`, `fd3e743`.

Use one SQLite database per project under platformdirs, UUID-based identity,
a catalog database, and `state.json` for selection state. Projects hold configs,
records, sessions, and command history. Export whole projects as consistent
SQLite `.ctui-project` snapshots and configs as versioned JSON. Apps can
register config templates. TOML was discussed for display, not chosen as the
config exchange format; Python 3.11 became the minimum.

Project commands include statistics, create/clone/save-as, list/load/rename,
import/export, selective reset, and permanent delete. Deletion is permanent
by explicit preference. Destructive operations use formatted confirmation
messages, UI confirmation dialogs, and trailing `confirm` in noninteractive
execution. Do not replace the format string with a boolean-only setting.

Support `record_history=False`; loading a project should not enter the outgoing
project's history. Use `project reset history` rather than a separate
`history clear`. History export is its own discoverable command, supports all
or the last N entries, and produces a replayable UTF-8 command file. Generic
record-management commands were not requested.

## D08 — Real asynchronous SQLite; recoverable migrations

Accepted, Sep 13; `7921344`, `f6b3b98`.

Use `aiosqlite` so database work does not block the event loop, with serialized
access where required. Current dependency is `aiosqlite>=0.22,<0.23`; Python
3.11 remains the baseline. This supersedes the Aug 26 standard-library SQLite
workaround. The earlier observed hang is not an established incompatibility
or a reason to remove the now-tested async backend.

Validate integrity and framework/application schema versions on open/import.
Use ordered SQL migrations keyed by the previous version; run migrations
transactionally and create a timestamped backup first. Reject newer schemas,
missing migration paths, corrupt files, and incompatible imports. Failure must
preserve the active project and avoid orphaned catalog/filesystem state.

## D09 — Compact, bounded protocol argument types

Accepted, Sep 13; `1cc1d8e`, `dfa4d88`, `64f813c`, `3fb8ff9`.

- `HexBytes` is an immutable `bytes` subclass used as a parameter annotation.
  Accept common contiguous, separated, prefixed, and escaped byte notation;
  validate complete bytes. This combines conversion and validation without
  another source of type metadata.
- `FuzzyHexPattern` and `FuzzyStringPattern` represent finite possibilities
  without eagerly expanding them. Provide exact counts, bounded lazy
  expansion (default 65,536 results), unique sampling, and fixed repetition.
  Hex repetition operates on nibbles; formatting remains compatible with
  `HexBytes`, including fuzzy prefixed/escaped byte forms.
- Generated string wildcard alphabets/ranges are ASCII-bounded; explicitly
  supplied Unicode literals are preserved. This is a finite pattern language,
  not unrestricted regular-expression generation.
- `IntegerRanges` holds ordered immutable `IntegerSpan(start, count)` values;
  input ranges are inclusive and `stop` is exclusive. Keep spans compact,
  provide lazy expansion, sampling and nonmutating sorted/unique/merged
  operations. Accept nonnegative ascending ranges. Existing collection
  annotations cover simple comma-separated integers.

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

Maintain root `AGENTS.md` for operating instructions, `docs/STATUS.md` for
current work/next steps, and this file for durable decisions and rationale.
Update them alongside meaningful work and transfer them with the working
branch. Keep the evidence and outstanding questions visible; neither a new
session nor another laptop should need the original private transcripts.

## D12 — Hierarchical help with interface-specific presentation

Accepted, September 18, during RC2 development.

In the full-screen UI, explicit help opens a scrollable popup, preserves the
main output, and restores focus on close. CLI help prints normally. Main help
lists only root commands/groups; `help <command> [<subcommand> ...]` drills
into immediate children and command arguments. Commands may have both their
own arguments and children. Reuse aliases, unique prefixes, and completion.

Main help combines customizable CLI/UI introductions, default interface
guidance, and a shared generated reference. UI guidance distinguishes input
editing from output navigation while input retains focus, and lists built-in
and application shortcuts. Targeted help omits the introduction. Existing
validation-error presentation remains separate from explicit help.

Follow-up accepted September 18: help opens with Ok focused. Read-only message
and Yes/No confirmation dialogs scroll with Up/Down and Page Up/Page Down
without moving focus from their buttons. Enter activates the selected button;
Tab and Left/Right retain their button-navigation behavior. This supersedes
the initial help-text focus and Tab-to-Ok interaction. Text-entry dialogs
continue to focus their editable input.

Main help ordering clarified: welcome text (app name/version, then description)
comes first, interface guidance follows, and the generated command reference
comes last. Targeted help omits the welcome and interface introduction.

## D13 — Retain reusable dialogs; remove unused legacy metadata

Accepted September 18: keep the dialog classes and convenience wrappers for
application developers, including text-input and callback-based dialogs.
Remove obsolete `functions.show_help`, unused `Commands.descriptions`, and
redundant `Command.string`, `string_parts`, and `func_name`. Keep active command
descriptions (`desc`/`description`) used by generated help and completion.
The obsolete helper was the only tabulate consumer, so remove that dependency.
