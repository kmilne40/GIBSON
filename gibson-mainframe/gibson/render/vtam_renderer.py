from __future__ import annotations

import os

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.screens.vtam_model import VtamScreenModel

BLOCK_FALLBACK = "#"

# Block glyphs the banner may be composed of, across source ('#'), the legacy
# solid logo ('▇'/'█') and the half-height blocks ('▄'/'▀').
BANNER_GLYPHS = {"#", "▇", "█", "▄", "▀"}

# Selectable fill glyph for the *displayed* banner.  The model still emits an
# ASCII-safe '#' logo (so render_plain / TN3270 / tests stay byte-stable); the
# ANSI path swaps in the chosen glyph for display.
_FILL_CHOICES = {
    "half": "▄",    # U+2584 LOWER HALF BLOCK (default - "half size" block)
    "halfblock": "▄",
    "lower": "▄",
    "upper": "▀",   # U+2580 UPPER HALF BLOCK
    "block": "█",   # U+2588 FULL BLOCK (solid)
    "full": "█",
    "seven": "▇",   # U+2587 lower seven-eighths
    "hash": "#",    # original ASCII-safe hatching
    "ascii": "#",
}


def _safe_ansi_text(text: str) -> str:
    return text.replace("▇", BLOCK_FALLBACK)


def is_banner_line(line: str) -> bool:
    """True for the block-letter hostname banner rows.

    Those rows are produced by block_letters.block_lines() and contain only a
    block glyph ('#', '▇' or '█') plus spacing, which uniquely distinguishes
    them from the '*' title border, the '-' separators, and ordinary text.
    """
    stripped = (line or "").strip()
    if not stripped:
        return False
    chars = set(stripped)
    return chars <= (BANNER_GLYPHS | {" "}) and bool(chars & BANNER_GLYPHS)


def banner_fill() -> str:
    """Resolve the glyph used to draw the displayed banner (GIBSON_BANNER_FILL).

    Defaults to the half-height block ('▄') for a lighter "half size" logo.
    Other options: block (█), upper (▀), seven (▇), hash (#, ASCII-safe).
    """
    choice = (os.environ.get("GIBSON_BANNER_FILL", "half") or "half").strip().lower()
    return _FILL_CHOICES.get(choice, "▄")


def solidify_banner(line: str, glyph: str | None = None) -> str:
    """Swap the ASCII '#' fill of a banner row for the chosen display glyph."""
    g = glyph if glyph is not None else banner_fill()
    if g == "#":
        return line
    out = line
    for src in ("#", "▇", "█", "▄", "▀"):
        if src != g:
            out = out.replace(src, g)
    return out


def banner_opener() -> str:
    """Resolve the SGR opener used to make the hostname banner glow.

    Honours the GIBSON_HOSTNAME_GLOW switch.  Defaults to the cyan 'banner'
    look; 'off' disables the effect; 'banner_pulse' adds a blink.
    """
    style = (os.environ.get("GIBSON_HOSTNAME_GLOW", "banner") or "banner").strip().lower()
    opener = colors.GLOW_STYLES.get(style)
    if opener is None:
        opener = colors.GLOW_STYLES["banner"]
    return opener


def classify_line(line: str) -> str:
    upper = line.upper()
    stripped = line.strip()
    if "RESTRICTED INFORMATION" in upper or "MONITORED" in upper or "UNAUTHORIZED" in upper or "CONSENT" in upper:
        return "red"
    # Banner rows are checked before the blue heuristic so a '▇'/'█' filled
    # logo is treated as a banner rather than incidentally classified blue.
    if is_banner_line(line):
        return "banner"
    if "PRODUCTION LPAR" in upper or (stripped and set(stripped) <= {"*"}):
        return "blue"
    return "green"


def colour_for_line(line: str) -> str:
    cls = classify_line(line)
    if cls == "red":
        return colors.RED
    if cls == "blue":
        return colors.BLUE
    # "banner" keeps a plain green base here so the TN3270 buffer and other
    # callers are unchanged; the glow is layered on only in render_ansi.
    return colors.GREEN


def render_plain(model: VtamScreenModel, *, compact: bool = False) -> str:
    lines = model.compact_lines() if compact else model.full_lines()
    return "\n".join(lines) + "\n"


def render_ansi(model: VtamScreenModel, *, compact: bool = False) -> str:
    lines = model.compact_lines() if compact else model.full_lines()
    opener = banner_opener()
    glyph = banner_fill()
    out = []
    for line in lines:
        if not line:
            out.append(line)
            continue
        if is_banner_line(line):
            # Hostname logo: swap the ASCII '#' for the chosen display glyph
            # (default the half-height block) and make it glow.
            lead = opener if opener else colors.TURQUOISE
            out.append(f"{lead}{solidify_banner(line, glyph)}{colors.RESET}")
        else:
            out.append(f"{colour_for_line(line)}{line}{colors.RESET}")
    return "\n".join(out) + "\n"


def render_3270(model: VtamScreenModel) -> ScreenBuffer:
    visible = [line for line in model.full_lines() if line.strip()]
    s = ScreenBuffer(rows=24, cols=80)
    s.extended_attributes = True
    s.bound_input_fields = True
    # 3270 has no SGR colour pulse, but the blink extended-highlight attribute
    # gives the hostname banner an animated "pulse".  On by default; disable
    # with GIBSON_HOSTNAME_GLOW=off (or steady) for a non-animated bright logo.
    _glow = (os.environ.get("GIBSON_HOSTNAME_GLOW", "banner") or "banner").strip().lower()
    banner_blink = _glow not in ("off", "steady", "banner_steady", "none")
    row = 1
    input_row = 24
    input_col = 13
    for line in visible:
        if row > 24:
            break
        if line.startswith("Logon Type:") or line.strip().startswith("Logon Type:"):
            label = "Logon Type:"
            s.put(row, 1, label, colors.GREEN, protected=True)
            input_row = row
            input_col = len(label) + 2
            s.add_field(row, input_col, max(1, 80 - input_col), "", name="logon_type", colour=colors.GREEN, protected=False)
            row += 1
            continue
        is_banner = is_banner_line(line)
        highlight = "blink" if (banner_blink and is_banner) else "normal"
        if is_banner:
            # The ANSI path makes the hostname banner glow (bold bright colour);
            # 3270 has no SGR pulse, so approximate the glow with an intensified
            # turquoise field, which c3270/x3270 render as a bright hostname.
            s.put(row, 1, _safe_ansi_text(line[:79]), colors.TURQUOISE, protected=True,
                  highlight=highlight, intensified=True)
        else:
            s.put(row, 1, _safe_ansi_text(line[:79]), colour_for_line(line), protected=True, highlight=highlight)
        row += 1
    s.set_cursor(input_row, input_col)
    return s
