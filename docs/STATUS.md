# Project status

Last reconciled: 2026-10-05, web frontend work on `feat/web-frontend`, based on
`main` at `fdda194`. Main was fetched from GitHub at workspace setup; no live
remote CI or publication checks are claimed.

## Current state

- Metadata remains `1.0.0rc1`; RC2 is next, pending owner acceptance and the
  release checks in [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md).
- Main includes reusable path completion (`fdda194`), dialog redraw, command
  error containment, and the post-RC1 help/type improvements.
- Browser support uses required aiohttp; standard installs include it. `--web` runs a browser-only
  session; default full-screen UI and command/file CLI behavior remain intact.
- Existing supported compose() widgets render in plain HTML/CSS/JavaScript.
  One app process/port owns a shared session; tabs keep local drafts/scrolling.
  Submitted commands survive disconnect; unanswered dialogs cancel. Help opens
  a popup and preserves output. See D15 and the README for the accepted design.
- Remote binds require supplied TLS cert/key files. Session token authentication,
  origin/host checks, bounded update queues, and independent per-process cookies
  are implemented. The web extra was removed at the owner's direction (D15).

## Validation evidence

- October 5 dependency change: standard locked sync installed aiohttp without
  extras; all 152 tests passed on Python 3.11.16, Linux x86-64. Black/isort,
  lockfile and whitespace checks passed. Built wheel and source distribution
  passed isolated base and web smoke checks without extra dependency flags.
  Remote CI and other Python/platform checks remain pending for this change.
- The following broader frontend evidence is from October 1, before this change.

- All 152 unittest tests passed on Python 3.11.16 and 3.14.7 on Linux x86-64.
  The web tests exercise real HTTP/WebSocket connections, independent sessions,
  multi-tab output, reconnect, completion, dialogs, custom controls, TLS, malformed
  input, disconnect behavior, and startup/shutdown cleanup.
- Chromium and Firefox checked shared output, local drafts, both main and targeted
  help popups, preserved output, keyboard popup scrolling, focus restoration,
  buttons, F2 shortcuts, completion, and narrow browser layout. The reusable check
  is [browser_smoke.py](../tests/browser_smoke.py).
- All 16 tutorial applications passed in Firefox through real --web startup,
  including async downloads, progress, storage, custom layouts, filesystem/path
  completion and per-app help popups. A test timing issue in tutorial 15 reproduced
  in Chromium; awaiting its progress update fixed the check in both browsers.
  [browser_tutorials.py](../tests/browser_tutorials.py) supports individual repeats.
  Tutorial 15's progress command was also checked in CLI mode after guarding UI
  invalidation when no frontend exists.
- Wheel and source distribution built and passed isolated base and web
  smoke tests, including bundled static assets and WebSocket dispatch.
- Black/isort, lockfile, JavaScript syntax and whitespace checks passed. CI now
  now uses standard installs for platform tests and installed web artifacts.
  Remote CI has not been run from this workspace.

## Next steps

- Owner acceptance: try actual downstream tools in terminal, CLI and --web modes,
  including custom layouts, background progress and remote trusted certificates.
- Confirm Safari behavior and the cross-platform CI matrix.
  Arbitrary third-party prompt-toolkit controls, custom floats and renderer
  internals require dedicated browser adapters; these are documented limitations.
- Reconcile release labels: CHANGELOG says stable 1.0 while package metadata is
  RC1. Prepare RC2 only after acceptance, complete release verification and
  matching tag/publication checks. No release/version change made here.
- Resolve D07's outstanding history-clear naming discrepancy with the owner
  before changing that behavior. Existing palette definitions remain identical;
  no theme redesign is included in this work.

## Handoff

Development is isolated on `feat/web-frontend`. Check its Git history and status
for the latest local commits. Push/pull that branch to transfer it to another
machine; main is unchanged. A merge and package publication are separate steps.
