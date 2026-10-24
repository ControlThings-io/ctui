# Changelog

All notable changes to ctui are documented in this file.

The project follows [Semantic Versioning](https://semver.org/). Dates use the
ISO 8601 format.

## [Unreleased]

### Added

- Browser mode via `--web` and `CtuiApp.run_web()`, included in standard installs
  and using the same application definition as terminal and CLI modes.
- Shared browser sessions with per-tab drafts, completion and dialogs, plus
  authenticated HTTPS access using supplied certificates.
- Hierarchical command help, targeted help popups, and interface-specific
  editing and shortcut guidance.
- Reusable `PathCompleter` for file and directory arguments, with optional
  directory-only suggestions and file filters.
- Comma-separated list completion and project-name suggestions for loading
  and deleting projects.
- Button-choice, radio/checkbox-list, and typed dictionary-editor dialogs with
  synchronous validation.
- `@command(result_title=...)` for presenting command results in queued dialogs
  while preserving application output.
- Explicit mixed-radix byte formats for `HexBytes` and `FuzzyHexPattern`,
  including decimal components.

### Changed

- Startup always opens the persistent `default` project. Saved projects require
  an explicit `project load`.
- Configuration and history commands now live under `project`; see the command
  migration table below. `project history clear` and `project reset history`
  share the same confirmed reset operation.
- Built-in project and history results appear in dialogs in terminal and browser
  modes, preserving application output. CLI mode continues to print results.
- Interactive `exit` requires confirmation. Approved browser exit stops the
  shared session and attempts to close the submitting tab.
- Tab accepts the highlighted completion (or first candidate) in terminal and
  browser modes. With empty input or between command words, Tab first reveals a
  hidden menu without insertion. Escape dismisses visible or pending menus.
  Accepted commands and scalar/file arguments advance with a separator;
  directories and lists remain editable, including inside generated quotes.
- Arguments using `PathCompleter` remain literal during dispatch. Use Tab to
  accept filesystem suggestions explicitly.
- Alt-Up/Down scroll output one line; Alt-Left/Right scroll horizontally while
  command input retains focus.
- Plain hexadecimal input accepts whitespace between digits or pattern elements.

### Fixed

- Repeated spaces and tabs between command words and aliases now work
  consistently, preserving quoted argument values and error positions.
- Path completion preserves quote style, reuses closing quotes, and retains
  later arguments. Windows paths preserve the user's typed separators.
- Browser completion popups give labels the full width when help text is absent,
  avoiding cramped path/tag suggestions. Long values wrap within the viewport;
  optional help stays aligned on desktop and stacks on narrow screens.
- Background stdout, stderr, and logging output no longer overwrite the
  full-screen terminal layout.
- Command, completion, and UI callback failures are contained and reported;
  argument errors identify the offending input in command-line order.
- Dialogs redraw after asynchronous work, retain button focus while scrolling,
  and clean up correctly after cancellation or focus failures.
- Decorated command type hints and named-option choice-prefix expansion are
  preserved consistently.
- Browser rendering supports the declared minimum prompt-toolkit version.

### Removed

- The top-level `clear` command; use Ctrl-L in terminal and browser modes.
- The obsolete `functions.show_help` helper, unused command/help metadata,
  and the unused `tabulate` dependency.

### Compatibility

Applications and command files upgrading from rc1 should update these names:

| Previous command | Replacement |
| --- | --- |
| `history …` | `project history …` |
| `configs …` | `project configs …` |
| `clear` | Ctrl-L in terminal/browser modes |

The old command names have no compatibility aliases. Applications without a
project backend retain in-memory history and input recall, with no built-in
history commands. See the [public API and compatibility policy](README.md#public-api-and-compatibility)
for the supported Python interface.

## [1.0.0rc1] - 2026-09-13

This release candidate introduces the redesigned API for typed command tools
that run as full-screen terminal applications or conventional command-line
programs.

[Unreleased]: https://github.com/ControlThings-io/ctui/compare/v1.0.0rc1...HEAD
[1.0.0rc1]: https://github.com/ControlThings-io/ctui/releases/tag/v1.0.0rc1

### Added

- Typed command conversion, validation, completion, aliases, unique-prefix
  matching, confirmation prompts, and precise argument-error locations.
- Explicit Linux-style named arguments through `Argument(flags=...)`, while
  parameters without declared flags remain positional.
- Automatic CLI routing with repeatable `--command` and `--file` options.
- `HexBytes` for converting common hexadecimal representations to immutable
  bytes.
- Lazy, bounded `FuzzyHexPattern` and `FuzzyStringPattern` expansion and
  sampling.
- `IntegerRanges` and `IntegerSpan` for compact, non-expanding integer ranges.
- Async commands, lifecycle hooks, application events, progress reporting, and
  application-wide keyboard shortcuts.
- Project-scoped SQLite persistence for configs, command history, sessions,
  and records, using `aiosqlite` for non-blocking access.
- Versioned project migrations, integrity checks, and recoverable backups.
- JSON config and SQLite project import/export.
- A documented top-level public API and installed-package version metadata.
- Ordered tutorials covering the primary framework features.
- Cross-platform CI for Python 3.11 through 3.14 on Linux x86-64, Linux ARM64,
  Windows, and macOS.
- Isolated wheel and source-distribution smoke tests before publication.
- Trusted PyPI publishing, PEP 740 attestations, and automatic GitHub releases.

### Changed

- Python 3.11 is now the minimum supported Python version.
- SQLite operations use an asynchronous backend.
- Command parameters are positional unless their `Argument` metadata
  explicitly declares one or more option flags.

### Compatibility

Versions before 1.0 were development releases. Applications upgrading from a
0.x release should review the current README and tutorials rather than assume
compatibility with undocumented earlier behavior.

