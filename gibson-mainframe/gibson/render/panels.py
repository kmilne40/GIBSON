"""Phase 0 - shared 3270 panel/field toolkit (EBCDIC).

A thin, declarative layer over ``ScreenBuffer`` so subsystems (TSO, CICS, DB2I,
SDSF, ISPF) describe panels instead of hand-computing 3270 addresses.  The heavy
lifting -- CP037 encoding, SFE extended attributes, non-display fields, and the
inbound address->field-name mapping -- already lives in ``ScreenBuffer``; this
module packages it into a reusable, tested shape.

Pieces:
  * ``Label`` / ``Field`` / ``Output``  -- declarative panel elements.
  * ``Panel``        -- ``render() -> ScreenBuffer`` + cursor/message/PF legend.
  * ``PanelInput``   -- parsed inbound: AID key + ``{field_name: value}``.
  * ``aid_key`` / ``AID_TO_KEY`` -- full PF1-24 / PA1-3 / CLEAR / ENTER map.
  * ``ScrollList``   -- reusable scrollable list controller (PF7/8/10/11 etc).
  * ``PanelSession`` -- the session contract every subsystem implements.

Named-field parsing is automatic: any ``ScreenBuffer`` built with ``add_field``
already answers ``field_name_for_address``, which ``parse_3270_input_frame``
uses to populate ``event.fields_by_name``.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gibson.render.screen3270 import ScreenBuffer
from gibson.render import colors

import re as _re

_ANSI_RE = _re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI/VT escape sequences so reused text renders cleanly in 3270.

    Several existing engines (CICS, SDSF) colour their text output with ANSI
    escapes intended for the telnet/NVT path.  3270 panels must not carry ANSI,
    so callers strip it before placing the text with ``ScreenBuffer.put``.
    """
    return _ANSI_RE.sub("", text or "")


