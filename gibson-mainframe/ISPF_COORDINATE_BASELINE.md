# ISPF Coordinate Baseline

Baseline package: `gibson-mainframe-ispf-stability-fix-v1.zip`.

Findings:
- `SocketInputDriver.read_line_at(row, col)` sends ANSI cursor-positioning directly and therefore expects one-based row/column values.
- ISPF DSLIST used a rendered ANSI panel and a separate fielded panel builder. Both described `Command ===>` on row 3, but title/header content could exceed the visible terminal width and cause wrapping before the command line.
- The editor used zero-based internal rows/columns but `_ansi_move()` applied a hard-coded `row0 + 2` correction. That made the physical cursor one row lower than the logical editor row and could make input look wrapped or shifted.

Decision:
- Keep `read_line_at()` one-based for compatibility.
- Introduce explicit coordinate helpers for zero-based and one-based ANSI moves.
- Use a zero-based contract inside the editor and convert once at cursor output.
