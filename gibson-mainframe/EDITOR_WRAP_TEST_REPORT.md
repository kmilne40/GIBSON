# Editor Wrap Test Report

Validated:
- Editor `_ansi_move()` now uses a true zero-based coordinate contract.
- Physical cursor clamping keeps the cursor inside the visible text area.
- Typing 60 characters no longer depends on terminal wrapping and remains in the logical record.
- Rendered editor lines remain within 80 visible columns after ANSI stripping.
