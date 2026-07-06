# Changelog

## gibson-mainframe-login-blank-screen-and-startup-fixes-v1

- Fixed the VTAM "Logon Type:" login field wrapping around the entire 3270
  screen buffer (unbounded input field), which caused the screen to blank
  on the first keystroke for real 3270 clients. `render_3270()` now sets
  `bound_input_fields = True`.
- `gibsonctl.sh` no longer passes `--no-tn3270` by default, so the
  dedicated TN3270 listener (port 3270, used by `web3270`/x3270 clients)
  starts automatically.
- `gibsonctl.sh` now resolves `setsid` correctly on macOS by falling back
  to Homebrew's keg-only `util-linux` build when `setsid` isn't already on
  `PATH`. Previously `start`/`restart` failed silently on macOS with
  `setsid: command not found`.
- The non-interactive `--ipl-prestart-console` scripted reply sequence
  (used by `gibsonctl.sh` for automated start/restart) only answered
  IPL replies R01-R05. It now also answers R06 (DVCAPIN) with `SKIP`,
  since the boot sequence added that prompt after the scripted list was
  last updated. Non-interactive starts previously aborted with
  `GIBMCS010E IPL REPLY SEQUENCE ENDED BEFORE COMPLETION` before any
  service came up.
- Fixed an infinite TN3270E telnet negotiation loop in
  `tn3270_server.py`: `_reply_telnet()` always replied `DONT TN3270E` to
  a `WONT`, even when the client was just re-acknowledging a `DONT` it
  had already sent. Paired with a matching bug in the `web3270` bridge,
  this bounced forever at wire speed the moment TN3270E was
  (re)negotiated - reproduced when logging into the ZVM app. The server
  now stops replying once TN3270E is already marked rejected.

## gibson-mainframe-ispf-coordinate-editor-fix-v1

- Added `gibson.render.coordinates` with explicit zero-based and one-based ANSI cursor helpers.
- Added DSLIST layout constants and fixed-width title generation.
- Confirmed DSLIST input reads from the visible `Command ===>` field.
- Removed editor `_ansi_move()` hard-coded one-row correction.
- Added editor physical cursor clamping to visible field width.
- Added regression tests for DSLIST and editor coordinate/no-wrap stability.
- Left Option 5 and language runtimes unchanged.
