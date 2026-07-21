"""M1 - TSO/E LOGON panel + READY session in authentic EBCDIC 3270.

Implements the Phase-0 ``PanelSession`` contract:

    app = Tso3270App(state, peer_addr="1.2.3.4")
    screen = app.initial_screen()          # TSO/E LOGON panel
    screen = app.handle(panel_input)        # -> next screen, or None to leave

Authentication, password policy and command execution all reuse the existing
engines (``state.racf``, ``state.uads``, ``state.password_policy`` and
``TsoCommandProcessor``); this module only adds the 3270 presentation.
"""
from __future__ import annotations

import re

from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import (
    Panel, Label, Field, PanelInput, PanelSession, ScrollList,
)
from gibson.apps.tso import TsoCommandProcessor

_LOGON = "LOGON"
_READY = "READY"
_HELP = "HELP"

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_OUTPUT_ROWS = 21  # transcript window height in the READY screen (Model 2)


def rows_for_terminal(ttype: str) -> int:
    """Map a negotiated 3270 terminal type to its alternate screen height.

    IBM-3278/3279 model 2 -> 24, model 3 -> 32, model 4 -> 43, model 5 -> 27.
    Anything unrecognised stays at the safe Model-2 default of 24 rows.
    """
    t = (ttype or "").upper()
    if "DYNAMIC" in t:
        return 24
    # Model is the digit after IBM-3278-/IBM-3279- (optionally followed by -E).
    m = re.search(r"IBM-32(?:78|79)-(\d)", t)
    model = m.group(1) if m else "2"
    return {"2": 24, "3": 32, "4": 43, "5": 27}.get(model, 24)


