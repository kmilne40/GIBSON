
from __future__ import annotations

from typing import Dict, Any

from gibson.render.aid_keys import AID_BYTE_TO_KEY, command_from_key, extract_ansi_function_key, normalise_aid_alias
from gibson.render.terminal_event import TerminalEvent, event_from_ascii

IAC = 0xFF
EOR = 0xEF
SBA = 0x11
SF = 0x1D
SFE = 0x29
IC = 0x13
SA = 0x28
MF = 0x2C
RA = 0x3C
EUA = 0x12
GE = 0x08
PT = 0x05
ORDER_BYTES = {SBA, SF, SFE, IC, SA, MF, RA, EUA, GE, PT}
# 12-bit 3270 address translation table used by 3278 model-2 terminals.
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
REV_CODE_TABLE = {b: i for i, b in enumerate(CODE_TABLE)}
LOW_AID_BYTES = {b for b in AID_BYTE_TO_KEY if b < 0x80}


def aid_byte_to_name(byte: int) -> str:
    return AID_BYTE_TO_KEY.get(byte, "UNKNOWN")


def aid_name_to_byte(name: str) -> int | None:
    target = (name or "").upper()
    for b, n in AID_BYTE_TO_KEY.items():
        if n == target or (target.startswith('F') and n == 'P' + target):
            return b
    return None


def decode_3270_address(byte1: int, byte2: int) -> int:
    if byte1 in REV_CODE_TABLE and byte2 in REV_CODE_TABLE:
        return (REV_CODE_TABLE[byte1] << 6) | REV_CODE_TABLE[byte2]
    if (byte1 & 0xC0) == 0:
        return ((byte1 & 0x3F) << 8) | byte2
    return ((byte1 & 0x3F) << 6) | (byte2 & 0x3F)


def encode_3270_address(address: int) -> bytes:
    # 12-bit buffer addressing covers 0-4095, which spans every standard model
    # (Model 2 24x80=1920 ... Model 4 43x80=3440 ... Model 5 27x132=3564).
    a = max(0, min(int(address), 4095))
    return bytes((CODE_TABLE[(a >> 6) & 0x3F], CODE_TABLE[a & 0x3F]))


