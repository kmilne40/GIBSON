# DSLIST Command Field Fix

Changes:
- Added DSLIST layout constants to keep render/input positions aligned.
- Added a fixed-width DSLIST title formatter so row-count text does not wrap into the command area.
- Confirmed DSLIST command input is read from row 3, column 13, matching the visible `Command ===>` row.
- Preserved existing command-line line-command model such as `E 1`, `B 1`, `M 1`.
