# Project status

Last reconciled: 2026-10-23 on `main` at `755f5ac`. The latest GitHub run passed
all 16 platform/Python combinations, formatting, and wheel/sdist build and
installed smoke checks, including the web frontend. Release metadata remains
RC1; the owner reports testing complete. RC2 release preparation remains
pending. No RC2 publication is claimed.

## Current state

- D07 is resolved: history display/search/export now live under `project history`
  without top-level aliases. `project history clear` and `project reset history`
  share a confirmed backend reset and suppress their own history entries.
  Apps without a project backend retain internal memory history and input recall
  with no built-in history commands. README, changelog and D07 document the move.

- Windows CI test fixes preserve quote-escaping coverage through a synthetic
  path suggestion instead of creating a filename containing a forbidden double
  quote. Completion checks wait for populated results; dialog keyboard tests
  wait for rendered focus targets before sending input. Dialog tests deliberately
  delay redraw to exercise this synchronization. Runtime behavior is unchanged.

- Tab now accepts the highlighted suggestion (or first candidate). Commands and
  scalar/file values add/reuse a separator and request the next suggestions;
  directories and comma-separated lists stay editable. Quoted continuing values
  keep the cursor inside the closing quote; Space finishes the argument and a
  matching typed quote reuses it. Shared terminal/browser edits preserve quote
  style, later arguments and browser Unicode cursor positions. Browser clicks
  use the same policy and stale completion responses are ignored. PathCompleter
  directory-only/filter configuration and advisory validation remain unchanged.
  Dispatch now keeps filesystem arguments literal instead of expanding them
  into a sole child or a similarly named existing file.
  Arrow-key previews now reuse the closing quote under the cursor and preserve
  its quote style, preventing duplicate quotes when selecting path children.
  See [completion usage](../README.md#completion-and-validation) and D04.

- Metadata remains `1.0.0rc1`; RC2 is next, pending release preparation and the
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
  Alt-Up/Down now replace Ctrl-Up/Down for one-line vertical output scrolling;
  Alt-Left/Right scroll unwrapped output horizontally. All four retain input
  focus in terminal and browser modes. Browser vertical steps use the rendered
  line height. README and generated UI help list the updated shortcuts (D05).

- Full-screen lifecycle queues stdout/stderr and pre-existing standard-stream
  logging through prompt-toolkit, preserves diagnostics, and restores streams
  and handler references on exit. CLI/web behavior stays unchanged (D05).

- Config commands now live under `project configs` with list/show/export/import/
  reset subcommands, without old-name aliases. `self.configs`, persistence, JSON
  format and reset confirmation are unchanged (D07).

- Built-in history/project results, including project configs, use queued UI
  dialogs and preserve application output. Actions finish before presentation;
  browser results belong to the submitting tab. CLI printing and clear/help/exit
  behavior stay unchanged. Application commands can opt in with result_title.

- Dialog support now includes button choices, radio/checkbox lists and a typed
  fixed-key dictionary editor in both interactive UIs. Shared synchronous
  validators retain invalid edits, focus inputs and propagate unexpected errors.
  Dictionary fields now use aligned label/value rows, a divider, distinct input
  backgrounds and focus highlights; help sits below its value. Other dialog
  layouts remain as before. All dialogs share a per-application/view queue;
  Escape follows the documented
  cancellation conventions. Convenience tasks participate in runtime shutdown.
  See D13 and [the dialog tutorial](../examples/16_dialogs.py).
- Dialog buttons now subclass upstream prompt-toolkit instead of copying its
  implementation. Cleanup removes floats before focus restoration, including
  cancellation and focus failures. The browser adapter supports older permitted
  ConditionalContainers without alternative_content. Locked prompt-toolkit is
  still 3.0.53; no dependency/version change is needed.

## Validation evidence

- October 23 D07 history hierarchy on `755f5ac` plus the working tree:
  all 202 tests passed on Python 3.11.16/Linux. Coverage includes retained memory
  history without commands, removed top-level names, nested help/completion and
  path providers, replayable exports and export errors, active-project switching,
  explicit history overrides, confirmation rejection and both shared clearing
  paths, CLI output, and browser result-dialog isolation/background output.
  Black/isort, lockfile and whitespace checks passed. Tests and formatting ran
  outside the sandbox to avoid previously observed executor stalls. Remote CI
  and manual acceptance remain pending for this command migration.

- October 23 release-readiness review: [GitHub run 40041532116](https://github.com/ControlThings-io/ctui/actions/runs/40041532116)
  passed at `755f5ac`: Python 3.11–3.14 on Linux x86-64, Linux ARM64, Windows,
  and macOS; Black/isort; distribution builds; isolated wheel/sdist base and
  web smoke tests; artifact upload. This resolves the remote Windows and
  artifact-job gaps below. These artifacts still report `1.0.0rc1`; final RC2
  metadata and artifacts need release verification. The owner subsequently
  reported testing complete on October 23; no per-platform manual results were
  supplied. Earlier evidence below describes checks and gaps at those revisions.

- October 23 Windows test fixes on `8a409c4` plus the working tree: all 198 tests
  passed on Python 3.11.16/Linux. Controlled 100 ms provider/redraw delays
  reproduced the empty completion list and dialog selection timeout in the
  original tests; corrected tests passed with the same delays. Black/isort,
  lockfile and whitespace checks passed. Windows execution remains pending.
- Inspected [GitHub run 40040974891](https://github.com/ControlThings-io/ctui/actions/runs/40040974891)
  at `8a409c4`: all four Windows versions rejected the double-quote filename;
  3.11–3.13 also timed out in dialog selection, and 3.11–3.12 additionally timed
  out in dictionary validation and checked an empty, still-loading completion
  list. All 12 Linux/macOS test jobs and formatting passed; artifact jobs were
  skipped because tests failed. Earlier console/path fixes are no longer the
  failures reported by this run.

- October 23 quoted-path preview fix on `8374bee` plus the working tree: all 198
  tests passed on Python 3.11.16/Linux, including repeated menu selections,
  cancellation, both quote styles, apostrophes, inline options, later arguments,
  and real terminal input processing for Down/Up, Tab and Space. Black/isort,
  lockfile and whitespace checks passed. The sandbox stalled asyncio executor
  shutdown; the suite passed outside it. Manual terminal
  acceptance, browser smoke and remote platform checks remain pending for this fix.

- October 20 completion acceptance on `d060d28` plus the working tree: all 197
  ctui tests passed on Python 3.11.16/Linux, including the real terminal input
  processor, highlighted previews, directory-child refresh, quoted paths,
  lists, inline options, existing separators and literal dispatch paths.
  Headless Chromium passed [browser_completion.py](../tests/browser_completion.py),
  covering immediate Tab, selected candidates, clicks, nested directory-only
  completion, Space acceptance, filenames with spaces/apostrophes/double quotes
  and Unicode, later arguments, list continuation and literal directory dispatch.
  All 127 downstream ctmodbus tests passed with the editable ctui override before
  the final terminal-menu refresh; its real terminal test passed again afterward.
  Black/isort, JavaScript syntax, both project lockfiles and whitespace passed.
  Dependency metadata is unchanged. Manual terminal acceptance, Firefox/Safari
  and remote platform checks remain pending; no release/artifact checks were run.

- October 20 output-scroll shortcut change on `72ad45d` plus the working tree:
  all 40 focused application/footer/help tests passed on Python 3.11.16 using
  ctmodbus with the adjacent editable ctui checkout. Direct terminal-binding
  checks verified exact one-line steps, retained input/cursor/focus, removal of
  Ctrl-Up/Down, and updated help. Node handler checks verified Alt arrows,
  rendered-line vertical steps, Ctrl removal, paging and plain-arrow history.
  JavaScript syntax, changed-file Black/isort and whitespace checks passed.
  Manual terminal/browser acceptance and remote platform checks remain pending.

- October 7 dialog expansion and inline dictionary layout: all 187 tests passed
  on Python 3.11.16/Linux x86-64 with locked prompt-toolkit 3.0.53. All 15 dialog
  regressions also passed with the permitted minimum 3.0.36; the earlier full
  185-test suite passed with that minimum before the layout follow-up.
  Coverage includes terminal alignment at 56/140 columns, wide characters,
  long labels in a 40-column dialog, focus styling, keyboard navigation,
  conversion/validation, queue cleanup, cancellation and real WebSocket flows.
  Chromium smoke and tutorial 16 passed, including aligned rows at desktop and
  390px mobile widths, accessible field help, retained edits and background
  output updates. Black/isort, lockfile and whitespace checks passed. Real
  terminal visual acceptance, Firefox/Safari and remote platform checks remain
  pending.

- October 7 prompt-toolkit audit: installed/locked 3.0.53 matches current PyPI
  release. All 146 installed package files with recorded hashes matched their
  installation metadata; no source overwrite or runtime monkey-patching found.
  Compared local dialog/button code with installed upstream implementations.
  Isolated 3.0.36 check confirms ConditionalContainer lacks alternative_content;
  current browser adapter reads it although metadata permits that version.
  Audit recommendations are now implemented in the dialog expansion below.

- Result popup change: all 171 tests passed on Python 3.11.16/Linux x86-64,
  covering action completion, metadata, terminal queuing, output updates while
  dialogs are open, web tab isolation/disconnect, and normal CLI printing.
  Chromium storage tutorial 14 passed with the result popup flow. Black/isort
  and whitespace checks passed. Manual terminal and remote matrix acceptance
  remain pending.

- October 6 config command move: all 166 tests passed on Python 3.11.16/Linux
  x86-64, covering nested help/completion, old-name removal, unchanged reset
  prompt, config exchange and project statistics. Storage tutorial 14 passed in
  Chromium; automatic CLI showed its local config through the new command.
  Black/isort and whitespace checks passed. Remote matrix/manual terminal
  acceptance remain pending.

- October 6 terminal-output protection: all 165 tests passed on Python
  3.11.16/Linux x86-64. Real terminal application tests cover existing handlers,
  background writes, CommandError popup and input preservation; scope tests cover
  failure/cancellation, partial output and retained handlers after shutdown.
  Black/isort and whitespace checks passed. Real console and remote platform
  matrix acceptance remain pending.

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

- Owner testing is complete as reported October 23. The cross-platform CI matrix
  and artifact jobs passed at `755f5ac`; remote checks for the subsequent D07
  command migration and release-version checks remain pending.
- Prepare an explicit dated `1.0.0rc2` changelog section covering the comparison
  with `v1.0.0rc1`, including command/API compatibility changes; reconcile the
  existing stable `1.0.0` heading with the actual prerelease history. Current
  Unreleased notes cover only browser support and completion, omitting other
  shipped changes. The publishing workflow falls back to the stable section
  unless an exact RC2 section exists.
- Set `pyproject.toml` to `1.0.0rc2`, refresh the root package
  entry in `uv.lock`, and follow [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
  on the intended release revision: source/lock checks, artifact smoke tests
  and archive metadata inspection, then a passing branch build. Confirm trusted
  publishing configuration before an explicitly authorized matching tag/push.
  Verify PyPI artifacts/attestations, GitHub prerelease status and an isolated
  published-package tutorial afterward. No release/version change made here.

## Handoff

Implementation and Windows test portability/synchronization fixes are committed
through `755f5ac` on `main`. The status reconciliation and D07 follow-up are
uncommitted, including project history command migration, regression tests, README,
changelog and decision updates. Remaining release work and validation are listed
above.
Commit/push only with explicit authorization.
