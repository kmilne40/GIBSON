from __future__ import annotations

import socket
import socketserver
import threading
import time
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from gibson.apps.cics import CicsSimulator
from gibson.apps.zvm import ZvmSession
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.render.screen3270 import ScreenBuffer
from gibson.render import colors
from gibson.render.ansi3270 import render_ansi_to_screen, strip_ansi
from gibson.net.vtam_frontend import tn3270_vtam_screen
from gibson.net.telnet3270 import normalise_client_input
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.apps.ispf3270.editor import Ispf3270Editor


class _Subsys(NamedTuple):
    """One declaration of an interactive subsystem reachable from TSO READY.

    The single source of truth for EBCDIC subsystem dispatch: entry (launch),
    sub-mode, and how that sub-mode consumes input.  Both the entry routing and
    the per-mode input routing derive from this, so a subsystem can't be
    half-wired (added to one dispatch site but forgotten in another).

    line   - line-oriented sub-mode: handle_tso passes the typed line here.
    panel  - 3270 panel app (e.g. OEDIT) dispatched in serve() via a 3270 frame;
             app_attr names the session attribute holding the live app instance.
    """
    name: str
    enter: Callable
    mode: str
    line: Optional[Callable] = None
    panel: bool = False
    app_attr: str = ""


class _Omvs3270Editor(Ispf3270Editor):
    """The ISPF 3270 full-screen editor, but persisting to the z/OS UNIX
    filesystem instead of a dataset — this is what OEDIT edits."""

    def __init__(self, state, userid, dsname, text, save_callback, **kw):
        super().__init__(state, userid, dsname, text, **kw)
        self._omvs_save = save_callback

    def _save(self) -> None:
        if self.readonly:
            self._message = "FILE IS READ-ONLY - NOT SAVED"
            return
        try:
            self._omvs_save("\n".join(self.lines) + "\n")
            self.changed = False
            self._renumber(True)
            self._message = f"{self.dsname} SAVED"
        except Exception as exc:  # noqa: BLE001
            self._message = f"SAVE FAILED: {exc}"


IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0
EOR = 0xEF
# Rows of TSO output shown per screen before a '***' continuation pause.
_TSO_PAGE = 21


def _omvs_wants_password(text: str) -> bool:
    """True if the OMVS program output is prompting for a password, so the next
    3270 input field should be rendered non-display."""
    if not text:
        return False
    tail = text.rstrip()
    last = tail.splitlines()[-1].strip().lower() if tail.splitlines() else ""
    return (last.endswith("password:") or last.endswith("password :")
            or "send password" in last or last == "password"
            or last.endswith("passphrase:") or last.endswith("password?")
            or last.startswith("331 ")              # FTP: need password
            or "enter password" in last)
BINARY = 0x00
TTYPE = 0x18
OPT_EOR = 0x19
TN3270 = 0x1C
TN3270E = 0x28
SEND = 0x01
IS = 0x00

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

AID_ENTER = 0x7D
AID_PF3 = 0xF3
AID_PF12 = 0x7C
AID_PF24 = 0x4C
AID_CLEAR = 0x6D

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


class ClientDisconnected(Exception):
    """Connection dropped while servicing a TN3270 session."""


