from __future__ import annotations


def ansi_move_zero_based(row0: int, col0: int) -> str:
    """Return ANSI cursor-position sequence for zero-based coordinates.

    Gibson panel/editor internals use zero-based row/column positions. ANSI
    terminals use one-based row/column positions. Keep that conversion in one
    named helper so future panel fixes do not mix conventions.
    """
    if row0 < 0 or col0 < 0:
        raise ValueError("negative zero-based terminal coordinates are invalid")
    return f"\x1b[{row0 + 1};{col0 + 1}H"


def ansi_move_one_based(row1: int, col1: int) -> str:
    """Return ANSI cursor-position sequence for one-based coordinates."""
    if row1 < 1 or col1 < 1:
        raise ValueError("ANSI one-based coordinates must be >= 1")
    return f"\x1b[{row1};{col1}H"
