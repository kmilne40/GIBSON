from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ANSI/xterm sequences commonly produced by terminals for function/navigation keys.
ANSI_FUNCTION_KEY_MAP: dict[bytes, str] = {
    b"\x1bOP": "F1", b"\x1bOQ": "F2", b"\x1bOR": "F3", b"\x1bOS": "F4",
    b"\x1b[11~": "F1", b"\x1b[12~": "F2", b"\x1b[13~": "F3", b"\x1b[14~": "F4",
    b"\x1b[15~": "F5", b"\x1b[17~": "F6", b"\x1b[18~": "F7", b"\x1b[19~": "F8",
    b"\x1b[20~": "F9", b"\x1b[21~": "F10", b"\x1b[23~": "F11", b"\x1b[24~": "F12",
    # Shifted/extended variants used by VT220/xterm-style terminals.
    b"\x1b[25~": "F13", b"\x1b[26~": "F14", b"\x1b[28~": "F15", b"\x1b[29~": "F16",
    b"\x1b[31~": "F17", b"\x1b[32~": "F18", b"\x1b[33~": "F19", b"\x1b[34~": "F20",
    # Cursor/navigation keys are already used by Gibson panels.
    b"\x1b[A": "UP", b"\x1b[B": "DOWN", b"\x1b[C": "RIGHT", b"\x1b[D": "LEFT",
    b"\x1bOA": "UP", b"\x1bOB": "DOWN", b"\x1bOC": "RIGHT", b"\x1bOD": "LEFT",
    # Common NVT/xterm/c3270 variants seen in training labs.
    b"\x1b[1~": "F3", b"\x1b[4~": "F8", b"\x1b[5~": "F7", b"\x1b[6~": "F8",
}

# Text forms that can leak into NVT/ANSI input fields when clients render ESC
# as caret notation.  Keep this central so panel readers can sanitize them
# before the text is inserted into ISPF/RACF/SDSF option lines.
TEXT_FUNCTION_KEY_MAP: dict[str, str] = {
    "^[OP": "F1", "^[OQ": "F2", "^[OR": "F3", "^[OS": "F4",
    "^[[11~": "F1", "^[[12~": "F2", "^[[13~": "F3", "^[[14~": "F4",
    "^[[15~": "F5", "^[[17~": "F6", "^[[18~": "F7", "^[[19~": "F8",
    "^[[20~": "F9", "^[[21~": "F10", "^[[23~": "F11", "^[[24~": "F12",
    "^[[A": "UP", "^[[B": "DOWN", "^[[C": "RIGHT", "^[[D": "LEFT",
    "^I": "TAB", "\t": "TAB",
}


def extract_text_function_key(text: str) -> Optional[str]:
    """Return a logical key for leaked caret/ANSI text, if exact.

    This is deliberately exact-match based.  It prevents accidental conversion
    of ordinary user commands that merely contain characters resembling escape
    fragments.
    """
    return TEXT_FUNCTION_KEY_MAP.get((text or "").strip())


def strip_known_control_text(text: str) -> str:
    """Remove exact known leaked control tokens from a panel field.

    Used only as a defensive fallback; the input driver should normally consume
    these before they reach the field.
    """
    out = text or ""
    for seq in sorted(TEXT_FUNCTION_KEY_MAP, key=len, reverse=True):
        out = out.replace(seq, "")
    return out

# 3270 AID bytes.  Gibson recognises these without reintroducing live EBCDIC
# field decoding.  Some values overlap printable ASCII, so callers should only
# use them when a frame looks like 3270/TN3270 input.
AID_BYTE_TO_KEY: dict[int, str] = {
    0x7D: "ENTER", 0x6D: "CLEAR", 0x6C: "PA1", 0x6E: "PA2", 0x6B: "PA3",
    0xF1: "PF1", 0xF2: "PF2", 0xF3: "PF3", 0xF4: "PF4", 0xF5: "PF5", 0xF6: "PF6",
    0xF7: "PF7", 0xF8: "PF8", 0xF9: "PF9", 0x7A: "PF10", 0x7B: "PF11", 0x7C: "PF12",
    0xC1: "PF13", 0xC2: "PF14", 0xC3: "PF15", 0xC4: "PF16", 0xC5: "PF17", 0xC6: "PF18",
    0xC7: "PF19", 0xC8: "PF20", 0xC9: "PF21", 0x4A: "PF22", 0x4B: "PF23", 0x4C: "PF24",
}

# 3270 order bytes used only as frame-evidence hints; not as a full parser.
ORDER_BYTES = {0x11, 0x13, 0x3C, 0x1D, 0x29, 0x28, 0x2C, 0x12, 0x08, 0x05}
HIGH_AID_BYTES = {b for b in AID_BYTE_TO_KEY if b >= 0x80}