def address_to_row_col(address: int, cols: int = 80) -> tuple[int, int]:
    a = max(0, int(address))
    return (a // cols) + 1, (a % cols) + 1


def row_col_to_address(row: int, col: int, cols: int = 80) -> int:
    return (max(1, int(row)) - 1) * cols + (max(1, int(col)) - 1)


def _printable_score(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum() or ch in " ._-$()/@#=:'\"+-")

def decode_ebcdic_field(data: bytes, force_ebcdic: bool = False) -> str:
    raw = data or b""
    ebcdic_text = raw.decode("cp037", errors="ignore").replace("\x00", " ").rstrip()
    if force_ebcdic:
        return ebcdic_text
    ascii_text = raw.decode("ascii", errors="ignore").replace("\x00", " ").rstrip()
    # Gibson compatibility: tests and nmap-style training tools use ASCII field
    # payloads, while real TN3270 frames use CP037. Prefer the more command-like string.
    # Use EBCDIC when tied — ASCII scoring is inflated by 0x40 EBCDIC-space bytes
    # that happen to equal ASCII '@', which outscores short EBCDIC commands otherwise.
    return ebcdic_text if _printable_score(ebcdic_text) >= _printable_score(ascii_text) else ascii_text


def encode_ebcdic_field(text: str) -> bytes:
    return (text or "").encode("cp037", errors="replace")


def _strip_telnet_iac(data: bytes) -> tuple[bytes, bool]:
    out = bytearray(); saw_eor = False; i = 0
    while i < len(data):
        b = data[i]
        if b != IAC:
            out.append(b); i += 1; continue
        if i + 1 >= len(data):
            break
        cmd = data[i+1]
        if cmd == IAC:
            out.append(IAC); i += 2; continue
        if cmd == EOR:
            saw_eor = True; i += 2; continue
        # Skip IAC command triplets and subnegotiation roughly; strict telnet parsing lives elsewhere.
        if cmd in (0xFB,0xFC,0xFD,0xFE):
            i += 3; continue
        if cmd == 0xFA:
            end = data.find(bytes([IAC, 0xF0]), i+2)
            if end == -1: break
            i = end + 2; continue
        i += 2
    return bytes(out), saw_eor


def looks_like_3270_frame(data: bytes) -> bool:
    clean, saw_eor = _strip_telnet_iac(data or b"")
    if not clean or clean[0] not in AID_BYTE_TO_KEY:
        return False
    if clean[0] not in LOW_AID_BYTES:
        return True
    # Avoid treating ASCII 'L', 'M', 'N', 'z', '{', '|', '}' as PF/PA keys.
    # Low AID bytes must include real 3270 orders such as SBA/SF/SFE; CR/NUL/EOR is not enough.
    if len(clean) == 3 and clean[1] in REV_CODE_TABLE and clean[2] in REV_CODE_TABLE:
        return True
    tail = clean[1:12]
    return any((b in ORDER_BYTES) for b in tail)


def parse_modified_fields(data: bytes, force_ebcdic: bool = False) -> Dict[int, str]:
    fields: Dict[int, str] = {}
    i = 0
    current_addr: int | None = None
    buf = bytearray()

    def flush() -> None:
        nonlocal buf, current_addr
        if current_addr is not None:
            fields[current_addr] = decode_ebcdic_field(bytes(buf), force_ebcdic=force_ebcdic)
        buf = bytearray()

    while i < len(data):
        b = data[i]
        if b == SBA and i + 2 < len(data):
            flush()
            current_addr = decode_3270_address(data[i+1], data[i+2])
            i += 3
            continue
        if b == SF and i + 1 < len(data):
            i += 2; continue
        if b == SFE and i + 1 < len(data):
            pairs = data[i+1]
            i += 2 + (pairs * 2)
            continue
        if b in (SA, MF) and i + 2 < len(data):
            i += 3; continue
        if b in ORDER_BYTES:
            i += 1; continue
        if current_addr is not None:
            buf.append(b)
        i += 1
    flush()
    return fields


def _registry_field_name(screen_registry: Any, address: int) -> str | None:
    if screen_registry is None:
        return None
    if hasattr(screen_registry, 'field_name_for_address'):
        try: return screen_registry.field_name_for_address(address)
        except Exception: return None
    if isinstance(screen_registry, dict):
        return screen_registry.get(address) or screen_registry.get(str(address))
    return None


def parse_3270_input_frame(data: bytes, screen_registry=None) -> TerminalEvent:
    raw = data or b""
    clean, _saw_eor = _strip_telnet_iac(raw)
    if not looks_like_3270_frame(raw):
        return normalise_terminal_input(raw, screen_registry=screen_registry)
    raw_aid = clean[0]
    aid = aid_byte_to_name(raw_aid)
    pos = 1
    cursor_address = None
    cursor_row = cursor_col = None
    if len(clean) >= 3:
        cursor_address = decode_3270_address(clean[1], clean[2])
        cursor_row, cursor_col = address_to_row_col(cursor_address)
        pos = 3
    fields_by_address = parse_modified_fields(clean[pos:], force_ebcdic=True)
    fields_by_name: Dict[str, str] = {}
    for address, value in fields_by_address.items():
        name = _registry_field_name(screen_registry, address)
        if name:
            fields_by_name[name] = value
    cmd = ""
    for k in ("COMMAND", "OPTION", "SELECT", "CMD"):
        for actual, val in fields_by_name.items():
            if actual.upper() == k and val.strip():
                cmd = val.strip(); break
        if cmd: break
    return TerminalEvent(aid=aid, raw_aid=raw_aid, is_aid=True, command_text=cmd, raw_text="", cursor_address=cursor_address, cursor_row=cursor_row, cursor_col=cursor_col, fields_by_address=fields_by_address, fields_by_name=fields_by_name, source="tn3270", raw_frame=raw[:4096], client_mode="tn3270", fallback_used=False)


def _best_decode_ascii(data: bytes) -> str:
    # Keep line-oriented tools compatible: prefer ASCII, fall back to CP037 only for 3270 frames.
    return data.decode("ascii", errors="ignore").replace("\x00", " ").strip()


def normalise_terminal_input(data_or_text, screen_registry=None) -> TerminalEvent:
    if isinstance(data_or_text, str):
        return event_from_ascii(data_or_text, source="ascii")
    raw = bytes(data_or_text or b"")
    if looks_like_3270_frame(raw):
        return parse_3270_input_frame(raw, screen_registry=screen_registry)
    clean, _ = _strip_telnet_iac(raw)
    ansi_key = extract_ansi_function_key(clean)
    if ansi_key:
        return TerminalEvent(aid=ansi_key if ansi_key.startswith('PF') else ansi_key, is_aid=True, command_text=command_from_key(ansi_key), raw_frame=raw[:4096], client_mode="ansi", source="ansi", fallback_used=True)
    text = " ".join(_best_decode_ascii(clean).replace("\r", " ").replace("\n", " ").split())
    mapped = normalise_aid_alias(text)
    if mapped:
        return TerminalEvent(aid=mapped.aid, is_aid=True, command_text=mapped.command, raw_text=text, raw_frame=raw[:4096], client_mode="ascii", source="ascii", fallback_used=True)
    return event_from_ascii(text, source="ascii", raw_frame=raw[:4096])


def build_wcc(reset_mdt: bool = True, keyboard_restore: bool = True, sound_alarm: bool = False, reset_device: bool = False) -> int:
    # 0x40 is the common base for reset-MDT/keyboard-restore style writes in Gibson;
    # keep compatibility with legacy 0x42 while making intent explicit.
    wcc = 0x00
    if reset_mdt:
        wcc |= 0x40
    if keyboard_restore:
        wcc |= 0x02
    if sound_alarm:
        wcc |= 0x04
    if reset_device:
        wcc |= 0x80
    return wcc or 0x00