class Tn3270Session:
    def __init__(self, state: GibsonState, conn: socket.socket, addr: Tuple[str, int], initial_negotiation=None):
        self.state = state
        self.conn = conn
        self.addr = addr
        self.mode = "VTAM"
        self.userid = ""
        self.pending_user = ""
        self.cics = CicsSimulator(state, "IBMUSER")
        self.zvm: ZvmSession | None = None
        self.tso_app = None
        self.tso = None              # TsoCommandProcessor, created at logon
        self.omvs_shell = None       # OmvsShellSession when in TSO_OMVS submode
        self.console_ctl = None      # MasterConsoleController when in TSO_CONSOLE
        self.cics_app = None
        self.db2_app = None
        self.sdsf_app = None
        self.ispf_app = None
        self.ims_app = None          # Ims3270Session when in IMSAPP mode
        self.tpf_app = None          # Ztpf3270Session when in TPFAPP mode
        self.oedit_app = None        # _Omvs3270Editor when in OEDITAPP mode
        self.ftp_app = None          # TsoFtpClientApp when in TSO_FTP mode
        self.telnet_app = None       # TelnetSubsession when in TSO_TELNET mode
        self._panel_return = "TSO_READY"  # where a panel app (OEDIT) returns on exit
        self._omvs_repl_prompt = None      # callable -> prompt, while in TSO_OMVS_REPL
        self._omvs_repl_step = None        # callable(line) -> str|None, None ends the REPL
        # 10d: single declaration of every interactive subsystem reachable from
        # TSO READY.  Entry routing, per-mode input routing, and panel dispatch
        # all derive from this list, so a subsystem can't be half-wired.
        self._subsystems = [
            _Subsys("OMVS",    self._enter_omvs,    "TSO_OMVS",    line=self._handle_omvs_line),
            _Subsys("CONSOLE", self._enter_console, "TSO_CONSOLE", line=self._handle_console_line),
            _Subsys("FTP",     self._enter_ftp,     "TSO_FTP",     line=self._handle_ftp_line),
            _Subsys("TELNET",  self._enter_telnet,  "TSO_TELNET",  line=self._handle_telnet_line),
            _Subsys("OEDIT",   self._enter_oedit,   "OEDITAPP",    panel=True, app_attr="oedit_app"),
        ]
        self._subsys_by_target = {s.name: s for s in self._subsystems}
        self._subsys_by_mode = {s.mode: s for s in self._subsystems}
        self._ftp_stage = None       # "USER" | "PASS" | "CMD"
        self._ftp_user = ""
        self._tso_more = None        # pending paged TSO output (*** continuation)
        self._newpass = None         # forced initial-password-change flow state
        self.cursor_row = 24
        self.cursor_col = 1
        self.tn3270e_requested = False
        self.tn3270e_rejected = False
        self.tn3270e_active = False
        self.tn3270e_device_type = "IBM-3278-2-E"
        self.terminal_type = ""
        self.tn3270e_functions: bytes = b""
        self.local_binary = False
        self.remote_binary = False
        self.local_eor = False
        self.remote_eor = False
        self.remote_ttype = False
        self.terminal_type_send_sent = False
        self.in_3270_mode = False
        self.negotiated_once = False
        self.sent_3270_bytes = False
        self.failure_reason = ""
        self.current_screen: ScreenBuffer | None = None
        self.current_registry = None
        # The frontend is a passive router.  If it consumed initial TELNET/IAC
        # bytes, feed them into this single negotiation state machine instead
        # of trusting frontend-derived flags.
        self.initial_bytes = b""
        if initial_negotiation is not None:
            self.initial_bytes = bytes(getattr(initial_negotiation, "client_bytes", b"") or b"")
            pb = bytes(getattr(initial_negotiation, "pushback", b"") or b"")
            if pb and not self.initial_bytes:
                self.initial_bytes = pb
        # Plain ASCII (non-IAC) bytes seen while we were attempting TN3270
        # negotiation.  If the client turns out not to be a 3270 terminal
        # (e.g. netcat), these are handed back so the NVT/ASCII path can use
        # them instead of losing the user's first keystrokes.
        self.pending_ascii = bytearray()

    def send(self, data: bytes) -> None:
        # Classic TN3270 only in this build.  Do not add TN3270E headers.
        try:
            self.conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            raise ClientDisconnected() from exc

    def negotiate(self) -> None:
        """Send the single classic TN3270 host prologue for this session.

        TERMINAL-TYPE SEND is deliberately not sent here.  It is emitted only
        after the client has replied WILL TERMINAL-TYPE.
        """
        if self.negotiated_once:
            return
        self.negotiated_once = True
        # Offer TN3270E first so service scanners (e.g. `nmap -sV`) identify the
        # listener as "IBM Telnet TN3270 (TN3270E)". We do not actually run in
        # TN3270E data mode: _reply_telnet declines it (DONT on WILL / accepts
        # WONT), so every client cleanly falls back to classic TN3270.
        self.send(bytes([
            IAC, DO, TN3270E,
            IAC, WILL, BINARY,
            IAC, DO, BINARY,
            IAC, WILL, OPT_EOR,
            IAC, DO, OPT_EOR,
            IAC, DO, TTYPE,
        ]))

    def _request_terminal_type_once(self) -> None:
        if self.terminal_type_send_sent:
            return
        self.terminal_type_send_sent = True
        self.send(bytes([IAC, SB, TTYPE, SEND, IAC, SE]))

    def _send_tn3270e_sb(self, *parts: bytes | int) -> None:
        payload = bytearray([IAC, SB, TN3270E])
        for part in parts:
            if isinstance(part, int):
                payload.append(part)
            else:
                payload.extend(part)
        payload.extend([IAC, SE])
        try:
            self.conn.sendall(bytes(payload))
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            raise ClientDisconnected() from exc

    def _handle_tn3270e_subnegotiation(self, sub: bytes) -> None:
        # TN3270E is intentionally not implemented in this corrective build.
        # Option-level DO/WILL TN3270E is rejected in _reply_telnet; stray
        # subnegotiation is recorded but does not activate TN3270E mode.
        if sub and sub[0] == TN3270E:
            self.tn3270e_requested = False
            self.tn3270e_rejected = True
            self.tn3270e_active = False

    def _reply_telnet(self, cmd: int, opt: int) -> None:
        if cmd == DO:
            if opt == BINARY:
                self.local_binary = True
                self.send(bytes([IAC, WILL, opt]))
            elif opt == OPT_EOR:
                self.local_eor = True
                self.send(bytes([IAC, WILL, opt]))
            elif opt == TN3270E:
                self.tn3270e_requested = False
                self.tn3270e_rejected = True
                self.tn3270e_active = False
                self.send(bytes([IAC, WONT, opt]))
            else:
                self.send(bytes([IAC, WONT, opt]))
        elif cmd == DONT:
            if opt == BINARY:
                self.local_binary = False
            elif opt == OPT_EOR:
                self.local_eor = False
            elif opt == TN3270E:
                self.tn3270e_requested = False
                self.tn3270e_rejected = True
                self.tn3270e_active = False
            self.send(bytes([IAC, WONT, opt]))
        elif cmd == WILL:
            if opt == BINARY:
                self.remote_binary = True
                self.send(bytes([IAC, DO, opt]))
            elif opt == OPT_EOR:
                self.remote_eor = True
                self.send(bytes([IAC, DO, opt]))
            elif opt == TTYPE:
                self.remote_ttype = True
                # Do NOT echo IAC DO TTYPE — we already sent it in negotiate().
                # Echoing it creates a WILL TTYPE → DO TTYPE → WILL TTYPE loop.
                self._request_terminal_type_once()
            elif opt == TN3270E:
                self.tn3270e_requested = False
                self.tn3270e_rejected = True
                self.tn3270e_active = False
                self.send(bytes([IAC, DONT, opt]))
            else:
                self.send(bytes([IAC, DONT, opt]))
        elif cmd == WONT:
            if opt == BINARY:
                self.remote_binary = False
            elif opt == OPT_EOR:
                self.remote_eor = False
            elif opt == TTYPE:
                self.remote_ttype = False
            elif opt == TN3270E:
                # WONT TN3270E is itself the client's acknowledgment of our
                # earlier DONT. Replying again invites an endless
                # DONT -> WONT -> DONT ping-pong with clients (e.g. web3270)
                # that always re-ack a DONT with another WONT.
                already_rejected = self.tn3270e_rejected
                self.tn3270e_requested = False
                self.tn3270e_rejected = True
                self.tn3270e_active = False
                if already_rejected:
                    return
            self.send(bytes([IAC, DONT, opt]))

    def _classic_3270_ready(self) -> bool:
        ttype = (self.terminal_type or self.tn3270e_device_type or "").upper()
        is_3270_type = ("IBM-3278" in ttype) or ("IBM-3279" in ttype) or ("IBM-DYNAMIC" in ttype) or ("IBM-3287" in ttype)
        return self.local_binary and self.remote_binary and self.local_eor and self.remote_eor and is_3270_type

    def _ready_for_initial_screen(self) -> bool:
        # This build is classic TN3270 only.  TN3270E offers are explicitly
        # rejected and must never cause TN3270E headers or half-state.
        return self._classic_3270_ready()

    def _mark_3270_mode_if_ready(self) -> bool:
        self.in_3270_mode = self._ready_for_initial_screen()
        return self.in_3270_mode

    def _process_negotiation_bytes(self, data: bytes, pending: bytearray) -> None:
        pending.extend(data)
        i = 0
        while i < len(pending):
            b = pending[i]
            if b != IAC:
                self.pending_ascii.append(b)
                i += 1
                continue
            if i + 1 >= len(pending):
                break
            cmd = pending[i + 1]
            if cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(pending):
                    break
                self._reply_telnet(cmd, pending[i + 2])
                i += 3
                continue
            if cmd == SB:
                end = pending.find(bytes([IAC, SE]), i + 2)
                if end == -1:
                    break
                sub = bytes(pending[i + 2 : end])
                if len(sub) >= 2 and sub[0] == TTYPE and sub[1] == SEND:
                    self.send(bytes([IAC, SB, TTYPE, IS]) + self.tn3270e_device_type.encode("ascii") + bytes([IAC, SE]))
                elif len(sub) >= 3 and sub[0] == TTYPE and sub[1] == IS:
                    ttype = sub[2:].decode("ascii", errors="ignore").strip()
                    if ttype:
                        self.terminal_type = ttype
                        self.tn3270e_device_type = ttype
                elif sub[:1] == bytes([TN3270E]):
                    self._handle_tn3270e_subnegotiation(sub)
                i = end + 2
                continue
            if cmd == IAC:
                i += 2
                continue
            i += 2
        if i:
            del pending[:i]

    def _wait_for_initial_negotiation(self, timeout: float = 0.75) -> bool:
        """Wait for BINARY, EOR and TERMINAL-TYPE readiness.

        This method processes any TELNET bytes consumed by the frontend and
        then reads fresh data until classic TN3270 is ready or the bounded
        timeout expires.  It never sends a 3270 screen on failure.
        """
        pending = bytearray()
        deadline = time.monotonic() + timeout
        old_timeout = self.conn.gettimeout()
        try:
            if self.initial_bytes:
                self._process_negotiation_bytes(self.initial_bytes, pending)
                self.initial_bytes = b""
            while time.monotonic() < deadline and not self._ready_for_initial_screen():
                remaining = max(0.02, deadline - time.monotonic())
                self.conn.settimeout(min(0.2, remaining))
                try:
                    data = self.conn.recv(4096)
                except (TimeoutError, socket.timeout):
                    continue
                except (ConnectionResetError, OSError) as exc:
                    raise ClientDisconnected() from exc
                if not data:
                    break
                self._process_negotiation_bytes(data, pending)
        finally:
            self.conn.settimeout(old_timeout)
        if self._mark_3270_mode_if_ready():
            self.failure_reason = ""
            return True
        self.in_3270_mode = False
        self.failure_reason = (
            f"not-ready terminal_type={self.terminal_type!r} "
            f"binary=({self.local_binary},{self.remote_binary}) "
            f"eor=({self.local_eor},{self.remote_eor}) "
            f"tn3270e_rejected={self.tn3270e_rejected}"
        )
        return False

    def recv_packet(self) -> bytes:
        # After the initial screen is written, a 3270 terminal performs local
        # editing: TAB, cursor movement and typed text usually do not traverse
        # the socket until ENTER/PF/PA is pressed.  A read timeout is therefore
        # an idle wait, not EOF.  Only a zero-length recv or socket error closes
        # the session.
        old_timeout = self.conn.gettimeout()
        self.conn.settimeout(30)
        payload = bytearray()
        try:
            while True:
                try:
                    data = self.conn.recv(4096)
                except (TimeoutError, socket.timeout):
                    continue
                except (ConnectionResetError, OSError) as exc:
                    raise ClientDisconnected() from exc
                if not data:
                    return b""
                i = 0
                while i < len(data):
                    b = data[i]
                    if b != IAC:
                        payload.append(b)
                        i += 1
                        continue
                    if i + 1 >= len(data):
                        i += 1
                        continue
                    cmd = data[i + 1]
                    if cmd == IAC:
                        payload.append(IAC)
                        i += 2
                        continue
                    if cmd == EOR:
                        out = bytes(payload)
                        if self.tn3270e_active and len(out) >= TN3270E_HEADER_LEN:
                            out = out[TN3270E_HEADER_LEN:]
                        return out
                    if cmd in (DO, DONT, WILL, WONT):
                        if i + 2 < len(data):
                            self._reply_telnet(cmd, data[i + 2])
                        i += 3
                        continue
                    if cmd == SB:
                        end = data.find(bytes([IAC, SE]), i + 2)
                        if end == -1:
                            # Keep partial payload; wait for the rest instead
                            # of closing the session on a fragmented SB.
                            break
                        sub = data[i + 2 : end]
                        if len(sub) >= 2 and sub[0] == TTYPE and sub[1] == SEND:
                            self.send(bytes([IAC, SB, TTYPE, IS]) + self.tn3270e_device_type.encode("ascii") + bytes([IAC, SE]))
                        elif len(sub) >= 3 and sub[0] == TTYPE and sub[1] == IS:
                            ttype = sub[2:].decode("ascii", errors="ignore").strip()
                            if ttype:
                                self.terminal_type = ttype
                                self.tn3270e_device_type = ttype
                        elif sub[:1] == bytes([TN3270E]):
                            self._handle_tn3270e_subnegotiation(sub)
                        i = end + 2
                        continue
                    i += 2
        finally:
            try:
                self.conn.settimeout(old_timeout)
            except Exception:
                pass

    @staticmethod
    def _decode_baddr(byte1: int, byte2: int) -> int:
        if (byte1 & 0xC0) == 0:
            return ((byte1 & 0x3F) << 8) | byte2
        return ((byte1 & 0x3F) << 6) | (byte2 & 0x3F)

    def _parse_packet(self, packet: bytes) -> tuple[int, List[Tuple[int, str]]]:
        if not packet:
            return AID_ENTER, []
        event = parse_3270_input_frame(packet, screen_registry=self.current_registry)
        aid_byte = event.raw_aid if event.raw_aid is not None else (packet[0] if packet else AID_ENTER)
        entries: List[Tuple[int, str]] = []
        for addr, text in sorted((event.fields_by_address or {}).items()):
            if text.strip():
                entries.append((addr, text))
        # Prefer explicit command/option/select fields, then contextual legacy AID.
        text = (event.command_text or "").strip()
        if not text:
            text = event.to_legacy_command(self.mode).strip()
        if text and not entries:
            entries.append((0, text))
        return aid_byte, entries

    def _row_col(self, addr: int) -> tuple[int, int]:
        return (addr // 80) + 1, (addr % 80) + 1

    def _text_from_entries(self, entries: List[Tuple[int, str]]) -> str:
        if not entries:
            return ""
        entries = sorted(entries, key=lambda item: item[0])
        if len(entries) == 1:
            return entries[0][1].strip()
        return " ".join(text.strip() for _addr, text in entries if text.strip())

    def _send_screen(self, screen: ScreenBuffer) -> None:
        if not self.in_3270_mode:
            raise ClientDisconnected("3270 screen requested before negotiated 3270 mode")
        self.cursor_row = screen.cursor_row
        self.cursor_col = screen.cursor_col
        self.current_screen = screen
        self.current_registry = screen
        self.send(screen.to_3270())

    def _simple_screen(self, title: str, lines: List[str], cursor: tuple[int, int] = (24, 1),
                       input_field: bool = False, input_hidden: bool = False) -> ScreenBuffer:
        s = ScreenBuffer()
        row = 1
        if title:
            s.put(row, 1, title[:79])
            row += 2
        for line in lines:
            if row > s.rows:
                break
            s.put(row, 1, line[:79])
            row += 1
        cr, cc = cursor
        if input_field:
            # Block-mode 3270 needs a real unprotected field to capture typed
            # input; without it the client's Read Modified returns raw buffer /
            # attribute bytes that EBCDIC-decode to garbage (e.g. a mangled
            # userid).  Give the prompt one input field spanning to end of line.
            width = max(1, s.cols - cc - 1)
            s.add_field("CMDLINE", cr, cc, width, protected=False,
                        hidden=bool(input_hidden), role="command")
        s.set_cursor(cr, cc)
        return s

    def vtam_screen(self) -> ScreenBuffer:
        return tn3270_vtam_screen(addr=self.addr, service_port=self.state.config.port, system_name=self.state.get_system_hostname())

    def tso_user_screen(self, message: str = "") -> ScreenBuffer:
        lines = []
        if message:
            lines.append(message)
            lines.append("")
        lines.extend(["LOGON", "", "IKJ56700A ENTER USERID -"])
        return self._simple_screen("", lines, (4 if message else 3, 25), input_field=True)

    def tso_password_screen(self, userid: str, message: str = "") -> ScreenBuffer:
        lines = []
        if message:
            lines.extend([message, ""])
        lines.append(f"ENTER CURRENT PASSWORD FOR {userid}-")
        return self._simple_screen("", lines, (3 if message else 1, len(lines[-1]) + 1), input_field=True, input_hidden=True)

    def tso_mfa_screen(self, userid: str, message: str = "") -> ScreenBuffer:
        lines = []
        if message:
            lines.extend([message, ""])
        lines.extend(["MFA TOKEN REQUIRED", "ENTER MFA TOKEN (PIN+HHMM) -"])
        return self._simple_screen("", lines, (4 if message else 2, len(lines[-1]) + 1), input_field=True)

    def tso_ready_screen(self, message: str = "READY", cmd_value: str = "",
                         cmd_modified: bool = False) -> ScreenBuffer:
        body = [] if (not message or message == "READY") else self._wrap_lines(message)
        return self._render_tso_page(body, "READY", colors.RED, more=False,
                                     cmd_value=cmd_value, cmd_modified=cmd_modified)

    def tso_output_screen(self, output: str, prompt: str = "READY",
                          base_colour: str = None) -> ScreenBuffer:
        """Render a single screen of TSO output in colour (no paging).

        Used for short output and logon-style screens.  ANSI in the source is
        converted to 3270 colour fields by render_ansi_to_screen, so no escape
        bytes ever reach the datastream.
        """
        base = base_colour or colors.RED
        page = self._wrap_lines(output)[:_TSO_PAGE]
        return self._render_tso_page(page, prompt, base, more=False)

    def _wrap_lines(self, output: str) -> List[str]:
        lines: List[str] = []
        for ln in (output or "").replace("\r", "").split("\n"):
            ln = ln.rstrip()
            while len(ln) > 79:
                lines.append(ln[:79]); ln = ln[79:]
            lines.append(ln)
        return lines

    def _render_tso_page(self, page: List[str], footer: str, base: str,
                         more: bool, hidden: bool = False, cmd_value: str = "",
                         cmd_modified: bool = False) -> ScreenBuffer:
        s = ScreenBuffer()
        if any(page):
            render_ansi_to_screen("\n".join(page), base_colour=base,
                                  screen=s, start_row=1)
        frow = min(len(page) + 2, 24)
        s.put(frow, 1, footer, base)
        if more:
            # '***' continuation: any AID (ENTER) advances; no input field.
            s.set_cursor(min(frow + 1, 24), 1)
        else:
            # A single unprotected command field from the row below the prompt
            # to the end of the screen, so a long command wraps across rows and
            # is returned as one contiguous run (no split or spurious spaces).
            irow = min(frow + 1, 24)
            start = (irow - 1) * s.cols
            length = max(1, s.rows * s.cols - 2 - start)  # keep last cell for stop
            s.add_field("COMMAND", irow, 1, length, protected=False, colour=base,
                        hidden=bool(hidden), value=(cmd_value or ""),
                        mdt=bool(cmd_modified))
            s.bound_input_fields = True
            s.set_cursor(irow, 2 + len(cmd_value or ""))
        return s

    def _emit_tso_output(self, text: str, *, prompt: str = "READY",
                         base_colour: str = None,
                         return_mode: str = "TSO_READY",
                         input_hidden: bool = False) -> None:
        """Send TSO output, paging with '***' (ENTER to continue) when it does
        not fit one screen, instead of truncating.  Returns to return_mode once
        the last page has been shown.  ``input_hidden`` renders the command
        field as non-display (used for password prompts)."""
        base = base_colour or colors.RED
        self._tso_more = {"lines": self._wrap_lines(text), "prompt": prompt,
                          "base": base, "return": return_mode, "pos": 0,
                          "hidden": bool(input_hidden)}
        self._send_tso_page()

    def _send_tso_page(self) -> None:
        st = self._tso_more
        page = st["lines"][st["pos"]: st["pos"] + _TSO_PAGE]
        st["pos"] += len(page)
        more = st["pos"] < len(st["lines"])
        s = self._render_tso_page(page, "***" if more else st["prompt"],
                                  st["base"], more, hidden=(st.get("hidden", False) and not more))
        if more:
            self.mode = "TSO_MORE"
        else:
            self.mode = st["return"]
            self._tso_more = None
        self._send_screen(s)

    def _pending_messages_text(self) -> str:
        """Read and clear any SEND messages queued for this user (delivered at
        logon, matching the ASCII/NVT path)."""
        try:
            pending = self.state.racf.ensure_user_dir(
                self.state.config.files_root, self.userid) / "pending_messages.txt"
            if pending.exists():
                text = pending.read_text(encoding="utf-8", errors="ignore")
                pending.unlink(missing_ok=True)
                if text.strip():
                    return text.rstrip("\n")
        except Exception:
            pass
        return ""

    def cics_gm_screen(self) -> ScreenBuffer:
        return self._simple_screen(
            "WELCOME TO CICS",
            [
                "",
                "CLEAR THE SCREEN TO ENTER A TRANSACTION.",
                "EXAMPLES: CESF  CEMT  CEDA  CECI  GMVB",
            ],
            (24, 1),
        )

    def cics_blank_screen(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.set_cursor(1, 1)
        return s

    def cics_text_screen(self, text: str) -> ScreenBuffer:
        lines = (text or "").replace("\r", "").splitlines() or [""]
        s = ScreenBuffer()
        for idx, line in enumerate(lines[:24], start=1):
            s.put(idx, 1, line[:79])
        s.set_cursor(min(24, len(lines) + 1), 1)
        return s

    def handle_vtam(self, text: str) -> None:
        uc = text.strip().upper()
        # VTAM IBMTEST echo test. Real VTAM replies to IBMTEST by echoing the
        # alphabet+digits prefixed with IBMECHO. nmap's vtam-enum uses this exact
        # string to confirm it is talking to a genuine VTAM USS environment.
        if uc == "IBMTEST" or uc.startswith("IBMTEST "):
            echo = "IBMECHO ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            self._send_screen(self._simple_screen("", [echo, "", echo, "", echo, "", "ENTER APPLID"], (8, 1)))
            return
        applid = uc
        if uc.startswith("LOGON APPLID(") and uc.endswith(")"):
            applid = uc[len("LOGON APPLID(") : -1].strip()
        elif uc in {"L TSO", "LTSO"}:
            applid = "TSO"
        elif uc in {"L CICS", "LCICS"}:
            applid = "CICS"
        elif uc in {"L DB2", "LDB2"}:
            applid = "DB2"
        elif uc in {"L DSN", "LDSN", "L DB2C", "LDB2C"}:
            applid = "DSN"
        elif uc in {"L SDSF", "LSDSF"}:
            applid = "SDSF"
        elif uc in {"L ISPF", "LISPF", "L ISPF/PDF", "ISPF"}:
            applid = "ISPF"
        elif uc in {"L ZVM", "LZVM"}:
            applid = "ZVM"
        elif uc in {"L IMS", "LIMS"}:
            applid = "IMS"
        elif uc in {"L TPF", "LTPF", "L ZTPF", "LZTPF"}:
            applid = "TPF"
        if applid == "TSO":
            from gibson.apps.tso3270 import Tso3270App
            from gibson.apps.tso3270.tso_session import rows_for_terminal
            self.tso_app = Tso3270App(
                self.state, peer_addr=self.addr[0],
                rows=rows_for_terminal(getattr(self, "terminal_type", "")
                                       or getattr(self, "tn3270e_device_type", "")),
            )
            self.mode = "TSOAPP"
            self._send_screen(self.tso_app.initial_screen())
            return
        if applid == "CICS":
            from gibson.apps.cics3270 import Cics3270Session
            self.cics_app = Cics3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "CICSAPP"
            self._send_screen(self.cics_app.initial_screen())
            return
        if applid == "ZVM":
            self.zvm = ZvmSession(self.state, peer_addr=self.addr[0])
            self.mode = "ZVM"
            self._send_screen(self.zvm.logon_screen())
            return
        if applid == "IMS":
            from gibson.apps.ims.ims3270 import Ims3270Session
            self.ims_app = Ims3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "IMSAPP"
            self._send_screen(self.ims_app.initial_screen())
            return
        if applid == "TPF":
            from gibson.apps.ztpf.ztpf3270 import Ztpf3270Session
            self.tpf_app = Ztpf3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "TPFAPP"
            self._send_screen(self.tpf_app.initial_screen())
            return
        if applid == "DB2":
            # L DB2 / LOGON APPLID(DB2) goes to the DSN line-mode command
            # processor (the authentic DB2 entry from VTAM), not the DB2I ISPF
            # panel. The DB2I primary option menu remains reachable from ISPF.
            from gibson.apps.db2i3270 import Db2i3270Session
            self.db2_app = Db2i3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "DB2APP"
            self._send_screen(self.db2_app._enter_dsn())
            return
        if applid == "DSN":
            from gibson.apps.db2i3270 import Db2i3270Session
            self.db2_app = Db2i3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "DB2APP"
            self._send_screen(self.db2_app._enter_dsn())
            return
        if applid == "SDSF":
            from gibson.apps.sdsf3270 import Sdsf3270Session
            self.sdsf_app = Sdsf3270Session(self.state, peer_addr=self.addr[0])
            self.mode = "SDSFAPP"
            self._send_screen(self.sdsf_app.initial_screen())
            return
        if applid == "ISPF":
            from gibson.apps.ispf3270 import IspfSplitManager
            self.ispf_app = IspfSplitManager(self.state, peer_addr=self.addr[0])
            self.mode = "ISPFAPP"
            self._send_screen(self.ispf_app.initial_screen())
            return
        self._send_screen(self._simple_screen("", [
            f"IST097I APPLICATION {applid or 'BLANK'} NOT FOUND",
            f"UNABLE TO ESTABLISH SESSION WITH {applid or 'BLANK'}",
            "",
            "ENTER APPLID",
        ], (4, 1)))

    def handle_tso(self, text: str) -> None:
        if self.mode == "TSO_MORE":
            # At a '***' pause any AID (ENTER) shows the next page.
            return self._send_tso_page()
        uc = text.strip().upper()
        if uc.startswith("LOGON APPLID(") or uc in {"TSO", "CICS", "DB2", "DSN", "ZVM", "IMS", "L TSO", "L CICS", "L DB2", "L DSN", "L ZVM", "L IMS", "L TPF", "LTSO", "LCICS", "LDB2", "LDSN", "LZVM", "LIMS", "LTPF"}:
            self.mode = "VTAM"
            self.handle_vtam(uc)
            return
        if self.mode == "TSO_USER":
            user = text.strip().upper()
            if not user:
                self._send_screen(self.tso_user_screen())
                return
            self.state.racf.load(merge=True)
            if not self.state.racf.exists(user):
                self.state.note_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port, service="TN3270/TSO")
                self.state.record_security_event(user, "LOGON", "USERID NOT DEFINED", result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
                self._send_screen(self.tso_user_screen(f"IKJ56420I Userid {user} not authorized to use TSO"))
                return
            rec = self.state.racf.get(user)
            if rec and rec.revoked:
                self.state.record_security_event(user, "LOGON", "USERID REVOKED", result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
                self._send_screen(self.tso_user_screen(f"ICH70001I USERID {user} IS REVOKED - LOGON REJECTED BY RACF"))
                return
            self.pending_user = user
            self.mode = "TSO_PASS"
            self._send_screen(self.tso_password_screen(user))
            return
        if self.mode == "TSO_PASS":
            pw = text.strip()
            user = self.pending_user or "IBMUSER"
            if self.state.racf.verify_password(user, pw):
                if self.state.mfa_required_for(user):
                    self.mode = "TSO_MFA"
                    self._send_screen(self.tso_mfa_screen(user))
                    return
                self.userid = user
                self.state.clear_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port)
                if user == "IBMUSER" and getattr(self.state.config, "security_mode", "vuln") == "secure":
                    self.state.record_break_glass("IBMUSER", "TN3270 LOGON")
                self.state.record_security_event(user, "LOGON", "PASSWORD", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
                self._post_auth(user)
                return
            self.state.note_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port, service="TN3270/TSO")
            self.state.record_security_event(user, "LOGON", "PASSWORD FAILURE", result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_password_screen(user, "PASSWORD INCORRECT"))
            return
        if self.mode == "TSO_MFA":
            token = text.strip()
            user = self.pending_user or "IBMUSER"
            if self.state.validate_mfa_token(token):
                self.userid = user
                self.state.clear_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port)
                if user == "IBMUSER" and getattr(self.state.config, "security_mode", "vuln") == "secure":
                    self.state.record_break_glass("IBMUSER", "TN3270 LOGON")
                self.state.record_security_event(user, "LOGON", "PASSWORD MFA SUCCESS", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
                self._post_auth(user)
                return
            self.state.note_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port, service="TN3270/TSO")
            self.state.record_security_event(user, "MFA", "TOKEN FAILURE", result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_mfa_screen(user, "MFA TOKEN INVALID"))
            return
        if self.mode == "TSO_NEWPASS":
            return self._handle_newpass_line(text)
        if self.mode == "TSO_OMVS_REPL":
            return self._handle_omvs_repl_line(text)
        sub = self._subsys_by_mode.get(self.mode)
        if sub is not None and sub.line is not None:
            return sub.line(text)
        uc = text.strip().upper()
        if uc in {"LOGOFF", "SIGNOFF", "EXIT"}:
            self.mode = "VTAM"
            self.userid = ""
            self.pending_user = ""
            self.tso = None
            self._send_screen(self.vtam_screen())
            return
        if uc.startswith("IND$FILE ") or uc.startswith("INDSFILE ") or uc.startswith("IND\\$FILE "):
            self._run_indfile_cut(text.strip())
            return
        self._handle_tso_command(text)

    # ---- post-logon TSO command execution (parity with the ASCII path) ----
    def _login_complete(self, user: str, note: str = None) -> None:
        from gibson.apps.tso import TsoCommandProcessor
        self.userid = user
        self.tso = TsoCommandProcessor(self.state, user)
        self.mode = "TSO_READY"
        msg = f"USER EXISTS-LOGIN COMPLETE FOR {user}"
        if note:
            msg = note + "\n\n" + msg
        pend = self._pending_messages_text()
        if pend:
            self._send_screen(self.tso_output_screen(
                msg + "\n\n*** YOU HAVE NEW MESSAGES ***\n" + pend))
        else:
            self._send_screen(self.tso_ready_screen(msg))

    def _enter_oedit(self, cmd: str) -> None:
        """OEDIT pathname - open a z/OS UNIX file in the ISPF 3270 full-screen
        editor, saving back to the OMVS filesystem (parity with the ASCII path)."""
        import shlex
        proc = self._ensure_tso()
        if not proc.has_omvs_segment():
            self._emit_tso_output("FSUM6003 user does not have an OMVS segment",
                                  base_colour=colors.RED, return_mode="TSO_READY")
            return
        try:
            argv = shlex.split(cmd)
        except ValueError:
            argv = cmd.split()
        path = argv[1].strip() if len(argv) > 1 else ""
        if not path:
            self._emit_tso_output("OEDIT: MISSING PATHNAME - usage: OEDIT pathname",
                                  base_colour=colors.RED, return_mode="TSO_READY")
            return
        from gibson.apps.omvs import OmvsEnvironment
        env = OmvsEnvironment(self.state)
        env.ensure_user_profile(self.userid)
        clean = path.strip().strip("'").strip('"')
        vp = env.resolve(f"/u/{self.userid.lower()}", clean)
        try:
            text = env.read_text(vp)
        except Exception:
            text = ""
        self.oedit_app = _Omvs3270Editor(
            self.state, self.userid, vp, text,
            save_callback=lambda new_text, target=vp, e=env: e.write_text(target, new_text))
        self._panel_return = "TSO_READY"
        self.mode = "OEDITAPP"
        self._send_screen(self.oedit_app.initial_screen())

    def _enter_ftp(self, cmd: str) -> None:
        """FTP <host> <port> - interactive FTP client as a TSO sub-mode, driving
        the shared TsoFtpClientApp.handle_command (parity with the ASCII loop)."""
        from gibson.apps.ftp_client import TsoFtpClientApp
        argv = cmd.split()
        host = argv[1] if len(argv) > 1 else "127.0.0.1"
        port = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else None
        self.ftp_app = TsoFtpClientApp(self.state, self.userid, host, port)
        self._ftp_stage = "USER"
        self._ftp_user = ""
        self.mode = "TSO_FTP"
        banner = self.ftp_app._banner()
        self._emit_tso_output(strip_ansi(banner), prompt=f"User ({host}):",
                              base_colour=colors.TURQUOISE, return_mode="TSO_FTP")

    def _handle_ftp_line(self, text: str) -> None:
        from gibson.apps.ftp_client import _FTP_QUIT
        val = text.strip()
        app = self.ftp_app
        if app is None:
            self.mode = "TSO_READY"
            self._send_screen(self.tso_ready_screen("READY"))
            return
        if self._ftp_stage == "USER":
            self._ftp_user = val.upper() or self.userid
            self._ftp_stage = "PASS"
            self._emit_tso_output("", prompt="Password:",
                                  base_colour=colors.TURQUOISE, return_mode="TSO_FTP",
                                  input_hidden=True)
            return
        if self._ftp_stage == "PASS":
            user = self._ftp_user
            self.state.racf.load(merge=True)
            if not self.state.racf.verify_password(user, val):
                self.state.note_failed_logon(user, self.addr[0], port=self.state.config.tn3270_port, service="FTP-CLIENT")
                self.ftp_app = None
                self._ftp_stage = None
                self._emit_tso_output("530 Login incorrect.",
                                      base_colour=colors.RED, return_mode="TSO_READY")
                return
            app.s.remote_user = user
            app.s.remote_prefix = user
            app.s.authed = True
            self._ftp_stage = "CMD"
            self._emit_tso_output(f"230 {user} logged in.", prompt="ftp>",
                                  base_colour=colors.TURQUOISE, return_mode="TSO_FTP")
            return
        # CMD stage
        resp = app.handle_command(val)
        if resp is _FTP_QUIT:
            self.ftp_app = None
            self._ftp_stage = None
            self._emit_tso_output("221 Quit", base_colour=colors.RED,
                                  return_mode="TSO_READY")
            return
        self._emit_tso_output(resp or "", prompt="ftp>",
                              base_colour=colors.TURQUOISE, return_mode="TSO_FTP")

    def _split_prompt(self, out: str, default: str = "telnet>") -> tuple:
        """Telnet output embeds its own trailing prompt ('telnet> ', 'login: ',
        'Password: ').  Peel it off so the body renders and the prompt drives the
        input field, rather than showing a doubled prompt."""
        s = strip_ansi(out or "").rstrip("\n").rstrip()
        lines = s.split("\n")
        last = lines[-1].strip() if lines else ""
        if last and (last.endswith(">") or last.endswith(":")) and len(last) <= 30:
            return "\n".join(lines[:-1]), last
        return s, default

    def _enter_telnet(self, cmd: str) -> None:
        """TELNET <host> <port> - interactive line-mode Telnet client as a TSO
        sub-mode over the shared TelnetSubsession (parity with the ASCII loop)."""
        from gibson.apps.uss_telnet_client import TelnetSubsession
        argv = cmd.split()
        host = argv[1] if len(argv) > 1 else ""
        port = argv[2] if len(argv) > 2 and argv[2].isdigit() else "23"
        self.telnet_app = TelnetSubsession(timeout=5)
        self.mode = "TSO_TELNET"
        out = self.telnet_app.banner()
        if host:
            out = out.rstrip() + "\n" + self.telnet_app.handle(f"open {host} {port}")
        body, prompt = self._split_prompt(out)
        self._emit_tso_output(body, prompt=prompt, base_colour=colors.TURQUOISE,
                              return_mode="TSO_TELNET")

    def _handle_telnet_line(self, text: str) -> None:
        app = self.telnet_app
        if app is None:
            self.mode = "TSO_READY"
            self._send_screen(self.tso_ready_screen("READY"))
            return
        out = app.handle(text.strip())
        if getattr(app, "done", False):
            self.telnet_app = None
            body, _ = self._split_prompt(out, default="")
            self._emit_tso_output(body or "TELNET SESSION CLOSED",
                                  base_colour=colors.RED, return_mode="TSO_READY")
            return
        body, prompt = self._split_prompt(out)
        self._emit_tso_output(body, prompt=prompt, base_colour=colors.TURQUOISE,
                              return_mode="TSO_TELNET")

    def _change_required(self, user: str) -> bool:
        """RACF/GACF.DB is the source of truth for the initial/expired password
        flag, so an ADDUSER'd user is forced through an initial change here and a
        stale SYS1.UADS can never trap or skip it."""
        try:
            rec = self.state.racf.get(user)
            return rec is not None and bool(getattr(rec, "password_change_required", False))
        except Exception:
            return False

    def _post_auth(self, user: str) -> None:
        """After a verified password (and MFA), force an initial/expired
        password change before reaching READY, matching the ASCII/NVT path."""
        if self._change_required(user):
            self.userid = user
            self._newpass = {"user": user, "first": None}
            self.mode = "TSO_NEWPASS"
            self._send_screen(self.tso_newpass_screen(
                "ICH70008I YOUR PASSWORD HAS EXPIRED OR IS INITIAL; "
                "A NEW PASSWORD IS REQUIRED"))
            return
        self._login_complete(user)

    def tso_newpass_screen(self, message: str = "", reenter: bool = False) -> ScreenBuffer:
        lines: List[str] = []
        if message:
            lines.extend([message, ""])
        prompt = "RE-ENTER NEW PASSWORD -" if reenter else "ENTER NEW PASSWORD -"
        lines.append(prompt)
        return self._simple_screen("", lines, (len(lines), len(prompt) + 1), input_field=True, input_hidden=True)

    def _handle_newpass_line(self, text: str) -> None:
        np = self._newpass or {"user": self.userid, "first": None}
        user = np.get("user") or self.userid
        val = text.strip()
        if not val:
            # empty entry - re-prompt at the current step
            self._send_screen(self.tso_newpass_screen(reenter=np.get("first") is not None))
            return
        if np.get("first") is None:
            np["first"] = val
            self._newpass = np
            self._send_screen(self.tso_newpass_screen(reenter=True))
            return
        first = np["first"]
        if val != first:
            self._newpass = {"user": user, "first": None}
            self.state.record_security_event(user, "PASSWORD CHANGE", "CONFIRMATION MISMATCH", result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_newpass_screen(
                "ICH70009I PASSWORD CHANGE FAILED - VALUES DID NOT MATCH"))
            return
        from gibson.core.security_freeze import verify_password_hash as _verify_hash
        try:
            ent = self.state.uads.get(user)
        except Exception:
            ent = None
        history = list(getattr(ent, "password_history", []) or [])
        ok, msg = self.state.password_policy.validate_new_password(user, first, history, _verify_hash)
        if not ok:
            self._newpass = {"user": user, "first": None}
            self.state.record_security_event(user, "PASSWORD CHANGE", msg, result="FAILURE", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_newpass_screen(msg))
            return
        self.state.racf.altuser(user, password=first)
        self.state.racf.save()
        new_rec = self.state.racf.get(user)
        try:
            self.state.uads.set_password(user, new_rec.password if new_rec else "", change_required=False)
            self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
        except Exception:
            pass
        self.state.record_security_event(user, "PASSWORD CHANGE", "INITIAL PASSWORD CHANGED", service="TN3270/TSO", addr=self.addr[0], terminal="3270")
        self._newpass = None
        self._login_complete(user, note="ICH70007I PASSWORD CHANGED SUCCESSFULLY")

    def _ensure_tso(self):
        if self.tso is None:
            from gibson.apps.tso import TsoCommandProcessor
            self.tso = TsoCommandProcessor(self.state, self.userid or "IBMUSER")
        return self.tso

    def _handle_tso_command(self, text: str) -> None:
        cmd = text.strip()
        if not cmd:
            self._send_screen(self.tso_ready_screen())
            return
        uc = cmd.upper()
        # record into the command-history ring (dedupe consecutive repeats)
        hist = getattr(self, "command_history", None)
        if hist is None:
            hist = self.command_history = []
        if not hist or hist[-1] != cmd:
            hist.append(cmd)
            if len(hist) > 100:
                del hist[:-100]
        self._hist_pos = len(hist)
        # HISTORY: list the last 50 commands (bash-style numbering)
        if uc == "HISTORY" or uc.startswith("HISTORY "):
            recent = hist[-50:]
            start = max(1, len(hist) - len(recent) + 1)
            body = "\n".join(f"{start + i:5}  {h}" for i, h in enumerate(recent)) or "No commands in history."
            self._emit_tso_output(body, base_colour=colors.TURQUOISE, return_mode="TSO_READY")
            return
        # interactive sub-systems that need a dedicated 3270 mode
        if uc == "OMVS" or uc.startswith("OMVS "):
            return self._enter_omvs()
        if uc == "CONSOLE" or uc.startswith("CONSOLE "):
            return self._enter_console()
        if uc in {"ISPF", "PDF", "ISPF/PDF"}:
            self.mode = "VTAM"
            return self.handle_vtam("L ISPF")
        _VTAM_APPS = {"SDSF": "L SDSF", "ISF": "L SDSF", "CICS": "L CICS", "DB2": "L DB2", "DSN": "L DSN"}
        if uc in _VTAM_APPS:
            self.mode = "VTAM"
            return self.handle_vtam(_VTAM_APPS[uc])
        # SDSF/ISF with a trailing sub-command must still reach the 3270-native
        # SDSF, never the ASCII SdsfApp (which would leak ANSI into the stream).
        if uc.startswith(("SDSF ", "ISF ")):
            self.mode = "VTAM"
            return self.handle_vtam("L SDSF")
        proc = self._ensure_tso()
        try:
            output = proc.run(cmd)
        except Exception as exc:
            output = f"IKJ56650I COMMAND FAILED - {exc}"
        # the processor signals interactive hand-offs with a sentinel
        if isinstance(output, str) and output.startswith("GIBSON-INTERACTIVE:"):
            target = output.split(":", 1)[1].strip().upper()
            sub = self._subsys_by_target.get(target)
            if sub is not None:
                return sub.enter(cmd)
            if target in {"ISPF", "EDIT", "CICS", "DB2"}:
                self.mode = "VTAM"
                return self.handle_vtam(f"L {target}" if target != "EDIT" else "L ISPF")
            output = f"{target} is not available from the EBCDIC 3270 session."
        self._emit_tso_output(output or "READY", base_colour=colors.RED,
                              return_mode="TSO_READY")

    def _enter_omvs(self, cmd: str = "") -> None:
        from gibson.apps.omvs import OmvsShellSession
        rec = self.state.racf.get(self.userid)
        mgr = getattr(self.state, "service_manager", None)
        if mgr is not None and not mgr.is_available("OMVS"):
            self._send_screen(self.tso_output_screen("BPXM010I OMVS NOT AVAILABLE."))
            return
        if not rec or not getattr(rec, "has_omvs", False):
            self.state.record_security_event(self.userid, "OMVS", "NO OMVS SEGMENT",
                                             result="FAILURE", service="TN3270/TSO",
                                             addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_output_screen("FSUM6003 user does not have an OMVS segment"))
            return
        self.omvs_shell = OmvsShellSession(self.state, self.userid, self._ensure_tso(), mode="OMVS3270")
        self.mode = "TSO_OMVS"
        banner = ("OMVS shell - z/OS UNIX System Services.  Type 'exit' to return to TSO.\n"
                  f"{self.omvs_shell.cwd} $ ")
        self._send_screen(self.tso_output_screen(banner, prompt=f"{self.omvs_shell.cwd} $", base_colour=colors.LIGHT_BLUE))

    def _enter_omvs_editor(self, prog: str, args: List[str]) -> None:
        """vi/view/ex/edit/oedit inside OMVS -> the 3270 full-screen editor,
        persisting to the z/OS UNIX filesystem and returning to the shell prompt.
        This is the EBCDIC counterpart of the ASCII path's _vi_interactive /
        _oedit_interactive (which execute() only stubs)."""
        shell = self.omvs_shell
        prompt = shell.shell_prompt() if shell is not None else "$"
        files = [a for a in args if not a.startswith("-")]
        if not files:
            self._emit_tso_output(f"{prog}: missing filename", prompt=prompt,
                                  base_colour=colors.LIGHT_BLUE, return_mode="TSO_OMVS")
            return
        env = shell.env
        vp = env.resolve(shell.cwd, files[0].strip().strip("'").strip('"'))
        try:
            body = env.read_text(vp)
        except Exception:
            body = ""
        readonly = prog == "view" or "-R" in args or "-r" in args
        self.oedit_app = _Omvs3270Editor(
            self.state, self.userid, vp, body,
            save_callback=lambda new_text, target=vp, e=env: e.write_text(target, new_text),
            readonly=readonly)
        self._panel_return = "TSO_OMVS"
        self.mode = "OEDITAPP"
        self._send_screen(self.oedit_app.initial_screen())

    def _enter_omvs_repl(self, *, banner: str, prompt, step) -> None:
        """Generic interactive OMVS program driven turn-by-turn (the EBCDIC
        counterpart of the ASCII reader/writer loop).  `prompt()` returns the
        current prompt; `step(line)` returns output text, or None to exit back
        to the shell.  Used for msfconsole (and, once extracted, lynx / rss)."""
        self._omvs_repl_prompt = prompt
        self._omvs_repl_step = step
        self._emit_tso_output(strip_ansi(banner or ""), prompt=prompt(),
                              base_colour=colors.LIGHT_BLUE, return_mode="TSO_OMVS_REPL")

    def _handle_omvs_repl_line(self, text: str) -> None:
        step = self._omvs_repl_step
        try:
            out = step(text.rstrip()) if step is not None else None
        except Exception as exc:  # noqa: BLE001
            out = f"{type(exc).__name__}: {exc}"
        if out is None:                      # program exited -> OMVS shell prompt
            self._omvs_repl_prompt = self._omvs_repl_step = None
            prompt = self.omvs_shell.shell_prompt() if self.omvs_shell else "$"
            self._emit_tso_output("", prompt=prompt, base_colour=colors.LIGHT_BLUE,
                                  return_mode="TSO_OMVS")
            return
        self._emit_tso_output(strip_ansi(out or ""), prompt=self._omvs_repl_prompt(),
                              base_colour=colors.LIGHT_BLUE, return_mode="TSO_OMVS_REPL")

    def _enter_omvs_msf(self, args: List[str]) -> None:
        """msfconsole / msf6 inside OMVS -> interactive sub-mode (parity with the
        ASCII run_msfconsole_interactive), sharing the MsfConsoleSim engine."""
        from gibson.apps.msfconsole_sim import MsfConsoleSim
        sim = MsfConsoleSim(self.state, env=self.omvs_shell.env, cwd=self.omvs_shell.cwd)
        if args and args[0] == "-x" and len(args) > 1:    # one-shot, no sub-mode
            out = sim.execute(" ".join(args[1:]))
            self._emit_tso_output(strip_ansi(out or ""),
                                  prompt=self.omvs_shell.shell_prompt(),
                                  base_colour=colors.LIGHT_BLUE, return_mode="TSO_OMVS")
            return

        def step(line: str):
            t = line.strip()
            if not t:
                return ""
            out = sim.one(t)
            return None if out == "__EXIT__" else out

        self._enter_omvs_repl(banner=sim.banner(), prompt=sim.prompt, step=step)

    def _enter_omvs_rss(self, args: List[str]) -> None:
        """cti-rss / rss inside OMVS -> interactive 3270 feed-reader sub-mode,
        sharing the CtiRssSession command grammar with run_cti_rss_interactive."""
        from gibson.apps.cti_rss import CtiRssSession
        sess = CtiRssSession(self.state, self.userid)
        self._enter_omvs_repl(banner=sess.banner() + sess.preamble(),
                              prompt=sess.prompt, step=sess.step)

    def _enter_omvs_lynx(self, args: List[str]) -> None:
        """lynx URL inside OMVS -> interactive 3270 browser sub-mode, sharing the
        LynxSession command grammar with the ASCII run_lynx_interactive path."""
        from gibson.apps.omvs_lynx import LynxSession
        sess = LynxSession(args, state=self.state, userid=self.userid)
        self._enter_omvs_repl(banner=sess.start(), prompt=sess.prompt, step=sess.handle)

    def _handle_omvs_line(self, text: str) -> None:
        line = text.rstrip()
        argv = line.strip().split()
        if argv and argv[0].lower() in {"vi", "view", "ex", "edit", "oedit"}:
            return self._enter_omvs_editor(argv[0].lower(), argv[1:])
        if argv and argv[0].lower() in {"msfconsole", "msfconsole-sim", "msf6"}:
            return self._enter_omvs_msf(argv[1:])
        if (argv and argv[0].lower() == "lynx" and len(argv) >= 2
                and not argv[1].startswith("-")):     # `lynx URL` -> interactive
            return self._enter_omvs_lynx(argv[1:])    # (-dump/-links/help stay one-shot)
        if argv and argv[0].lower() in {"cti-rss", "rss"}:
            return self._enter_omvs_rss(argv[1:])
        try:
            out = self.omvs_shell.execute(line)
        except Exception as exc:
            out = f"FSUM7351 {exc}"
        if out is None:        # exit / logout
            self.omvs_shell = None
            self.mode = "TSO_READY"
            self._send_screen(self.tso_ready_screen("FSUM5006 OMVS SESSION ENDED"))
            return
        prompt = self.omvs_shell.shell_prompt()
        if out == "__CLEAR__":
            self._send_screen(self.tso_output_screen("", prompt=prompt))
            return
        from gibson.render.ansi3270 import strip_ansi
        clean = strip_ansi(out or "")
        # If the program is asking for a password, render the next command field
        # non-display so the typed password is never shown on the 3270.
        want_hidden = _omvs_wants_password(clean)
        self._emit_tso_output(clean, prompt=prompt,
                              base_colour=colors.LIGHT_BLUE,
                              return_mode="TSO_OMVS", input_hidden=want_hidden)

    def _enter_console(self, cmd: str = "") -> None:
        from gibson.apps.master_console import MasterConsoleController
        if not self._ensure_tso().is_special():
            self.state.record_security_event(self.userid, "CONSOLE", "NOT AUTHORIZED",
                                             result="FAILURE", service="TN3270/TSO",
                                             addr=self.addr[0], terminal="3270")
            self._send_screen(self.tso_output_screen("IEE345I CONSOLE AUTHORITY INSUFFICIENT - ACCESS DENIED"))
            return
        self.console_ctl = MasterConsoleController(self.state, self.userid)
        self.mode = "TSO_CONSOLE"
        self._send_screen(self.tso_output_screen(
            "IEE612I CN=TSO CONSOLE ACTIVATED.  Enter MVS commands; END to exit.",
            prompt="CONSOLE ==>", base_colour=colors.GREEN))

    def _handle_console_line(self, text: str) -> None:
        cmd = text.strip()
        if cmd.upper() in {"END", "EXIT", "QUIT", "K E", "=X"}:
            self.console_ctl = None
            self.mode = "TSO_READY"
            self._send_screen(self.tso_ready_screen("IEE600I TSO CONSOLE VIEW ENDED"))
            return
        try:
            self.state.audit.record(self.userid or "UNKNOWN", cmd, "ENTER", "CONSOLE")
        except Exception:
            pass
        try:
            result = self.console_ctl.execute(cmd)
            out = getattr(result, "text", str(result))
        except Exception as exc:
            out = f"IEE305I COMMAND FAILED - {exc}"
        self._emit_tso_output(out, prompt="CONSOLE ==>",
                              base_colour=colors.GREEN,
                              return_mode="TSO_CONSOLE")

    def _run_indfile_cut(self, command: str) -> None:
        """Drive a real IND$FILE CUT-mode transfer over the live 3270 session.

        This is the path that interoperates with c3270/x3270 File->Transfer
        (the Transfer() action types ``IND$FILE GET|PUT ...`` + ENTER, then
        reacts to the host's CUT frames).  Binary mode is used on the wire;
        choose Binary in the emulator's transfer dialog.
        """
        from gibson.core.indfile_options import parse_options
        from gibson.core.transfers import get_transfer_manager
        from gibson.net.indfile.ft_cut_host import CutHost, SocketChannel, TransferError
        from gibson.net.indfile.ft_cut_layout import DEFAULT_LAYOUT
        from gibson.net.indfile import ft_cut_frames as F

        opts = parse_options(command)
        dsn = (opts.host_file or "").strip()
        userid = self.userid or "IBMUSER"
        meta = {"MODE": opts.mode, "CR": opts.cr, "EXIST": opts.exist,
                "RECFM": opts.recfm, "LRECL": str(opts.lrecl),
                "BLKSIZE": str(opts.blksize)}
        mgr = get_transfer_manager(self.state)
        channel = SocketChannel(DEFAULT_LAYOUT, send_bytes=self.send,
                                recv_packet=self.recv_packet)
        host = CutHost(channel, DEFAULT_LAYOUT)

        try:
            if not dsn:
                raise TransferError("missing host dataset name")
            if opts.direction == "GET":
                _name, data = mgr.indfile_get(userid, dsn, note="CUT-3270", options=meta)
                host.get(bytes(data))
                msg = (f"IND$FILE004I TRANSFER COMPLETE DIRECTION(GET) "
                       f"DATASET({dsn.upper()}) BYTES({len(data)})")
            else:
                data = host.put()
                info = mgr.indfile_put(userid, dsn, bytes(data), note="CUT-3270", options=meta)
                msg = (f"IND$FILE004I TRANSFER COMPLETE DIRECTION(PUT) "
                       f"DATASET({info.get('target', dsn).upper()}) BYTES({len(data)})")
        except TransferError as exc:
            # best-effort abort so the emulator doesn't hang waiting for us
            try:
                channel.exchange(F.build_abort(
                    DEFAULT_LAYOUT, DEFAULT_LAYOUT.sc_abort_file,
                    str(exc).encode("cp037", "replace")))
            except Exception:
                pass
            msg = f"IND$FILE013E TRANSFER FAILED - {exc}"
        except ClientDisconnected:
            raise
        except Exception as exc:  # dataset/security errors from the manager
            msg = f"IND$FILE013E TRANSFER FAILED - {exc}"
        self._send_screen(self.tso_ready_screen(msg))

    def handle_cics(self, aid: int, text: str) -> None:
        if aid == AID_CLEAR:
            self.send(bytes([0xF5, 0xF1, IAC, EOR]))
            return
        if aid == AID_PF3:
            self.send(bytes([0xF5, 0xF1, IAC, EOR]))
            return
        if not text.strip():
            self._send_screen(self.cics_blank_screen())
            return
        out = self.cics.execute(text.strip())
        self._send_screen(self.cics_text_screen(out))

    def _dispatch_panel_app(self, packet, app, return_mode: str = "VTAM") -> bool:
        """Drive one Phase-0 PanelSession from an inbound packet.

        Returns True when the session ended (caller clears its handle); on exit
        we return to return_mode (VTAM by default, or TSO READY for apps such as
        OEDIT that are launched from the TSO command line).
        """
        from gibson.render.panels import panel_input_from_event
        from gibson.net.datastream3270 import parse_3270_input_frame
        event = parse_3270_input_frame(packet, screen_registry=self.current_registry)
        pi = panel_input_from_event(event)
        # PA2 = Reshow: redisplay the current panel verbatim (discard pending
        # input), consistently for every panel subsystem.
        if pi.key == "PA2" and self.current_screen is not None:
            self._send_screen(self.current_screen)
            return False
        screen = app.handle(pi) if app is not None else None
        if screen is None:
            if return_mode == "TSO_OMVS" and self.omvs_shell is not None:
                # editor launched from inside OMVS -> back to the shell prompt
                self._emit_tso_output("", prompt=self.omvs_shell.shell_prompt(),
                                      base_colour=colors.LIGHT_BLUE, return_mode="TSO_OMVS")
            elif return_mode in ("TSO_READY", "TSO_OMVS"):
                self.mode = "TSO_READY"
                self._send_screen(self.tso_ready_screen("READY"))
            else:
                self.mode = "VTAM"
                self._send_screen(self.vtam_screen())
            return True
        self._send_screen(screen)
        return False

    def _maybe_global_jump(self, packet) -> bool:
        """Cross-app ISPF-style ``=`` jump from SDSF/CICS/DB2/TSO panels.

        ISPF handles its own ``=`` jumps, so this is only invoked for the other
        panel subsystems.  Returns True if the jump was handled (a screen was
        sent and the active app/mode switched); False to let the app proceed.
        """
        from gibson.render.panels import panel_input_from_event
        from gibson.net.datastream3270 import parse_3270_input_frame
        try:
            event = parse_3270_input_frame(packet, screen_registry=self.current_registry)
            pi = panel_input_from_event(event)
        except Exception:
            return False
        if pi.key not in ("ENTER", ""):
            return False
        raw = (pi.stripped("COMMAND") or pi.stripped("CMD")
               or pi.stripped("OPTION") or pi.stripped("CMDLINE") or "").strip()
        if not raw.startswith("="):
            return False
        target = raw[1:].strip().upper()
        return self._do_global_jump(target)

    def _do_global_jump(self, target: str) -> bool:
        # only act on recognised jump targets; otherwise let the app handle it
        if not (target == "" or target == "X" or target in ("S", "SDSF")
                or (target[:1].isdigit())):
            return False
        active = (self.tso_app or self.cics_app or self.db2_app or self.sdsf_app)
        userid = getattr(active, "userid", "") or "IBMUSER"
        if target in ("", "X"):
            self.mode = "VTAM"
            self._send_screen(self.vtam_screen())
            return True
        if target in ("S", "SDSF"):
            from gibson.apps.sdsf3270 import Sdsf3270Session
            self.sdsf_app = Sdsf3270Session(self.state, peer_addr=self.addr[0], userid=userid)
            self.mode = "SDSFAPP"
            self._send_screen(self.sdsf_app.initial_screen())
            return True
        # ISPF option target (e.g. 3.4, 6, 0): launch ISPF and dispatch it
        from gibson.apps.ispf3270 import IspfSplitManager
        from gibson.render.panels import PanelInput
        self.ispf_app = IspfSplitManager(self.state, peer_addr=self.addr[0], userid=userid)
        self.ispf_app.initial_screen()
        screen = self.ispf_app.handle(PanelInput(aid=0, key="ENTER", fields={"OPTION": target}))
        self.mode = "ISPFAPP"
        self._send_screen(screen if screen is not None else self.ispf_app.initial_screen())
        return True

    def run(self, allow_nvt_fallback: bool = False) -> bool:
        """Negotiate TN3270 (server-initiated) and serve the 3270 session.

        Returns True if a formatted 3270 session ran.  When
        ``allow_nvt_fallback`` is set and the peer does not complete a classic
        TN3270 handshake (e.g. netcat, plain telnet), returns False instead of
        disconnecting so the caller can run the ASCII/NVT path; any ASCII bytes
        the peer already sent are available in ``self.pending_ascii``.
        """
        try:
            self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.negotiate()
        if not self._wait_for_initial_negotiation():
            return False
        self.serve()
        return True

    def serve(self) -> None:
        self._send_screen(self.vtam_screen())
        while True:
            packet = self.recv_packet()
            if not packet:
                return
            aid, entries = self._parse_packet(packet)
            text = self._text_from_entries(entries)
            if self.mode == "TSOAPP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, self.tso_app):
                    self.tso_app = None
            elif self.mode == "CICSAPP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, self.cics_app):
                    self.cics_app = None
            elif self.mode == "DB2APP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, self.db2_app):
                    self.db2_app = None
            elif self.mode == "SDSFAPP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, self.sdsf_app):
                    self.sdsf_app = None
            elif self.mode == "ISPFAPP":
                if self._dispatch_panel_app(packet, self.ispf_app):
                    self.ispf_app = None
            elif self.mode == "IMSAPP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, getattr(self, "ims_app", None)):
                    self.ims_app = None
            elif self.mode == "TPFAPP":
                if self._maybe_global_jump(packet):
                    continue
                if self._dispatch_panel_app(packet, getattr(self, "tpf_app", None)):
                    self.tpf_app = None
            elif self.mode in self._subsys_by_mode and self._subsys_by_mode[self.mode].panel:
                sub = self._subsys_by_mode[self.mode]
                if self._dispatch_panel_app(packet, getattr(self, sub.app_attr),
                                            return_mode=getattr(self, "_panel_return", "TSO_READY")):
                    setattr(self, sub.app_attr, None)
            elif self.mode == "VTAM":
                self.handle_vtam(text)
            elif self.mode.startswith("TSO"):
                # PF12/PF24 = RETRIEVE: recall the previous command into the
                # READY command field (the 3270 equivalent of line-mode F12/Up).
                # PF24 (AID 0x4C, Shift+F12 on most x3270/c3270 keymaps) is the
                # conventional secondary RETRIEVE binding and walks the same
                # history. The recalled field is sent with MDT set so a bare
                # Enter re-submits it.
                if aid in (AID_PF12, AID_PF24) and self.mode == "TSO_READY":
                    hist = getattr(self, "command_history", None) or []
                    pos = getattr(self, "_hist_pos", len(hist))
                    if hist and pos > 0:
                        pos -= 1
                        self._hist_pos = pos
                        self._send_screen(
                            self.tso_ready_screen(cmd_value=hist[pos], cmd_modified=True))
                    else:
                        self._send_screen(self.tso_ready_screen())
                    continue
                self.handle_tso(text)
            elif self.mode == "ZVM":
                if self.zvm is None:
                    self.zvm = ZvmSession(self.state, peer_addr=self.addr[0])
                screen = self.zvm.handle(aid, text)
                if screen is None:
                    self.mode = "VTAM"
                    self.zvm = None
                    self._send_screen(self.vtam_screen())
                else:
                    self._send_screen(screen)
            else:
                self.handle_cics(aid, text)


class _Handler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.tn3270_port, service="TN3270")
        except Exception:
            pass
        try:
            Tn3270Session(self.state, self.request, self.client_address).run()
        except ClientDisconnected:
            return
        except Exception as exc:
            if is_expected_disconnect(exc):
                return
            if self.state.issue_log is not None:
                self.state.issue_log.record_traceback("TN3270", self.client_address, exc)
            return


class ThreadedTn3270Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_tn3270(state: GibsonState) -> ThreadedTn3270Server:
    _Handler.state = state
    server = ThreadedTn3270Server((state.config.host, state.config.tn3270_port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonTN3270").start()
    return server