def text_to_lines(text: str) -> list:
    """ANSI-stripped, CR-normalised lines ready for a ScrollList."""
    return strip_ansi(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

# --------------------------------------------------------------------------- #
# AID map (inbound attention-identifier byte -> logical key name)
# --------------------------------------------------------------------------- #
AID_ENTER = 0x7D
AID_CLEAR = 0x6D
AID_PA1 = 0x6C
AID_PA2 = 0x6E
AID_PA3 = 0x6B

AID_TO_KEY: Dict[int, str] = {
    0x7D: "ENTER",
    0x6D: "CLEAR",
    0x6C: "PA1",
    0x6E: "PA2",
    0x6B: "PA3",
    # PF1-PF12
    0xF1: "PF1", 0xF2: "PF2", 0xF3: "PF3", 0xF4: "PF4", 0xF5: "PF5",
    0xF6: "PF6", 0xF7: "PF7", 0xF8: "PF8", 0xF9: "PF9",
    0x7A: "PF10", 0x7B: "PF11", 0x7C: "PF12",
    # PF13-PF24
    0xC1: "PF13", 0xC2: "PF14", 0xC3: "PF15", 0xC4: "PF16", 0xC5: "PF17",
    0xC6: "PF18", 0xC7: "PF19", 0xC8: "PF20", 0xC9: "PF21",
    0x4A: "PF22", 0x4B: "PF23", 0x4C: "PF24",
}
KEY_TO_AID: Dict[str, int] = {v: k for k, v in AID_TO_KEY.items()}


def aid_key(aid: Optional[int]) -> str:
    """Map a raw AID byte to a logical key name (defaults to ENTER)."""
    if aid is None:
        return "ENTER"
    return AID_TO_KEY.get(int(aid), "ENTER")


# --------------------------------------------------------------------------- #
# Declarative panel elements
# --------------------------------------------------------------------------- #
@dataclass
class Label:
    """Protected static text."""
    row: int
    col: int
    text: str
    colour: str = colors.GREEN
    intense: bool = False


@dataclass
class Output:
    """Protected dynamic text (program output region, one line)."""
    row: int
    col: int
    text: str
    colour: str = colors.GREEN
    intense: bool = False


@dataclass
class Field:
    """An input (unprotected) or output (protected) field with attributes."""
    name: str
    row: int
    col: int
    length: int
    protected: bool = False
    hidden: bool = False
    numeric: bool = False
    colour: str = colors.TURQUOISE if hasattr(colors, "TURQUOISE") else colors.GREEN
    value: str = ""
    intense: bool = False


# --------------------------------------------------------------------------- #
# Parsed inbound
# --------------------------------------------------------------------------- #
@dataclass
class PanelInput:
    aid: int
    key: str
    fields: Dict[str, str]
    cursor: Tuple[Optional[int], Optional[int]] = (None, None)

    def field(self, name: str, default: str = "") -> str:
        return (self.fields.get(name, default) or default)

    def stripped(self, name: str, default: str = "") -> str:
        return self.field(name, default).strip()


def panel_input_from_event(event: Any) -> PanelInput:
    """Build a :class:`PanelInput` from a parsed ``TerminalEvent``."""
    aid = getattr(event, "raw_aid", None)
    if aid is None:
        aid = AID_ENTER
    fields = dict(getattr(event, "fields_by_name", None) or {})
    return PanelInput(
        aid=int(aid),
        key=aid_key(aid),
        fields=fields,
        cursor=(getattr(event, "cursor_row", None), getattr(event, "cursor_col", None)),
    )


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #
@dataclass
class Panel:
    title: str = ""
    elements: List[Any] = _dc_field(default_factory=list)
    message: str = ""
    message_row: int = 23
    message_colour: str = colors.YELLOW if hasattr(colors, "YELLOW") else colors.WHITE
    pfkeys: str = ""
    pfkeys_row: int = 24
    cursor: Any = None  # field-name str, or (row, col) tuple
    extended: bool = True

    def add(self, element: Any) -> "Panel":
        self.elements.append(element)
        return self

    def render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = self.extended
        if self.title:
            s.put(1, 1, self.title[:79], getattr(colors, "WHITE", colors.GREEN))
        cursor_rc: Optional[Tuple[int, int]] = None
        _tab = 1
        for el in self.elements:
            if isinstance(el, Label):
                s.put(el.row, el.col, el.text[:79], el.colour)
            elif isinstance(el, Output):
                s.put(el.row, el.col, el.text[:79], el.colour)
            elif isinstance(el, Field):
                s.add_field(
                    el.name, el.row, el.col, el.length,
                    value=el.value, colour=el.colour,
                    protected=el.protected, hidden=el.hidden, numeric=el.numeric,
                    role=("output" if el.protected else "input"),
                    tab_order=(None if el.protected else _tab),
                )
                if not el.protected:
                    _tab += 1
        if self.message:
            s.put(self.message_row, 2, self.message[:78], self.message_colour)
        if self.pfkeys:
            _pf = str(self.pfkeys).split("\n")
            if len(_pf) == 1:
                s.put(self.pfkeys_row, 1, _pf[0][:79], getattr(colors, "BLUE", colors.GREEN))
            else:
                s.put(self.pfkeys_row - 1, 1, _pf[0][:79], getattr(colors, "BLUE", colors.GREEN))
                s.put(self.pfkeys_row, 1, _pf[1][:79], getattr(colors, "BLUE", colors.GREEN))
        # cursor placement
        if isinstance(self.cursor, str):
            for el in self.elements:
                if isinstance(el, Field) and el.name == self.cursor:
                    cursor_rc = (el.row, el.col)
                    break
        elif isinstance(self.cursor, tuple) and len(self.cursor) == 2:
            cursor_rc = (int(self.cursor[0]), int(self.cursor[1]))
        if cursor_rc:
            s.set_cursor(*cursor_rc)
        return s


# --------------------------------------------------------------------------- #
# Scrollable list controller
# --------------------------------------------------------------------------- #
class ScrollList:
    """Reusable scrollable-list controller for ISPF 3.4, member lists, SDSF.

    ``items`` is any sequence of pre-formatted row strings.  The controller
    tracks the top index and horizontal offset and renders a window into a
    region of a :class:`ScreenBuffer`.
    """

    def __init__(self, items: Sequence[str], *, height: int = 18, top: int = 0, hoff: int = 0):
        self.items: List[str] = list(items)
        self.height = max(1, int(height))
        self.top = max(0, int(top))
        self.hoff = max(0, int(hoff))

    def set_items(self, items: Sequence[str]) -> None:
        self.items = list(items)
        self.top = min(self.top, max(0, len(self.items) - 1))

    def page_down(self) -> None:
        if self.top + self.height < len(self.items):
            self.top = min(self.top + self.height, max(0, len(self.items) - 1))

    def page_up(self) -> None:
        self.top = max(0, self.top - self.height)

    def page_right(self, cols: int = 20) -> None:
        self.hoff += cols

    def page_left(self, cols: int = 20) -> None:
        self.hoff = max(0, self.hoff - cols)

    def to_top(self) -> None:
        self.top = 0

    def to_bottom(self) -> None:
        self.top = max(0, len(self.items) - self.height)

    def locate(self, key: str) -> bool:
        key = (key or "").strip().lower()
        if not key:
            return False
        for idx, row in enumerate(self.items):
            if row.lower().lstrip().startswith(key):
                self.top = idx
                return True
        return False

    def scroll(self, panel_key: str) -> None:
        """Apply a PF-key scroll action (PF7/8/10/11, MAX top/bottom)."""
        if panel_key == "PF8":
            self.page_down()
        elif panel_key == "PF7":
            self.page_up()
        elif panel_key == "PF11":
            self.page_right()
        elif panel_key == "PF10":
            self.page_left()

    def visible(self) -> List[str]:
        window = self.items[self.top:self.top + self.height]
        if self.hoff:
            window = [row[self.hoff:] for row in window]
        return window

    def render_into(self, screen: ScreenBuffer, top_row: int, *, left: int = 1, width: int = 79,
                    colour: str = colors.GREEN) -> None:
        for i, row in enumerate(self.visible()):
            screen.put(top_row + i, left, row[:width], colour)

    @property
    def position_label(self) -> str:
        if not self.items:
            return "Row 0 of 0"
        first = self.top + 1
        return f"Row {first} of {len(self.items)}"


# --------------------------------------------------------------------------- #
# Session contract
# --------------------------------------------------------------------------- #
class PanelSession:
    """Contract every subsystem implements (mirrors ZvmSession).

    ``initial_screen()`` returns the first ``ScreenBuffer``; ``handle()`` takes a
    :class:`PanelInput` and returns the next screen, or ``None`` to end/leave the
    session (return to the caller, e.g. VTAM).
    """

    def initial_screen(self) -> ScreenBuffer:  # pragma: no cover - interface
        raise NotImplementedError

    def handle(self, panel_input: PanelInput) -> Optional[ScreenBuffer]:  # pragma: no cover
        raise NotImplementedError
