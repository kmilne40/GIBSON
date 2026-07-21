"""M3b - SDSF in authentic EBCDIC 3270.

Renders SDSF natively (proper colours, real column grid, per-row NP action
fields) from the structured panel objects produced by ``SdsfApp`` rather than
flattening its ANSI text.  Supports the SDSF action characters (S/?/P/C/A/E)
and the ``/`` System Command Extension dialog, plus the full command line
(ST/DA/O/H/I/LOG/OPERLOG/ULOG/AD/AS and the PREFIX/OWNER scope filters).
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.sdsf import SdsfApp, SdsfRow

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_WHITE = getattr(colors, "WHITE", colors.GREEN)
_BODY_ROWS = 20
_PAGE = 14  # data rows visible per page in the native grid
_ACTION_BAR = "Display  Filter  View  Print  Options  Search  Help"
_ACTIONS = {
    "P": "$P  - PURGE requested",
    "C": "$C  - CANCEL requested",
    "A": "$A  - RELEASE requested",
    "E": "$E  - RESTART (release for execution)",
    "H": "$H  - HOLD requested",
    "O": "$O  - RELEASE output",
    "?": "JDS - expand job data sets (use S to browse)",
}
_JOB_PANELS = {"ST", "DA", "I", "O", "H", "AD", "AS"}

# Per-row line actions that mutate real JES job state.
_JES_ACTIONS = {
    "P": ("purge", "$HASP250 {jn} PURGED"),
    "C": ("cancel", "$HASP890 {jn} CANCEL ACCEPTED"),
    "H": ("hold", "$HASP890 {jn} HELD"),
    "A": ("release", "$HASP890 {jn} RELEASED"),
    "E": ("release", "$HASP890 {jn} RELEASED FOR EXECUTION"),
    "O": ("release", "$HASP890 {jn} OUTPUT RELEASED"),
}


def _seed_demo_jobs(state, userid: str) -> None:
    """Populate the spool with a handful of jobs so the SDSF panels have rows
    the operator can act on (purge/cancel/hold/release actually change state)."""
    try:
        jes = state.jes
    except Exception:
        return
    if getattr(jes, "jobs", None):
        return
    try:
        from datetime import datetime
        from gibson.core.jes import Job, JobStatus, SpoolFile
    except Exception:
        return
    seed = [
        ("PAYROLL", userid, JobStatus.OUTPUT, 0),
        ("EMPMAINT", userid, JobStatus.HELD, 0),
        ("NIGHTBKP", "OPER", JobStatus.EXECUTION, 0),
        ("DB2BIND", userid, JobStatus.OUTPUT, 4),
        ("BADJOB", userid, JobStatus.FAILED, 12),
        ("CICSGIB1", "CICSUSER", JobStatus.ACTIVE, 0),
    ]
    for name, owner, status, rc in seed:
        try:
            jid = jes.next_jobid()
        except Exception:
            jid = f"JOB{len(jes.jobs) + 1:05d}"
        job = Job(jid, name, owner.upper(),
                  f"//{name} JOB (ACCT),CLASS=A,MSGCLASS=X\n//S1 EXEC PGM=IEFBR14",
                  status=status, rc=rc, message_class="A", job_class="A")
        if status in (JobStatus.OUTPUT, JobStatus.FAILED, JobStatus.HELD):
            job.ended = datetime.now()
        job.spool.append(SpoolFile("JESMSGLG",
                                   f"$HASP373 {name} STARTED - INIT 1 - CLASS A\n"
                                   f"$HASP395 {name} ENDED - RC={rc:04d}\n"))
        job.spool.append(SpoolFile("JESYSMSG",
                                   f"IEF142I {name} S1 - STEP WAS EXECUTED - COND CODE {rc:04d}\n"))
        jes.jobs[jid] = job


class Sdsf3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = (userid or "IBMUSER").upper()
        self.sdsf = SdsfApp(state, self.userid)
        self.panel_cmd: Optional[str] = None    # None == primary menu
        self.page = 0
        self.mode = "PANEL"                      # PANEL | OUTPUT | DIALOG
        self._message = ""
        self.lines: List[str] = []
        self._scroll: Optional[ScrollList] = None
        self._rows: List[SdsfRow] = []
        self._columns: List[str] = []
        self._title = ""
        self._dialog_target = ""
        _seed_demo_jobs(state, self.userid)

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        return self._render_panel()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        key = pi.key
        if self.mode == "OUTPUT":
            if key in ("PF3", "PF15"):
                self.mode = "PANEL"
                return self._render_panel()
            if key in ("PF7", "PF8", "PF10", "PF11") and self._scroll:
                self._scroll.scroll(key)
            return self._render_output()
        if self.mode == "DIALOG":
            return self._handle_dialog(pi)

        # PANEL mode
        if key in ("PF3", "PF15"):
            if self.panel_cmd is not None:
                self.panel_cmd = None
                self.page = 0
                self._message = ""
                return self._render_panel()
            return None  # leave SDSF
        if key in ("PF7", "PF8"):
            self._page(key)
            return self._render_panel()
        return self._process_panel_input(pi)

    # --------------------------------------------------------- panel input
    def _process_panel_input(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        # 1) per-row action characters typed in the NP fields
        acts = []
        for name, val in pi.fields.items():
            if name.startswith("NP") and val.strip():
                try:
                    acts.append((int(name[2:]), val.strip().upper()))
                except ValueError:
                    pass
        if acts:
            acts.sort()
            idx, act = acts[0]
            return self._apply_action(idx, act)

        # 2) command line
        cmd = pi.stripped("CMD")
        if not cmd:
            return self._render_panel()
        up = cmd.upper().strip()
        if up in ("=X", "RETURN"):
            self.panel_cmd = None
            self.page = 0
            return self._render_panel()
        if up == "/":
            # System Command Extension from the command line (Image 6)
            self._dialog_target = self.panel_cmd or "SYSTEM"
            self.mode = "DIALOG"
            return self._render_dialog()
        if up.startswith("/"):
            # '/<operator command>' entered directly on the command line runs
            # the MVS/JES command in one step (authentic SDSF), instead of the
            # two-step pop-up.  Shares the same backend + render as the dialog.
            out = self._run_system_command(cmd[1:].strip())
            if out and "\n" in out:
                self.lines = [l.rstrip() for l in text_to_lines(out)]
                self._scroll = ScrollList(self.lines, height=_BODY_ROWS)
                self.mode = "OUTPUT"
                return self._render_output(title="SYSTEM COMMAND RESPONSE")
            self._message = out or f"$HASP000 OK - '{cmd[1:].strip()[:24]}' accepted"
            return self._render_panel()
        if up in ("TOP", "BOTTOM", "BOT", "MAX", "M"):
            self.page = 0 if up == "TOP" else max(0, self._last_page())
            return self._render_panel()
        if up.startswith("S ") and self.panel_cmd:
            sel = up.split(None, 1)[1].strip()
            if sel.isdigit():
                return self._browse_row(int(sel))
        new_panel, message = self.sdsf.apply_sdsf_command(cmd)
        if new_panel is not None:
            self.panel_cmd = new_panel
            self.page = 0
        self._message = message or ""
        if self._message and "\n" in self._message:
            self.lines = [l.rstrip() for l in text_to_lines(self._message)]
            self._message = ""
            self._scroll = ScrollList(self.lines, height=_BODY_ROWS)
            self.mode = "OUTPUT"
            return self._render_output(title="SDSF OUTPUT")
        return self._render_panel()

    def _apply_action(self, idx: int, act: str) -> Optional[ScreenBuffer]:
        row_number = idx + 1
        # On the primary menu, S (or ENTER on the NP field) selects that panel.
        if self.panel_cmd is None:
            if idx < len(self._rows):
                name = self._rows[idx].cells.get("NAME", "")
                if name and (act.startswith("S") or act == ""):
                    self.panel_cmd = name
                    self.page = 0
                    self._message = ""
                    return self._render_panel()
            self._message = "ISF031I USE S TO SELECT A PANEL"
            return self._render_panel()
        target = None
        try:
            target = self.sdsf.row_target(self.panel_cmd, row_number)
        except Exception:
            target = None
        target = target or f"ROW {row_number}"
        if act.startswith("S"):
            return self._browse_row(row_number)
        if act.startswith("/"):
            self._dialog_target = target
            self.mode = "DIALOG"
            return self._render_dialog()
        # Real per-row job-state change against the JES spool.
        ja = _JES_ACTIONS.get(act[0])
        if ja and self.panel_cmd in _JOB_PANELS and not str(target).startswith("ROW"):
            method, msg = ja
            job = None
            try:
                job = self.state.jes.jobs.get(str(target).upper())
            except Exception:
                job = None
            jn = job.jobname if job else target
            ok = False
            try:
                ok = bool(getattr(self.state.jes, method)(target))
            except Exception:
                ok = False
            self._message = (msg.format(jn=jn) if ok
                             else f"ISF754I {target} NOT ELIGIBLE FOR {act[0]}")
            self.page = 0
            return self._render_panel()
        verb = _ACTIONS.get(act[0])
        if verb:
            self._message = f"{verb} for {target}"
        else:
            self._message = f"ISF031I ACTION '{act}' NOT VALID ON THIS PANEL"
        return self._render_panel()

    def _page(self, key: str) -> None:
        total = len(self._rows)
        last = max(0, (total - 1) // _PAGE)
        if key == "PF8":
            self.page = min(self.page + 1, last)
        else:
            self.page = max(0, self.page - 1)

    def _last_page(self) -> int:
        return max(0, (len(self._rows) - 1) // _PAGE)

    def _browse_row(self, row_number: int) -> Optional[ScreenBuffer]:
        try:
            target = self.sdsf.row_target(self.panel_cmd, row_number)
        except Exception:
            target = None
        if not target:
            self._message = f"ISF754I ROW {row_number} NOT AVAILABLE"
            return self._render_panel()
        try:
            text = self.sdsf.browse_job(target)
        except Exception as exc:
            text = f"ISF765I CANNOT BROWSE {target}: {exc}"
        self.lines = [l.rstrip() for l in text_to_lines(text)]
        self._scroll = ScrollList(self.lines, height=_BODY_ROWS)
        self.mode = "OUTPUT"
        return self._render_output(title=f"SDSF BROWSE {target}")

    # ------------------------------------------------------- panel sources
    def _load_panel(self):
        if self.panel_cmd is None:
            self._title = "SDSF MENU V2R5M0"
            self._columns = ["NP", "NAME", "Description", "Group", "Status"]
            self._rows = [SdsfRow({"NAME": i.command, "Description": i.description,
                                   "Group": i.group, "Status": i.status})
                          for i in self.sdsf.MENU_ITEMS]
            return "ACTION=S-Select"
        panel = self.sdsf.build_panel(self.panel_cmd)
        rows = self.sdsf._apply_filters(panel.rows, panel.columns)
        if self.sdsf.sort_column and self.sdsf.sort_column in panel.columns:
            rows = sorted(rows, key=lambda r: r.cells.get(self.sdsf.sort_column, ""))
        self._title = panel.title
        self._columns = list(panel.columns)
        self._rows = list(rows)
        return panel.action_help

    def _fmt(self, cells) -> str:
        widths = self.sdsf._widths(self._columns)
        parts = []
        for c in self._columns:
            if c == "NP":
                continue
            w = widths.get(c, 8)
            parts.append(f"{str(cells.get(c, '')):<{w}}"[:w])
        return " ".join(parts)[:75]

    # -------------------------------------------------------------- render
    def _render_panel(self) -> ScreenBuffer:
        action_help = self._load_panel()
        s = ScreenBuffer()
        s.extended_attributes = True
        now = datetime.datetime.now().strftime("%H:%M:%S")
        total = len(self._rows)
        last = max(0, (total - 1) // _PAGE)
        self.page = min(self.page, last)
        start = self.page * _PAGE
        end = min(total, start + _PAGE)
        is_jobs = (self.panel_cmd in _JOB_PANELS)

        s.put(1, 1, _ACTION_BAR, _WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        s.put(3, 1, f"SDSF {self._title}  GIBPLEX  MVSC {now}"[:55], colors.GREEN)
        s.put(3, 60, f"LINE {start + 1 if total else 0}-{end} ({total})"[:19], colors.GREEN)
        s.put(4, 1, "COMMAND INPUT ===>", _WHITE)
        s.add_field("CMD", 4, 20, 40, colour=_TURQ, role="command")
        s.put(4, 62, "SCROLL ===> CSR", colors.BLUE)
        body_top = 5
        if is_jobs:
            s.put(5, 1, (f"PREFIX={self.sdsf.prefix:<8} DEST={self.sdsf.dest:<8} "
                         f"OWNER={self.sdsf.owner:<8} SYSNAME={self.sdsf.sysname}")[:79], colors.GREEN)
            body_top = 6
        s.put(body_top, 1, action_help[:79], _TURQ)
        hdr = body_top + 1
        s.put(hdr, 1, "NP", colors.BLUE)
        s.put(hdr, 4, self._fmt({c: c for c in self._columns}), colors.BLUE)

        r = hdr + 1
        maxr = 21
        if total == 0:
            s.put(r, 4, "NO ROWS TO DISPLAY", colors.GREEN)
        for i in range(start, end):
            if r > maxr:
                break
            s.add_field(f"NP{i:02d}", r, 1, 2, colour=_TURQ, role="line_command")
            s.put(r, 4, self._fmt(self._rows[i].cells), colors.GREEN)
            r += 1

        s.put(22, 1, (f"Row {start + 1 if total else 0} of {total}").ljust(20), colors.BLUE)
        if self._message:
            s.put(22, 26, self._message[:53], colors.YELLOW)
        s.put(23, 1, ("F1=Help  F3=Exit  F5=Rfind  F7=Up  F8=Down  "
                      "F10=Left  F11=Right")[:79], colors.BLUE)
        s.put(24, 1, ("F9=Swap  F12=Cancel  PA2=Reshow    WHO  SET  SORT  FILTER")[:79], colors.BLUE)
        s.set_cursor(4, 20)
        return s

    def _render_output(self, title: str = "") -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        scroll = self._scroll or ScrollList(self.lines, height=_BODY_ROWS)
        s.put(1, 1, (title or "SDSF OUTPUT")[:79], _WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        scroll.render_into(s, 3, left=1, width=79, colour=colors.GREEN)
        s.put(23, 1, scroll.position_label.ljust(20), colors.BLUE)
        s.put(24, 1, "F3=Exit  F7=Up  F8=Down  F10=Left  F11=Right  PA2=Reshow", colors.BLUE)
        return s

    # -------------------------------------------------------------- dialog
    def _render_dialog(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, _ACTION_BAR, _WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        s.put(3, 1, f"SDSF {self._title}  GIBPLEX"[:55], colors.GREEN)
        bl, bw, top = 12, 56, 8
        bar = "+" + "-" * (bw - 2) + "+"
        s.put(top, bl, bar, _WHITE)
        s.put(top + 1, bl, ("|  System Command Extension").ljust(bw - 1) + "|", _WHITE)
        s.put(top + 2, bl, "|".ljust(bw - 1) + "|", _WHITE)
        s.put(top + 3, bl, "|  ===>", _WHITE)
        s.add_field("DLGCMD", top + 3, bl + 8, 42, colour=_TURQ, role="command")
        s.put(top + 4, bl, "|".ljust(bw - 1) + "|", _WHITE)
        s.put(top + 5, bl, (f"|  Target: {self._dialog_target}")[:bw - 1].ljust(bw - 1) + "|", colors.GREEN)
        s.put(top + 6, bl, ("|  Enter a system command, then press ENTER.").ljust(bw - 1) + "|", colors.TURQUOISE)
        s.put(top + 7, bl, ("|  Press PF3 to cancel.").ljust(bw - 1) + "|", colors.TURQUOISE)
        s.put(top + 8, bl, bar, _WHITE)
        s.put(24, 1, "ENTER=Run command   F3=Cancel", colors.BLUE)
        s.set_cursor(top + 3, bl + 8)
        return s

    def _handle_dialog(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF12", "PF15"):
            self.mode = "PANEL"
            self._message = "System command extension cancelled"
            return self._render_panel()
        cmd = pi.stripped("DLGCMD")
        if not cmd:
            self.mode = "PANEL"
            self._message = "No command entered"
            return self._render_panel()
        # Execute the operator command and show its response (authentic SDSF /).
        out = self._run_system_command(cmd)
        if out and "\n" in out:
            self.lines = [l.rstrip() for l in text_to_lines(out)]
            self._scroll = ScrollList(self.lines, height=_BODY_ROWS)
            self.mode = "OUTPUT"
            return self._render_output(title="SYSTEM COMMAND RESPONSE")
        self.mode = "PANEL"
        self._message = out or f"$HASP000 OK - '{cmd[:24]}' accepted"
        return self._render_panel()

    def _run_system_command(self, cmd: str) -> str:
        """Run an MVS/JES operator command entered via the / extension."""
        text = (cmd or "").strip()
        try:
            from gibson.apps.master_console import MasterConsoleController
            res = MasterConsoleController(self.state, self.userid).execute(text)
            out = getattr(res, "text", str(res))
            if out and out.strip():
                return out
        except Exception:
            pass
        # JES2 $-commands and anything the console didn't recognise: try SDSF engine.
        try:
            _panel, msg = self.sdsf.apply_sdsf_command(text)
            if msg and msg.strip():
                return msg
        except Exception:
            pass
        return f"$HASP000 {text[:40]} - no response"
