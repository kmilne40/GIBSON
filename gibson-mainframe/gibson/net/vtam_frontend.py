from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import socket
import time

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer

from gibson.screens.vtam_model import VtamScreenModel
from gibson.render.vtam_renderer import render_plain, render_ansi, render_3270, colour_for_line
from gibson.net.telnet3270 import IAC, DO, DONT, WILL, WONT, SB, SE, BINARY, TERMINAL_TYPE, END_OF_RECORD, TN3270E

SCREEN_PATH = Path(__file__).resolve().parents[1] / "screens" / "vtam.txt"
LIKELY_3270_TERMINALS = ("IBM-3278", "IBM-3279", "IBM-DYNAMIC", "IBM-3287")
BLOCK_FALLBACK = "#"

@dataclass
class VtamNegotiationResult:
    use_tn3270: bool
    terminal_type: str = ""
    client_bytes: bytes = b""
    local_binary: bool = False
    remote_binary: bool = False
    local_eor: bool = False
    remote_eor: bool = False
    tn3270e: bool = False
    use_tn3270e: bool = False
    binary_negotiated: bool = False
    eor_negotiated: bool = False
    reason: str = "ASCII_FALLBACK"
    pushback: bytes = b""

def load_vtam_text(path: Path | None = None) -> str:
    src = path or SCREEN_PATH
    return src.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

def _safe_ansi_text(text: str) -> str:
    return text.replace("▇", BLOCK_FALLBACK)

def _classify_line(line: str) -> str:
    from gibson.render.vtam_renderer import classify_line
    return classify_line(line)

def ascii_vtam_screen(text: str | None = None, *, addr: tuple | None = None, service_port: int | str = 2023, system_name: str | None = None) -> str:
    if text is not None:
        return text if text.endswith("\n") else text + "\n"
    return render_plain(VtamScreenModel.from_addr(addr, service_port=service_port, system_name=system_name))

def coloured_ascii_vtam_screen(text: str | None = None, *, addr: tuple | None = None, service_port: int | str = 2023, compact: bool = False, system_name: str | None = None) -> str:
    if text is not None:
        from gibson.render.vtam_renderer import is_banner_line, banner_opener, banner_fill, solidify_banner
        opener = banner_opener()
        glyph = banner_fill()
        out = []
        for line in text.splitlines():
            if not line:
                out.append(line)
            elif is_banner_line(line):
                disp = solidify_banner(line, glyph)
                lead = opener if opener else colors.TURQUOISE
                out.append(f"{lead}{disp}{colors.RESET}")
            else:
                out.append(f"{colour_for_line(line)}{line}{colors.RESET}")
        return "\n".join(out) + "\n"
    return render_ansi(VtamScreenModel.from_addr(addr, service_port=service_port, system_name=system_name), compact=compact)

def tn3270_vtam_screen(text: str | None = None, *, addr: tuple | None = None, service_port: int | str = 2023, system_name: str | None = None) -> ScreenBuffer:
    if text is not None:
        # Compatibility path for tests that still pass a raw template.
        lines = [line.rstrip("\n") for line in text.splitlines()]
        s = ScreenBuffer(rows=24, cols=80)
        s.extended_attributes = True
        row = 1; input_row = 24; input_col = 13
        for line in [line for line in lines if line.strip()]:
            if row > 24: break
            if line.startswith("Logon Type:"):
                label = "Logon Type:"
                s.put(row, 1, label, colors.GREEN, protected=True)
                input_row = row; input_col = len(label) + 2
                s.add_field(row, input_col, max(1, 80 - input_col), "", name="logon_type", colour=colors.GREEN, protected=False)
                row += 1; continue
            s.put(row, 1, _safe_ansi_text(line[:79]), colour_for_line(line), protected=True)
            row += 1
        s.set_cursor(input_row, input_col)
        return s
    return render_3270(VtamScreenModel.from_addr(addr, service_port=service_port, system_name=system_name))

def _terminal_type_from_sb(sub: bytes) -> str:
    if len(sub) >= 3 and sub[0] == TERMINAL_TYPE and sub[1] == 0x00:
        return sub[2:].decode("ascii", errors="ignore").strip()
    return ""



