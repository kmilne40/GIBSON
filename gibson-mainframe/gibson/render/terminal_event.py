
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from gibson.render.aid_keys import normalise_aid_alias, map_aid_to_command


@dataclass
class TerminalEvent:
    """Fielded terminal input event used by Operation 3270 Fidelity.

    The object deliberately supports both true 3270/AID input and Gibson's
    legacy ASCII line-oriented training surface.  Existing applications may use
    to_legacy_command(), while fielded panels can inspect fields_by_name,
    cursor_row/col and aid directly.
    """
    aid: str = ""
    raw_aid: Optional[int] = None
    is_aid: bool = False
    command_text: str = ""
    raw_text: str = ""
    cursor_address: Optional[int] = None
    cursor_row: Optional[int] = None
    cursor_col: Optional[int] = None
    fields_by_address: Dict[int, str] = field(default_factory=dict)
    fields_by_name: Dict[str, str] = field(default_factory=dict)
    line_commands: Dict[str, str] = field(default_factory=dict)
    text_updates: Dict[str, str] = field(default_factory=dict)
    source: str = "unknown"
    raw_frame: bytes = b""
    client_mode: str = "ascii"
    fallback_used: bool = False

    def has_field(self, name: str) -> bool:
        return (name or "").upper() in {k.upper(): v for k, v in self.fields_by_name.items()}

    def field(self, name: str, default: str = "") -> str:
        target = (name or "").upper()
        for k, v in self.fields_by_name.items():
            if k.upper() == target:
                return v
        return default

    def normalized_aid(self) -> str:
        return (self.aid or "").upper()

    def primary_command(self) -> str:
        if self.command_text:
            return self.command_text.strip()
        for key in ("COMMAND", "OPTION", "SELECT", "CMD"):
            value = self.field(key, "")
            if value.strip():
                return value.strip()
        vals = [v.strip() for v in self.fields_by_address.values() if str(v).strip()]
        if len(vals) == 1:
            return vals[0]
        vals = [v.strip() for v in self.fields_by_name.values() if str(v).strip()]
        if len(vals) == 1:
            return vals[0]
        return ""

    def is_pf(self, n: int) -> bool:
        return self.normalized_aid() in {f"PF{n}", f"F{n}"}

    def is_enter(self) -> bool:
        return self.normalized_aid() == "ENTER"

    def is_clear(self) -> bool:
        return self.normalized_aid() == "CLEAR"

    def is_tab(self) -> bool:
        return self.normalized_aid() == "TAB"

    def is_backtab(self) -> bool:
        return self.normalized_aid() == "BACKTAB"

    def is_cursor_move(self) -> bool:
        return self.normalized_aid() in {"CURSOR_UP", "CURSOR_DOWN", "CURSOR_LEFT", "CURSOR_RIGHT", "UP", "DOWN", "LEFT", "RIGHT"}

    def to_legacy_command(self, context: str | None = None) -> str:
        cmd = self.primary_command()
        if cmd:
            return cmd
        if self.aid:
            return map_aid_to_command(self.aid, context)
        return self.raw_text.strip()


AidEvent = TerminalEvent


def event_from_ascii(text: str, *, source: str = "ascii", context: str | None = None, raw_frame: bytes = b"") -> TerminalEvent:
    raw = text or ""
    mapped = normalise_aid_alias(raw, context)
    if mapped:
        return TerminalEvent(
            aid=mapped.aid,
            raw_aid=None,
            is_aid=True,
            command_text=mapped.command,
            raw_text=raw,
            source=source,
            raw_frame=raw_frame,
            client_mode="ascii",
            fallback_used=True,
        )
    return TerminalEvent(command_text=raw.strip(), raw_text=raw, source=source, raw_frame=raw_frame, client_mode="ascii", fallback_used=True)
