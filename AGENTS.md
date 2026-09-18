# Repository instructions

## Project continuity

- Before working, read `docs/STATUS.md` and `docs/DECISIONS.md`, then inspect
  the current branch, working tree, and recent commits. Reconcile stale notes
  with the code and the user's latest instructions.
- After meaningful work, update status with completed changes, checks actually
  run, outstanding tasks, blockers, and concrete next steps. Include these
  updates with the corresponding code changes.
- Record significant accepted decisions and their rationale in the decision
  log. Explicitly identify proposals, inferred rationale, and superseded
  decisions. Do not turn assistant suggestions into user commitments.
- Keep status concise; retain durable rationale in the decision log and use
  Git history for detailed changes. Link to existing documentation instead of
  duplicating it. Use repository-relative paths so notes work on every laptop.
- Never claim a test, publication, or remote CI run succeeded without evidence.
  Historical validation must include its date or revision.
- Before a laptop handoff, record unfinished work and remaining validation.
  Code and notes must be committed and pushed to transfer through Git; the
  receiving laptop must pull the same branch before starting a new session.

## Project purpose and conventions

- ctui is a reusable Python framework for typed, asynchronous terminal tools,
  including protocol clients, servers, proxies, and testing tools. Keep common
  application code simple and examples approachable for newer Python developers.
- Use `CtuiApp` subclasses and `@command`, with one dispatch path for the
  full-screen UI and automatic CLI. Preserve the decisions in the decision log.
- Use Conventional Commit messages, such as `feat:`, `fix:`, `docs:`, or
  `test:`, followed by a concise description.
- Follow applicable Python standards and PEPs; use official Python and PyPA
  documentation as primary references for packaging and language questions.
- Follow sound GitHub development practices proportionately: clear changes,
  appropriate tests and review, secure defaults, managed dependencies, and the
  documented release procedure.
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

Run checks appropriate to the change. Documentation-only changes ordinarily
need content, link, and whitespace review, not the whole runtime suite.
For packaging or release changes, follow `RELEASE_CHECKLIST.md`, including
wheel and source-distribution smoke tests. Do not infer remote matrix success
from local tests. Update examples and README when public behavior changes.

## Code map

- `src/ctui/application.py`: lifecycle, dispatch, and UI/CLI routing.
- `src/ctui/commands.py`, `completion.py`: registration, parsing, validation,
  generated help, built-in commands, and completion.
- `src/ctui/types.py`: hexadecimal, fuzzy-pattern, and integer-range types.
- `src/ctui/services.py`, `projects.py`: service interfaces and SQLite projects.
- `src/ctui/layout.py`, `keybindings.py`, `functions.py`, `dialogs.py`,
  `widgets.py`: terminal presentation and interaction.
- `tests/`: unittest suite and installed-artifact smoke test.
- `examples/README.md`: ordered, focused tutorials.
- `.github/workflows/`: platform tests and tag-triggered publishing.
