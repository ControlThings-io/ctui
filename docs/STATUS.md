# Project status

Last reconciled: 2026-09-19, against `main` at `6587918` plus the current
repository-wide docstring changes in the working tree.

## Scope and evidence

This handoff summarizes 36 locally available commits across all local refs
from August 22, 2026 onward, including the overhaul merge. Conversation review
covered local ctui sessions started August 22, August 26, and September 13
(two overlapping logs), plus the September 18 continuity discussion. These
logs are machine-local evidence, not dependencies of this documentation.
Chats only on other laptops, in other products, or absent from local logs were
not available. The owner confirmed the August 22, 2026 cutoff and that no
earlier conversations need preserving. User decisions are distinguished from assistant proposals in
[DECISIONS.md](DECISIONS.md).

Continuity files were committed in `0002665`. The working tree was clean
before the current help task. Remote refs have not been refreshed.

## Current state

- The major overhaul was merged in PR #6 at `dc6e1ef` on September 13.
- `pyproject.toml` and `uv.lock` identify the package as `1.0.0rc1`.
- The local annotated `v1.0.0rc1` tag points to `dc6e1ef`.
- `7e4e971` subsequently corrected OS classifiers to macOS, Windows, and Linux;
  that change is not included in the RC tag.
- The implementation, public API documentation, migrations, CI matrix,
  artifact smoke tests, and prerelease publishing workflow are in place.
- The owner confirmed on September 18 that RC1 was successfully published to
  PyPI and is functional. Additional testing and changes remain; RC2 is required.
- Live GitHub CI results, attestations, and detailed acceptance-test outcomes
  have not been independently verified during this review.

## Completed milestones

| Period | Changes and evidence |
| --- | --- |
| Aug 22 | Publishing setup, lock update, and obsolete Kaitai file cleanup (`c77c7f3`, `14c824a`, `3162dd5`); class-based, event-driven overhaul with typed commands, dispatch, services, and tests (`46eb6a8`); API comments and focused tutorials (`10cc7cb`, `fdb633b`). |
| Aug 23 | Tutorial refinements (`448fc65`, `e7896e1`, `32ac521`, `da79748`); unique-prefix matching, quote-aware completion, typed dropdown aids (`9a7611c`); append output and concurrent progress (`84679d3`); automatic CLI and old API removal (`806187f`); precise error positions (`d106e49`); shortcuts, terminal-native selection, output scrolling, layouts, storage error handling, and expanded examples (`1b53da9`). |
| Aug 26–27 | Per-project SQLite configs, records, sessions, history, import/export, templates, confirmations, and Python 3.11 baseline (`7a46034`); replayable history export (`fd3e743`); one-word suggestions and completion after abbreviated commands (`4aeb8e6`, `d307e0b`). |
| Sep 13: arguments and types | Explicit opt-in short/long flags and tutorial (`b031e15`, `213043a`); `HexBytes` (`1cc1d8e`); bounded lazy fuzzy hex/string patterns (`dfa4d88`); consistent fuzzy nibble/hex formatting (`64f813c`); compact integer ranges and tutorial (`3fb8ff9`). |
| Sep 13: release hardening | Parser, lifecycle cleanup, error events, layout/dialog, validation, docs, metadata/license, and formatting fixes (`63e4c81`); real async SQLite via `aiosqlite` (`7921344`); cross-platform CI and artifact smoke tests (`b6ae3be`); public API and runtime version (`bfe795c`); transactional migrations, integrity checks, backups, and failed-import cleanup (`f6b3b98`); quoted Windows-path tests (`420daed`). |
| Sep 13–18: release preparation | Changelog/checklist (`c2b944f`); tag/version checks, prerelease classification and curated release notes (`351436a`); RC lockfile (`1f9707d`); overhaul merge (`dc6e1ef`); OS classifiers corrected (`7e4e971`). |

## Next steps: prepare RC2

