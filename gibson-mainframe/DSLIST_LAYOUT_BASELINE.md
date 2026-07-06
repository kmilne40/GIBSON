# DSLIST Layout Baseline

Findings:
- DSLIST renders `Command ===>` visually on row 3 and should read at row 3, column 13 in the current `read_line_at()` convention.
- The title line combined a variable prefix with row-count text and could exceed 79 visible columns when the prefix or row count was long.
- Long visible title lines can wrap in ANSI clients and make subsequent input appear to land above or outside the intended `Command ===>` field.

Decision:
- Add DSLIST layout constants.
- Build the title line with a fixed visible width and a non-overlapping row-count suffix.
- Continue using the existing command-line shortcut model (`E 1`, `B 1`, `M 1`) rather than redesigning DSLIST line-command fields.
