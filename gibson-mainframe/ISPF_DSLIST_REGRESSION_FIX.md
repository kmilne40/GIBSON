# ISPF DSLIST Regression Fix

## Root cause
The prior PF/control-sequence update changed DSLIST input handling to use `panel_input_value(...)` but left later code referencing `raw`. That made normal DSLIST commands such as `E 1`, `B 1` and `M 1` capable of raising `NameError`. The same code read input from row 4, column 13, which is the DSLIST message/help row, not the rendered `Command ===>` field.

## Fix
- DSLIST now reads from row 3, column 13, matching the visible command field.
- DSLIST keeps both values needed by the panel:
  - raw typed text for line-command parsing, dataset specs, allocation and sort/refresh commands;
  - logical command/action for PF3/PF7/PF8/PF12 handling.
- PF-key actions still work without inserting escape text into the command field.
- Normal line commands such as `E 1`, `B 1`, `V 1`, `S 1`, `M 1`, `D 1`, and `R 1` no longer crash due to the missing raw variable.