def _parse_iac_stream(data: bytes, result: VtamNegotiationResult) -> None:
    """Parse a bounded TELNET negotiation sample into result flags.

    This intentionally recognises only negotiation metadata. Any non-IAC bytes
    are preserved in result.pushback so ASCII clients do not lose early input.
    """
    i = 0
    push = bytearray()
    while i < len(data):
        b = data[i]
        if b != IAC:
            push.append(b); i += 1; continue
        if i + 1 >= len(data):
            break
        cmd = data[i + 1]
        if cmd in (DO, DONT, WILL, WONT):
            if i + 2 >= len(data):
                break
            opt = data[i + 2]
            if cmd == DO and opt == BINARY:
                result.local_binary = True
            elif cmd == WILL and opt == BINARY:
                result.remote_binary = True
            elif cmd == DO and opt == END_OF_RECORD:
                result.local_eor = True
            elif cmd == WILL and opt == END_OF_RECORD:
                result.remote_eor = True
            elif opt == TN3270E and cmd in (DO, WILL):
                # Record but do not enable TN3270E in this corrective build.
                # Classic TN3270 is used unless a full TN3270E state machine is implemented.
                result.tn3270e = True
                result.use_tn3270e = False
            i += 3
            continue
        if cmd == SB:
            end = data.find(bytes([IAC, SE]), i + 2)
            if end == -1:
                break
            sub = data[i + 2:end]
            ttype = _terminal_type_from_sb(sub)
            if ttype:
                result.terminal_type = ttype
            i = end + 2
            continue
        if cmd == IAC:
            push.append(IAC); i += 2; continue
        i += 2
    result.client_bytes += data[:4096]
    result.pushback += bytes(push)
    result.binary_negotiated = result.local_binary and result.remote_binary
    result.eor_negotiated = result.local_eor and result.remote_eor


def _is_3270_terminal_type(ttype: str) -> bool:
    upper = (ttype or "").upper()
    return any(token in upper for token in LIKELY_3270_TERMINALS)


def negotiate_tn3270_or_ascii(conn: socket.socket, timeout: float = 0.45) -> VtamNegotiationResult:
    """Classify a port-2023 connection without negotiating TN3270.

    Port 2023 is dual-mode.  This frontend is now a passive router only:
    it may peek/consume a small amount of already-sent client data to decide
    whether bytes look like TELNET/IAC negotiation or plain ASCII/NVT input.
    It must not send a TN3270 prologue, TERMINAL-TYPE SEND, BINARY, EOR, or
    TN3270E bytes.  Tn3270Session is the single authoritative owner of all
    TN3270 option negotiation.
    """
    result = VtamNegotiationResult(use_tn3270=False)
    try:
        old_timeout = conn.gettimeout()
    except Exception:
        old_timeout = None
    try:
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            try:
                conn.settimeout(max(0.02, min(0.05, deadline - time.monotonic())))
                data = conn.recv(4096, socket.MSG_PEEK)
            except (socket.timeout, TimeoutError, BlockingIOError):
                continue
            except (TypeError, ValueError, OSError):
                result.reason = "ASCII_TLS_OR_NO_PEEK"
                return result
            if not data:
                result.reason = "ASCII_EMPTY_OR_CLOSED"
                return result
            if data[:1] != bytes([IAC]):
                result.reason = "ASCII_EARLY_TEXT"
                return result
            consumed = conn.recv(len(data))
            _parse_iac_stream(consumed, result)
            if (result.local_binary or result.remote_binary or
                    result.local_eor or result.remote_eor or
                    _is_3270_terminal_type(result.terminal_type)):
                result.use_tn3270 = True
                result.reason = "TN3270_CLIENT_IAC_ROUTED"
                return result
            # A telnet-aware client (it sent IAC negotiation) is, on a mainframe
            # front door, almost certainly a 3270 emulator (c3270/x3270/tn3270)
            # whose BINARY/EOR/TERMINAL-TYPE markers simply have not arrived in
            # this first batch.  Route it to the active TN3270 negotiation owned
            # by Tn3270Session, which drives TERMINAL-TYPE/BINARY/EOR properly so
            # the client lands in formatted EBCDIC 3270 (function keys arrive as
            # AID bytes, never ANSI "ESC O R").  nc/ncat send no IAC and are
            # handled by the ASCII_EARLY_TEXT branch above, so they stay NVT.
            # Set GIBSON_2023_PASSIVE=1 to restore the old passive-only routing.
            if os.getenv("GIBSON_2023_PASSIVE", "") not in ("1", "true", "TRUE", "yes"):
                result.use_tn3270 = True
                result.reason = "TN3270_CLIENT_IAC_ACTIVE_NEGOTIATION"
                return result
            result.use_tn3270 = False
            result.reason = "ASCII_TELNET_NVT"
            return result

        # If no client bytes arrive during the passive probe window, preserve
        # the historical ASCII/NVT behaviour.  Routing an idle raw socket into
        # TN3270 sends EBCDIC/3270 datastream bytes to netcat/ncat, which is
        # exactly the mojibake regression users observed.  Real c3270/x3270
        # clients normally send TELNET/IAC negotiation bytes promptly and are
        # routed above; an idle socket must remain readable ASCII.
        result.use_tn3270 = False
        result.reason = "ASCII_IDLE_FALLBACK"
        return result
    finally:
        try:
            conn.settimeout(old_timeout)
        except Exception:
            pass
