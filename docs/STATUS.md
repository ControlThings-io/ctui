# Project status

Last reconciled: 2026-09-18, against `main` at `7e4e971`.

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

The working tree was clean before these three continuity files were added.
Local `origin/main` also pointed to `7e4e971`; remote refs were not refreshed.

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
- [ ] Capture the owner's remaining changes and acceptance tests as concrete
  RC2 tasks; their details have not yet been supplied.
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

This September 18 task changes documentation only. Content was reconciled
against local conversation records, commit history, source, tests, and release
workflows. Runtime tests were not rerun for this documentation update.
All three new files passed local Markdown-link and whitespace checks;
`git diff --check` also passed for the tracked working tree.

## Details still needed

- Which changes and additional tests should be completed for RC2? The owner
  has confirmed they are needed but has not yet listed them.

## Laptop handoff

Update this file and relevant decisions with the work, commit and push the
working branch, then pull that branch on the other laptop before starting
Codex. Start by reading `AGENTS.md` and these notes. Uncommitted/unpushed work
does not transfer. Do not store full private transcripts in the repository.
