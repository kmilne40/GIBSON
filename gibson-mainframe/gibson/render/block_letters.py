from __future__ import annotations

import re

# Deterministic in-tree 5x5 block glyphs.  Kept intentionally compact so an
# eight-character z/OS-style sysname fits in an 80x24 VTAM panel.
GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#### ", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "F": ("#####", "#    ", "#### ", "#    ", "#    "),
    "G": (" ####", "#    ", "# ###", "#   #", " ####"),
    "H": ("#   #", "#   #", "#####", "#   #", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "#####"),
    "J": ("#####", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "###  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#### ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "S": (" ####", "#    ", " ### ", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "# # #", "## ##", "#   #"),
    "X": ("#   #", " # # ", "  #  ", " # # ", "#   #"),
    "Y": ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "   # ", "  #  ", " #   ", "#####"),
    "0": (" ### ", "#  ##", "# # #", "##  #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "#####"),
    "2": (" ### ", "#   #", "   # ", "  #  ", "#####"),
    "3": ("#### ", "    #", " ### ", "    #", "#### "),
    "4": ("#   #", "#   #", "#####", "    #", "    #"),
    "5": ("#####", "#    ", "#### ", "    #", "#### "),
    "6": (" ### ", "#    ", "#### ", "#   #", " ### "),
    "7": ("#####", "   # ", "  #  ", " #   ", "#    "),
    "8": (" ### ", "#   #", " ### ", "#   #", " ### "),
    "9": (" ### ", "#   #", " ####", "    #", " ### "),
    "-": ("     ", "     ", " ### ", "     ", "     "),
    " ": ("     ", "     ", "     ", "     ", "     "),
}

VALID_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,14}$")


def validate_hostname(name: str, *, max_len: int = 15) -> tuple[bool, str, str]:
    raw = (name or "").strip().upper()
    if not raw:
        return False, "", "HOSTNAME IS REQUIRED"
    if len(raw) > max_len:
        return False, raw, f"HOSTNAME TOO LONG - MAXIMUM {max_len} CHARACTERS"
    if not VALID_RE.fullmatch(raw):
        return False, raw, "USE A-Z, 0-9 OR HYPHEN; FIRST CHARACTER MUST BE A LETTER"
    return True, raw, ""


def block_lines(word: str, *, max_width: int = 78, fill: str = "#") -> list[str]:
    safe = (word or "GIBSON").strip().upper() or "GIBSON"
    safe = ''.join(ch if ch in GLYPHS else '-' for ch in safe)
    # Prefer mainframe-like 1-9 sysname display; wider names fall back to first
    # nine chars to keep the 3270 panel stable (9 glyphs = 61 cols < 78).
    if len(safe) > 9:
        safe = safe[:9]
    rows = ["" for _ in range(5)]
    for ch in safe:
        glyph = GLYPHS.get(ch, GLYPHS["-"])
        for idx, part in enumerate(glyph):
            rows[idx] += part.replace("#", fill) + "  "
    rows = [r.rstrip() for r in rows]
    width = max(len(r) for r in rows) if rows else 0
    if width <= max_width:
        pad = max(0, (max_width - width) // 2)
        return [(" " * pad + r)[:max_width] for r in rows]
    return [safe.center(max_width)]


def render_block_word(word: str, *, max_width: int = 78) -> str:
    return "\n".join(block_lines(word, max_width=max_width))
