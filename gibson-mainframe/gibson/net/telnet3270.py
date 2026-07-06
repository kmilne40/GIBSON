from __future__ import annotations

from gibson.render.aid_keys import command_from_key, extract_3270_aid_key, normalise_aid_alias
from gibson.net.datastream3270 import normalise_terminal_input, looks_like_3270_frame

# Telnet commands
IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0
EOR = 0xEF

# Telnet option numbers used by TN3270/TN3270E detection.
BINARY = 0x00
TERMINAL_TYPE = 0x18        # IANA: 24
END_OF_RECORD = 0x19        # IANA: 25
TN3270_REGIME = 0x1D        # IANA: 29
TN3270E = 0x28              # IANA: 40

SEND = 0x01
IS = 0x00

# TN3270E subnegotiation codes used by Gibson's minimal implementation.
TN3270E_ASSOCIATE = 0x00
TN3270E_CONNECT = 0x01
TN3270E_DEVICE_TYPE = 0x02
TN3270E_FUNCTIONS = 0x03
TN3270E_IS = 0x04
TN3270E_REASON = 0x05
TN3270E_REJECT = 0x06
TN3270E_REQUEST = 0x07
TN3270E_SEND = 0x08
TN3270E_DATA = 0x00
TN3270E_HEADER_LEN = 5


def initial_tn3270_negotiation(*, include_regime: bool = False) -> bytes:
    """Return a conservative TN3270 negotiation prologue.

    Port 2023 now runs a dual-mode frontend.  This prologue is only sent after
    the frontend has decided to probe for 3270 capability; plain ASCII clients
    that send text promptly remain on the ASCII path and do not require AID
    frames.
    """
    parts = [
        IAC, WILL, BINARY,
        IAC, DO, BINARY,
        IAC, WILL, END_OF_RECORD,
        IAC, DO, END_OF_RECORD,
        IAC, DO, TERMINAL_TYPE,
    ]
    # TN3270E is intentionally not advertised by default. Gibson currently
    # implements reliable classic TN3270 (BINARY + EOR + TERMINAL-TYPE).
    # Half-negotiating TN3270E can leave real x3270/c3270 sessions in NVT mode.
    if include_regime:
        parts.extend([IAC, DO, TN3270E])
    return bytes(parts)

def terminal_type_is(device_type: str = "IBM-3278-2-E") -> bytes:
    return bytes([IAC, SB, TERMINAL_TYPE, IS]) + device_type.encode("ascii", "ignore") + bytes([IAC, SE])

# 3270 AID/order constants used by the defensive input normaliser.
AID_ENTER = 0x7D
AID_CLEAR = 0x6D
AID_PF3 = 0xF3
SBA = 0x11
IC = 0x13
RA = 0x3C
SF = 0x1D
SFE = 0x29
SA = 0x28
MF = 0x2C
EUA = 0x12
GE = 0x08
PT = 0x05
ORDER_BYTES = {SBA, IC, RA, SF, SFE, SA, MF, EUA, GE, PT}


def strip_telnet_iac(data: bytes) -> bytes:
    """Remove TELNET command sequences while preserving application bytes.

    The function is deliberately tolerant of truncated/malformed IAC sequences:
    incomplete commands are discarded rather than causing a caller to wait for
    more bytes forever.  IAC IAC is unescaped to a single data 0xff byte.
    """
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= len(data):
            break
        cmd = data[i + 1]
        if cmd == IAC:
            out.append(IAC)
            i += 2
            continue
        if cmd == EOR:
            i += 2
            continue
        if cmd in (DO, DONT, WILL, WONT):
            i += 3 if i + 2 < len(data) else len(data) - i
            continue
        if cmd == SB:
            end = data.find(bytes([IAC, SE]), i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        i += 2
    return bytes(out)


def _decode_baddr(byte1: int, byte2: int) -> int:
    if (byte1 & 0xC0) == 0:
        return ((byte1 & 0x3F) << 8) | byte2
    return ((byte1 & 0x3F) << 6) | (byte2 & 0x3F)


def _printable_score(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum() or ch in " ._-$()/@#=:'\"+-")


def _best_decode(data: bytes) -> str:
    """Decode live terminal command bytes as ANSI/ASCII only.

    EBCDIC/CP037 is intentionally not used in live interactive command paths.
    Gibson is a classroom simulator and prioritises reliable c3270/x3270,
    telnet and netcat connectivity over strict 3270 field-map emulation.
    """
    return data.decode("ascii", errors="ignore")

def normalise_client_input(raw: bytes, session_mode: str = "ansi") -> str:
    """Return a legacy ASCII Gibson command from client bytes.

    Operation 3270 Fidelity adds a real TerminalEvent parser but this function
    intentionally preserves the old string API used by TN3270 server tests and
    nmap-sim.py compatibility.  Valid 3270 frames are parsed into events and
    converted back to the contextual legacy command; plain ASCII remains plain
    ASCII and is never forced into binary 3270 mode.
    """
    raw = raw or b""
    ev = normalise_terminal_input(raw)
    if ev.client_mode == "tn3270":
        # Prefer a fielded primary command when present, otherwise map the AID.
        return ev.to_legacy_command(session_mode)
    text = ev.to_legacy_command(session_mode)
    mapped = normalise_aid_alias(text)
    return mapped.command if mapped else text
