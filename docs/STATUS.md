# Project status

Last reconciled: 2026-09-21, `main` at `91c3a6c`; working tree was clean before
the current help-dialog fix. Remote refs and live CI were not refreshed.

## Current state

- Package metadata and lockfile remain `1.0.0rc1`. The owner confirmed RC1
  publication and basic functionality on September 18. RC2 is next; stable 1.0
  still requires additional changes and acceptance testing (decision D10).
- Since RC1: OS classifiers, hierarchical help/dialog scrolling, completion,
  documentation, error containment, and protocol argument types were improved.
  Latest committed change: positional-help guidance added in `91c3a6c`.
- Mixed byte input requires explicit `0x`/`0b`/`0o`/`0d` prefixes; fuzzy patterns
  support bounded mixed-radix byte choices. See [types.py](../src/ctui/types.py)
  and the latest entries in [DECISIONS.md](DECISIONS.md).

## Current work

- Fixed missing modal redraws after asynchronous work. With `app_id`, SQLite
  history writes can finish after the input redraw; help then took focus without
  becoming visible. `show_dialog` now requests redraws on opening and cleanup.
- Removed the earlier unnecessary Enter-priority and float-order changes and
  their unsupported explanation in D12.
- Replaced the mocked help-opening regression with a real renderer/input test
  using SQLite history delayed beyond the input redraw. It checks visible help
  without another keystroke, dismissal, restored focus, and subsequent typing.
- Changes remain uncommitted.

## Validation evidence

- The new regression failed before the redraw fix and passed afterward, with
  the original Enter binding and float order restored. All eight help tests
  passed on Python 3.11.
- All 132 tests passed on Python 3.11; full Black/isort, lockfile, and
  whitespace checks passed.
- Earlier tests mocked dialog display and did not detect this rendering bug.
  The prior PTY verification claim was insufficient; no fresh manual terminal
  acceptance or remote CI is claimed.
- Artifact checks from September 18 predate these runtime changes; repeat them
  for RC2 following the release checklist.

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
