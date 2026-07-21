# Editor Cursor / No-Wrap Fix

Changes:
- Removed the hard-coded `row0 + 2` cursor correction in the editor.
- Editor cursor movement now uses the zero-based coordinate helper.
- Added `_physical_cursor_col()` to clamp the terminal cursor to Command, line-command or visible text field bounds.
- Data-entry cursor no longer advances to the full terminal edge when the visible text field is narrower.
- Header column range now reports the current visible range consistently.