DEFAULT_AID_MAP: dict[str, str] = {
    "PF1": "HELP", "F1": "HELP",
    "PF2": "SPLIT", "F2": "SPLIT",
    "PF3": "END", "F3": "END",
    "PF4": "RETURN", "F4": "RETURN",
    "PF5": "RFIND", "F5": "RFIND",
    "PF6": "RCHANGE", "F6": "RCHANGE",
    "PF7": "UP", "F7": "UP",
    "PF8": "DOWN", "F8": "DOWN",
    "PF9": "SWAP", "F9": "SWAP",
    "PF10": "LEFT", "F10": "LEFT",
    "PF11": "RIGHT", "F11": "RIGHT",
    "PF12": "CANCEL", "F12": "CANCEL",
    "ENTER": "ENTER", "CLEAR": "CLEAR", "PA1": "PA1", "PA2": "PA2", "PA3": "PA3",
    "ATTN": "ATTN", "SYSREQ": "SYSREQ", "RESET": "RESET", "CANCEL": "CANCEL",
    "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
}
for n in range(13, 25):
    DEFAULT_AID_MAP.setdefault(f"PF{n}", f"AID-UNSUPPORTED PF{n}")
for n in range(13, 25):
    DEFAULT_AID_MAP.setdefault(f"F{n}", f"AID-UNSUPPORTED F{n}")

_CONTEXT_OVERRIDES: dict[str, dict[str, str]] = {
    "TSO": {"PF3": "END", "F3": "END", "PF12": "CANCEL", "F12": "CANCEL"},
    "VTAM": {"PF1": "HELP", "F1": "HELP", "PF3": "END", "F3": "END", "CLEAR": "CLEAR"},
    "ISPF": {"PF3": "END", "F3": "END", "PF12": "CANCEL", "F12": "CANCEL"},
    "ISPF_EDITOR": {"PF3": "END", "F3": "END", "PF5": "RFIND", "F5": "RFIND", "PF6": "RCHANGE", "F6": "RCHANGE"},
    "SDSF": {"PF3": "END", "F3": "END", "PF12": "CANCEL", "F12": "CANCEL"},
    "CICS": {"ENTER": "ENTER", "PF3": "END", "F3": "END", "CLEAR": "CLEAR", "PA1": "PA1", "ATTN": "ATTN"},
    "DB2": {"PF3": "END", "F3": "END", "PF12": "CANCEL", "F12": "CANCEL"},
}

@dataclass(frozen=True)
class AidMapping:
    aid: str
    command: str


def _canonical_aid(token: str) -> Optional[str]:
    t = " ".join((token or "").strip().upper().split())
    if not t:
        return None
    if t.startswith("AID "):
        t = t[4:].strip()
    if t and t[0] in "/:":
        t = t[1:].strip()
    if t in DEFAULT_AID_MAP:
        return t
    if t.startswith("PF") and t[2:].isdigit() and 1 <= int(t[2:]) <= 24:
        return t
    if t.startswith("F") and t[1:].isdigit() and 1 <= int(t[1:]) <= 24:
        return t
    return None


def normalise_aid_alias(text: str, context: str | None = None) -> Optional[AidMapping]:
    aid = _canonical_aid(text)
    if not aid:
        return None
    return AidMapping(aid=aid, command=map_aid_to_command(aid, context))


def map_aid_to_command(aid: str, context: str | None = None) -> str:
    canon = _canonical_aid(aid) or (aid or "").strip().upper()
    ctx = (context or "").strip().upper()
    if ctx in _CONTEXT_OVERRIDES and canon in _CONTEXT_OVERRIDES[ctx]:
        return _CONTEXT_OVERRIDES[ctx][canon]
    return DEFAULT_AID_MAP.get(canon, f"AID-UNSUPPORTED {canon}")


def extract_ansi_function_key(raw: bytes) -> Optional[str]:
    return ANSI_FUNCTION_KEY_MAP.get(raw)


def looks_like_3270_aid_frame(data: bytes, *, saw_eor: bool = False) -> bool:
    if not data or data[0] not in AID_BYTE_TO_KEY:
        return False
    if data[0] in HIGH_AID_BYTES:
        return True
    if saw_eor:
        return True
    # Low-value AID bytes overlap ASCII characters.  Only accept them when the
    # following bytes look frame-like rather than like a normal typed command.
    tail = data[1:10]
    return any(((b < 32 and b not in (9, 10, 13)) or b in ORDER_BYTES) for b in tail)


def extract_3270_aid_key(data: bytes, *, saw_eor: bool = False) -> Optional[str]:
    if looks_like_3270_aid_frame(data, saw_eor=saw_eor):
        return AID_BYTE_TO_KEY.get(data[0])
    return None


def command_from_key(key: str, context: str | None = None) -> str:
    return map_aid_to_command(key, context)
