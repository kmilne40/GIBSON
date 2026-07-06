"""Render ANSI-coloured text into a 3270 ScreenBuffer.

Several Gibson subsystems (DVCA/Mel's Cargo, OMEN/CBSA, the DB2 command
processor, CICS CEMT output) emit colour with ANSI SGR escapes.  When those
appear in the EBCDIC/3270 path the escapes must not reach the datastream;
instead this helper walks the SGR runs and lays down correspondingly coloured
3270 fields, so the colour survives without any ``\\x1b`` bytes.
"""
from __future__ import annotations

import re
from typing import Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer

_SGR = re.compile(r"\x1b\[([0-9;]*)m")
# Any CSI escape sequence: ESC [ params final-byte (@ through ~). Covers SGR
# colours (...m), erase (2J), cursor home/move (H/f), etc.
_CSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# OSC (Operating System Command): ESC ] ... terminated by BEL or ST (ESC \).
# e.g. window-title sequences like ESC ]0;title BEL - these leak past a CSI-only
# stripper and show as "]0;title" garble on a 3270.
_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?")

# Other ESC escapes: two-char (ESC c, ESC 7/8 ...) and charset selects (ESC ( B).
_ESC_OTHER = re.compile(r"\x1b[ -/]*[0-~@-Z\\-_]")

# Any control/escape residue (a lone ESC or other C0 control: BEL, CR, etc.)
# must never reach a 3270 field; cp037 would turn it into bracket garble. Newline
# (\x0a) and tab (\x09) are deliberately preserved.
_C0 = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _strip_residual_csi(seg: str) -> str:
    if not seg:
        return seg
    if "\x1b" in seg:
        # Same escape pipeline as strip_ansi (CSI -> OSC -> other-ESC) so the
        # 3270 render path doesn't leak OSC window-title strings (']0;title')
        # or two-char ESC selects as bracket garble in '?' help and friends.
        seg = _CSI.sub("", seg)
        seg = _OSC.sub("", seg)
        seg = _ESC_OTHER.sub("", seg)
    return _C0.sub("", seg)

# SGR colour code -> 3270 colour.  Bright variants fold onto the base colour
# but raise the intensity flag.
_FG = {
    30: colors.WHITE, 90: colors.WHITE,
    31: colors.RED, 91: colors.RED,
    32: colors.GREEN, 92: colors.GREEN,
    33: colors.YELLOW, 93: colors.YELLOW,
    34: colors.BLUE, 94: colors.BLUE,
    35: colors.WHITE, 95: colors.WHITE,
    36: colors.TURQUOISE, 96: colors.TURQUOISE,
    37: colors.WHITE, 97: colors.WHITE,
}
_BRIGHT = {90, 91, 92, 93, 94, 95, 96, 97}


def strip_ansi(text: str) -> str:
    cleaned = _CSI.sub("", text or "")
    cleaned = _OSC.sub("", cleaned)
    cleaned = _ESC_OTHER.sub("", cleaned)
    cleaned = _C0.sub("", cleaned)   # residual C0 controls (BEL, CR, lone ESC); keeps \n \t
    # Transliterate box-drawing/Unicode glyphs that have no cp037 mapping (they
    # would otherwise render as '?' on a 3270) to plain ASCII equivalents.
    return cleaned.translate(_ASCII_FOLD)


_ASCII_FOLD = {
    0x2500: ord("-"), 0x2501: ord("-"), 0x2550: ord("="),   # ─ ━ ═
    0x2502: ord("|"), 0x2503: ord("|"), 0x2551: ord("|"),   # │ ┃ ║
    0x250C: ord("+"), 0x2510: ord("+"), 0x2514: ord("+"), 0x2518: ord("+"),
    0x251C: ord("+"), 0x2524: ord("+"), 0x252C: ord("+"), 0x2534: ord("+"),
    0x253C: ord("+"), 0x2022: ord("*"), 0x00B7: ord("."), 0x2026: ord("."),
    0x2018: ord("'"), 0x2019: ord("'"), 0x201C: ord('"'), 0x201D: ord('"'),
    0x2013: ord("-"), 0x2014: ord("-"),
}


def render_ansi_to_screen(text: str, *, base_colour: str = colors.GREEN,
                          rows: int = 24, cols: int = 80,
                          screen: Optional[ScreenBuffer] = None,
                          start_row: int = 1) -> ScreenBuffer:
    """Convert ANSI text into a coloured ScreenBuffer (no escapes in output)."""
    s = screen if screen is not None else ScreenBuffer(rows=rows, cols=cols)
    s.extended_attributes = True
    row = start_row
    for raw_line in (text or "").replace("\r", "").split("\n"):
        if row > rows:
            break
        col = 1
        colour = base_colour
        intens = False
        pos = 0
        for m in _SGR.finditer(raw_line):
            seg = _strip_residual_csi(raw_line[pos:m.start()])
            if seg:
                s.put(row, col, seg[: max(0, cols - col + 1)], colour,
                      protected=True, intensified=intens)
                col += len(seg)
            for part in (m.group(1) or "0").split(";"):
                if part == "" or part == "0":
                    colour, intens = base_colour, False
                elif part == "1":
                    intens = True
                elif part.isdigit():
                    code = int(part)
                    if code in _FG:
                        colour = _FG[code]
                        if code in _BRIGHT:
                            intens = True
            pos = m.end()
        tail = _strip_residual_csi(raw_line[pos:])
        if tail:
            s.put(row, col, tail[: max(0, cols - col + 1)], colour,
                  protected=True, intensified=intens)
        row += 1
    return s
