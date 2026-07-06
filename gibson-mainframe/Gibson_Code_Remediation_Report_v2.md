# Gibson Code Remediation Report v2

## 1. Summary

This remediation pass applied the approved fixes to the latest uploaded Gibson package `gibson-mainframe-ispf-coordinate-editor-fix-v1(2).zip`.

Implemented changes:

- **Fix A — ISPF/eZedit coordinate correction and `LN(x)` support**: corrected the ANSI editor render/cursor contract, removed the extra clear-line displacement, made the visible editor panel fit a 24-line terminal, added explicit `LN(n)` / `TEXT(n)` command support, and added regression tests.
- **Fix B — VTAM/RASFRAME alignment and ASCII-safe logo correction**: replaced hard-coded banner spacing with calculated centred framing, removed Unicode block rendering from terminal VTAM panels, regenerated canonical VTAM assets, and updated tests to assert ASCII-safe output.
- **Fix C — DVCA MCAD PIN brute-force workflow**: changed DVCAPIN fallback from `1234` to `1337`, normalised brute-force candidates to exactly 20 attempts, ensured the active DVCAPIN is included, and routed legacy DVCA brute-force logic to the same DVCAPIN semantics.
- **Fix D — ZSEC SMF7 routing**: added `SMF7` to the structured zSecure SMF review route.
- **Fix E — Regression tests**: added `tests/test_remediation_v2.py` and updated legacy tests where old expectations conflicted with approved behaviour.

## 2. Files changed

Source files changed:

- `gibson/apps/editor.py` — fixed ANSI clear/render row alignment, added 24-line-safe editor layout, centralised visual row/file index helpers, added `LN(n)` and `TEXT(n)` support.
- `gibson/screens/vtam_model.py` — added centred VTAM frame helper; switched VTAM terminal logo rendering to ASCII-safe dynamic block output.
- `gibson/render/block_letters.py` — changed default block fill from Unicode `▇` to ASCII `#` for terminal safety.
- `gibson/screens/vtam.txt` — regenerated canonical VTAM screen asset.
- `gibson/assets/vtam.txt` — regenerated canonical VTAM screen asset.
- `gibson/core/dvcapin.py` — added `FALLBACK_PIN = '1337'`, changed unset fallback verification/reveal behaviour, added `active_training_pin()` helper.
- `gibson/apps/pin_bruteforce.py` — added `MAX_PIN_ATTEMPTS = 20` and deterministic DVCAPIN-aware candidate normalisation.
- `gibson/apps/dvca/programs.py` — updated legacy DVCA brute-force and PIN check behaviour to use DVCAPIN semantics and 20-attempt normalisation.
- `gibson/apps/zsecure_engine.py` — routed `ZSEC SMF7` through the structured SMF review path.

Test files changed or added:

- `tests/test_remediation_v2.py` — new regression tests for editor coordinates, VTAM alignment, DVCA/DVCAPIN, and ZSEC SMF7.
- `tests/test_canonical_vtam_renderer.py` — updated legacy expectation from Unicode logo to ASCII-safe VTAM logo.
- `tests/test_vtam_front_screen.py` — updated legacy expectation from Unicode logo to ASCII-safe VTAM logo.
- `tests/test_r05_osint_cti_board_v1.py` — updated IPL flow expectation to account for current R06 DVCAPIN step after R05 hostname.

## 3. Fix details

### Fix A — ISPF/eZedit coordinate correction

Root cause: the ANSI editor renderer placed `colors.CLEAR` as a separate list element and then joined it with newlines. This caused the visible editor content to start one line lower than the logical cursor coordinates. The editor also attempted to render 25 logical rows into a 24-line terminal, which could drop status/cursor context and produce apparent one-line cursor errors. `LN(x)` syntax was not explicitly supported.

Implementation detail:

- Removed the separate clear-line row and prepend `colors.CLEAR` directly to the rendered screen string.
- Reduced visible data rows to 19 so the panel fits as title, command, top marker, 19 data rows, bottom marker, and status.
- Added visual row/file-index helper methods.
- Added explicit `LN(n)`, `LINE(n)`, `LC(n)`, `LINECMD(n)`, `TEXT(n)`, `TXT(n)`, and `DATA(n)` command parsing.
- Preserved existing PF-key and save/cancel behaviour.

Tests added:

- `test_editor_screen_fits_24_rows_without_truncating_status`
- `test_editor_ln_paren_moves_to_correct_line_command_row`
- `test_editor_text_paren_moves_to_correct_text_row_after_scroll`

### Fix B — VTAM/RASFRAME alignment

Root cause: the VTAM/RASFRAME frame was hard-coded with the top asterisk line at column 1 while the title and bottom frame lines were indented. The terminal logo also used Unicode block characters that can render as mojibake in raw telnet/3270 clients.

