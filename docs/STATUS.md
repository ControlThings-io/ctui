# Project status

Last reconciled: 2026-09-21, `main` at `094b932`; working tree was clean before
the current positional-help task. Remote refs and live CI were not refreshed.

## Current state

- Package metadata and lockfile remain `1.0.0rc1`. The owner confirmed RC1
  publication and basic functionality on September 18. RC2 is next; stable 1.0
  still requires additional changes and acceptance testing (decision D10).
- Since RC1: OS classifiers, hierarchical help/dialog scrolling, completion,
  documentation, error containment, and protocol argument types were improved.
  Latest code change: project-load suggestions added in `b124603`.
- Mixed byte input requires explicit `0x`/`0b`/`0o`/`0d` prefixes; fuzzy patterns
  support bounded mixed-radix byte choices. See [types.py](../src/ctui/types.py)
  and the latest entries in [DECISIONS.md](DECISIONS.md).

## Current work

- Added concise help metadata for every previously undocumented user-facing
  positional argument in the framework, project commands, and examples 05–14.
- Preserved tutorial progression by leaving examples 01–03 unchanged; example
  04 remains the first introduction to `Argument` help metadata.
- Removed the redundant `(default)` wording from the `history` count description;
  generated detailed help already displays its default value separately.
- Changes remain uncommitted.

## Validation evidence

Historical results recorded in the previous status; not rerun for this task:

- September 19, mixed-radix work (`af7e363`): all 126 tests passed on Python
  3.11; changed-file Black, full isort, and whitespace checks passed.
- September 19, completion fix (`6e17839`): eight focused completion tests,
  changed-file Black, and whitespace checks passed. The full suite was not
  rerun after this fix.
- September 18, legacy cleanup (recorded in `ba28f5a`): wheel/sdist builds and
  isolated artifact smoke tests passed. These predate subsequent runtime changes.
- Current documentation task: content review, relative-link checks, and
  `git diff --check` passed. Runtime tests were not needed or rerun.
- Current project-completion task: all 15 project tests passed on Python 3.11;
  changed-file Black/isort and whitespace checks passed.
- Current cursor-restoration task: all five error-boundary tests passed on
  Python 3.11; changed-file Black/isort and whitespace checks passed.
- Current argument-order task: all 130 tests passed on Python 3.11; full Black,
  isort, lockfile, and whitespace checks passed.
- Current history-help task: all seven help tests passed on Python 3.11;
  changed-file Black/isort and whitespace checks passed.
- Current positional-help task: all 131 tests passed on Python 3.11; full Black,
  isort, lockfile, whitespace, and command-metadata audit checks passed. The
  audit's only help-free positional arguments are intentionally in examples 01–03.
- No fresh remote CI, publication, or manual terminal acceptance is claimed.

## Next steps: RC2

- Manually check help scrolling and focus restoration in real terminals,
  including narrow windows and application-specific shortcuts.
- Capture further owner-requested RC2 changes and acceptance tests. Record
  platform, Python version, package/revision, and results for acceptance runs.
- Reconcile release documentation: CHANGELOG currently labels `[1.0.0]` stable
  while metadata remains RC1. Confirm intended labels/date and readiness
  classifier; RC note fallback alone is not a workflow failure.
- Prepare `1.0.0rc2` after remaining changes/testing, including post-RC1 fixes.
  Follow [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) for that revision,
  including full source/artifact checks, remote CI, matching tag, publication,
  and release/attestation links. Do not reuse RC1 validation as RC2 evidence.
- Resolve D07's outstanding `history clear` versus `project reset history`
  discrepancy with the owner before changing that behavior.

## Optional follow-ups, not release commitments

- Background-job service and `py.typed` remain explicitly optional (D10).
- Assess existing tests before adding cancellation/database, large-transfer,
  or repeated-lifecycle stress coverage; reduce duplicate CI runs if warranted.
- Previously documented limits: example 13's custom root lacks modal float
  support; theme palettes are identical; dialogs have a horizontal-scrollbar
  TODO. Cancellation cleanup was subsequently fixed in `be050b8`.

## Handoff

No implementation blocker identified. Remaining validation is listed above.
Repository notes transfer with the branch only after explicitly authorized
commit/push, followed by a pull on the receiving laptop. Copy the global
`~/.codex/AGENTS.md` separately; it is not tracked by this repository.
