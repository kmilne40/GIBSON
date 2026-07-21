# Editor Wrap Baseline

Findings:
- `InteractiveEditor` has a logical record width (`LRECL`) and a visible text width (`TEXT_FIELD_WIDTH = 74`).
- `_ansi_move()` used `row0 + 2`, which made the physical terminal cursor inconsistent with internal editor coordinates.
- Cursor movement could be clamped to the full screen width rather than the visible text field, allowing terminal auto-wrap near the right margin.

Decision:
- Remove the global row correction.
- Clamp the physical cursor to the visible field, not the full 80-column screen.
- Keep logical record content separate from visible terminal width.
