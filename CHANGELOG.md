# Changelog

All notable changes to ctui are documented in this file.

The project follows [Semantic Versioning](https://semver.org/). Dates use the
ISO 8601 format.

## [1.0.0] - 2026-09-13

ctui 1.0 establishes the first stable public API for building typed command
tools that can run as either full-screen terminal applications or conventional
command-line programs.

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

[1.0.0]: https://github.com/ControlThings-io/ctui/releases/tag/v1.0.0