The owner confirmed RC2 is the next release, with more changes and testing
needed before stable 1.0. Publication and basic functionality of RC1 are
confirmed by the owner; remaining checks do not imply publication failed.

- [x] Confirm RC1 was published to PyPI and is functional (owner, September 18).
- [x] Implement the requested help redesign: UI popup, hierarchical command
  reference, CLI/UI introductions, and input/output shortcut guidance.
- [ ] Manually check help scrolling and focus restoration in real terminals,
  including narrow windows and application-specific shortcuts.
- [ ] Capture any further owner-requested RC2 changes and acceptance tests.
- [ ] Complete additional acceptance testing and record the platform, Python
  version, tested package/revision, and outcomes.
- [ ] Record GitHub release/attestation links and full remote CI results for
  the release revision.
- [ ] Reconcile release documentation before the next release:
  `CHANGELOG.md` currently presents `[1.0.0] - 2026-09-13` as stable, while
  package metadata is RC1. The workflow deliberately supports falling back
  to base-version notes for RCs, so this is not by itself a workflow failure.
  Confirm the intended changelog labels/date and stable-readiness classifier.
- [ ] Prepare `1.0.0rc2` after the remaining changes and testing. Include the
  post-RC1 OS-classifier correction; do not move directly to stable 1.0.
- [ ] Follow [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) on the actual
  release revision: version/lockfile, changelog, source checks, built artifacts,
  passing CI, matching tag, and post-publication checks. Do not reuse RC1.

## Optional ideas, not approved commitments

The owner explicitly kept the job manager and typing marker optional on
September 18; neither is an RC2 requirement.

- Background-job service: identifiers, progress, cancellation, failures,
  automatic cleanup, and job commands. Suggested August 23; async commands and
  application-managed progress already exist, but this service does not.
- `py.typed` and a defined downstream typing promise. Suggested September 13;
  no marker currently exists. Assess annotation completeness first.
- Additional stress/failure coverage for cancellation during database work,
  large project transfers, and repeated startup/shutdown. Some related
  regression coverage exists; inspect it before treating suggestions as gaps.
- Reduce duplicate branch-push/PR CI runs, if runner usage warrants it.
- Existing source TODO: dynamic horizontal scrollbar in `dialogs.py`.

## Validation record

Historical September 13 release rehearsal reported 101 passing unit tests,
Black/isort and lockfile checks, successful wheel/source builds and isolated
smoke tests, and correct metadata/license inclusion. These are historical
session results, not fresh results at `7e4e971` or proof of remote CI success.

Current September 18 help work (working tree based on `0002665`):
- Added hierarchical help with aliases, unique prefixes, and target completion.
- UI help opens a focusable, scrollable popup and preserves main output;
  CLI help prints normally, including direct `help history export` invocation.
- Added independent `ui_help_intro` / `cli_help_intro` customization and
  documented input editing versus output scrolling, clipboard use, dialog
  navigation, and application shortcuts. Updated README and decision D12.
- Python 3.11.16: all 106 unittest tests passed, including five new help
  regression tests. Black, isort, lockfile, and whitespace checks passed.
  Full tests and formatting checks ran outside the sandbox after sandbox
  processes stalled. No remote CI or manual terminal acceptance run performed.

## Details still needed

- Which additional changes and acceptance tests should be completed for RC2?

## Laptop handoff

Update this file and relevant decisions with the work, commit and push the
working branch, then pull that branch on the other laptop before starting
Codex. Start by reading `AGENTS.md` and these notes. Uncommitted/unpushed work
does not transfer. Do not store full private transcripts in the repository.

## Dialog follow-up (September 18, based on `63de2cc`)

- Help now keeps Ok focused; message and Yes/No dialogs support line/page
  scrolling from their buttons. Updated help guidance and README.
- Dialog text width accounts for the scrollbar and trailing buffer cell,
  preventing avoidable wrapping of the longest line, including wide Unicode.
- Added rendered-dialog regression coverage for button focus, one-line
  scrolling, Enter activation, and longest-line sizing.
