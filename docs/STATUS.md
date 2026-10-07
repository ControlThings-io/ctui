# Project status

Last reconciled: 2026-10-06 on `main` at `216ef28`, after PR #7 merged the
web frontend. Owner-supplied Windows CI output reports seven test errors across
Python 3.11–3.14; no successful remote rerun or publication is claimed.

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

- Typed `exit` now uses the shared confirmation flow in both interactive UIs.
  Approved web exit stops the shared session and asks only the submitting tab
  to close, with a manual-close message when browser policy blocks closure.

- Web completion rows separate bright suggestion labels from muted help with
  aligned columns and a subtle divider; narrow screens stack indented help.

- Startup always opens `default`, creating it if absent. Saved projects require
  manual loading; default data persists. Current selection remains informational
  in state.json. See D07 for the superseded startup behavior.

- `project delete` completion lists inactive catalog projects, filters prefixes,
  and refreshes after switching or deleting projects in both frontends.

- List argument completion continues after commas in both frontends. ctui
  excludes exact typed elements, leaves partial matches available, and preserves
  earlier elements on insertion; providers receive an empty word (D04).

- New terminal output follows the final line at column zero and resets horizontal
  scrolling, preserving long lines without shifting right to their ends.
  Alt-Left/Right scroll unwrapped output horizontally with input retaining focus
  in terminal and browser modes. Generated UI help lists the Alt-arrow shortcuts
  beside the existing output navigation keys.

## Validation evidence

- October 6 output alignment/scrolling: all 162 tests passed on Python
  3.11.16/Linux x86-64. Regressions cover wide output, empty/trailing lines,
  horizontal bounds, bindings and unchanged input. Chromium smoke passed with
  both Alt-arrow shortcuts and focus preservation. Black/isort and whitespace
  checks passed. Manual terminal and remote matrix validation remain pending.

- October 6 list completion: all 160 tests passed on Python 3.11.16/Linux
  x86-64, including optional lists, inline options, unfinished quotes, insertion,
  exact filtering, help hints, Literal element choices, and unchanged dispatch
  list values. Black/isort and whitespace checks passed. Remote matrix and manual
  frontend acceptance remain pending.

- October 6 deletion completion: all 158 tests passed locally on Python
  3.11.16/Linux x86-64, including catalog order, active-project exclusion,
  prefix filtering and refresh after load/delete. Black/isort and whitespace
  checks passed. Remote CI remains pending.

- October 6 startup change: all 157 tests passed on Python 3.11.16/Linux x86-64.
  Regressions verify restart after saveas/load, preserved data, manual loading,
  and creation of default when only a renamed saved project exists. Black/isort
  and whitespace checks passed. Remote matrix validation remains pending.

- October 5 Windows CI fix: help fixtures use explicit pipe input/dummy output,
  avoiding Windows console discovery. Path suggestions preserve typed separators
  so forward-slash Windows prefixes survive dispatcher filtering. All 155 tests
  passed locally on Python 3.11.16/Linux x86-64, including simulated Windows path
  operations. Black/isort, lockfile and whitespace checks passed. A Windows CI
  rerun on Python 3.11–3.14 is still required.

- October 5 completion layout: Chromium browser smoke check passed, including
  separate label/help columns, stacked mobile help, Tab insertion, shared output,
  local drafts, help popups, focus and controls. Black/isort and whitespace checks
  passed. Firefox/Safari and remote CI remain unchecked for this layout change.

- October 5 exit change: all 154 unittest tests passed on Python 3.11.16,
  Linux x86-64, including rejection/approval and per-tab shutdown notification.
  Black/isort and whitespace checks passed. Manual terminal and real-browser
  tab-close acceptance remain pending; browser tutorial checks now approve exit.

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
  uses standard installs for platform tests and installed web artifacts.
  Remote CI has not been run from this workspace.

## Next steps

- Owner acceptance: try actual downstream tools in terminal, CLI and --web modes,
  including custom layouts, background progress and remote trusted certificates.
- Rerun Windows CI on Python 3.11–3.14 for the console/path fixes.
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

Web frontend changes are merged into `main` via PR #7; Windows CI fixes are
committed at `4833e58`; default-project startup is committed at `813f9aa`.
Project deletion completion is committed at `d4dd614`; list completion is
committed at `216ef28`. Output alignment changes are local and uncommitted;
commit/push only with explicit authorization.
