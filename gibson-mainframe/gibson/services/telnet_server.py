from __future__ import annotations

import os
import select
import socketserver
import subprocess
import shlex
import threading
import time
from typing import Optional

from gibson.apps.autocomplete import TsoAutocomplete
from gibson.apps.cics import CicsSimulator
from gibson.apps.db2_sim import Db2TerminalSession
from gibson.apps.zvm import ZvmSession
from gibson.apps.master_console import MasterConsoleController
from gibson.apps.editor import InteractiveEditor
from gibson.apps.tso_line_editor import TsoLineEditorSession
from gibson.apps.ispf import IspfApp
from gibson.apps.omvs import OmvsShellSession, OmvsEnvironment
from gibson.apps.sdsf import SdsfApp
from gibson.apps.ftp_client import TsoFtpClientApp
from gibson.apps.uss_telnet_client import TelnetSubsession
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.core.passticket import get_passticket_service
from gibson.render import colors
from gibson.render.input import InputResult, SocketInputDriver
from gibson.net.vtam_frontend import coloured_ascii_vtam_screen, negotiate_tn3270_or_ascii
from gibson.services.tn3270_server import Tn3270Session, ClientDisconnected as Tn3270ClientDisconnected
from gibson.core.terminal_compat import detect_terminal_profile, normalize_crlf, compact_vtam_screen
from gibson.core.security_mode import is_secure_mode
from gibson.core import v26_features
from gibson.net.tls import wrap_server_socket


class ClientDisconnected(Exception):
    """Connection dropped while servicing an interactive terminal session."""


def _send(conn, text: str) -> None:
    try:
        conn.sendall(text.encode("utf-8", errors="ignore"))
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        raise ClientDisconnected() from exc