- Validation: all 108 tests passed on Python 3.11; Black, isort, and whitespace
  checks passed. Real-terminal visual acceptance remains outstanding.
- Owner approved committing and pushing these fixes on September 18.

## Filesystem example follow-up (September 18, based on `f4c48bf`)

- Renamed example commands to `ls` and `cd`. `ls` accepts a file or directory
  (default current directory) and `-l`/`--long` for permissions, link count,
  numeric owner/group, byte size, modification time, and symlink targets.
- Added relative, absolute, home-relative, and nested path suggestions;
  `cd` suggests directories only. Directory listing runs in a worker thread.
- Updated example usage and tutorial index. This is a teaching example, not
  a complete implementation of system ls.
- Python 3.11 temporary-directory smoke checks passed for file/directory
  listing, both flags, quoted paths, nested completion, missing-path errors,
  and directory changes. Black, isort, and whitespace checks passed. The
  full framework suite was not rerun for this example-only change.
- Owner approved submission; filesystem example committed as `e285326` and pushed.

## Help ordering follow-up

- Moved welcome text above interface guidance in UI and CLI main help.
  The generated command reference no longer embeds the welcome text.
- Preserved owner edits to default application metadata.
- All six focused help tests passed, including ordering, single welcome
  occurrence, and omission from targeted help. Formatting and whitespace
  checks passed. Owner approved committing and pushing the help changes.

## Legacy cleanup follow-up

- Removed obsolete `show_help`, unused `Commands.descriptions`, and redundant
  command metadata. Preserved all reusable dialogs and current help summaries.
- Removed unused tabulate dependency and refreshed the lockfile; no other
  dependency changes. Fixed existing example description formatting.
- September 18 validation: all 109 tests passed on Python 3.11. Black, isort,
  lockfile, whitespace checks, wheel/sdist builds, and isolated smoke tests
  for both distributions passed. No remote CI run claimed.
- Owner approved committing and pushing this cleanup.

## Named argument completion fixes

- Fixed disappearing type aids immediately after argument-separating spaces:
  retain non-inserting hints when prompt-toolkit discards a no-op completion.
- Expand unique Literal prefixes before completing later arguments, including
  both `--option value` and `--option=value`; ambiguous prefixes remain errors.
- Named numeric values show their type before typing. Selecting a type hint
  preserves existing input. Quoted and escaped spaces stay in the current value.
- All 116 tests passed on Python 3.11, including real buffer completion tests;
  Black, isort, lockfile, and whitespace checks passed.
- Owner approved committing and pushing the completion fixes and legacy cleanup.

## Example 04 argument-help tutorial

- Added help for the positional target and all named options, with separate
  descriptions for environment choices. The opening docstring introduces
  argument help, choice descriptions, and the distinction between help and flags.
- Updated the tutorial index. Seven named-completion tests, Black/isort,
  CLI `help deploy`, and whitespace checks passed. Owner approved submission.

## Type documentation follow-up (September 18, based on `c18ef0c`)

- Expanded all five public type docstrings and their operations in
  [types.py](../src/ctui/types.py) with syntax, limits, semantics, examples,
  and local rationale. Shortened D09 to shared architectural rationale and
  recorded the owner's approved documentation placement.
- Validation: reviewed documentation against implementation; Black, relative
  link-target checks, and whitespace checks passed. AST comparison confirmed
  that Python changes affect only docstrings. Runtime tests were not rerun
  for this documentation-only change.
- No blockers. Owner approved committing and pushing these documentation
  changes on September 18.

## Repository-wide docstrings (September 18–19, based on `6587918`)

- Reviewed all tracked Python files, locally available session logs/history
  index, and repository Markdown. Expanded framework contracts, tutorial
  explanations, and test scope/fixture rationale. Existing type docs remain.
- Shortened implementation-heavy decision entries to rationale and source
  links; recorded documentation placement in D14. README keeps practical usage.
