# Project status

Last reconciled: 2026-09-19, `main` at `88df143`; working tree was clean before
this instruction/documentation task. Remote refs and live CI were not refreshed.

## Current state

- Package metadata and lockfile remain `1.0.0rc1`. The owner confirmed RC1
  publication and basic functionality on September 18. RC2 is next; stable 1.0
  still requires additional changes and acceptance testing (decision D10).
- Since RC1: OS classifiers, hierarchical help/dialog scrolling, completion,
  documentation, error containment, and protocol argument types were improved.
  Latest code change: duplicate group suggestions fixed in `6e17839`.
- Mixed byte input requires explicit `0x`/`0b`/`0o`/`0d` prefixes; fuzzy patterns
  support bounded mixed-radix byte choices. See [types.py](../src/ctui/types.py)
  and the latest entries in [DECISIONS.md](DECISIONS.md).

## Current documentation work

- Separated personal Git, continuity, documentation, and verification preferences
  into `~/.codex/AGENTS.md`; repository instructions retain ctui conventions,
  tooling, compatibility, and a code map.
- Replaced accumulated status history with this snapshot. Earlier milestones,
  session evidence, and validation records remain in Git (`88df143` and earlier).
- Preserved decision rationale, clarified superseded radix rules, and recorded
  the instruction split in D15. Startup reading now targets relevant decisions.
- Documentation changes remain uncommitted. No runtime behavior changed.

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
