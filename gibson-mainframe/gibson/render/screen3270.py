from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from . import colors
from gibson.net.datastream3270 import build_wcc, encode_3270_address, row_col_to_address, address_to_row_col


def _enc_3270_text(text: str) -> bytes:
    """Encode display text for a 3270 data stream.

    3270 terminals do not expect ASCII payload text in formatted screens;
    display text must be encoded in an EBCDIC code page.  Gibson uses CP037
    for the classic US/UK-style 3270 training environment.
    """
    return (text or "").encode("cp037", errors="replace")


# Backwards-compatible private alias for older imports/tests.
def _enc_ansi(text: str) -> bytes:
    return _enc_3270_text(text)


@dataclass
class Field:
    row: int
    col: int
    text: str = ""
    colour: str = colors.GREEN
    protected: bool = True
    high_intensity: bool = False
    name: str = ""
    hidden: bool = False
    width: int = 0
    numeric: bool = False
    intensified: bool = False
    color: str | None = None
    highlight: str = "normal"
    mdt: bool = False
    fset: bool = False
    label: str = ""
    app: str = ""
    panel: str = ""
    role: str = ""
    tab_order: int | None = None

    @property
    def length(self) -> int:
        return self.width or len(self.text) or 1

    @property
    def address(self) -> int:
        return row_col_to_address(self.row, self.col)

    @property
    def display_text(self) -> str:
        width = self.width or len(self.text) or 1
        value = (self.text or "")[:width]
        if self.hidden:
            value = "*" * min(width, max(len(value), 1))
        return value.ljust(width)


# Prompt-compatible public name.
ScreenField = Field