Implementation detail:

- Added `_centered_frame()` to build all frame lines together with the same indent and width.
- Rendered all VTAM terminal logos through ASCII-safe `block_lines(..., fill="#")`.
- Changed the default block letter fill to ASCII `#`.
- Regenerated `gibson/screens/vtam.txt` and `gibson/assets/vtam.txt`.

Tests added/updated:

- `test_vtam_frame_aligned_and_ascii_safe_for_rasframe`
- Updated legacy VTAM logo expectations in existing tests.

### Fix C — DVCA DVCAPIN/20-attempt workflow

Root cause: the DVCAPIN fallback was `1234`, and the brute-force candidate loader could return only four candidates from the default file. A separate legacy DVCA brute-force path used its own fixed supervisor PIN and attempt count.

Implementation detail:

- Changed DVCAPIN fallback to `1337`.
- Added `dvcapin.active_training_pin()`.
- Added `MAX_PIN_ATTEMPTS = 20`.
- Normalised brute-force candidate sets to exactly 20 entries.
- Guaranteed the active DVCAPIN or fallback `1337` is present in the 20-attempt candidate set.
- If the supplied dataset is longer than 20 entries and does not include the target, the target is forced into the final slot.
- Updated legacy DVCA brute-force logic to use the same normalisation and DVCAPIN verification.

Tests added:

- `test_dvcapin_unset_fallback_is_1337_not_1234`
- `test_dvca_pin_uses_configured_dvcapin_and_20_attempts`
- `test_pin_bruteforce_long_dataset_forces_target_into_twenty`

### Fix D — ZSEC SMF7 routing

Root cause: `ZSEC SMF7` was listed/expected but was not included in the structured zSecure SMF topic set.

Implementation detail:

- Added `SMF7` to the zSecure structured SMF review topic set.

Test added:

- `test_zsec_smf7_routes_to_structured_smf7_view`

## 4. Additional findings

During broader targeted test runs, unrelated failures were observed in existing tests outside the approved patch scope:

- `tests/test_tn3270_and_editor_additions.py::test_tn3270_listener_supports_vtam_to_tso_and_cics` returned an empty first screen in the no-negotiation path. The negotiated TN3270 tests pass, so this appears to be a pre-existing or separate no-negotiation listener issue.
- Some broad zSecure tests expect older report semantics for `ZSEC CICS`, `ZSEC DB2`, `ZSEC SMF30`, and main-menu banner text. These are outside the requested `ZSEC SMF7` fix and should be reviewed separately before changing zSecure routing more broadly.
- One broad OMVS/nmap mapping test expects exact text for a port 23-to-2023 compatibility message; this is unrelated to the DVCA PIN change.
- Full pytest was not completed due to sandbox time limits.

## 5. Test results

The strongest relevant regression set passed:

```text
29 passed, 24 warnings
```

Command:

```bash
pytest -q tests/test_ispf_coordinate_editor_fix_v1.py tests/test_ispf_stability_fix_v1.py tests/test_v5_pin_autotick_dvcapin_welcome.py tests/test_gibby_masterconsole_cti_manual_dvca.py tests/test_smf7_data_lost_records.py tests/test_zsecure_smf_views.py tests/test_remediation_v2.py
```

The new remediation regression file passed:

```text
8 passed
```

Command:

```bash
pytest -q tests/test_remediation_v2.py
```

Targeted VTAM, DVCA/PIN, and zSecure keyword runs were also attempted. They surfaced unrelated or broader legacy expectation failures, documented in `Gibson_Code_Remediation_Test_Results_v2.txt`.

## 6. Known limitations

- Full test suite execution was not completed in the sandbox due to time limits.
- The no-negotiation TN3270 listener test still fails and should be treated as a separate listener compatibility issue.
- Some older tests still assert historical output strings or routing semantics that conflict with newer behaviour or are outside the approved fixes.
- The patch does not attempt broad zSecure, OMVS/nmap, or TN3270 listener refactoring beyond the requested scope.

## 7. Packaging

Output package:

```text
gibson-mainframe-fixed-v2.zip
```

The zip contains the full patched `gibson-mainframe` source tree, not only changed files.

## 8. Verification checklist

```text
[x] ISPF/eZedit cursor issue patched
[x] LN(x) behaviour patched
[x] VTAM/RASFRAME alignment patched
[x] VTAM terminal logo ASCII-safe
[x] DVCA brute force uses 20 attempts
[x] DVCA brute force uses DVCAPIN
[x] DVCA fallback PIN is 1337
[x] 1234 is not accepted unless configured
[x] ZSEC SMF7 routing patched
[x] Targeted tests run
[x] Full package zip created
[ ] Full test suite completed without timeout
[ ] Unrelated TN3270 no-negotiation listener issue resolved
```
