"""M2 - CICS in authentic EBCDIC 3270.

Implements the Phase-0 ``PanelSession`` contract: good-morning -> blank
transaction entry -> transactions.  Reuses ``CicsSimulator`` for all behaviour
(``execute`` for CEMT/CECI/CEDA output, ``build_fielded_panel`` for the operator
menu, ``region.signon/signoff`` for sign-on state); this module is presentation
+ pseudo-conversational routing only.

States:
  GM      - good-morning banner
  ENTRY   - cleared screen, type a 4-char transaction id
  CESN    - sign-on map (userid + non-display password)
  OPMENU  - fielded CICS operator menu (a real input map; option -> command)
  RUN     - scrollable output of a transaction, with a command line
"""
from __future__ import annotations

from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import Panel, Label, Field, PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.render.ansi3270 import render_ansi_to_screen
from gibson.apps.cics import CicsSimulator
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.cbsa.cics_session import execute_omen

_GM = "GM"
_ENTRY = "ENTRY"
_CESN = "CESN"
_OPMENU = "OPMENU"
_RUN = "RUN"
_LAB = "LAB"
_CEMT = "CEMT"
_CBTR = "CBTR"

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_OUTPUT_ROWS = 21

# Transactions we route to CicsSimulator.execute (rendered scrollably).
_EXEC_TRANS = {"CEMT", "CECI", "CEDA", "CSMT", "CEBR", "CEDF", "HELP", "?"}
# Lab applications (Mel's Cargo / DVCA, CBSA / OMEN) — interactive, PF-key and
# field driven, rendered in colour and kept active across submissions.
_LAB_START = {"DVCA", "OMEN", "CBSA", "MCGM", "MCMM", "MCOR", "MCAD", "MCHI", "MCHS", "SCRT"}
# Typing a real CICS transaction while in a lab leaves the lab and runs it.
_CICS_TRANS = {"CEMT", "CECI", "CEDA", "CEDF", "CEBR", "CSMT", "CEOT", "CEST",
               "CMAC", "CWTO", "CRTE", "CSGM", "CESF", "CESN"}

# CEMT INQUIRE resource detection + colour helpers for the fielded panels.
_CEMT_RES_WORDS = [
    ("FILE", ("FILE", "FIL", "DSN")),
    ("PROGRAM", ("PROGRAM", "PROG", "PROG")),
    ("TASK", ("TASK", "TAS")),
    ("TRANSACTION", ("TRANSACTION", "TRAN", "TRANS")),
    ("TERMINAL", ("TERMINAL", "TERM")),
]


def _cemt_inquiry_target(raw: str):
    uc = (raw or "").upper()
    if " I " not in f" {uc} " and "INQUIRE" not in uc and not uc.strip().endswith(" I"):
        # allow "CEMT I FILE" / "CEMT INQUIRE FILE"
        if "INQ" not in uc and " I" not in f" {uc}":
            return None
    for res, words in _CEMT_RES_WORDS:
        for w in words:
            if w in uc:
                return res
    return None


def _cemt_status_colour(value: str):
    v = (value or "").upper()
    if any(k in v for k in ("ENABLED", "OPEN", "INSERVICE", "ACTIVE", "ACQUIRED", "RUN")):
        return colors.GREEN
    if any(k in v for k in ("DISABLED", "CLOSED", "OUTSERVICE", "PURGED", "FAILED", "RELEASED")):
        return colors.RED
    if "HELD" in v or "WAIT" in v:
        return colors.YELLOW
    return colors.GREEN
# Additional supervisory / inquiry transactions handled in the 3270 wrapper so
# they produce authentic output instead of "command not recognized".
_EXTRA_TRANS = {"CEOT", "CMAC", "CWTO", "CEST", "CSGM", "CRTE"}
# Map option numbers on the operator menu to direct commands.
_OPMENU_CMD = {
    "1": "CEMT INQUIRE TASK", "2": "CEDA DISPLAY", "3": "CECI",
    "4": "CEDF", "5": "CEBR", "6": "CSMT",
    "7": "SECURITY", "8": "CEMT INQUIRE DB2CONN", "9": "CICS RESOURCE STATUS",
    "10": "DVCA", "11": "OMEN", "12": "HELP",
}