def _colourize_vtam_screen(text: str) -> str:
    """Apply an IBM-inspired ANSI palette to the VTAM welcome screen."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        upper = stripped.upper()
        colour = colors.GREEN
        if 'GIBSON PRODUCTION LPAR' in upper:
            colour = colors.LIGHT_BLUE
        elif ('RESTRICTED INFORMATION' in upper or 'MONITORED' in upper or 'UNAUTHORIZED USE' in upper or 'CONSENT TO MONITORING' in upper):
            colour = colors.RED
        elif set(stripped) <= {'*'}:
            colour = colors.LIGHT_BLUE
        elif 'LU NAME:' in upper or 'SENSE CODE:' in upper or 'PORT:' in upper or 'IP ADDRESS:' in upper or 'GTSOV' in upper or 'GBV' in upper or 'GICS' in upper:
            colour = colors.GREEN
        out.append(f"{colour}{line}{colors.RESET}")
    return '\n'.join(out)


class _VtamBannerPulse:
    """Animate the VTAM hostname banner as a breathing light-blue<->dark-blue glow.

    On by default.  Only used on the interactive coloured ANSI logon screen.
    It repaints just the banner rows on a timer using cursor save/restore
    (DECSC/DECRC) so the logon input line is never moved, cycling through real
    blue shades (never to black, so the hostname never disappears).  It waits a
    short grace period before the first frame, so automated clients that submit
    a logon type immediately never see a single animation byte; and it stops the
    instant login input is accepted.
    """

    # Breathing ramp: pale light-blue (bloom peak) -> deep dark-blue and back,
    # via the xterm-256 blue range.  The darkest step is still clearly blue, so
    # the hostname never blinks out to black.
    _RAMP = (153, 117, 111, 75, 39, 33, 27, 21, 20, 19, 20, 21, 27, 33, 39, 75, 111, 117)
    _FRAMES = tuple(f"\x1b[1m\x1b[38;5;{n}m" for n in _RAMP)

    def __init__(self, session, rows, interval: float = 0.13, startup_delay: float = 0.45):
        self.session = session
        self.rows = rows                # list[(screen_row_1based, text)]
        self.interval = interval
        self.startup_delay = startup_delay
        self._stop = threading.Event()
        self._thread = None
        self._animated = False          # True once at least one frame was painted

    @classmethod
    def enabled(cls) -> bool:
        # On by default; GIBSON_HOSTNAME_PULSE=off/0/false/no disables it.
        val = (os.environ.get("GIBSON_HOSTNAME_PULSE", "on") or "on").strip().lower()
        return val not in {"0", "off", "false", "no", "none"}

    @classmethod
    def for_session(cls, session):
        """Build a pulse for the model the coloured logon screen just rendered."""
        if not cls.enabled():
            return None
        try:
            from gibson.screens.vtam_model import VtamScreenModel
            from gibson.render.vtam_renderer import is_banner_line, banner_fill, solidify_banner
            model = VtamScreenModel.from_addr(session.addr, service_port=session.state.config.port, system_name=session.state.get_system_hostname())
            glyph = banner_fill()
            rows = [(i + 1, solidify_banner(line, glyph)) for i, line in enumerate(model.full_lines()) if is_banner_line(line)]
        except Exception:
            return None
        return cls(session, rows) if rows else None

    def start(self) -> None:
        if not self.rows:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="vtam-banner-pulse")
        self._thread.start()

    def _frame(self, colour: str) -> str:
        body = "".join(f"\x1b[{row};1H{colour}{text}{colors.RESET}" for row, text in self.rows)
        return "\x1b7" + body + "\x1b8"   # DECSC ... DECRC (save/restore cursor)

    def _run(self) -> None:
        # Grace period: if input arrives first, no animation byte is ever sent.
        if self._stop.wait(self.startup_delay):
            return
        i = 0
        while not self._stop.is_set():
            try:
                self.session._raw_send(self._frame(self._FRAMES[i % len(self._FRAMES)]))
                self._animated = True
            except Exception:
                return
            i += 1
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=0.5)
        # Only repaint to the steady light-blue state if we actually animated;
        # a client that submitted within the grace period sees zero frames.
        if not self._animated:
            return
        try:
            self.session._raw_send(self._frame(colors.BOLD + colors.BRIGHT_BLUE))
        except Exception:
            pass


class GibsonTelnetSession:
    """Interactive VTAM/TSO/CICS/ISPF session wired to shared GibsonState."""

    def __init__(self, state: GibsonState, conn, addr):
        self.state = state
        self.conn = conn
        self.addr = addr
        self.terminal_profile = detect_terminal_profile(addr)
        self._write_lock = threading.RLock()
        self.input = SocketInputDriver(conn, echo=self.terminal_profile.echo_input, write_lock=self._write_lock)
        self.userid: Optional[str] = None
        self.processor: Optional[TsoCommandProcessor] = None
        self.autocomplete = TsoAutocomplete(state)
        self.running = True
        self._ansi_probe_complete = False
        self.command_history: list = []   # SHIFT+UP / UP recalls previous commands

    def send(self, text: str) -> None:
        if getattr(self, "terminal_profile", None) is not None and self.terminal_profile.crlf:
            text = normalize_crlf(text)
        with self._write_lock:
            _send(self.conn, text)

    def _raw_send(self, text: str) -> None:
        """Send raw bytes (no CRLF normalisation) under the shared write lock.

        Used by the animated banner pulse, whose ANSI cursor-positioning frames
        must not be reflowed and must not interleave with input echo."""
        with self._write_lock:
            _send(self.conn, text)

    def read(self, prompt: str = "", hidden: bool = False) -> InputResult:
        return self.input.read_line(prompt, hidden=hidden)

    @staticmethod
    def _password_mask_char() -> str:
        """Mask glyph for password entry (GIBSON_PASSWORD_MASK; default '*')."""
        ch = (os.environ.get("GIBSON_PASSWORD_MASK", "*") or "*").strip()
        return (ch[:1] or "*")

    def _send_iac(self, data: bytes) -> None:
        with self._write_lock:
            try:
                self.conn.sendall(data)
            except Exception:
                pass

    def read_password(self, prompt: str = "") -> InputResult:
        """Read a password, echoing a RED mask glyph (* or #) per character.

        The server always takes over echo for the duration of password entry by
        sending TELNET IAC WILL ECHO.  This suppresses local echo on c3270 /
        x3270 (NVT line mode), raw telnet, nc and the web terminal alike, so the
        real keystrokes never appear and the server is the sole echoer -- it
        prints the mask glyph in red.  WONT ECHO restores the prior echo model.
        The client's DO/DONT reply is discarded by the input reader's IAC
        handler, so it cannot corrupt the password.
        """
        if prompt:
            self.send(prompt)
        mask_char = self._password_mask_char()
        prev_echo = self.input.echo
        self._send_iac(bytes([0xFF, 0xFB, 0x01]))   # IAC WILL ECHO -> client stops local echo
        self.input.echo = True
        self.send(colors.RED)                        # mask glyphs in red
        try:
            return self.input.read_line("", hidden=True, mask=True, mask_char=mask_char)
        finally:
            self.send(colors.RESET)
            self.input.echo = prev_echo
            self._send_iac(bytes([0xFF, 0xFC, 0x01]))  # IAC WONT ECHO -> restore

    def enter_tso_colour(self) -> None:
        self.send(colors.RED)

    def leave_tso_colour(self) -> None:
        self.send(colors.RESET)

    def send_ready(self, leading_newline: bool = False, clear_screen: bool = False) -> None:
        """Render a clean TSO READY prompt.

        Full-screen applications such as ISPF and SDSF leave the cursor inside
        their last panel. Clear before READY so the prompt never overwrites
        panel text.
        """
        if clear_screen:
            self.send(colors.CLEAR)
        self.enter_tso_colour()
        self.send(("\n" if leading_newline and not clear_screen else "") + "READY\n")
    def run(self) -> None:
        try:
            # Port 2023 is dual-mode.  TN3270-capable clients such as
            # x3270/c3270 are routed to the true 3270 datastream loop; plain
            # telnet/netcat/nmap-sim.py clients remain on the historical
            # ANSI/NVT line-oriented path.
            if not self._ansi_probe_complete:
                self._ansi_probe_complete = True
                # Port 2023 is dual-mode.  Real TN3270 clients (c3270/x3270)
                # are *server-initiated*: they connect and wait for the host to
                # start option negotiation.  So we proactively send the TN3270
                # prologue and give the peer a brief window to complete a
                # classic 3270 handshake.  If it does, we serve formatted EBCDIC
                # 3270 (function keys arrive as AID bytes - no ANSI "ESC O R",
                # no "^I" tabs).  If it does not (netcat, plain telnet), we fall
                # back to the historical ASCII/NVT path, preserving any bytes the
                # peer already typed.  Set GIBSON_2023_PASSIVE=1 to skip the
                # active probe and behave as a pure ASCII port.
                if os.getenv("GIBSON_2023_PASSIVE", "") not in ("1", "true", "TRUE", "yes"):
                    try:
                        tn = Tn3270Session(self.state, self.conn, self.addr)
                        became_3270 = tn.run(allow_nvt_fallback=True)
                    except Tn3270ClientDisconnected:
                        return
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
                    if became_3270:
                        return
                    # Not a 3270 terminal: hand back any ASCII already typed.
                    if getattr(tn, "pending_ascii", None):
                        self.input._push_front(bytes(tn.pending_ascii))
                else:
                    try:
                        negotiation = negotiate_tn3270_or_ascii(self.conn)
                        if getattr(negotiation, "use_tn3270", False):
                            try:
                                Tn3270Session(self.state, self.conn, self.addr, initial_negotiation=negotiation).run()
                            except Tn3270ClientDisconnected:
                                pass
                            return
                        pushback = getattr(negotiation, "pushback", b"") or b""
                        if pushback:
                            self.input._push_front(pushback)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
            while self.running:
                if not self.login():
                    break
                self.command_loop()
        finally:
            if self.userid:
                self.state.sessions.remove(self.userid)

    def _display_login_screen(self) -> bool:
        """Mirror original gibson-new.py display_login_screen().

        Returns True when the full coloured ANSI screen (with the glowing
        hostname banner) was sent, False for the compact/monochrome path.
        """
        self.leave_tso_colour()
        if self.terminal_profile.is_guacamole or self.terminal_profile.cols < 120:
            self.send(colors.CLEAR + compact_vtam_screen(ip_address=self.addr[0], port=(self.addr[1] if len(self.addr) > 1 else ""), service_port=self.state.config.port, system_name=self.state.get_system_hostname()))
            return False
        self.send(colors.CLEAR + coloured_ascii_vtam_screen(addr=self.addr, service_port=self.state.config.port, system_name=self.state.get_system_hostname()))
        return True

    def _show_tso_and_welcome(self) -> None:
        """Mirror original show_tso_and_welcome() as closely as possible."""
        assert self.userid
        self.enter_tso_colour()
        self.send("USER EXISTS-LOGIN COMPLETE\n")

        logon_panel = self.state.templates.render("tso-logon.txt", self.userid)
        if not logon_panel and getattr(self.state.config, "logon_panel", False):
            logon_panel = v26_features.tsoe_logon_panel(self.userid)
        if logon_panel:
            self.leave_tso_colour()
            self.send(colors.CLEAR + colors.WHITE)
            logon_panel = logon_panel.replace("ACCT#", colors.RED + "ACCT#" + colors.WHITE)
            logon_panel = logon_panel.replace("xxxxxxx", colors.BLUE + self.userid + colors.WHITE)
            self.send(logon_panel)
            try:
                r, _, _ = select.select([self.conn], [], [], 0.2)
                if r:
                    self.input.read_line("", hidden=True)
            except Exception:
                pass
        else:
            self.enter_tso_colour()
            self.send("IKJ56455I USERID LOGGED ON TO GIBSON TSO\n")

        welcome = self.state.templates.render("welcome.txt", self.userid)
        if welcome:
            self.enter_tso_colour()
            lines = welcome.splitlines()
            self.send(colors.CLEAR)
            if lines:
                self.send(lines[0] + "\n")
            time.sleep(0.2)
            self.send(colors.CLEAR)
            remaining = "\n".join(lines[1:]) if len(lines) > 1 else ""
            if remaining:
                self.send(remaining + "\n\n")

        self.send_ready()
        self._display_pending_messages()


    def _tso_ptkt_applid(self) -> str:
        return f"TSO{self.state.network.hostname.upper()[:4]}" if self.state.config.strict_tso_ptkt else "TSO"

    def _check_tso_credential(self, username: str, secret: str) -> tuple[bool, str]:
        value = (secret or "").strip()
        applid = self._tso_ptkt_applid()
        if value.upper().startswith("PTKT(") and value.endswith(")"):
            ticket = value[5:-1].strip()
            result = get_passticket_service(self.state).validate(username, applid, ticket, consumer="TSO")
            if result.get("ok"):
                self.state.record_security_event(username, "LOGON", f"PASSTICKET APPL={applid}", service="TSO", addr=self.addr[0], terminal="VTAM")
                return True, "PASSTICKET"
            self.state.record_security_event(username, "LOGON", str(result.get("message", "PASSTICKET FAILURE")), result="FAILURE", service="TSO", addr=self.addr[0], terminal="VTAM")
            return False, str(result.get("message", "INVALID PASSTICKET"))
        if value.upper().startswith("PASSTICKET "):
            ticket = value.split(None, 1)[1].strip()
            result = get_passticket_service(self.state).validate(username, applid, ticket, consumer="TSO")
            if result.get("ok"):
                self.state.record_security_event(username, "LOGON", f"PASSTICKET APPL={applid}", service="TSO", addr=self.addr[0], terminal="VTAM")
                return True, "PASSTICKET"
            self.state.record_security_event(username, "LOGON", str(result.get("message", "PASSTICKET FAILURE")), result="FAILURE", service="TSO", addr=self.addr[0], terminal="VTAM")
            return False, str(result.get("message", "INVALID PASSTICKET"))
        if self.state.racf.verify_password(username, value):
            self.state.record_security_event(username, "LOGON", "PASSWORD", service="TSO", addr=self.addr[0], terminal="VTAM")
            return True, "PASSWORD"
        self.state.record_security_event(username, "LOGON", "PASSWORD FAILURE", result="FAILURE", service="TSO", addr=self.addr[0], terminal="VTAM")
        return False, "PASSWORD INCORRECT"

    def login(self) -> bool:
        """Legacy-compatible VTAM/TSO/CICS/DB2 logon loop.

        Preserve the original gibson-new.py transcript and failure behaviour so
        nmap-sim.py and the NSE enumeration scripts can distinguish existing
        users by the PASSWORD prompt and non-existing users by IKJ56420I.
        """
        while self.running:
            coloured = self._display_login_screen()
            pulse = _VtamBannerPulse.for_session(self) if coloured else None
            if pulse:
                pulse.start()
            try:
                logon_res = self.read("")
            finally:
                if pulse:
                    pulse.stop()
            if logon_res.key == "EOF":
                return False
            logon_type = logon_res.text.strip().upper()
            valid_types = {"L TSO", "LTSO", "L CICS", "LOGON APPLID(CICS)", "L DB2", "LDB2", "LOGON APPLID(TSO)", "L ZVM", "LZVM", "L IMS", "LIMS", "LOGON APPLID(IMS)", "LOGON APPLID(IMS1)", "L TPF", "LTPF", "L ZTPF", "LZTPF", "LOGON APPLID(TPF)"}
            if logon_type not in valid_types:
                self.send("\nInvalid logon type. Please try again.\n")
                time.sleep(2)
                continue

            if logon_type in {"L CICS", "LOGON APPLID(CICS)"}:
                self.leave_tso_colour()
                self.send(colors.CLEAR + "Starting external CICS session...\n")
                self.cics_loop("DEFAULT")
                return True

            if logon_type in {"L DB2", "LDB2"}:
                self.leave_tso_colour()
                self.send(colors.CLEAR)
                self.db2_loop("IBMUSER")
                return True

            if logon_type in {"L ZVM", "LZVM"}:
                self.leave_tso_colour()
                self.send(colors.CLEAR)
                self.zvm_loop()
                return True

            if logon_type in {"L IMS", "LIMS", "LOGON APPLID(IMS)", "LOGON APPLID(IMS1)", "L TPF", "LTPF", "L ZTPF", "LZTPF", "LOGON APPLID(TPF)"}:
                self.leave_tso_colour()
                self.send(colors.CLEAR)
                self.ims_loop()
                return True

            self.leave_tso_colour()
            self.send(colors.CLEAR)
            user_res = self.read("LOGON\n\nIKJ56700A ENTER USERID : ")
            if user_res.key == "EOF":
                return False
            username = user_res.text.strip().upper()
            if not username:
                time.sleep(0.2)
                continue

            mgr = getattr(self.state, "service_manager", None)
            if mgr is not None and not mgr.is_available("RACF"):
                self.send("IRR555I RACF SUBSYSTEM NOT ACTIVE\n")
                time.sleep(2)
                continue

            self.state.racf.load(merge=True)
            if not self.state.racf.exists(username):
                self.state.note_failed_logon(username, self.addr[0], port=self.state.config.port, service="VTAM/TSO")
                self.send(f"\nIKJ56420I USERID ({username}) NOT AUTHORIZED FOR TSO:- RE-ENTER -\n")
                time.sleep(2)
                continue
            user_rec = self.state.racf.get(username)
            if user_rec and user_rec.revoked:
                self.state.record_security_event(username, "LOGON", "USERID REVOKED", result="FAILURE", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                self.send(f"\nICH70001I USERID {username} IS REVOKED\nLOGON REJECTED BY RACF\n")
                time.sleep(2)
                continue

            # Password entry: echo a mask glyph (* or #) per character so the
            # user sees their keystrokes masked rather than hidden entirely.
            self.send(f"ENTER CURRENT PASSWORD FOR {username}-")
            pw_res = self.read_password("")
            self.send(colors.RED)
            if pw_res.key == "EOF":
                return False
            password = pw_res.text.strip()
            if not self.state.racf.verify_password(username, password):
                self.state.note_failed_logon(username, self.addr[0], port=self.state.config.port, service="VTAM/TSO")
                self.state.record_security_event(username, "LOGON", "PASSWORD FAILURE", result="FAILURE", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                self.send("\nPASSWORD INCORRECT\n")
                time.sleep(2)
                continue

            # v30.287-freeze: new RACF users created with an initial password
            # must change it before reaching READY/ISPF.  Policy validation is
            # driven by the simulated SETROPTS PASSWORD options and SYS1.UADS.
            try:
                rec_pc = self.state.racf.get(username)
                if rec_pc is not None and getattr(rec_pc, "password_change_required", False):
                    self.leave_tso_colour()
                    self.send("\nICH70008I YOUR PASSWORD HAS EXPIRED OR IS INITIAL; A NEW PASSWORD IS REQUIRED\n")
                    new1 = self.read_password("ENTER NEW PASSWORD - ").text.strip()
                    new2 = self.read_password("RE-ENTER NEW PASSWORD - ").text.strip()
                    self.enter_tso_colour()
                    if new1 != new2:
                        self.state.record_security_event(username, "PASSWORD CHANGE", "CONFIRMATION MISMATCH", result="FAILURE", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                        self.send("\nICH70009I PASSWORD CHANGE FAILED - VALUES DID NOT MATCH\n")
                        time.sleep(2)
                        continue
                    from gibson.core.security_freeze import verify_password_hash as _verify_hash
                    _hist = (getattr(rec_pc, 'password_history', None)
                             or getattr(self.state.uads.get(username), 'password_history', None) or [])
                    ok, msg = self.state.password_policy.validate_new_password(username, new1, list(_hist), _verify_hash)
                    if not ok:
                        self.state.record_security_event(username, "PASSWORD CHANGE", msg, result="FAILURE", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                        self.send("\n" + msg + "\n")
                        time.sleep(2)
                        continue
                    self.state.racf.altuser(username, password=new1)
                    self.state.racf.save()
                    new_rec = self.state.racf.get(username)
                    self.state.uads.set_password(username, new_rec.password if new_rec else "", change_required=False)
                    try:
                        self.state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(self.state.uads.list_lines()) + "\n")
                    except Exception:
                        pass
                    self.state.record_security_event(username, "PASSWORD CHANGE", "INITIAL PASSWORD CHANGED", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                    self.send("\nICH70007I PASSWORD CHANGED SUCCESSFULLY\n")
            except Exception:
                pass

            if self.state.mfa_required_for(username):
                self.leave_tso_colour()
                token_res = self.read("\nMFA TOKEN REQUIRED\nEnter MFA token (PIN+HHMM): ", hidden=True)
                self.enter_tso_colour()
                if token_res.key == "EOF":
                    return False
                if not self.state.validate_mfa_token(token_res.text):
                    self.state.note_failed_logon(username, self.addr[0], port=self.state.config.port, service="VTAM/TSO")
                    self.state.record_security_event(username, "MFA", "TOKEN FAILURE", result="FAILURE", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
                    self.send("\nMFA TOKEN INVALID\n")
                    time.sleep(2)
                    continue
                self.state.record_security_event(username, "MFA", "TOKEN SUCCESS", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")

            self.state.clear_failed_logon(username, self.addr[0], port=self.state.config.port)
            if username == "IBMUSER" and getattr(self.state.config, "security_mode", "vuln") == "secure":
                self.state.record_break_glass("IBMUSER", "TSO LOGON")
            if not self.state.dynamic_racf.has_access("APPL", "TSO", username, "READ", self.state.racf):
                self.send(f"\nIKJ56420I USERID ({username}) NOT AUTHORIZED FOR TSO:- RE-ENTER -\n")
                time.sleep(2)
                continue

            self.state.record_security_event(username, "LOGON", "PASSWORD", service="VTAM/TSO", addr=self.addr[0], terminal="VTAM")
            self.userid = username
            self.processor = TsoCommandProcessor(self.state, username)
            self.state.sessions.add(username, self.addr[0], notifier=lambda msg, self=self: self.send("\n" + msg + "\n"))
            self.state.racf.ensure_user_dir(self.state.config.files_root, username)
            self._show_tso_and_welcome()
            if getattr(self.state.config, "logon_panel", False):
                self.leave_tso_colour()
                self.ispf_loop()
                self.send_ready(clear_screen=True)
            return True

    def command_loop(self) -> None:
        assert self.userid and self.processor
        self.enter_tso_colour()
        while self.running and self.userid:
            res = self.input.read_line("", history=self.command_history)
            if res.key == "EOF":
                self.running = False
                return
            cmd = res.text.strip()
            if res.key == "TAB":
                completed, help_text = self.autocomplete.complete(cmd)
                self.enter_tso_colour()
                self.send(help_text)
                if completed and completed != cmd:
                    self.send(completed)
                continue
            # Fallback for clients/emulators that consume TAB locally.
            # Type ? for all commands, or LISTU? / SEND? for matching syntax.
            if cmd == "?" or cmd.endswith("?"):
                prefix = "" if cmd == "?" else cmd[:-1].strip()
                _completed, help_text = self.autocomplete.complete(prefix)
                self.enter_tso_colour()
                self.send(help_text)
                continue
            if not cmd:
                continue
            # record in the command-history ring (dedupe consecutive repeats)
            if not self.command_history or self.command_history[-1] != cmd:
                self.command_history.append(cmd)
                if len(self.command_history) > 100:
                    self.command_history = self.command_history[-100:]
            u = cmd.upper()
            try:
                self.state.audit.record(self.userid or "UNKNOWN", cmd, "ENTER", "TSO")
            except Exception:
                pass
            if u == "HISTORY" or u.startswith("HISTORY "):
                # show the last 50 commands (most recent last), bash-style numbering
                recent = self.command_history[-50:]
                start = max(1, len(self.command_history) - len(recent) + 1)
                self.enter_tso_colour()
                if not recent:
                    self.send("No commands in history.\n")
                else:
                    for i, h in enumerate(recent):
                        self.send(f"{start + i:5}  {h}\n")
                self.send_ready(leading_newline=True)
                continue
            if u in ("LOGOFF", "LOGOUT", "EXIT"):
                self.send("IKJ56400I LOGOFF IN PROGRESS\n")
                self.state.sessions.remove(self.userid)
                self.userid = None
                self.processor = None
                return
            if u in ("SDSF", "ISF") or u.startswith("SDSF ") or u.startswith("ISF "):
                parts = cmd.split(maxsplit=1)
                initial = parts[1].strip().upper() if len(parts) > 1 else "MENU"
                self.leave_tso_colour()
                self.sdsf_loop(initial)
                self.send_ready(clear_screen=True)
                continue
            if u in ("ISPF", "START"):
                self.leave_tso_colour()
                self.ispf_loop()
                self.send_ready(clear_screen=True)
                continue
            if u.startswith("FTP"):
                self.leave_tso_colour()
                parts = cmd.split()
                host = parts[1] if len(parts) >= 2 else "127.0.0.1"
                port = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else self.state.config.ftp_port
                self.ftp_loop(host, port)
                self.send_ready(leading_newline=True)
                continue
            if u.startswith("TELNET"):
                self.leave_tso_colour()
                parts = cmd.split()
                host = parts[1] if len(parts) >= 2 else ""
                port = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 23
                self.telnet_client_loop(host, port)
                self.send_ready(leading_newline=True)
                continue
            if u.startswith("OEDIT"):
                path, recfm, lrecl = self._parse_oedit_spec(cmd)
                if not path:
                    path = self.read("ENTER PATHNAME - ").text.strip()
                if path:
                    self.leave_tso_colour()
                    self.file_editor_loop(path, mode="EDIT", recfm=recfm, lrecl=lrecl)
                    self.send_ready(leading_newline=True)
                else:
                    self.send("OEDIT: MISSING PATHNAME\n")
                    self.send_ready()
                continue
            if u.startswith("EDIT"):
                dsname = self._parse_edit_dataset(cmd)
                if not dsname:
                    dsname = self.read("ENTER DATA SET NAME - ").text.strip()
                if dsname:
                    self.leave_tso_colour()
                    self.tso_line_editor_loop(dsname)
                    self.send_ready(leading_newline=True)
                else:
                    self.send("IKJ56700I MISSING DATA SET NAME\n")
                    self.send_ready()
                continue
            if u.startswith("CONSOLE"):
                self.leave_tso_colour()
                self.console_loop()
                self.send_ready(leading_newline=True)
                continue
            if u == "OMVS":
                if not self.processor.has_omvs_segment():
                    self.enter_tso_colour()
                    self.send("FSUM6003 user does not have an OMVS segment\n")
                    self.send_ready()
                    continue
                self.leave_tso_colour()
                self.omvs_loop()
                self.send_ready(leading_newline=True)
                continue
            if u in ("CICS", "L CICS"):
                if not self.processor.can_access_appl("CICS"):
                    self.enter_tso_colour()
                    self.send("ICH408I NOT AUTHORIZED TO APPLID CICS\n")
                    self.send_ready()
                    continue
                self.leave_tso_colour()
                self.cics_loop(self.userid)
                self.send_ready(leading_newline=True)
                continue
            if u in ("DB2", "L DB2"):
                if not self.processor.can_access_appl("DB2"):
                    self.enter_tso_colour()
                    self.send("ICH408I NOT AUTHORIZED TO APPLID DB2\n")
                    self.send_ready()
                    continue
                self.leave_tso_colour()
                self.db2_loop(self.userid)
                self.send_ready(leading_newline=True)
                continue

            output = self.processor.run(cmd)
            if output.startswith("GIBSON-INTERACTIVE:"):
                target = output.split(":", 1)[1].strip().upper()
                self.leave_tso_colour()
                if target == "EDIT":
                    dsname = self._parse_edit_dataset(cmd) or self.read("ENTER DATA SET NAME - ").text.strip()
                    if dsname:
                        self.tso_line_editor_loop(dsname)
                elif target == "OEDIT":
                    if not self.processor.has_omvs_segment():
                        self.send("FSUM6003 user does not have an OMVS segment\n")
                    else:
                        path, recfm, lrecl = self._parse_oedit_spec(cmd)
                        path = path or self.read("ENTER PATHNAME - ").text.strip()
                        if path:
                            self.file_editor_loop(path, mode="EDIT", recfm=recfm, lrecl=lrecl)
                elif target == "CONSOLE":
                    self.console_loop()
                elif target == "OMVS":
                    if not self.processor.has_omvs_segment():
                        self.send("FSUM6003 user does not have an OMVS segment\n")
                    else:
                        self.omvs_loop()
                elif target == "ISPF":
                    self.ispf_loop()
                elif target == "CICS":
                    if self.processor.can_access_appl("CICS"):
                        self.cics_loop(self.userid)
                    else:
                        self.send("ICH408I NOT AUTHORIZED TO APPLID CICS\n")
                elif target == "DB2":
                    if self.processor.can_access_appl("DB2"):
                        self.db2_loop(self.userid)
                    else:
                        self.send("ICH408I NOT AUTHORIZED TO APPLID DB2\n")
                elif target == "TELNET":
                    parts = cmd.split()
                    host = parts[1] if len(parts) >= 2 else ""
                    port = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 23
                    self.telnet_client_loop(host, port)
                self.send_ready(clear_screen=(target in {"ISPF", "SDSF"}))
                continue
            self.enter_tso_colour()
            self.send(output.rstrip("\n") + "\n")
            if not output.endswith("READY"):
                self.send_ready()

    def ispf_loop(self) -> None:
        assert self.userid and self.processor
        app = IspfApp(self.state, self.userid, self.processor.run)
        try:
            app.run(self.input, self.send, self.sdsf_loop)
        except Exception as exc:
            # Panel exceptions should not make the terminal appear to corrupt or
            # dump the user back to a local shell with the old full-screen panel
            # still visible.  Log the traceback for developers and present a
            # small recovery panel to the user.  Tests still exercise the panel
            # code directly, so this wrapper does not hide unit-test failures.
            try:
                if self.state.issue_log is not None:
                    self.state.issue_log.record_traceback("ISPF", self.addr, exc)
            except Exception:
                pass
            try:
                self.leave_tso_colour()
                self.send(colors.CLEAR + colors.RED + "GIBSON PANEL ERROR" + colors.RESET + "\n")
                self.send("A panel input error occurred and has been logged.\n")
                self.send("Press ENTER to return to TSO READY.\n")
                self.input.read_line("")
            except Exception:
                pass

    def sdsf_loop(self, initial: str = "MENU") -> None:
        assert self.userid
        app = SdsfApp(self.state, self.userid)
        current = (initial or "MENU").upper()
        if current in ("SDSF", "ISF"):
            current = "MENU"
        page = 0
        message = ""
        while True:
            self.send(app.render_main(page, message) if current == "MENU" else app.render_panel(current, page, message))
            message = ""
            res = self.input.read_line_at(4, 19)
            key = res.key or ""
            text = res.text.strip()
            upper = text.upper()

            if key == "F7" or upper in ("F7", "PF7"):
                page = max(0, page - 1)
                continue
            if key == "F8" or upper in ("F8", "PF8"):
                page += 1
                continue
            if key == "F3" or upper in ("F3", "PF3"):
                if current == "MENU":
                    return
                current = "MENU"; page = 0
                continue
            if key == "EOF":
                self.running = False
                return
            if not upper:
                continue
            if upper in ("X", "EXIT", "END"):
                if current == "MENU":
                    return
                current = "MENU"; page = 0
                continue

            if current == "MENU":
                if upper.isdigit():
                    chosen = app.find_menu_command_by_number(int(upper))
                    if chosen:
                        current = chosen; page = 0; continue
                    message = "ISF754I ROW NOT FOUND"; continue
                new_panel, msg = app.apply_sdsf_command(text)
                if new_panel:
                    current = new_panel; page = 0
                message = msg
                continue

            parts = upper.split()
            if len(parts) >= 2 and (parts[0] in ("S", "?", "P", "C", "A", "/") or parts[0].startswith("%")) and parts[1].isdigit():
                if current == "APF" and parts[0] == "/" and self.state.config.sdsf_apf_popup:
                    popup = "\n".join([
                        colors.CLEAR + colors.WHITE + "SDSF APF POP-UP" + colors.RESET,
                        "",
                        "Enter operator command:",
                        "",
                        colors.BLUE + "COMMAND ===> " + colors.RESET,
                        "",
                        colors.BLUE + "PF3 to cancel" + colors.RESET,
                    ])
                    self.send(popup + "\n")
                    entered = self.input.read_line_at(5, 13)
                    cmd_text = (entered.text or "").strip()
                    if (entered.key or "").upper() in ("F3", "PF3") or cmd_text.upper() in {"X", "EXIT", "END", ""}:
                        message = "ISF031I POP-UP CANCELLED"
                        continue
                    cmd_out = TsoCommandProcessor(self.state, self.userid).run(cmd_text)
                    self.send(app._message_screen(cmd_out))
                    while True:
                        back = self.input.read_line_at(4, 19)
                        bkey = back.key or back.text.strip().upper()
                        if bkey in ("F3", "PF3", "END", "EXIT", "X"):
                            break
                    message = "ISF031I COMMAND COMPLETE"
                    continue
                screen, msg = app.perform_action(current, parts[0], int(parts[1]))
                if screen:
                    self.send(screen)
                    while True:
                        row = 2 if "SDSF OUTPUT DISPLAY" in screen else 4
                        back = self.input.read_line_at(row, 19)
                        bkey = back.key or back.text.strip().upper()
                        if bkey in ("F3", "PF3", "END", "EXIT", "X"):
                            break
                        if bkey in ("F7", "PF7", "F8", "PF8", ""):
                            continue
                    message = msg
                else:
                    message = msg
                continue

            new_panel, msg = app.apply_sdsf_command(text)
            if new_panel:
                current = new_panel; page = 0
            message = msg

    def ftp_loop(self, host: str = "127.0.0.1", port: int | None = None) -> None:
        assert self.userid
        app = TsoFtpClientApp(self.state, self.userid, host, port)
        app.run(self.input, self.send)

    def telnet_client_loop(self, host: str = "", port: int | None = None) -> None:
        app = TelnetSubsession(timeout=5)
        self.send("\n" + app.banner())
        if host:
            self.send(app.handle("open " + host + " " + str(port or 23)))
        while self.running and not app.done:
            res = self.read("")
            if res.key == "EOF":
                self.running = False
                try:
                    app.close(silent=True)
                except Exception:
                    pass
                return
            self.send(app.handle(res.text.strip()))

    def _parse_edit_dataset(self, cmd: str) -> str:
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return ""
        return parts[1].strip().strip("'").strip('"')

    def _display_pending_messages(self) -> None:
        if not self.userid:
            return
        pending = self.state.racf.ensure_user_dir(self.state.config.files_root, self.userid) / "pending_messages.txt"
        if pending.exists():
            try:
                text = pending.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    self.send("\n*** You have new messages: ***\n" + text + "\n")
                pending.unlink(missing_ok=True)
            except Exception:
                pass

    def _parse_oedit_spec(self, cmd: str) -> tuple[str, str, int]:
        try:
            argv = shlex.split(cmd)
        except ValueError:
            return "", "VB", 255
        if not argv or argv[0].upper() != "OEDIT":
            return "", "VB", 255
        args = list(argv[1:])
        recfm, lrecl = "VB", 255
        if len(args) >= 2 and args[0] == "-r":
            try:
                lrecl = int(args[1])
            except ValueError:
                lrecl = 80
            recfm = "FB"
            args = args[2:]
        return (args[0] if args else "", recfm, lrecl)

    @staticmethod
    def _has_member_spec(dsname: str) -> bool:
        text = (dsname or "").strip()
        return "(" in text and text.endswith(")")

    def _pds_member_loop(self, pdsname: str) -> Optional[str]:
        assert self.userid
        pds_path = self.state.datasets.ds_path(self.userid, pdsname)
        pds_path.mkdir(parents=True, exist_ok=True)
        message = ""
        while True:
            members = sorted([p.name.upper() for p in pds_path.iterdir() if p.is_file() and not p.name.endswith('.meta')])
            lines = [colors.CLEAR, colors.BLUE + f"EDIT     ---- {pdsname[:60]:<60}" + colors.RESET, colors.BLUE + "Command ===>                                        Scroll ===> CSR" + colors.RESET]
            if message:
                lines.append(colors.RED + message[:79] + colors.RESET)
            else:
                lines.append(colors.TURQUOISE + "TYPE A MEMBER NAME OR A NUMBER. ENTER BLANK TO CREATE NEW; F3=EXIT" + colors.RESET)
            lines.append(colors.BLUE + "Name     Prompt       Size" + colors.RESET)
            for idx, name in enumerate(members[:14], 1):
                size = (pds_path / name).stat().st_size
                lines.append(colors.TURQUOISE + f"____  {idx:>3} {name:<8} {size:>8}" + colors.RESET)
            while len(lines) < 23:
                lines.append("")
            lines.append(colors.BLUE + "Enter member number/name ===> " + colors.RESET)
            self.send("\n".join(lines) + "\n")
            res = self.input.read_line()
            key = (res.key or "").upper()
            text = res.text.strip().upper()
            if key in {"EOF", "F3", "PF3"} or text in {"END", "EXIT", "X"}:
                return None
            if text.isdigit() and 1 <= int(text) <= len(members):
                return members[int(text)-1]
            if text:
                cleaned = ''.join(ch for ch in text if ch.isalnum() or ch in {'@', '#', '$'})[:8]
                if cleaned:
                    return cleaned
                message = "INVALID MEMBER NAME"
                continue
            new_member = self.read("NEW MEMBER NAME - ").text.strip().upper()
            cleaned = ''.join(ch for ch in new_member if ch.isalnum() or ch in {'@', '#', '$'})[:8]
            if cleaned:
                return cleaned
            message = "MEMBER NAME REQUIRED"

    def tso_line_editor_loop(self, dsname: str) -> None:
        assert self.userid and self.processor
        clean_name = self.processor.qualify_dataset_name(dsname)
        exists = False
        text = ""
        try:
            text = self.state.datasets.read(self.userid, clean_name)
            exists = True
        except PermissionError as exc:
            self.send(str(exc) + "\n")
            return
        except FileNotFoundError:
            exists = False
            text = ""

        def save_text(new_text: str, name: str = clean_name) -> None:
            nonlocal exists
            if not exists:
                if self._has_member_spec(name):
                    self.state.datasets.write(self.userid, name, new_text)
                else:
                    self.state.datasets.allocate(self.userid, name, org="PS")
                    self.state.datasets.write(self.userid, name, new_text)
                exists = True
            else:
                self.state.datasets.write(self.userid, name, new_text)

        def prompt_dataset_type() -> InputResult:
            return self.read("", hidden=False)

        TsoLineEditorSession(
            clean_name,
            text,
            exists=exists,
            save_callback=save_text,
            type_prompt_callback=prompt_dataset_type,
        ).run(self.input, self.send)

    def editor_loop(self, dsname: str, mode: str = "EDIT") -> None:
        assert self.userid and self.processor
        clean_name = self.processor.qualify_dataset_name(dsname)
        if not self._has_member_spec(clean_name):
            ds_path = self.state.datasets.ds_path(self.userid, clean_name)
            if ds_path.exists() and ds_path.is_dir():
                member = self._pds_member_loop(clean_name)
                if not member:
                    return
                clean_name = f"{clean_name}({member})"
        try:
            text = self.state.datasets.read(self.userid, clean_name)
        except PermissionError as exc:
            self.send(str(exc) + "\n")
            return
        except Exception:
            text = ""
            try:
                if self._has_member_spec(clean_name):
                    self.state.datasets.write(self.userid, clean_name, text)
                else:
                    self.state.datasets.allocate(self.userid, clean_name, org="PS")
            except PermissionError as exc:
                self.send(str(exc) + "\n")
                return

        def save_text(new_text: str, name: str = clean_name) -> None:
            self.state.datasets.write(self.userid, name, new_text)

        def submit_text(jcl_text: str) -> str:
            job = self.state.jes.submit(jcl_text, self.userid, runner=self.processor.run)
            return f"IKJ56250I JOB {job.jobname}({job.jobid}) SUBMITTED"

        InteractiveEditor(
            clean_name,
            text,
            mode=mode.upper(),
            recfm="FB",
            lrecl=80,
            save_callback=save_text,
            submitter=submit_text,
        ).run(self.input, self.send)

    def file_editor_loop(self, pathname: str, mode: str = "EDIT", recfm: str = "VB", lrecl: int = 255) -> None:
        assert self.userid and self.processor
        env = OmvsEnvironment(self.state)
        env.ensure_user_profile(self.userid)
        clean = pathname.strip().strip("'").strip('"')
        vp = env.resolve(f"/u/{self.userid.lower()}", clean)
        real = env.real_path(vp)
        real.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = env.read_text(vp)
        except Exception:
            text = ""
        InteractiveEditor(vp, text, mode=mode.upper(), recfm=recfm, lrecl=lrecl, save_callback=lambda new_text, target=vp: env.write_text(target, new_text)).run(self.input, self.send)

    def console_loop(self) -> None:
        assert self.userid and self.processor
        if not self.processor.is_special():
            self.enter_tso_colour()
            self.send("INSUFFICIENT ACCESS.\n")
            return
        controller = MasterConsoleController(self.state, self.userid)
        self.send(self._plain_console_snapshot(controller) + "\n")
        while True:
            res = self.read("CONSOLE ==> ")
            if res.key == "EOF":
                self.running = False
                return
            cmd = res.text.strip()
            u = (res.key or cmd).strip().upper()
            if not u:
                self.send(self._plain_console_snapshot(controller) + "\n")
                continue
            if u in {"QUIT", "EXIT", "END", "PF3", "F3", "PF12", "F12"}:
                self.send("IEE600I TSO CONSOLE VIEW ENDED\n")
                return
            try:
                self.state.audit.record(self.userid or "UNKNOWN", cmd, "ENTER", "CONSOLE")
            except Exception:
                pass
            result = controller.execute(cmd)
            if result.text:
                self.send(self._plain_console_snapshot(controller, result.text) + "\n")
            if result.action in {"quit", "shutdown"}:
                if result.action == "shutdown":
                    self.running = False
                return

    def _plain_console_snapshot(self, controller, latest: str = "") -> str:
        lines = [
            "GIBSON CONSOLE",
            "--------------",
        ]
        try:
            if latest:
                lines.extend(str(latest).strip().splitlines()[:12])
            else:
                lines.extend(controller._boot_complete_lines()[-8:])
        except Exception:
            if latest:
                lines.extend(str(latest).strip().splitlines()[:12])
        try:
            clog = getattr(self.state, "console_log", None)
            if clog and hasattr(clog, "tail"):
                tail = clog.tail(8)
                if tail:
                    lines.append("")
                    lines.append("RECENT OPERLOG")
                    lines.extend(str(x).strip()[:100] for x in tail)
        except Exception:
            pass
        lines.append("")
        lines.append("ENTER COMMAND OR END TO RETURN TO TSO")
        return "\n".join(lines)

    def omvs_loop(self) -> None:
        assert self.userid and self.processor
        mgr = getattr(self.state, "service_manager", None)
        if mgr is not None and not mgr.is_available("OMVS"):
            self.enter_tso_colour()
            self.send("BPXM010I OMVS NOT AVAILABLE.\n")
            return
        rec = self.state.racf.get(self.userid)
        if not rec or not rec.has_omvs:
            self.enter_tso_colour()
            self.send("ACCESS DENIED, INSUFFICIENT PRIVILEGES.\n")
            return

        shell = OmvsShellSession(self.state, self.userid, self.processor, mode="OMVS3270")
        shell.run_interactive(self.input, self.send)
        self.send(colors.RESET + "\nExiting OMVS shell. Returning to mainframe...\n")

    def cics_loop(self, userid: str) -> None:
        cics = CicsSimulator(self.state, userid)
        cics.run_terminal(self.input, self.send)

    def db2_loop(self, userid: str) -> None:
        Db2TerminalSession(self.state, userid).run(self.input, self.send)

    def zvm_loop(self) -> None:
        ZvmSession(self.state, peer_addr=self.addr[0]).run_terminal(self.input, self.send)

    def ims_loop(self) -> None:
        from gibson.apps.ims.ims_terminal import ImsTerminalSession
        ImsTerminalSession(self.state, peer_addr=self.addr[0]).run_terminal(self.input, self.send)

    def tpf_loop(self) -> None:
        from gibson.apps.ztpf.ztpf_terminal import ZtpfTerminalSession
        ZtpfTerminalSession(self.state, peer_addr=self.addr[0]).run_terminal(self.input, self.send)


class _Handler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            try:
                self.state.note_port_touch(self.client_address[0], self.state.config.port, service="VTAM/TSO")
            except Exception:
                pass
            GibsonTelnetSession(self.state, self.request, self.client_address).run()
        except ClientDisconnected:
            return
        except Exception as exc:
            if is_expected_disconnect(exc):
                return
            if self.state.issue_log is not None:
                self.state.issue_log.record_traceback("TELNET", self.client_address, exc)
            return


class ThreadedTelnetServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_telnet(state: GibsonState) -> ThreadedTelnetServer:
    _Handler.state = state
    try:
        server = ThreadedTelnetServer((state.config.host, state.config.port), _Handler)
    except PermissionError:
        port = state.config.port
        raise SystemExit(
            f"GIBSON: permission denied binding TN3270/line-mode port {port}.\n"
            f"Ports below 1024 are privileged. Grant the capability once with:\n"
            f"  sudo ./scripts/grant-port-capabilities.sh\n"
            f"(or run with sudo, or set GIBSON_PORT to a high port e.g. 2023)."
        )
    if is_secure_mode(state):
        server = wrap_server_socket(server, state, "TSO/TN3270")
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonTelnet").start()
    return server
