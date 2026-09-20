# ctui repository instructions

## Context

- Read `docs/STATUS.md` before working. Scan `docs/DECISIONS.md` headings and
  read entries relevant to the task; review the whole log for broad architecture
  changes. Preserve accepted decisions and update these files after meaningful work.
- Status is a current snapshot, not a changelog. Keep historical detail in Git
  and durable rationale in the decision log; implementation contracts live in
  docstrings (D14). Command docstrings also generate user help.

## Project purpose and conventions

- ctui is a reusable Python framework for typed, asynchronous terminal tools,
  including protocol clients, servers, proxies, and testing tools. Keep common
  application code simple and examples approachable for newer Python developers.
- Use `CtuiApp` subclasses and `@command`, with one dispatch path for the
  full-screen UI and automatic CLI.
- Supported Python baseline is 3.11. CI covers Python 3.11–3.14 on Linux x86-64,
  Linux ARM64, Windows, and macOS. Dependencies must be installable with uv/pip.
- The supported compatibility surface is documented in `README.md` and tested
  in `tests/test_public_api.py`. The 0.x overhaul did not require backward
  compatibility; that is not permission to break the documented 1.x API.

## Development and verification

Use uv and the checked-in lockfile:

```bash
uv sync --locked --python 3.11
uv run --python 3.11 python -m unittest discover -s tests -v
uv run --python 3.11 black --check src tests examples
uv run --python 3.11 isort --check-only src tests examples
uv lock --check
git diff --check
```

For packaging or release changes, follow `RELEASE_CHECKLIST.md`, including
wheel and source-distribution smoke tests. Update examples and README when
public behavior changes.

## Code map

- `src/ctui/application.py`: lifecycle, dispatch, and UI/CLI routing.
- `src/ctui/commands.py`, `completion.py`: registration, parsing, validation,
  built-in commands, and completion; `help.py`: generated help.
- `src/ctui/types.py`: hexadecimal, fuzzy-pattern, and integer-range types.
- `src/ctui/services.py`, `projects.py`: service interfaces and SQLite projects.
- `src/ctui/layout.py`, `keybindings.py`, `functions.py`, `dialogs.py`,
  `widgets.py`: terminal presentation and interaction.
- `tests/`: unittest suite and installed-artifact smoke test.
- `examples/README.md`: ordered, focused tutorials.
- `.github/workflows/`: platform tests and tag-triggered publishing.