class Cics3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "CICSUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.cics = CicsSimulator(state, userid)
        self._screen = _GM
        self._message = ""
        self.lines: List[str] = []
        self._scroll: Optional[ScrollList] = None
        self._lab: Optional[str] = None

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        # When password logon is enabled (CICS AUTH ON), present the CESN
        # sign-on screen first so a terminal (or cicspwn) meets the password
        # field before any transaction can run.
        if getattr(self.state.config, "realistic_cics_auth", False) and not self.cics.signed_on:
            self._screen = _CESN
            return self._cesn_panel("DFHCE3520 SIGN-ON REQUIRED - ENTER USERID AND PASSWORD")
        return self._gm_panel()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if self._screen == _GM:
            if pi.key in ("PF3", "PF15"):
                return None
            # A real terminal user types a transaction id straight onto the
            # good-morning screen.  If they did, honour it instead of throwing
            # the input away; otherwise just advance to the entry panel.
            self._screen = _ENTRY
            if self._first_command(pi):
                return self._handle_entry(pi)
            return self._entry_panel()
        if self._screen == _ENTRY:
            return self._handle_entry(pi)
        if self._screen == _CESN:
            return self._handle_cesn(pi)
        if self._screen == _OPMENU:
            return self._handle_opmenu(pi)
        if self._screen == _RUN:
            return self._handle_run(pi)
        if self._screen == _LAB:
            return self._handle_lab(pi)
        if self._screen == _CEMT:
            return self._handle_cemt(pi)
        if self._screen == _CBTR:
            return self._handle_cbtr(pi)
        return None

    # ------------------------------------------------------------- GM/ENTRY
    def _gm_panel(self) -> ScreenBuffer:
        p = Panel()
        p.add(Label(2, 25, "**  WELCOME TO CICS  **", colors.WHITE))
        p.add(Label(4, 20, "Customer Information Control System", colors.TURQUOISE))
        p.add(Label(6, 20, f"Applid . . . : {self._applid()}", colors.GREEN))
        p.add(Label(7, 20, "Release  . . : 0740", colors.GREEN))
        p.add(Label(10, 10, "Clear the screen, then type a transaction id and press ENTER.", colors.GREEN))
        p.add(Label(12, 10, "Examples:  CESN  CEMT I TASK|FILE|PROGRAM|TRANSACTION|TERMINAL", colors.GREEN))
        p.add(Label(13, 10, "           CEDA  CECI  CEBR  CEDF  CEOT  CEST  CMAC  CWTO  CSGM", colors.GREEN))
        p.add(Label(14, 10, "           COPS (operator menu)   CESF (sign off)", colors.GREEN))
        p.pfkeys = "ENTER/CLEAR ==> Continue        PF3 ==> Return to VTAM"
        return p.render()

    def _entry_panel(self) -> ScreenBuffer:
        p = Panel(cursor="TRAN")
        p.add(Field("TRAN", 1, 1, 32, colour=_TURQ))
        if self._message:
            p.add(Label(23, 2, self._message, colors.YELLOW))
        p.add(Label(24, 1, "Type a transaction id and press ENTER.   PF3 ==> VTAM   CLEAR ==> clear", colors.BLUE))
        s = p.render()
        s.set_cursor(1, 1)
        return s

    def _first_command(self, pi: PanelInput, *names: str) -> str:
        """Return the first non-empty input the user gave us.

        Real c3270/x3270 input may land in whichever field the cursor was in,
        and the parser names it from the rendered panel.  To be robust against
        cursor/field-name differences we look at the preferred field names
        first, then fall back to *any* non-empty field on the screen.  This is
        what makes numeric/transaction selections reliable over a live 3270.
        """
        candidates = names or ("TRAN", "OPTION", "COMMAND", "CMD", "ZCMD")
        for n in candidates:
            v = pi.stripped(n)
            if v:
                return v
        for v in (pi.fields or {}).values():
            if v and v.strip():
                return v.strip()
        return ""

    def _handle_entry(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            return None
        if pi.key == "CLEAR":
            return self._entry_panel()
        raw = self._first_command(pi)
        if not raw:
            return self._entry_panel()
        transid = raw.split()[0].upper()
        if transid == "CESN":
            self._screen = _CESN
            return self._cesn_panel()
        if transid in ("CESF", "LOGOFF", "SIGNOFF"):
            out = self.cics.execute("CESF")
            self._screen = _GM
            self._message = ""
            return self._gm_panel()
        if transid in ("COPS", "MENU", "CICS"):
            self._screen = _OPMENU
            return self.cics.build_fielded_panel("CICS_OPERATOR_MAIN")
        if transid == "CSGM":  # good-morning transaction -> redisplay the GM screen
            self._screen = _GM
            return self._gm_panel()
        if transid == "CBTR":  # CBSA fielded transfer-approval lab (hack3270 target)
            self._screen = _CBTR
            from gibson.apps.cbsa.transfer_lab import transfer_buffer
            return transfer_buffer(self.state, self.cics.userid)
        if transid in _LAB_START:
            return self._start_lab(raw)
        if transid == "CEMT":
            res = _cemt_inquiry_target(raw)
            if res:
                return self._cemt_panel(res)
        if transid in _EXTRA_TRANS or transid in _EXEC_TRANS:
            return self._run_command(raw)
        # Unknown transaction id -> authentic CICS message on the cleared screen.
        self._message = f"DFHAC2001 {self._now()} Transaction '{transid[:4]}' is not recognized. Check and try again."
        return self._entry_panel()

    # --------------------------------------------------------------- CESN
    def _cesn_panel(self, message: str = "") -> ScreenBuffer:
        p = Panel(cursor="USERID")
        p.add(Label(1, 1, "Signon to CICS                                 APPLID  " + self._applid(), colors.BLUE))
        p.add(Label(4, 2, "Type your userid and password, then press ENTER:", colors.GREEN))
        p.add(Label(7, 2, "Userid . . . .", colors.GREEN))
        p.add(Field("USERID", 7, 18, 8, colour=_TURQ))
        p.add(Label(8, 2, "Password . . .", colors.GREEN))
        p.add(Field("PASSWORD", 8, 18, 8, hidden=True, colour=_TURQ))
        p.add(Label(9, 2, "New Password .", colors.GREEN))
        p.add(Field("NEWPW", 9, 18, 8, hidden=True, colour=_TURQ))
        if message:
            p.add(Label(12, 2, message, colors.YELLOW))
        p.pfkeys = "PF3 ==> Cancel"
        return p.render()

    def _handle_cesn(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _ENTRY
            return self._entry_panel()
        userid = pi.stripped("USERID").upper()
        password = pi.stripped("PASSWORD")
        if not userid:
            return self._cesn_panel("DFHCE3501 Please type your userid.")
        try:
            self.state.racf.load(merge=True)
        except Exception:
            pass
        if not self.state.racf.exists(userid) or not self.state.racf.verify_password(userid, password):
            try:
                self.state.record_security_event(userid, "SIGNON", "AUTHENTICATION FAILED",
                                                  result="FAILURE", service="CICS", addr=self.peer_addr, terminal="3270")
            except Exception:
                pass
            return self._cesn_panel("DFHCE3520 Your signon could not be validated. Re-enter.")
        rec = self.state.racf.get(userid)
        if rec is not None and getattr(rec, "revoked", False):
            return self._cesn_panel(f"DFHCE3530 Userid {userid} is revoked.")
        # success
        self.cics.userid = userid
        self.cics.signed_on = True
        try:
            self.cics.region.signon(userid)
        except Exception:
            pass
        try:
            self.state.record_security_event(userid, "SIGNON", "PASSWORD",
                                              result="SUCCESS", service="CICS", addr=self.peer_addr, terminal="3270")
        except Exception:
            pass
        self._screen = _ENTRY
        self._message = f"DFHCE3549 Sign-on is complete (Language ENU). Userid {userid}."
        return self._entry_panel()

    # ------------------------------------------------------------- OPMENU
    def _handle_opmenu(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _ENTRY
            return self._entry_panel()
        opt = self._first_command(pi, "OPTION", "TRAN", "COMMAND", "CMD").upper()
        cmd = _OPMENU_CMD.get(opt)
        if not cmd:
            # re-render the menu (optionally with a hint)
            return self.cics.build_fielded_panel("CICS_OPERATOR_MAIN")
        transid = cmd.split()[0].upper()
        # Interactive labs (DVCA / CBSA-OMEN) must start through the lab driver,
        # not run as a one-shot command.
        if transid in _LAB_START:
            return self._start_lab(cmd)
        # CEMT inquiries render as colour fielded panels, like the entry screen.
        if transid == "CEMT":
            res = _cemt_inquiry_target(cmd)
            if res:
                return self._cemt_panel(res)
        return self._run_command(cmd)

    # --------------------------------------------------------------- RUN
    def _run_command(self, command: str) -> ScreenBuffer:
        transid = command.split()[0].upper() if command.split() else ""
        # A freshly-typed top-level transaction must not be trapped inside a
        # stale legacy menu sub-state (panel_state from an earlier CECI/CEMT/CEDA
        # navigation) - that produced spurious "INVALID SELECTION" for valid
        # transactions like CSMT. Numeric/keyword sub-options are left alone so
        # in-menu navigation still works.
        if transid in _EXEC_TRANS or transid in _EXTRA_TRANS:
            self.cics.panel_state = ""
        extra = self._extra_output(transid, command)
        if extra is not None:
            out = extra
        else:
            try:
                out = self.cics.execute(command)
            except Exception as exc:
                out = f"DFHAC2206 Transaction {command.split()[0][:4]} abended: {exc}"
        self.lines = [f"Transaction: {command}".rstrip(), ""]
        for line in text_to_lines(out):
            self.lines.append(line.rstrip())
        self._screen = _RUN
        return self._run_panel(to_bottom=False)

    def _extra_output(self, transid: str, command: str) -> Optional[str]:
        """Authentic responses for common supervisory/inquiry transactions."""
        termid = "S270"
        if transid == "CEOT":
            return ("CEOT  ---  TERMINAL OWN TERMINAL STATUS\n"
                    f"{termid}  TRANSCEIVE  INSERVICE  ATI  TTI  UCTRAN\n"
                    "DFHCE3120 STATUS DISPLAY COMPLETE.")
        if transid == "CEST":
            return ("CEST  ---  SUPERVISORY TERMINAL\n"
                    f"Tas Termid  Tertype    Status\n"
                    f"    {termid}    3270      INS TRANSCEIVE\n"
                    "Enter one of CEST INQUIRE/SET TERMINAL|TASK and press ENTER.")
        if transid == "CMAC":
            parts = command.split()
            if len(parts) > 1:
                msgid = parts[1].upper()
                return (f"CMAC  ---  MESSAGE {msgid}\n"
                        f"{msgid}  (message text not in local catalogue)\n"
                        "EXPLANATION: Refer to CICS Messages and Codes.\n"
                        "SYSTEM ACTION: None.   USER RESPONSE: None.")
            return ("CMAC  ---  CICS MESSAGES AND CODES\n"
                    "Enter:  CMAC message-number   (e.g. CMAC DFHAC2001)")
        if transid == "CWTO":
            parts = command.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                return ("+" + parts[1].strip()[:60] + "\n"
                        "DFHWT0001 MESSAGE WRITTEN TO CONSOLE OPERATOR.")
            return "CWTO  ---  Enter message text:  CWTO your-message-text"
        if transid == "CRTE":
            parts = command.split()
            sysid = parts[1].upper() if len(parts) > 1 and parts[1].upper().startswith("SYSID") else "CICR"
            return ("CRTE  ---  ROUTING TRANSACTION\n"
                    f"DFHAC1500 Routing session to system {sysid} established.\n"
                    "Enter CANCEL to end the routing session.")
        return None

    def _run_panel(self, to_bottom: bool = False) -> ScreenBuffer:
        self._scroll = ScrollList(self.lines, height=_OUTPUT_ROWS)
        if to_bottom:
            self._scroll.to_bottom()
        return self._render_run()

    def _render_run(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        (self._scroll or ScrollList(self.lines, height=_OUTPUT_ROWS)).render_into(
            s, 1, left=1, width=79, colour=colors.GREEN)
        pos = self._scroll.position_label if self._scroll else "Row 0 of 0"
        s.put(22, 1, pos.ljust(20), colors.BLUE)
        s.put(23, 1, "===>", colors.WHITE)
        s.add_field("CMD", 23, 6, 72, colour=_TURQ, role="command")
        s.put(24, 1, "F3=Back  F7=Up  F8=Down  CLEAR=New transaction  PA1=Attention", colors.BLUE)
        s.set_cursor(23, 6)
        return s

    # --------------------------------------------------------------- LAB
    def _start_lab(self, raw: str) -> ScreenBuffer:
        """Enter a DVCA/OMEN lab via the engine, which sets the active flag."""
        try:
            out = self.cics.execute(raw)
        except Exception as exc:
            out = f"DFHAC2206 {raw.split()[0][:4]} abended: {exc}"
        if getattr(self.cics, "dvca_active", False):
            self._lab = "DVCA"
            self._screen = _LAB
            return self._render_dvca()
        elif getattr(self.cics, "cbsa_active", False):
            self._lab = "OMEN"
        else:
            # Lab refused to start (blocked/secured) -> show the message normally.
            self.lines = [f"Transaction: {raw}".rstrip(), ""] + [l.rstrip() for l in text_to_lines(out)]
            self._screen = _RUN
            return self._run_panel(to_bottom=False)
        self._screen = _LAB
        return self._render_lab(out)

    def _dvca_screen(self) -> str:
        try:
            from gibson.apps.dvca.store import get_dvca_store
            sid = getattr(self.state, "dvca_cics_sessions", {}).get((self.cics.userid or "DVCA").upper())
            if sid:
                return (get_dvca_store(self.state).session(sid).screen or "").upper()
        except Exception:
            pass
        return ""

    def _exit_lab(self) -> Optional[ScreenBuffer]:
        self.cics.dvca_active = False
        self.cics.cbsa_active = False
        self._lab = None
        self._screen = _ENTRY
        self._message = ""
        return self._entry_panel()

    def _handle_lab(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        # The user may type into the app's own "Selection ===>" field (SELECT)
        # or the footer command line (CMD).  Honour whichever was used so menu
        # selections AND recognised commands (e.g. HACK ON) both work.
        cmd = pi.stripped("CMD") or pi.stripped("SELECT")
        uc = cmd.upper()
        first = uc.split()[0] if uc else ""
        # explicit exits
        if pi.key == "CLEAR" or first in {"CESF", "LOGOFF", "SIGNOFF", "EXIT", "CICS"}:
            if first in {"CESF", "LOGOFF", "SIGNOFF"}:
                self.cics.execute("CESF")
                self.cics.dvca_active = False
                self.cics.cbsa_active = False
                self._lab = None
                self._screen = _GM
                return self._gm_panel()
            return self._exit_lab()
        # typing a real CICS transaction leaves the lab and runs it
        if first in _CICS_TRANS:
            self.cics.dvca_active = False
            self.cics.cbsa_active = False
            self._lab = None
            self._screen = _ENTRY
            return self._handle_entry(pi)

        if self._lab == "DVCA":
            # PF3 on the top (good-morning) screen quits the lab; deeper screens
            # pass PF3 through for the app's own "back" navigation.
            if pi.key in ("PF3", "PF15") and self._dvca_screen() in ("", "MCGM"):
                return self._exit_lab()

            class _Ev:
                def __init__(self, fields, aid):
                    self.fields_by_name = fields
                    self.aid = aid
            ev = _Ev(dict(pi.fields), pi.key)
            try:
                out = execute_dvca(self.state, self.cics.userid, cmd, aid=pi.key, event=ev)
            except Exception as exc:
                return self._render_lab(f"DVCA ERROR: {exc}")
            return self._render_dvca()

        # OMEN / CBSA
        if pi.key in ("PF3", "PF15") and not uc:
            return self._exit_lab()
        try:
            out = execute_omen(self.state, self.cics.userid, cmd or pi.key)
        except Exception as exc:
            out = f"OMEN ERROR: {exc}"
        if isinstance(out, str) and out.startswith("GIBSON_CICS_ROUTE:"):
            routed = out.split(":", 1)[1]
            self.cics.cbsa_active = False
            self._lab = None
            self._screen = _RUN
            return self._run_command(routed)
        return self._render_lab(out)

    def _handle_cbtr(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        """Handle the CBSA fielded transfer-approval lab (a hack3270 target)."""
        from gibson.apps.cbsa.transfer_lab import handle_transfer
        if pi.key == "CLEAR" or pi.key in ("PF3", "PF15"):
            self._screen = _ENTRY
            self._message = ""
            return self._entry_panel()
        return handle_transfer(self.state, self.cics.userid, dict(pi.fields), aid=pi.key)

    def _render_dvca(self) -> ScreenBuffer:
        """Render the current DVCA screen as a genuine fielded 3270 panel so the
        real hack3270 proxy can reveal/unlock its BMS fields. A command line is
        kept on the bottom row for navigation and backward compatibility."""
        from gibson.apps.dvca.cics_session import dvca_buffer
        sb = dvca_buffer(self.state, self.cics.userid)
        sb.put(24, 1, "CLEAR=Exit  PF3=Back  PF5=Menu  PF7/8=Scroll   ===>", colors.BLUE)
        sb.add_field("CMD", 24, 53, 26, colour=_TURQ, role="command")
        return sb

    def _render_lab(self, ansi_text: str) -> ScreenBuffer:
        from gibson.render.ansi3270 import strip_ansi
        s = render_ansi_to_screen(ansi_text, base_colour=colors.GREEN, rows=24, cols=80, start_row=1)
        # Attach the input field to the app's own "===>" prompt so we don't
        # cover its message/PF-key legend.
        lines = strip_ansi(ansi_text).replace("\r", "").split("\n")
        prompt_row = prompt_col = None
        for i, ln in enumerate(lines[:24], start=1):
            j = ln.find("===>")
            if j != -1:
                prompt_row, prompt_col = i, j + 5  # just past "===>"
                break
        last_used = max((i for i, ln in enumerate(lines[:24], start=1) if ln.strip()), default=0)
        if prompt_row is None:
            prompt_row = min(24, max(last_used + 1, 23))
            s.put(prompt_row, 1, "===>", colors.WHITE)
            prompt_col = 6
        s.add_field("CMD", prompt_row, prompt_col, max(8, 79 - prompt_col), colour=_TURQ, role="command")
        # A one-line exit hint, only if the app left the last row free.
        if last_used < 24 and prompt_row != 24:
            hint = "CLEAR=Exit to CICS   (PF3=Quit/Back  PF5=Menu  PA3=Secret)"
            if self._lab == "OMEN":
                hint = "CLEAR=Exit to CICS   PF3=End   PF10=Instructions"
            s.put(24, 1, hint[:79], colors.BLUE)
        s.set_cursor(prompt_row, prompt_col)
        return s

    # -------------------------------------------------------------- CEMT
    def _cemt_build(self, res: str):
        """Return (title, columns, rows) for a CEMT INQUIRE resource panel.

        Each row is a dict: name (resource key), restype, and cells -> list of
        (text, colour) tuples aligned with columns.
        """
        c = self.cics
        rows = []
        if res == "FILE":
            cols = [("File", 9), ("Type", 6), ("Open", 7), ("Enable", 9), ("Rea", 4), ("Upd", 4), ("Dsname", 30)]
            for r in c.files.values():
                opn = getattr(r, "open_state", "OPEN")
                ena = "DISABLED" if "DIS" in (r.status or "").upper() else "ENABLED"
                rows.append(dict(name=r.name, restype="FILE", cells=[
                    (r.name, colors.TURQUOISE), (r.attr("TYPE", "VSAM"), colors.GREEN),
                    (opn, _cemt_status_colour(opn)), (ena, _cemt_status_colour(ena)),
                    (r.attr("READ", "YES"), colors.GREEN), (r.attr("UPDATE", "NO"), colors.GREEN),
                    (r.attr("DSN", f"GIBSON.{r.name}"), colors.WHITE)]))
            return "INQUIRE FILE", cols, rows
        if res == "PROGRAM":
            cols = [("Program", 9), ("Length", 8), ("Rescount", 9), ("Usecount", 9), ("Status", 10)]
            for r in c.programs.values():
                rows.append(dict(name=r.name, restype="PROGRAM", cells=[
                    (r.name, colors.TURQUOISE), (r.attr("LENGTH", "0000"), colors.GREEN),
                    (r.attr("RESCOUNT", "0000"), colors.GREEN), (r.attr("USECOUNT", "0000"), colors.GREEN),
                    (r.status, _cemt_status_colour(r.status))]))
            return "INQUIRE PROGRAM", cols, rows
        if res == "TASK":
            cols = [("Task", 7), ("Tran", 6), ("Facility", 9), ("Status", 9), ("Userid", 9), ("Program", 9)]
            for t in c.region.tasks.values():
                stt = t.get("STATUS", "RUNNING")
                rows.append(dict(name=str(t.get("TASK", "")), restype="TASK", cells=[
                    (str(t.get("TASK", "")), colors.TURQUOISE), (t.get("TRAN", ""), colors.GREEN),
                    (t.get("TERMID", ""), colors.GREEN), (stt, _cemt_status_colour(stt)),
                    (t.get("USERID", ""), colors.GREEN), (t.get("PROGRAM", ""), colors.GREEN)]))
            if not rows:
                now = self._now()
                rows.append(dict(name="0000001", restype="TASK", cells=[
                    ("0000001", colors.TURQUOISE), ("CEMT", colors.GREEN), ("LU320", colors.GREEN),
                    ("Running", colors.GREEN), (self.cics.userid, colors.GREEN), ("DFHEMTP", colors.GREEN)]))
            return "INQUIRE TASK", cols, rows
        if res == "TRANSACTION":
            cols = [("Tran", 6), ("Priority", 9), ("Program", 9), ("Status", 10), ("Tcl", 6)]
            for r in c.transactions.values():
                rows.append(dict(name=r.name, restype="TRANSACTION", cells=[
                    (r.name, colors.TURQUOISE), (r.attr("PRIORITY", "001"), colors.GREEN),
                    (r.attr("PROGRAM", "DFH"), colors.GREEN), (r.status, _cemt_status_colour(r.status)),
                    (r.attr("TCLASS", "No"), colors.GREEN)]))
            return "INQUIRE TRANSACTION", cols, rows
        # TERMINAL
        cols = [("Term", 6), ("Netname", 9), ("Status", 11), ("Userid", 9), ("Service", 11)]
        for r in c.terminal_resources.values():
            svc = "INSERVICE" if "OUT" not in (r.status or "").upper() else "OUTSERVICE"
            rows.append(dict(name=r.name, restype="TERMINAL", cells=[
                (r.name, colors.TURQUOISE), (r.attr("NETNAME", ""), colors.GREEN),
                (r.status, _cemt_status_colour(r.status)), (r.attr("USERID", ""), colors.GREEN),
                (svc, _cemt_status_colour(svc))]))
        if not rows:
            rows.append(dict(name="S270", restype="TERMINAL", cells=[
                ("S270", colors.TURQUOISE), ("LU320", colors.GREEN), ("Inservice", colors.GREEN),
                (self.cics.userid, colors.GREEN), ("Inservice", colors.GREEN)]))
        return "INQUIRE TERMINAL", cols, rows

    def _cemt_panel(self, res: str) -> ScreenBuffer:
        self._screen = _CEMT
        self._cemt_res = res
        title, cols, rows = self._cemt_build(res)
        self._cemt_rows = rows
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"CEMT {title}", colors.WHITE)
        s.put(1, 50, "STATUS:  RESULTS", colors.TURQUOISE)
        s.put(2, 1, f"Applid {self._applid()}   {len(rows)} result(s)   {self._now()}", colors.GREEN)
        s.put(2, 60, "OVERTYPE TO MODIFY", colors.TURQUOISE)
        # column header
        col_pos = []
        x = 5
        hdr = ""
        s.put(3, 1, "Act", colors.BLUE)
        for label, w in cols:
            col_pos.append((x, w))
            s.put(3, x, label[:w], colors.BLUE)
            x += w + 1
        r = 4
        maxr = 21
        for i, row in enumerate(rows):
            if r > maxr:
                break
            s.add_field(f"AC{i:02d}", r, 1, 3, colour=_TURQ, role="line_command")
            for (cx, cw), (text, colour) in zip(col_pos, row["cells"]):
                s.put(r, cx, str(text)[:cw], colour)
            r += 1
        if not rows:
            s.put(4, 5, "DFHCE3549 NO RESOURCES MATCH", colors.YELLOW)
        s.put(22, 1, (self._message or "Type an action in Act (e.g. OPEN/CLOSE/ENABLE/DISABLE/PURGE), ENTER")[:79],
              colors.YELLOW if self._message else colors.TURQUOISE)
        s.put(23, 1, "===>", colors.WHITE)
        s.add_field("CMD", 23, 6, 72, colour=_TURQ, role="command")
        s.put(24, 1, "PF3=End  PF7=Up  PF8=Down  ENTER=Apply overtyped actions  PA2=Reshow", colors.BLUE)
        s.set_cursor(4, 1)
        self._message = ""
        return s

    def _handle_cemt(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15") or pi.key == "CLEAR":
            self._screen = _ENTRY
            self._message = ""
            return self._entry_panel()
        cmd = pi.stripped("CMD")
        if cmd:
            first = cmd.split()[0].upper()
            if first in _CICS_TRANS:
                self._screen = _ENTRY
                return self._handle_entry(pi)
            res = _cemt_inquiry_target(cmd)
            if res:
                return self._cemt_panel(res)
            # treat as a raw CEMT command
            self._screen = _ENTRY
            return self._run_command(cmd)
        # apply overtyped action characters
        applied = []
        rows = getattr(self, "_cemt_rows", [])
        for name, val in pi.fields.items():
            if name.startswith("AC") and val.strip():
                try:
                    idx = int(name[2:])
                except ValueError:
                    continue
                if idx < len(rows):
                    row = rows[idx]
                    act = val.strip().upper()
                    out = self.cics.execute(f"CEMT SET {row['restype']}({row['name']}) {act}")
                    applied.append(out.splitlines()[0] if out else f"{row['name']} {act}")
        if applied:
            self._message = applied[0][:78]
        else:
            self._message = ""
        return self._cemt_panel(self._cemt_res)

    def _handle_run(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15") or pi.key == "CLEAR":
            self._screen = _ENTRY
            self._message = ""
            return self._entry_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=_OUTPUT_ROWS)
            self._scroll.scroll(pi.key)
            return self._render_run()
        cmd = pi.stripped("CMD")
        if cmd:
            transid = cmd.split()[0].upper()
            if transid in ("CESF", "LOGOFF"):
                self.cics.execute("CESF")
                self._screen = _GM
                return self._gm_panel()
            if transid == "CESN":
                self._screen = _CESN
                return self._cesn_panel()
            return self._run_command(cmd)
        return self._render_run()

    # --------------------------------------------------------------- utils
    def _applid(self) -> str:
        try:
            return (self.state.get_system_hostname() or "CICSGIB1")[:8].upper()
        except Exception:
            return "CICSGIB1"

    @staticmethod
    def _now() -> str:
        import datetime
        return datetime.datetime.now().strftime("%H:%M:%S")