- Corrected D02's stale claim that bare None is an accepted command result.
  Current code/tests require str or CommandResult. D07 now identifies the
  historical request to omit history clear versus its current tested presence;
  resolving that behavior difference remains a separate follow-up.
- September 19 validation: all 116 tests passed on Python 3.11, including
  help/CLI, rendered dialogs, completion, and persistence. Black and isort,
  local documentation links, and whitespace checks passed. AST comparison
  across all 44 tracked Python files confirmed only docstring changes in the
  43 edited files; the previously documented types.py is unchanged.
- Existing implementation limits are documented, not fixed here: example 13's
  custom root lacks modal float support; the two theme palettes are identical;
  show_dialog does not guarantee cleanup on cancellation. These are possible
  follow-ups, not newly accepted feature work. No remote CI, publication, or
  manual terminal acceptance is claimed.
- Owner approved the local documentation commit on September 19 and handles
  pushes on this computer. No blockers; next step is the owner's push.

## HexBytes extensions (September 19)

- Added whitespace-insensitive plain hex and mixed 0x/0b/0o/decimal byte
  components, with Python-style binary underscores and byte range checks.
- Preserved standalone 0x multi-byte notation and other existing formats.
  Updated type documentation, README, and example 05.
- All 118 tests passed on Python 3.11, including both command quote styles,
  requested inputs, ambiguity rules, invalid underscores, and overflow.
  Changed-file Black, full isort, and whitespace checks passed.
- Owner approved committing and pushing the HexBytes changes on September 19.

## Pattern example error handling (September 19)

- Example 06 now translates expansion ValueErrors into CommandErrors for
  concise UI error dialogs, preserving output and restoring submitted input.
- Both example expansion commands default to 1,024 instead of 1,000; explicit
  --limit overrides remain supported. Library defaults remain 65,536.
- All 120 tests passed on Python 3.11, including boundary, override, and UI
  error-presentation tests. Changed-file Black/isort and whitespace checks passed.
- Owner approved committing and pushing the pattern example fixes on September 19.

## Error boundary hardening (September 19)

- Examples 06/07 translate sampling and range-limit ValueErrors at command
  boundaries. Reusable type methods retain their Python exception contracts.
- Built-in project/config commands translate filesystem, Unicode, and SQLite
  failures while preserving existing CommandErrors.
- UI shortcut and completion callbacks contain exceptions; command result
  presentation also has a fallback dialog. Unexpected errors retain traceback
  details; cancellation/exit signals are not converted. Dialog cleanup uses
  finally so cancellation removes its float and restores focus.
- All 124 tests passed on Python 3.11; new regressions cover example failures,
  sync/async shortcuts, completion providers, and project export permissions.
- Owner approved committing and pushing these changes on September 19.

## Fuzzy-hex whitespace follow-up (September 19)

- Plain fuzzy hex accepts whitespace between pattern elements; classes/counts
  reject internal whitespace. Existing prefixed/separated formats are unchanged.
- Example 06 emits contiguous hex for expansion and sampling. Updated docs.
- All 125 tests passed on Python 3.11, including quoting, whitespace, invalid
  constructs, preserved string spaces, and existing format regressions.
- Changed-file Black/isort and whitespace checks passed. Owner approved
  committing and pushing these changes on September 19.

## Mixed-radix byte patterns (September 19)

- HexBytes now requires explicit 0d decimal components; bare numbers in mixed
  sequences are rejected. Updated examples and documentation.
- FuzzyHexPattern supports mixed hex/binary/octal byte patterns and decimal
  sets, including whitespace inside decimal brackets, sorted unique choices,
  exact counts, bounded lazy expansion, and unique sampling.
- All 126 tests passed on Python 3.11, plus changed-file Black, full isort, and
  whitespace checks. Decimal ranges are bounds-checked before enumeration;
  digit-pattern maxima are checked before Cartesian expansion.
- Owner approved committing and pushing these changes on September 19.