class Tso3270App(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "", rows: int = 24):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = (userid or "").upper()
        # Screen geometry: honour the negotiated 3270 model so a Model 3/4
        # terminal gets a taller transcript. Defaults to Model 2 (24 rows),
        # for which the derived rows match the historic hard-coded layout.
        self.rows = int(rows) if rows and int(rows) >= 24 else 24
        self._out_rows = self.rows - 3   # transcript window height
        self._pos_row = self.rows - 2    # "Row x of y" / SCROLL line
        self._cmd_row = self.rows - 1    # ===> command line
        self._pf_row = self.rows         # PF-key legend
        self.procedure = "ISPFPROC"
        self._screen = _LOGON
        self._message = ""
        self._cursor = "PASSWORD" if self.userid else "USERID"
        self.tso: Optional[TsoCommandProcessor] = None
        self.lines: List[str] = []
        self._scroll: Optional[ScrollList] = None
        self._more = False       # TSO "***" more-output paging active
        self._page_top = 0       # transcript index at top of the current *** page
        self.ispf = None  # nested ISPF sub-session (ISPF runs under TSO)
        self.sdsf = None  # nested SDSF sub-session (SDSF runs under TSO)
        self._pw_changed = False  # set when an initial password was changed at logon
        # Track the userid that has already passed password verification in this
        # logon session, so the mandatory password check is NOT re-run against the
        # (empty) hidden PASSWORD field on the second round-trip when the user is
        # entering a new password (forced change) or an MFA token. Without this,
        # the NEWPW / MFA round-trip fails with IKJ56421I PASSWORD NOT AUTHORIZED.
        self._auth_userid: Optional[str] = None
        self._submode: Optional[str] = None   # None | "OMVS" | "CONSOLE"
        self.omvs_shell = None                # OmvsShellSession in OMVS sub-mode
        self.omvs_editor = None               # Omvs3270Editor (oedit/vi) modal over OMVS
        self.lynx = None                      # LynxSession (text browser) modal over OMVS
        self.console_ctl = None               # MasterConsoleController in CONSOLE

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        return self._logon_panel()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if self.ispf is not None:
            screen = self.ispf.handle(pi)
            if screen is None:  # ISPF ended -> back to READY
                self.ispf = None
                self.lines.append("READY")
                return self._ready_panel(to_bottom=True)
            return screen
        if self.sdsf is not None:
            screen = self.sdsf.handle(pi)
            if screen is None:  # SDSF ended (PF3) -> back to READY
                self.sdsf = None
                self.lines.append("READY")
                return self._ready_panel(to_bottom=True)
            return screen
        if self._submode == "OMVS":
            if self.omvs_editor is not None:
                return self._handle_omvs_editor(pi)
            if self.lynx is not None:
                return self._handle_omvs_lynx(pi)
            return self._handle_omvs_line(pi)
        if self._submode == "CONSOLE":
            return self._handle_console_line(pi)
        if self._screen == _HELP:
            self._screen = _LOGON
            return self._logon_panel()
        if self._screen == _LOGON:
            return self._handle_logon(pi)
        if self._screen == _READY:
            return self._handle_ready(pi)
        return None

    # --------------------------------------------------------------- LOGON
    def _logon_panel(self) -> ScreenBuffer:
        p = Panel(cursor=self._cursor)
        p.add(Label(1, 1, "-" * 31 + " TSO/E LOGON " + "-" * 35, colors.WHITE))
        p.add(Label(3, 2, "Enter LOGON parameters below:", colors.GREEN))
        p.add(Label(3, 50, "RACF LOGON parameters:", colors.GREEN))

        p.add(Label(5, 2, "Userid    ===>", colors.GREEN))
        p.add(Field("USERID", 5, 17, 8, value=self.userid, colour=_TURQ))
        p.add(Label(7, 2, "Password  ===>", colors.GREEN))
        p.add(Field("PASSWORD", 7, 17, 8, hidden=True, colour=_TURQ))
        p.add(Label(7, 50, "New Password ===>", colors.GREEN))
        p.add(Field("NEWPW", 7, 68, 8, hidden=True, colour=_TURQ))
        p.add(Label(9, 2, "Procedure ===>", colors.GREEN))
        p.add(Field("PROC", 9, 17, 8, value=self.procedure, colour=_TURQ))
        # RACF MFA: token field shown on the panel; only required when MFA is
        # active for the user (parity with the ASCII/netcat logon path).
        p.add(Label(9, 50, "MFA Token ===>", colors.GREEN))
        p.add(Field("MFATOKEN", 9, 65, 12, hidden=True, colour=_TURQ))
        p.add(Label(11, 2, "Acct Nmbr ===>", colors.GREEN))
        p.add(Field("ACCT", 11, 17, 40, colour=_TURQ))
        p.add(Label(13, 2, "Size      ===>", colors.GREEN))
        p.add(Field("SIZE", 13, 17, 7, value="4096", numeric=True, colour=_TURQ))
        p.add(Label(15, 2, "Perform   ===>", colors.GREEN))
        p.add(Field("PERFORM", 15, 17, 4, numeric=True, colour=_TURQ))
        p.add(Label(17, 2, "Command   ===>", colors.GREEN))
        p.add(Field("COMMAND", 17, 17, 56, colour=_TURQ))

        p.add(Label(19, 2, "Enter an 'S' before each option desired below:", colors.GREEN))
        p.add(Field("OPT_NOMAIL", 20, 9, 1, colour=_TURQ))
        p.add(Label(20, 11, "Nomail", colors.GREEN))
        p.add(Field("OPT_NONOTICE", 20, 21, 1, colour=_TURQ))
        p.add(Label(20, 23, "Nonotice", colors.GREEN))
        p.add(Field("OPT_RECONNECT", 20, 35, 1, colour=_TURQ))
        p.add(Label(20, 37, "Reconnect", colors.GREEN))
        p.add(Field("OPT_OIDCARD", 20, 50, 1, colour=_TURQ))
        p.add(Label(20, 52, "OIDcard", colors.GREEN))

        p.pfkeys = "PF1/PF13 ==> Help   PF3/PF15 ==> Logoff   PA1 ==> Attention   PA2 ==> Reshow"
        if self._message:
            p.message = self._message
            p.message_colour = colors.YELLOW
        return p.render()

    def _logon_with(self, message: str, cursor: str = "USERID") -> ScreenBuffer:
        self._message = message
        self._cursor = cursor
        return self._logon_panel()

    def _help_panel(self) -> ScreenBuffer:
        p = Panel(title="TSO/E LOGON - HELP")
        for i, line in enumerate([
            "Enter your TSO userid and password to log on.",
            "",
            "  Userid     - your RACF user identity.",
            "  Password   - validated by RACF (shown non-display).",
            "  New Password - set only when changing your password.",
            "  Procedure  - logon procedure (default ISPFPROC).",
            "",
            "PF3 returns to the LOGON panel.",
        ]):
            p.add(Label(3 + i, 2, line, colors.GREEN))
        p.pfkeys = "PF3 ==> Return"
        return p.render()

    def _handle_logon(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._auth_userid = None
            return None  # logoff -> back to caller (VTAM)
        if pi.key in ("PF1", "PF13"):
            self._screen = _HELP
            return self._help_panel()
        if pi.key == "PA2":  # Reshow
            self._auth_userid = None
            self.userid = pi.stripped("USERID").upper() or self.userid
            return self._logon_panel()

        userid = pi.stripped("USERID").upper()
        password = pi.stripped("PASSWORD")
        newpw = pi.stripped("NEWPW")
        self.userid = userid
        self.procedure = pi.stripped("PROC") or "ISPFPROC"

        if not userid:
            return self._logon_with("ENTER USERID", "USERID")

        mgr = getattr(self.state, "service_manager", None)
        if mgr is not None and not mgr.is_available("RACF"):
            return self._logon_with("IRR555I RACF SUBSYSTEM NOT ACTIVE", "USERID")

        try:
            self.state.racf.load(merge=True)
            # Reload UADS from disk and re-sync it from the RACF authority on
            # every logon, so a password change made on another connection/path
            # (or a prior session) is picked up and the user is not stuck in a
            # stale forced-change loop.  RACF/GACF.DB is the source of truth.
            self.state.uads.load()
            self.state.uads.sync_from_racf(self.state.racf, self.state.password_policy)
        except Exception:
            pass
        if not self.state.racf.exists(userid):
            self._note_fail(userid)
            # Authentic z/OS wording (mixed case) shown on the TSO/E LOGON panel.
            # This exact text ("not authorized to use TSO") is what real tooling
            # (e.g. nmap tso-enum) matches to flag an invalid user ID.
            return self._logon_with(f"IKJ56420I Userid {userid} not authorized to use TSO", "USERID")

        rec = self.state.racf.get(userid)
        if rec is not None and getattr(rec, "revoked", False):
            self._record(userid, "LOGON", "USERID REVOKED", "FAILURE")
            return self._logon_with(f"ICH70001I USERID {userid} IS REVOKED - LOGON REJECTED BY RACF", "USERID")

        if self._auth_userid != userid:
            if not self.state.racf.verify_password(userid, password):
                self._note_fail(userid)
                self._record(userid, "LOGON", "PASSWORD FAILURE", "FAILURE")
                return self._logon_with("IKJ56421I PASSWORD NOT AUTHORIZED - RE-ENTER", "PASSWORD")
            # Password accepted: remember it for the NEWPW / MFA round-trips so the
            # empty hidden PASSWORD field on the next submit does not re-trigger
            # verification. Cleared when we leave the LOGON screen.
            self._auth_userid = userid

        # Initial / expired password handling (reuse UADS + policy).
        changed = self._maybe_change_password(userid, newpw)
        if changed is not None:
            return changed  # a message panel asking for / rejecting the new password

        # RACF MFA: once the password is resolved, require a valid MFA token if
        # MFA is active for this user (parity with the ASCII/netcat path).
        mfa = self._maybe_mfa(userid, pi.stripped("MFATOKEN"))
        if mfa is not None:
            return mfa

        # Success.
        self._auth_userid = None
        self._record(userid, "LOGON", "PASSWORD", "SUCCESS")
        self.tso = TsoCommandProcessor(self.state, userid)
        self._screen = _READY
        self.lines = []
        if self._pw_changed:
            self.lines.append("ICH70007I PASSWORD CHANGED SUCCESSFULLY")
            self._pw_changed = False
        self.lines += [
            f"ICH70001I {userid} LAST ACCESS AT {self._now()}",
            f"{userid} LOGON IN PROGRESS AT {self._now()}",
        ]
        # First-time-this-session GIBSON welcome banner: a short orientation so a
        # student knows what they have connected to. Authentic systems show a
        # site banner on logon; here it explains the training range succinctly.
        if not getattr(self, "_welcomed", False):
            self._welcomed = True
            host = str(getattr(self.state.network, "hostname", "GIBSON") or "GIBSON").upper()
            self.lines += [
                "*" * 60,
                "*  GIBSON z/OS SECURITY TRAINING SYSTEM".ljust(59) + "*",
                f"*  SYSTEM {host}   SYSPLEX GIBPLEX   z/OS 02.05.00".ljust(59) + "*",
                "*  Authorised training use only. This is a SIMULATED".ljust(59) + "*",
                "*  mainframe for the MOST course - every lab includes a".ljust(59) + "*",
                "*  Blue-Team remediation step. Type HELP for commands,".ljust(59) + "*",
                "*  ISPF for panels, SDSF for spool, or LOGON to switch user.".ljust(59) + "*",
                "*" * 60,
            ]
        self.lines += [
            "READY",
        ]
        self._register_session(userid)
        self._deliver_pending(userid)
        return self._ready_panel(to_bottom=True)

    def _register_session(self, userid: str) -> None:
        """Make this terminal an *active* session so SEND ... NOW can reach it.
        The notifier injects the message into our scrollable transcript, which
        the user sees on the next screen render (3270 is request/response)."""
        def _notify(message: str) -> None:
            self.lines.append(message)
        try:
            self.state.sessions.add(userid, self.peer_addr, _notify)
        except Exception:
            pass

    def _deliver_pending(self, userid: str) -> None:
        try:
            pending = self.state.racf.ensure_user_dir(
                self.state.config.files_root, userid) / "pending_messages.txt"
            if pending.exists():
                text = pending.read_text(encoding="utf-8", errors="ignore")
                pending.unlink(missing_ok=True)
                if text.strip():
                    self.lines.append("*** YOU HAVE NEW MESSAGES ***")
                    for ln in text.rstrip("\n").split("\n"):
                        self.lines.append(ln.rstrip())
                    self.lines.append("READY")
        except Exception:
            pass

    def _deregister_session(self) -> None:
        try:
            if self.userid:
                self.state.sessions.remove(self.userid)
        except Exception:
            pass

    def _maybe_change_password(self, userid: str, newpw: str) -> Optional[ScreenBuffer]:
        # RACF/GACF.DB is the single source of truth for the initial/expired
        # password state.  We read the flag straight from the RACF record so a
        # stale SYS1.UADS copy can never trap the user in a forced-change loop.
        try:
            rec = self.state.racf.get(userid)
        except Exception:
            rec = None
        if rec is None or not getattr(rec, "password_change_required", False):
            return None
        if not newpw:
            return self._logon_with(
                "ICH70008I PASSWORD EXPIRED OR INITIAL - ENTER A NEW PASSWORD", "NEWPW")
        try:
            from gibson.core.security_freeze import verify_password_hash as _vh
            hist = (getattr(rec, "password_history", None)
                    or getattr(self.state.uads.get(userid), "password_history", None) or [])
            ok, msg = self.state.password_policy.validate_new_password(
                userid, newpw, list(hist), _vh)
        except Exception:
            ok, msg = True, ""
        if not ok:
            self._record(userid, "PASSWORD CHANGE", msg, "FAILURE")
            return self._logon_with(msg or "ICH70009I PASSWORD CHANGE FAILED", "NEWPW")
        try:
            self.state.racf.altuser(userid, password=newpw)   # clears RACF flag
            self.state.racf.save()                            # persist to GACF.DB
            # Keep SYS1.UADS in step for realism/display only (not the authority).
            try:
                new_rec = self.state.racf.get(userid)
                self.state.uads.set_password(
                    userid, new_rec.password if new_rec else "", change_required=False)
                try:
                    self.state.datasets.write(
                        "IBMUSER", "SYS1.UADS",
                        "\n".join(self.state.uads.list_lines()) + "\n")
                except Exception:
                    pass
            except Exception:
                pass
            self._record(userid, "PASSWORD CHANGE", "INITIAL PASSWORD CHANGED", "SUCCESS")
            self._pw_changed = True
        except Exception:
            pass
        return None

    def _maybe_mfa(self, userid: str, token: str) -> Optional[ScreenBuffer]:
        """Enforce RACF MFA on the EBCDIC logon, mirroring the ASCII path:
        if MFA is active for the user, a valid token (PIN+HHMM) is required."""
        try:
            required = self.state.mfa_required_for(userid)
        except Exception:
            required = False
        if not required:
            return None
        if not token:
            return self._logon_with(
                "IRRC113I MFA TOKEN REQUIRED - ENTER PIN+HHMM", "MFATOKEN")
        try:
            valid = self.state.validate_mfa_token(token)
        except Exception:
            valid = False
        if not valid:
            self._note_fail(userid)
            self._record(userid, "MFA", "TOKEN FAILURE", "FAILURE")
            return self._logon_with("IRRC114I MFA TOKEN INVALID - RE-ENTER", "MFATOKEN")
        self._record(userid, "MFA", "TOKEN SUCCESS", "SUCCESS")
        return None

    # --------------------------------------------------------------- READY
    def _transcript_colour(self):
        """Base colour for the transcript, by context: TSO=red, OMVS/USS=light
        blue, CONSOLE=green - matching the ASCII/netcat path so the user can tell
        at a glance which subsystem they are in."""
        if self._submode == "OMVS":
            return getattr(colors, "LIGHT_BLUE", colors.GREEN)
        if self._submode == "CONSOLE":
            return colors.GREEN
        return colors.RED  # TSO READY

    def _ready_panel_more(self, anchor: Optional[int] = None) -> ScreenBuffer:
        """Render one screenful of transcript with a TSO '***' more prompt.

        Long command output (e.g. LU *) is shown a page at a time anchored at
        the start of the new output, rather than jumping to the final lines.
        ENTER advances; when the bottom is reached the normal READY prompt
        returns.
        """
        if anchor is not None:
            self._page_top = max(0, anchor)
        total = len(self.lines)
        win = max(1, self._out_rows - 1)  # reserve the last row for ***
        self._more = (self._page_top + win) < total
        s = ScreenBuffer(rows=self.rows)
        s.extended_attributes = True
        sl = ScrollList(self.lines, height=win, top=self._page_top)
        sl.render_into(s, 1, left=1, width=79, colour=self._transcript_colour())
        self._scroll = sl
        if self._more:
            s.put(self._out_rows, 1, "***", colors.WHITE)
        shown = min(self._page_top + win, total)
        s.put(self._pos_row, 1, (f"Row {shown} of {total}").ljust(20), colors.BLUE)
        s.put(self._pos_row, 60, "SCROLL ===> PAGE", colors.BLUE)
        s.put(self._cmd_row, 1, "===>", colors.WHITE)
        s.add_field("CMD", self._cmd_row, 6, 72, colour=_TURQ, role="command")
        s.put(self._pf_row, 1, "PF3=Logoff  PF7=Up  PF8=Down  ENTER=More" if self._more
              else "PF3=Logoff  PF7=Up  PF8=Down  PF10=Left  PF11=Right", colors.BLUE)
        s.set_cursor(self._cmd_row, 6)
        return s

    def _ready_panel(self, to_bottom: bool = False) -> ScreenBuffer:
        self._more = False
        self._scroll = ScrollList(self.lines, height=self._out_rows)
        if to_bottom:
            self._scroll.to_bottom()
        s = ScreenBuffer(rows=self.rows)
        s.extended_attributes = True
        self._scroll.render_into(s, 1, left=1, width=79, colour=self._transcript_colour())
        s.put(self._pos_row, 1, self._scroll.position_label.ljust(20), colors.BLUE)
        s.put(self._pos_row, 60, "SCROLL ===> PAGE", colors.BLUE)
        s.put(self._cmd_row, 1, "===>", colors.WHITE)
        s.add_field("CMD", self._cmd_row, 6, 72, colour=_TURQ, role="command")
        s.put(self._pf_row, 1, "PF3=Logoff  PF7=Up  PF8=Down  PF10=Left  PF11=Right", colors.BLUE)
        s.set_cursor(self._cmd_row, 6)
        return s

    def _handle_ready(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=self._out_rows)
            self._scroll.scroll(pi.key)
            return self._ready_panel_keep_scroll()
        # TSO "***" paging: ENTER with no command advances to the next page of
        # pending output instead of starting a new command.
        if self._more and pi.key in ("ENTER", "") and not pi.stripped("CMD"):
            self._page_top = min(self._page_top + max(1, self._out_rows - 1),
                                 max(0, len(self.lines) - 1))
            panel = self._ready_panel_more()
            if not self._more:  # reached the bottom -> close with a READY prompt
                self.lines.append("READY")
                return self._ready_panel(to_bottom=True)
            return panel
        cmd = pi.stripped("CMD")
        up = cmd.upper()
        if pi.key in ("PF3", "PF15") or up in ("LOGOFF", "LOGOFF HOLD", "LOGON OFF"):
            if self.userid:
                self._record(self.userid, "LOGOFF", "TSO", "SUCCESS")
            self._deregister_session()
            return None
        # Re-logon: LOGON or LOGON <userid> returns to the TSO/E LOGON panel so a
        # student can switch identity without dropping the TN3270 connection
        # (authentic: LOGOFF then a fresh LOGON on the same terminal).
        if up == "LOGON" or (up.startswith("LOGON ") and up != "LOGON OFF"):
            if self.userid:
                self._record(self.userid, "LOGOFF", "TSO RE-LOGON", "SUCCESS")
            self._deregister_session()
            newid = up.split(None, 1)[1].strip().split()[0] if " " in up else ""
            if newid and newid != "OFF":
                self.userid = newid[:8]
            self._screen = _LOGON
            self._message = "IKJ56455I LOGON RE-ENTERED - ENTER LOGON PARAMETERS"
            self._cursor = "PASSWORD" if newid else "USERID"
            return self._logon_panel()
        if not cmd:
            return self._ready_panel(to_bottom=True)
        # '?' help facility - parity with the ASCII/netcat path: any '?' or a
        # trailing '?' routes to the SAME TsoAutocomplete prefix-matcher, rendered
        # EBCDIC-safe (ANSI stripped) into the 3270 transcript.
        if cmd == "?" or cmd.endswith("?"):
            self._cmd_anchor = len(self.lines)
            self.lines.append("READY")
            self.lines.append(cmd)
            prefix = "" if cmd == "?" else cmd[:-1].strip()
            ac = getattr(self, "_autocomplete", None)
            if ac is None:
                from gibson.apps.autocomplete import TsoAutocomplete
                ac = TsoAutocomplete(self.state)
                self._autocomplete = ac
            try:
                _completed, help_text = ac.complete(prefix)
            except Exception as exc:  # never let help kill the session
                help_text = f"HELP UNAVAILABLE: {exc}"
            from gibson.render.ansi3270 import strip_ansi
            for line in strip_ansi(help_text or "").replace("\r\n", "\n").split("\n"):
                self.lines.append(line.rstrip())
            self.lines.append("READY")
            anchor = self._cmd_anchor
            if (len(self.lines) - anchor) > self._out_rows:
                return self._ready_panel_more(anchor)
            return self._ready_panel(to_bottom=True)
        self._cmd_anchor = len(self.lines)
        self.lines.append(f"READY")
        self.lines[-1] = "READY"
        # echo the command, then its output
        self.lines.append(cmd)
        if up in ("ISPF", "PDF", "ISPSTART", "ISP"):
            from gibson.apps.ispf3270 import IspfSplitManager
            self.ispf = IspfSplitManager(self.state, peer_addr=self.peer_addr, userid=self.userid)
            return self.ispf.initial_screen()
        if up == "SDSF" or up.startswith("SDSF "):
            from gibson.apps.sdsf3270.sdsf_session import Sdsf3270Session
            self.sdsf = Sdsf3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
            return self.sdsf.initial_screen()
        # interactive sub-systems get a dedicated 3270 sub-mode instead of
        # dumping a raw GIBSON-INTERACTIVE sentinel to the transcript.
        if up == "OMVS" or up.startswith("OMVS "):
            return self._enter_omvs()
        if up == "CONSOLE" or up.startswith("CONSOLE "):
            return self._enter_console()
        try:
            out = self.tso.run(cmd) if self.tso else ""
        except Exception as exc:  # never let a command kill the session
            from gibson.core.abend import symptom_dump
            cmdname = up.split()[0] if up else ""
            out = (f"IKJ56500I COMMAND {cmdname} ABENDED: {exc}\n"
                   + symptom_dump("S0C7", jobname=(self.userid or "IBMUSER"),
                                  stepname=cmdname[:8] or "TSO", progname=cmdname[:8] or "IKJEFT01"))
        if isinstance(out, str) and out.startswith("GIBSON-INTERACTIVE:"):
            target = out.split(":", 1)[1].strip().upper()
            if target == "OMVS":
                return self._enter_omvs()
            if target == "CONSOLE":
                return self._enter_console()
            if target in ("ISPF", "PDF", "EDIT"):
                from gibson.apps.ispf3270 import IspfSplitManager
                self.ispf = IspfSplitManager(self.state, peer_addr=self.peer_addr, userid=self.userid)
                return self.ispf.initial_screen()
            out = f"{target} is not available from this TSO view."
        # Strip ANSI colour/clear sequences: full-screen apps such as SDSF and
        # CONSOLE emit them, and in the 3270 transcript a raw \x1b[..m would be
        # cp037-mangled into Ý..m / Ý2JÝH bracket corruption.
        from gibson.render.ansi3270 import strip_ansi
        for line in strip_ansi(out or "").replace("\r\n", "\n").split("\n"):
            self.lines.append(line.rstrip())
        self.lines.append("READY")
        # keep transcript bounded
        if len(self.lines) > 2000:
            self.lines = self.lines[-2000:]
        # Long output (e.g. LU *) pages from the top with a TSO "***" prompt
        # rather than jumping to the final lines.
        anchor = getattr(self, "_cmd_anchor", 0)
        anchor = max(0, anchor - (len(self.lines) - 2000)) if len(self.lines) >= 2000 else anchor
        if (len(self.lines) - anchor) > self._out_rows:
            return self._ready_panel_more(anchor)
        return self._ready_panel(to_bottom=True)

    # --------------------------------------------------- OMVS sub-mode
    def _enter_omvs(self) -> Optional[ScreenBuffer]:
        from gibson.apps.omvs import OmvsShellSession
        rec = self.state.racf.get(self.userid)
        mgr = getattr(self.state, "service_manager", None)
        if mgr is not None and not mgr.is_available("OMVS"):
            self.lines.append("BPXM010I OMVS NOT AVAILABLE.")
            self.lines.append("READY")
            return self._ready_panel(to_bottom=True)
        if not rec or not getattr(rec, "has_omvs", False):
            self.lines.append("FSUM6003 user does not have an OMVS segment")
            self.lines.append("READY")
            try:
                self.state.record_security_event(self.userid, "OMVS", "NO OMVS SEGMENT",
                                                 result="FAILURE", service="TN3270/TSO",
                                                 addr=self.peer_addr, terminal="3270")
            except Exception:
                pass
            return self._ready_panel(to_bottom=True)
        self.omvs_shell = OmvsShellSession(self.state, self.userid, self.tso, mode="OMVS3270")
        self._submode = "OMVS"
        self.lines.append("IBM Licensed Material - z/OS UNIX System Services")
        self.lines.append("Type 'exit' to return to TSO READY.")
        self.lines.append(f"{self.omvs_shell.cwd} $")
        return self._ready_panel(to_bottom=True)

    def _handle_omvs_line(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=self._out_rows)
            self._scroll.scroll(pi.key)
            return self._ready_panel_keep_scroll()
        line = pi.stripped("CMD")
        if pi.key in ("PF3", "PF15"):
            line = "exit"
        echo_prompt = self.omvs_shell.shell_prompt()
        if line:
            self.lines.append(f"{echo_prompt} {line}")
        launched = self._launch_omvs_editor(line) if line else None
        if launched is not None:
            return launched
        launched = self._launch_omvs_lynx(line) if line else None
        if launched is not None:
            return launched
        try:
            out = self.omvs_shell.execute(line) if line else ""
        except Exception as exc:
            out = f"FSUM7351 {exc}"
        if out is None:  # exit / logout
            self._submode = None
            self.omvs_shell = None
            self.lines.append("FSUM5006 OMVS shell ended")
            self.lines.append("READY")
            return self._ready_panel(to_bottom=True)
        if out == "__CLEAR__":  # `clear` in the 3270 scroll panel
            self.lines = []
            self.lines.append(f"{self.omvs_shell.shell_prompt()}")
            self._scroll = None
            return self._ready_panel(to_bottom=True)
        from gibson.render.ansi3270 import strip_ansi
        for ln in strip_ansi(out or "").replace("\r\n", "\n").split("\n"):
            if ln:
                self.lines.append(ln.rstrip())
        self.lines.append(f"{self.omvs_shell.shell_prompt()}")
        if len(self.lines) > 2000:
            self.lines = self.lines[-2000:]
        return self._ready_panel(to_bottom=True)

    # ------------------------------------------------ OMVS full-screen editor
    def _launch_omvs_editor(self, line: str):
        """If `line` is an editor command (oedit/vi/edit/view/obrowse), open the
        full-screen 3270 editor and return its panel; otherwise return None."""
        import shlex
        try:
            parts = shlex.split(line)
        except ValueError:
            return None
        if not parts or parts[0].lower() not in {"oedit", "vi", "edit", "view", "obrowse"}:
            return None
        verb = parts[0].lower()
        readonly = verb in {"view", "obrowse"}
        args = parts[1:]
        lrecl, recfm = 255, "VB"
        if verb == "oedit" and len(args) >= 2 and args[0] == "-r":
            try:
                lrecl, recfm, args = int(args[1]), "FB", args[2:]
            except ValueError:
                pass
        sh = self.omvs_shell

        def _back(msg: str):
            self.lines.append(msg)
            self.lines.append(f"{sh.shell_prompt()}")
            return self._ready_panel(to_bottom=True)

        if not args:
            return _back(f"{verb}: missing file operand")
        vp = sh._resolved(args[0].strip().strip("'\""))
        if vp.startswith("/dsfs") and not readonly:
            return _back(f"{verb}: /dsfs is read-only; copy with OGET/OPUT first")
        try:
            text = sh.env.read_text(vp)
        except Exception:
            text = ""
        from gibson.apps.omvs_editor3270 import Omvs3270Editor
        self.omvs_editor = Omvs3270Editor(
            vp, text, readonly=readonly, recfm=recfm, lrecl=lrecl, rows=self.rows,
            save_cb=lambda new, target=vp: sh.env.write_text(target, new))
        return self.omvs_editor.render()

    def _handle_omvs_editor(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        ed = self.omvs_editor
        screen = ed.handle(pi)
        if not ed.ended:
            return screen
        self.omvs_editor = None
        if ed.readonly:
            self.lines.append(f"BROWSE ended: {ed.path}")
        elif ed.saved:
            self.lines.append(f"FSUM saved {ed.path} ({len(ed.lines)} lines)")
        else:
            self.lines.append(f"Edit cancelled (not saved): {ed.path}")
        self.lines.append(f"{self.omvs_shell.shell_prompt()}")
        return self._ready_panel(to_bottom=True)

    # ------------------------------------------------ OMVS lynx text browser
    def _append_lynx(self, out: str) -> None:
        from gibson.render.ansi3270 import strip_ansi
        for ln in strip_ansi(out or "").replace("\r\n", "\n").split("\n"):
            self.lines.append(ln.rstrip())
        if len(self.lines) > 2000:
            self.lines = self.lines[-2000:]

    def _launch_omvs_lynx(self, line: str):
        import shlex
        try:
            parts = shlex.split(line)
        except ValueError:
            return None
        if not parts or parts[0].lower() != "lynx":
            return None
        from gibson.apps.omvs_lynx import LynxSession, HELP
        rest = parts[1:]
        if rest and rest[0] in ("-dump", "-source", "-links", "-h", "--help", "help"):
            return None       # one-shot modes handled by the shell
        sess = LynxSession(rest, state=self.state, userid=self.userid)
        if not sess.has_url():
            for ln in HELP.splitlines():
                self.lines.append(ln)
            self.lines.append(f"{self.omvs_shell.shell_prompt()}")
            return self._ready_panel(to_bottom=True)
        self.lynx = sess
        self._append_lynx(sess.start())
        return self._ready_panel(to_bottom=True)

    def _handle_omvs_lynx(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=self._out_rows)
            self._scroll.scroll(pi.key)
            return self._ready_panel_keep_scroll()
        line = pi.stripped("CMD")
        if pi.key in ("PF3", "PF15"):
            line = "q"
        self.lines.append(f"lynx> {line}")
        try:
            out = self.lynx.handle(line)
        except Exception as exc:  # noqa: BLE001
            out = f"lynx: {exc}"
        if out is None:
            self.lynx = None
            self.lines.append("Leaving Lynx.")
            self.lines.append(f"{self.omvs_shell.shell_prompt()}")
            return self._ready_panel(to_bottom=True)
        self._append_lynx(out)
        return self._ready_panel(to_bottom=True)

    def _enter_console(self) -> Optional[ScreenBuffer]:
        from gibson.apps.master_console import MasterConsoleController
        if self.tso is None or not self.tso.is_special():
            self.lines.append("IEE345I CONSOLE AUTHORITY INSUFFICIENT - ACCESS DENIED")
            self.lines.append("READY")
            try:
                self.state.record_security_event(self.userid, "CONSOLE", "NOT AUTHORIZED",
                                                 result="FAILURE", service="TN3270/TSO",
                                                 addr=self.peer_addr, terminal="3270")
            except Exception:
                pass
            return self._ready_panel(to_bottom=True)
        self.console_ctl = MasterConsoleController(self.state, self.userid)
        self._submode = "CONSOLE"
        self.lines.append("IEE612I CN=TSO    CONSOLE ACTIVATED")
        self.lines.append("Enter MVS system commands; END to return to TSO READY.")
        self.lines.append("CONSOLE ==>")
        return self._ready_panel(to_bottom=True)

    def _handle_console_line(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=self._out_rows)
            self._scroll.scroll(pi.key)
            return self._ready_panel_keep_scroll()
        cmd = pi.stripped("CMD")
        if pi.key in ("PF3", "PF15") or cmd.upper() in ("END", "EXIT", "QUIT", "K E"):
            self._submode = None
            self.console_ctl = None
            self.lines.append("IEE600I TSO CONSOLE VIEW ENDED")
            self.lines.append("READY")
            return self._ready_panel(to_bottom=True)
        if cmd:
            self.lines.append(f"CONSOLE ==> {cmd}")
            try:
                self.state.audit.record(self.userid or "UNKNOWN", cmd, "ENTER", "CONSOLE")
            except Exception:
                pass
            try:
                result = self.console_ctl.execute(cmd)
                out = getattr(result, "text", str(result))
            except Exception as exc:
                out = f"IEE305I COMMAND FAILED - {exc}"
            for ln in (out or "").replace("\r\n", "\n").split("\n"):
                self.lines.append(ln.rstrip())
        self.lines.append("CONSOLE ==>")
        if len(self.lines) > 2000:
            self.lines = self.lines[-2000:]
        return self._ready_panel(to_bottom=True)

    def _ready_panel_keep_scroll(self) -> ScreenBuffer:
        s = ScreenBuffer(rows=self.rows)
        s.extended_attributes = True
        (self._scroll or ScrollList(self.lines, height=self._out_rows)).render_into(
            s, 1, left=1, width=79, colour=self._transcript_colour())
        pos = self._scroll.position_label if self._scroll else "Row 0 of 0"
        s.put(self._pos_row, 1, pos.ljust(20), colors.BLUE)
        s.put(self._pos_row, 60, "SCROLL ===> PAGE", colors.BLUE)
        s.put(self._cmd_row, 1, "===>", colors.WHITE)
        s.add_field("CMD", self._cmd_row, 6, 72, colour=_TURQ, role="command")
        s.put(self._pf_row, 1, "PF3=Logoff  PF7=Up  PF8=Down  PF10=Left  PF11=Right", colors.BLUE)
        s.set_cursor(self._cmd_row, 6)
        return s

    # --------------------------------------------------------------- utils
    def _note_fail(self, userid: str) -> None:
        try:
            self.state.note_failed_logon(
                userid, self.peer_addr, port=getattr(self.state.config, "tn3270_port", 0),
                service="TN3270/TSO")
        except Exception:
            pass

    def _record(self, userid: str, event: str, detail: str, result: str) -> None:
        try:
            self.state.record_security_event(
                userid, event, detail, result=result,
                service="TN3270/TSO", addr=self.peer_addr, terminal="3270")
        except Exception:
            pass

    @staticmethod
    def _now() -> str:
        import datetime
        return datetime.datetime.now().strftime("%H:%M:%S ON %A %B %d, %Y").upper()
