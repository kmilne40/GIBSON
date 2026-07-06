# ISPF Coordinate Contract

- Internal editor coordinates are zero-based.
- ANSI terminal coordinates are one-based.
- `ansi_move_zero_based(row0, col0)` converts zero-based coordinates to ANSI.
- `ansi_move_one_based(row1, col1)` emits already-one-based coordinates.
- `SocketInputDriver.read_line_at(row, col)` remains one-based for compatibility.
