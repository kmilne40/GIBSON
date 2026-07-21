from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class Field:
    name: str
    row: int
    col: int
    length: int
    value: str = ""
    protected: bool = False
    hidden: bool = False
    numeric: bool = False
    intensified: bool = False
    mdt: bool = False
    fset: bool = False
    modified: bool = False
    masked: bool = False
    source: str = ""
    def render_value(self, reveal_hidden: bool = False) -> str:
        if self.hidden and not reveal_hidden:
            return " " * self.length
        if self.masked and not reveal_hidden:
            fill = "#" if str(self.value or "").startswith("#") else "*"
            return (fill * self.length)[:self.length]
        return str(self.value or "")[:self.length].ljust(self.length)
    def as_dict(self, reveal_hidden: bool = False) -> dict[str, Any]:
        return {"name": self.name, "row": self.row, "col": self.col, "length": self.length, "value": self.render_value(reveal_hidden), "raw_value": self.value, "protected": self.protected, "hidden": self.hidden, "numeric": self.numeric, "intensified": self.intensified, "mdt": self.mdt, "fset": self.fset, "modified": self.modified, "masked": self.masked, "source": self.source}

@dataclass
class Screen:
    screen_id: str
    title: str
    lines: list[str]
    fields: list[Field] = field(default_factory=list)
    message: str = ""
    def render(self, *, reveal_hidden: bool = False, show_fields: bool = False) -> str:
        buf = [list((line[:80]).ljust(80)) for line in self.lines[:24]]
        while len(buf) < 24:
            buf.append(list(" " * 80))
        for f in self.fields:
            val = f.render_value(reveal_hidden)
            r = max(0, min(23, f.row - 1)); c = max(0, min(79, f.col - 1))
            for i, ch in enumerate(val[:max(0, 80-c)]):
                if c + i < 80:
                    buf[r][c+i] = ch
            if show_fields and c > 0:
                buf[r][c-1] = '['
                if c + f.length < 80:
                    buf[r][c+f.length] = ']'
        if show_fields:
            hack = "HACK ON" if reveal_hidden else "HACK OFF"
            legend = [("UNPROTECTED", "RED/ORANGE"), ("PROTECTED", "BLUE"), ("HIDDEN", "AMBER")]
            start = 2
            for off, (lab, tone) in enumerate(legend):
                row = start + off
                text = (lab + " " + ("RED" if reveal_hidden else tone))[:24]
                if row < 22:
                    for i, ch in enumerate(text):
                        col = 55 + i
                        if col < 80: buf[row][col] = ch
            banner = ("TRAINING LEGEND " + hack)[:24]
            for i, ch in enumerate(banner):
                col = 55 + i
                if col < 80: buf[1][col] = ch
        if self.message:
            buf[22] = list(self.message[:80].ljust(80))
        return "\n".join("".join(row).rstrip() for row in buf).rstrip() + "\n"

    def to_screenbuffer(self, *, reveal_hidden: bool = False):
        """Return a ScreenBuffer with DVCA BMS fields registered by name."""
        from gibson.render.screen3270 import ScreenBuffer
        from gibson.render import colors
        sb = ScreenBuffer()
        # Emit genuine 3270 field attributes (SFE) so a real terminal sees the
        # SELECT field (and the BMS fields) as actual fields. Trailing padding on
        # the protected label lines is trimmed so an 80-wide label attribute does
        # not overrun the row and swallow the input field that follows it.
        sb.extended_attributes = True
        sb.bound_input_fields = True
        for row_no, line in enumerate(self.lines[:24], 1):
            trimmed = line[:80].rstrip()
            if trimmed:
                sb.put(row_no, 1, trimmed, colors.GREEN, protected=True)
        for f in self.fields:
            if f.hidden:
                colour = colors.YELLOW if not reveal_hidden else colors.RED
            elif f.protected:
                colour = colors.LIGHT_BLUE
            else:
                colour = colors.RED
            highlight = "intensified" if (reveal_hidden and (f.hidden or f.modified)) else ("intensified" if f.modified else "normal")
            sb.add_field(
                f.name, f.row, f.col, f.length,
                value=f.render_value(reveal_hidden), protected=f.protected,
                hidden=(f.hidden and not reveal_hidden), numeric=f.numeric,
                color=colour, highlight=highlight,
                mdt=f.mdt, fset=f.fset, role="dvca_field", tab_order=None,
            )
        sb.set_cursor(20, 17 if self.screen_id == "MCMM" else 19)
        return sb
    def field_map(self) -> dict[str, Field]:
        return {f.name.upper(): f for f in self.fields}

@dataclass
class Event:
    event_id: str
    timestamp: str
    channel: str
    session_id: str
    user: str
    transaction: str
    screen: str
    action: str
    field: str = ""
    payload: str = ""
    result: str = ""
    scenario: str = ""
    correlation_id: str = ""
    def row(self) -> dict[str, str]:
        return dict(self.__dict__)

def now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