class ScreenBuffer:
    """Small 24x80 3270-style buffer shared by ANSI and TN3270 frontends.

    Operation 3270 Fidelity extends this object with a field registry.  Existing
    callers can still use put()/add_field(row, col, width, value=...) exactly as
    before, while fielded panels can register named protected/unprotected fields,
    resolve modified-field addresses, tab through input fields, and emit WCC/IC
    orders for TN3270 clients.
    """

    SF = 0x1D
    SFE = 0x29
    SBA = 0x11
    IC = 0x13
    EW = 0xF5
    EWA = 0x7E   # Erase/Write Alternate - selects the model's alternate (larger) buffer
    EOR = b"\xff\xef"
    IAC = 0xFF
    COLS = 80
    ROWS = 24
    CODE_TABLE = [
        0x40, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
        0xC8, 0xC9, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
        0x50, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7,
        0xD8, 0xD9, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
        0x60, 0x61, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7,
        0xE8, 0xE9, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
        0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7,
        0xF8, 0xF9, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
    ]

    def __init__(self, rows: int = 24, cols: int = 80):
        self.rows = rows
        self.cols = cols
        self.lines: List[List[str]] = [[" " for _ in range(cols)] for _ in range(rows)]
        self.fields: List[Field] = []
        self.cursor_row = 1
        self.cursor_col = 1
        self.extended_attributes = False
        # When True, to_3270() bounds each unprotected field with a trailing
        # protected stop-attribute (used by DVCA/CICS fielded panels whose
        # input fields would otherwise balloon to the next attribute). Default
        # False keeps every existing/golden panel byte-identical.
        self.bound_input_fields = False

    def clear(self) -> None:
        self.lines = [[" " for _ in range(self.cols)] for _ in range(self.rows)]
        self.fields.clear()
        self.cursor_row, self.cursor_col = 1, 1

    def put(self, row: int, col: int, text: str, colour: str = colors.GREEN, protected: bool = True, highlight: str = "normal", intensified: bool = False) -> None:
        clipped = (text or "")[: max(0, self.cols - col + 1)]
        self._overlay(row, col, clipped)
        self.fields.append(Field(row=row, col=col, text=clipped, colour=colour, color=colour, protected=protected, role="label" if protected else "field", width=len(clipped) or 1, highlight=str(highlight or "normal"), high_intensity=bool(intensified), intensified=bool(intensified)))

    def add_field(self, *args, **kwargs) -> Field:
        """Register a field while preserving both historical and new signatures.

        Historical Gibson:
            add_field(row, col, width, value="", name="FIELD", protected=False)
        Operation 3270 Fidelity:
            add_field("FIELD", row, col, length, protected=False, role="command")
        """
        if args and isinstance(args[0], str):
            name = args[0]
            row = int(args[1]) if len(args) > 1 else int(kwargs.pop("row"))
            col = int(args[2]) if len(args) > 2 else int(kwargs.pop("col"))
            width = int(args[3]) if len(args) > 3 else int(kwargs.pop("length", kwargs.pop("width", 1)))
            value = kwargs.pop("value", kwargs.pop("text", ""))
        else:
            row = int(args[0]) if len(args) > 0 else int(kwargs.pop("row"))
            col = int(args[1]) if len(args) > 1 else int(kwargs.pop("col"))
            width = int(args[2]) if len(args) > 2 else int(kwargs.pop("width", kwargs.pop("length", 1)))
            value = args[3] if len(args) > 3 else kwargs.pop("value", kwargs.pop("text", ""))
            name = kwargs.pop("name", "")
        colour = kwargs.pop("colour", kwargs.pop("color", colors.GREEN))
        field = Field(
            row=row,
            col=col,
            width=max(1, width),
            text=str(value or "")[: max(1, width)],
            name=str(name or ""),
            colour=colour,
            color=colour,
            protected=bool(kwargs.pop("protected", False)),
            hidden=bool(kwargs.pop("hidden", False)),
            high_intensity=bool(kwargs.pop("high_intensity", kwargs.pop("intensified", False))),
            intensified=bool(kwargs.pop("intensified", False)),
            numeric=bool(kwargs.pop("numeric", False)),
            highlight=str(kwargs.pop("highlight", "normal")),
            mdt=bool(kwargs.pop("mdt", False)),
            fset=bool(kwargs.pop("fset", False)),
            label=str(kwargs.pop("label", "")),
            app=str(kwargs.pop("app", "")),
            panel=str(kwargs.pop("panel", "")),
            role=str(kwargs.pop("role", "field")),
            tab_order=kwargs.pop("tab_order", None),
        )
        self.fields.append(field)
        self._overlay(row, col, field.display_text)
        return field

    def update_field(self, name: str, value: str) -> None:
        for field in self.fields:
            if field.name.upper() == (name or "").upper():
                width = field.width or len(field.text) or 1
                field.text = (value or "")[:width]
                field.mdt = True
                self._overlay(field.row, field.col, field.display_text)
                return

    def get_field(self, name: str) -> Optional[Field]:
        target = (name or "").upper()
        for field in self.fields:
            if field.name.upper() == target:
                return field
        return None

    def field_at_address(self, address: int) -> Optional[Field]:
        a = int(address)
        candidates = []
        for field in self.fields:
            start = field.address
            length = max(1, field.length)
            # The field attribute byte sits at ``start``; the modifiable data
            # occupies [start+1, start+1+length).  Accept the attribute position
            # itself too, so callers that pass either form resolve correctly.
            if start == a or (start + 1) <= a < (start + 1 + length):
                candidates.append(field)
        if not candidates:
            return None
        # Prefer an unprotected input field, then a named field over an unnamed
        # label (put() lays full-width protected labels that overlap the BMS
        # fields), then the narrowest span (most specific).
        candidates.sort(key=lambda f: (bool(f.protected), not bool(f.name), max(1, f.length)))
        return candidates[0]

    def field_by_row_col(self, row: int, col: int) -> Optional[Field]:
        return self.field_at_address(row_col_to_address(row, col, self.cols))

    def field_address_map(self) -> dict[int, str]:
        return {f.address: f.name for f in self.fields if f.name}

    def field_name_for_address(self, address: int) -> Optional[str]:
        f = self.field_at_address(address)
        return f.name if f and f.name else None

    def export_registry(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "cursor": {"row": self.cursor_row, "col": self.cursor_col},
            "fields": [
                {
                    "name": f.name, "row": f.row, "col": f.col, "length": f.length,
                    "address": f.address, "protected": f.protected, "numeric": f.numeric,
                    "hidden": f.hidden, "color": f.color or f.colour, "highlight": f.highlight,
                    "mdt": f.mdt, "fset": f.fset, "role": f.role, "tab_order": f.tab_order,
                } for f in self.fields
            ],
        }

    def tab_next(self, current_field: str | Field | None = None) -> Optional[Field]:
        candidates = [f for f in self.fields if not f.protected and not f.hidden and f.length > 0]
        candidates.sort(key=lambda f: (999999 if f.tab_order is None else f.tab_order, f.row, f.col))
        if not candidates:
            return None
        cur_name = current_field.name if isinstance(current_field, Field) else (current_field or "")
        if not cur_name:
            f = candidates[0]
        else:
            idx = next((i for i, f in enumerate(candidates) if f.name.upper() == cur_name.upper()), -1)
            f = candidates[(idx + 1) % len(candidates)] if idx >= 0 else candidates[0]
        self.set_cursor_field(f.name)
        return f

    def tab_previous(self, current_field: str | Field | None = None) -> Optional[Field]:
        candidates = [f for f in self.fields if not f.protected and not f.hidden and f.length > 0]
        candidates.sort(key=lambda f: (999999 if f.tab_order is None else f.tab_order, f.row, f.col))
        if not candidates:
            return None
        cur_name = current_field.name if isinstance(current_field, Field) else (current_field or "")
        idx = next((i for i, f in enumerate(candidates) if f.name.upper() == cur_name.upper()), 0)
        f = candidates[(idx - 1) % len(candidates)]
        self.set_cursor_field(f.name)
        return f

    def set_cursor_field(self, name: str) -> None:
        f = self.get_field(name)
        if f:
            self.set_cursor(f.row, f.col)

    def apply_modified_fields(self, fields_by_address: dict[int, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for address, value in fields_by_address.items():
            f = self.field_at_address(address)
            if not f or not f.name:
                continue
            out[f.name] = value[:f.length]
            f.text = out[f.name]
            f.mdt = True
            self._overlay(f.row, f.col, f.display_text)
        return out

    def set_cursor(self, row: int, col: int) -> None:
        self.cursor_row = max(1, min(self.rows, int(row)))
        self.cursor_col = max(1, min(self.cols, int(col)))

    def _effective_cursor(self) -> tuple[int, int]:
        """Cursor position adjusted off any field attribute byte.

        A field's attribute byte occupies its (row, col); the first writable
        character is at col+1.  Callers commonly ``set_cursor`` to a field's
        own (row, col), which would leave the cursor on the protected attribute
        (the 3270 "X Protected" / input-inhibited state).  Move it onto the
        first writable position in that case.
        """
        r, c = self.cursor_row, self.cursor_col
        for f in self.fields:
            if f.row == r and f.col == c:
                return r, min(self.cols, c + 1)
        return r, c

    def _overlay(self, row: int, col: int, text: str) -> None:
        if row < 1 or row > self.rows:
            return
        idx = max(0, col - 1)
        for ch in (text or "")[: max(0, self.cols - idx)]:
            if idx >= self.cols:
                break
            self.lines[row - 1][idx] = ch
            idx += 1

    def render_plain(self) -> str:
        return "\n".join("".join(line).rstrip() for line in self.lines)

    def render_ansi(self) -> str:
        return self.render()

    def render(self) -> str:
        row_fields = {r: [] for r in range(1, self.rows + 1)}
        for f in self.fields:
            row_fields.setdefault(f.row, []).append(f)
        out: List[str] = [colors.CLEAR]
        for row in range(1, self.rows + 1):
            base = "".join(self.lines[row - 1])
            fields = sorted(row_fields.get(row, []), key=lambda f: f.col)
            if not fields:
                out.append(base.rstrip())
                continue
            pos = 1
            line: List[str] = []
            for f in fields:
                if f.col > pos:
                    line.append(base[pos - 1 : f.col - 1])
                segment = base[f.col - 1 : f.col - 1 + f.length]
                colour = f.color or f.colour
                if f.highlight == "reverse":
                    segment = "\x1b[7m" + segment + "\x1b[27m"
                line.append(colour + segment + colors.RESET)
                pos = f.col + f.length
            if pos <= len(base):
                line.append(base[pos - 1 :])
            out.append("".join(line).rstrip())
        out.append(f"\x1b[{self._effective_cursor()[0]};{self._effective_cursor()[1]}H")
        return "\n".join(out)

    @classmethod
    def encode_baddr(cls, address: int) -> bytes:
        return encode_3270_address(address)

    def address(self, row: int, col: int) -> int:
        return row_col_to_address(row, col, self.cols)

    @staticmethod
    def _colour_code(colour: str) -> int:
        if colour == colors.BLUE or colour == colors.LIGHT_BLUE:
            return 0xF1
        if colour == colors.RED:
            return 0xF2
        if colour == colors.GREEN:
            return 0xF4
        if colour == colors.TURQUOISE:
            return 0xF5
        if colour == colors.YELLOW:
            return 0xF6
        if colour == colors.WHITE:
            return 0xF7
        return 0xF4

    @staticmethod
    def _field_attribute(*, protected: bool = True, high_intensity: bool = False, hidden: bool = False, numeric: bool = False, mdt: bool = False) -> int:
        attr = 0x20 if protected else 0x00
        if high_intensity:
            attr |= 0x08
        if hidden:
            attr |= 0x0C
        if numeric:
            attr |= 0x10
        if mdt or not protected:
            attr |= 0x01
        return attr

    @staticmethod
    def _highlight_code(highlight: str) -> int | None:
        """Map a highlight name to its 3270 extended-highlighting value.

        0xF1 blink, 0xF2 reverse video, 0xF4 underscore.  Returns None for
        normal/default so no highlight attribute pair is emitted.
        """
        return {
            "blink": 0xF1,
            "reverse": 0xF2,
            "reverse_video": 0xF2,
            "underscore": 0xF4,
            "underline": 0xF4,
        }.get((highlight or "normal").lower())

    def _field_to_3270(self, field: Field) -> bytes:
        payload = bytearray()
        payload.append(self.SBA)
        payload.extend(self.encode_baddr(self.address(field.row, field.col)))
        attr = self._field_attribute(protected=field.protected, high_intensity=field.high_intensity or field.intensified, hidden=field.hidden, numeric=field.numeric, mdt=field.mdt)
        if self.extended_attributes:
            hl = self._highlight_code(field.highlight)
            colour = self._colour_code(field.color or field.colour)
            if hl is not None:
                # 3 attribute pairs: field attr, extended highlighting, colour.
                payload.extend([self.SFE, 0x03, 0xC0, attr, 0x41, hl, 0x42, colour])
            else:
                payload.extend([self.SFE, 0x02, 0xC0, attr, 0x42, colour])
        else:
            payload.extend([self.SF, attr])
        payload.extend(_enc_3270_text(field.display_text))
        return bytes(payload)

    def to_3270(self) -> bytes:
        # A larger-than-default screen (Model 3/4/5 alternate size) must be sent
        # with Erase/Write Alternate so the terminal switches to its alternate
        # buffer; plain Erase/Write keeps it in the 24x80 default and any field
        # addressed beyond row 24 becomes unreachable.
        cmd = self.EWA if (self.rows > 24 or self.cols > 80) else self.EW
        payload = bytearray([cmd, build_wcc(reset_mdt=True, keyboard_restore=True)])
        if self.extended_attributes and self.fields:
            flds = [f for f in sorted(self.fields, key=lambda f: (f.row, f.col))
                    if 1 <= f.row <= self.rows and 1 <= f.col <= self.cols]
            attr_addrs = sorted(self.address(f.row, f.col) for f in flds)
            cap = self.rows * self.cols
            for field in flds:
                payload.extend(self._field_to_3270(field))
                # Bound an unprotected input field with a trailing protected
                # stop-attribute so it does not run on to the next field's
                # attribute, which otherwise leaves a large modifiable region
                # (the DVCA hack3270 "lots of yellow"). Skip when another field
                # already begins at/before the stop position, which keeps the
                # densely-packed TSO/ISPF golden panels byte-identical.
                if not field.protected and self.bound_input_fields:
                    start = self.address(field.row, field.col)
                    flen = field.width if field.width > 0 else max(1, len(field.display_text))
                    stop = start + 1 + flen
                    nxt = next((a for a in attr_addrs if a > start), None)
                    if stop < cap and (nxt is None or nxt > stop):
                        payload.append(self.SBA)
                        payload.extend(self.encode_baddr(stop))
                        stop_attr = self._field_attribute(protected=True)
                        payload.extend([self.SFE, 0x02, 0xC0, stop_attr,
                                        0x42, self._colour_code(colors.GREEN)])
        else:
            for row in range(1, self.rows + 1):
                text = "".join(self.lines[row - 1]).rstrip()
                if not text:
                    continue
                payload.append(self.SBA)
                payload.extend(self.encode_baddr(self.address(row, 1)))
                payload.extend(_enc_3270_text(text))
        payload.append(self.SBA)
        cr, cc = self._effective_cursor()
        payload.extend(self.encode_baddr(self.address(cr, cc)))
        payload.append(self.IC)
        data = bytes(payload).replace(bytes([self.IAC]), bytes([self.IAC, self.IAC]))
        return data + self.EOR


class PanelRenderer:
    def primary_frame(self, title: str) -> ScreenBuffer:
        s = ScreenBuffer()
        s.put(1, 1, "Menu  Utilities  Compilers  Options  Status  Help", colors.BLUE)
        s.put(2, 1, "─" * 79, colors.BLUE)
        s.put(3, 1, title.center(79), colors.WHITE)
        return s
