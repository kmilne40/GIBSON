"""Gibson Office Mail - an ISPF-style electronic mail facility.

A self-contained sub-application (like EZRecon/SYSVIEW) launched from the ISPF
Management menu.  It presents a menu, four folders (Inbox, Sent, Important,
Spam), a note reader, a compose form, and a configuration panel that reads and
writes SYS1.EMAIL.  Sending uses SMTP, downloading uses POP3; both fall back
cleanly to the seeded local mailbox when no network is available.

The look is deliberately its own: a turquoise name-plate, yellow option numbers,
and colour-coded folders/flags - distinct from the standard green ISPF panels.
"""
from __future__ import annotations

from typing import List, Optional

from gibson.render.panels import PanelInput, PanelSession, ScrollList
from gibson.render.screen3270 import ScreenBuffer
from gibson.render import colors

from .mail_store import MailStore, Message, FOLDERS
from . import mail_transport as tx
from . import mail_calendar as cal

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_BTURQ = getattr(colors, "BRIGHT_TURQUOISE", _TURQ)
_BYEL = getattr(colors, "BRIGHT_YELLOW", colors.YELLOW)
_YEL = colors.YELLOW
_BLUE = colors.BLUE
_GRN = colors.GREEN
_RED = colors.RED
_WHT = colors.WHITE

_MENU, _LIST, _READ, _COMP, _CONF, _DIR, _CAL, _CALADD = (
    "MENU", "LIST", "READ", "COMP", "CONF", "DIR", "CAL", "CALADD")
_BODY_ROWS = 16


def _flag_colour(flag: str) -> str:
    return {"NEW": _BYEL, "SENT": _GRN}.get(flag, _TURQ)


class Mail3270Session(PanelSession):
    def __init__(self, state, peer_addr=None, userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr
        self.userid = (userid or "IBMUSER").upper()
        self.store = MailStore(state, self.userid)
        self.view = _MENU
        self.cur_folder = "INBOX"
        self.list_top = 0
        self.read_idx = 0
        self.read_scroll: Optional[ScrollList] = None
        self.comp_to = ""
        self.comp_subj = ""
        self.comp_body: List[str] = []
        self._calstore = None
        _t = cal.today_iso()
        self.cal_year = int(_t[0:4])
        self.cal_month = int(_t[5:7])
        self.cal_sel = _t            # selected day, YYYY-MM-DD
        self._message = "Select an option and press ENTER.  PF3=Exit"

    def _cal(self):
        if self._calstore is None:
            self._calstore = cal.CalendarStore(self.state, self.userid)
        return self._calstore

    # ---------------------------------------------------------------- chrome
    def _titlebar(self, s: ScreenBuffer, context: str) -> None:
        s.extended_attributes = True
        s.put(1, 2, "GIBSON OFFICE MAIL", _BTURQ, intensified=True)
        if context:
            s.put(1, 23, context, _WHT)
        s.put(1, 66, self.userid.ljust(8), _YEL)
        s.put(2, 1, "=" * 79, _BLUE)

    def _pf(self, s: ScreenBuffer, text: str) -> None:
        s.put(23, 2, self._message[:76], _YEL)
        s.put(24, 2, text[:77], _BLUE)

    def initial_screen(self) -> ScreenBuffer:
        self.view = _MENU
        return self._menu_panel()

    # ---------------------------------------------------------------- MENU
    def _menu_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        self._titlebar(s, "Main Menu")
        s.put(3, 2, "Option ===>", _GRN)
        s.add_field("OPTION", 3, 14, 3, value="", colour=_TURQ, role="option")
        opts = [
            ("1", "Read the inbox"),
            ("2", "Write a new note"),
            ("3", "Sent notes"),
            ("4", "Important"),
            ("5", "Spam / junk"),
            ("6", "Configure mail server (SYS1.EMAIL)"),
            ("7", "Poll the server"),
            ("8", "Directory"),
            ("9", "Calendar"),
        ]
        r = 5
        for num, label in opts:
            s.put(r, 5, num, _BYEL, intensified=True)
            s.put(r, 8, label, _TURQ)
            r += 1
        # status box on the right
        c = self.store.counts()
        cfg = self.store.config
        bx = 46
        s.put(5, bx, "+--- MAILBOX --------------+", _BLUE)
        s.put(6, bx, f"| Inbox     {c['INBOX']:>3}  new {self.store.new_count():>3} |", _GRN)
        s.put(7, bx, f"| Sent      {c['SENT']:>3}           |", _GRN)
        s.put(8, bx, f"| Important {c['IMPORTANT']:>3}           |", _YEL)
        s.put(9, bx, f"| Spam      {c['SPAM']:>3}           |", _RED)
        s.put(10, bx, "+--- SERVER ---------------+", _BLUE)
        s.put(11, bx, f"| SMTP {cfg.get('SMTP_HOST','')[:19]:<19} |", _TURQ)
        s.put(12, bx, f"| Recv {cfg.get('RECV_PROTO','')[:4]:<4} {cfg.get('IMAP_HOST', cfg.get('POP_HOST',''))[:13]:<13} |", _TURQ)
        s.put(13, bx, f"| from {cfg.get('FROM','')[:19]:<19} |", _TURQ)
        s.put(14, bx, "+--------------------------+", _BLUE)
        self._pf(s, "ENTER=Select   1-7=Option   PF3=Exit")
        s.set_cursor(3, 14)
        return s

    # ---------------------------------------------------------------- LIST
    def _list_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        msgs = self.store.folder(self.cur_folder)
        total = len(msgs)
        self._titlebar(s, f"{self.cur_folder}  ({total})")
        s.put(3, 2, "Select ===>", _GRN)
        s.add_field("SEL", 3, 14, 3, value="", colour=_TURQ, role="entry", numeric=True)
        s.put(3, 30, "(type a note number, ENTER to open)", _BLUE)
        s.put(4, 2, " #  FROM                  SUBJECT                      DATE        FLAG", _BTURQ)
        top = self.list_top
        row = 5
        for i in range(top, min(total, top + _BODY_ROWS)):
            m = msgs[i]
            line = (f"{i+1:>2}  {m.frm[:20]:<20}  {m.subj[:26]:<26}  {m.date[:11]:<11}")
            s.put(row, 2, line, _TURQ)
            s.put(row, 70, m.flag[:6], _flag_colour(m.flag))
            row += 1
        if total == 0:
            s.put(7, 6, "(no notes in this folder)", _BLUE)
        s.put(22, 2, f"Row {min(top+1, total)} of {total}", _BLUE)
        self._pf(s, "ENTER=Open  PF7/PF8=Scroll  PF3=Back to menu")
        s.set_cursor(3, 14)
        return s

    # ---------------------------------------------------------------- READ
    def _read_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        msgs = self.store.folder(self.cur_folder)
        if not (0 <= self.read_idx < len(msgs)):
            self.view = _LIST
            return self._list_panel()
        m = msgs[self.read_idx]
        self._titlebar(s, f"{self.cur_folder}  note {self.read_idx+1}/{len(msgs)}")
        s.put(3, 2, "From:", _GRN); s.put(3, 9, m.frm[:60], _TURQ)
        s.put(4, 2, "To:  ", _GRN); s.put(4, 9, m.to[:60], _TURQ)
        s.put(5, 2, "Subj:", _GRN); s.put(5, 9, m.subj[:50], _BTURQ, intensified=True)
        s.put(5, 62, m.date[:16], _BLUE)
        s.put(6, 1, "-" * 79, _BLUE)
        if self.read_scroll is None:
            self.read_scroll = ScrollList(m.body or ["(empty note)"], height=_BODY_ROWS - 1, top=0)
        self.read_scroll.render_into(s, 7, left=2, width=76, colour=_GRN)
        self._pf(s, "PF6=Reply PF5=Forward PF10=Important PF4=Delete PF7/8=Scroll PF3=Back")
        return s

    # ---------------------------------------------------------------- COMPOSE
    def _comp_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        self._titlebar(s, "Write a note")
        s.put(3, 2, "To   ===>", _GRN)
        s.add_field("TO", 3, 12, 50, value=self.comp_to, colour=_TURQ, role="entry")
        s.put(4, 2, "Subj ===>", _GRN)
        s.add_field("SUBJ", 4, 12, 50, value=self.comp_subj, colour=_TURQ, role="entry")
        s.put(5, 1, "-" * 79, _BLUE)
        s.put(6, 2, "Note text:", _BTURQ)
        for i in range(10):
            val = self.comp_body[i] if i < len(self.comp_body) else ""
            s.add_field(f"B{i:02d}", 7 + i, 2, 75, value=val, colour=_GRN, role="entry")
        self._pf(s, "PF6=Send   PF3=Cancel")
        s.set_cursor(3, 12)
        return s

    # ---------------------------------------------------------------- CONFIG
    def _conf_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        cfg = self.store.config
        self._titlebar(s, "Configure (SYS1.EMAIL)")
        s.put(3, 2, "SENDING (SMTP)", _BYEL)
        smtp_rows = [
            ("SMTP Host ", "SMTP_HOST", 30, False),
            ("SMTP Port ", "SMTP_PORT", 6, False),
            ("SMTP User ", "SMTP_USER", 44, False),
            ("SMTP Pass ", "SMTP_PASS", 30, True),
            ("From addr ", "FROM", 30, False),
            ("TLS mode  ", "TLS", 10, False),
            ("Creds B64 ", "CREDS_B64", 4, False),
        ]
        r = 4
        for label, key, w, hide in smtp_rows:
            s.put(r, 2, label + "===>", _GRN)
            s.add_field(key, r, 18, w, value=str(cfg.get(key, "")), colour=_TURQ,
                        role="entry", hidden=hide)
            r += 1
        s.put(r, 2, "RECEIVING (POP3 / IMAP)", _BYEL)
        r += 1
        recv_rows = [
            ("Protocol  ", "RECV_PROTO", 6, False),
            ("IMAP Host ", "IMAP_HOST", 30, False),
            ("IMAP Port ", "IMAP_PORT", 6, False),
            ("POP  Host ", "POP_HOST", 30, False),
            ("POP  Port ", "POP_PORT", 6, False),
            ("Recv User ", "RECV_USER", 44, False),
            ("Recv Pass ", "RECV_PASS", 30, True),
        ]
        for label, key, w, hide in recv_rows:
            s.put(r, 2, label + "===>", _GRN)
            s.add_field(key, r, 18, w, value=str(cfg.get(key, "")), colour=_TURQ,
                        role="entry", hidden=hide)
            r += 1
        s.put(r, 2, "TLS: NO/STARTTLS/SSL   Protocol: POP3/IMAP/NONE   B64: YES/NO", _BLUE)
        self._pf(s, "ENTER/PF6=Save to SYS1.EMAIL   PF3=Back")
        s.set_cursor(4, 18)
        return s

    # ---------------------------------------------------------------- routing
    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        key = pi.key
        if self.view == _MENU:
            if key in ("PF3", "PF15"):
                return None
            opt = (pi.stripped("OPTION") or "").strip()
            return self._menu_select(opt)
        if self.view == _LIST:
            return self._list_handle(pi)
        if self.view == _READ:
            return self._read_handle(pi)
        if self.view == _COMP:
            return self._comp_handle(pi)
        if self.view == _CONF:
            return self._conf_handle(pi)
        if self.view == _DIR:
            self.view = _MENU
            return self._menu_panel()
        if self.view == _CAL:
            return self._cal_handle(pi)
        if self.view == _CALADD:
            return self._caladd_handle(pi)
        return None

    def _menu_select(self, opt: str) -> ScreenBuffer:
        m = {"1": "INBOX", "3": "SENT", "4": "IMPORTANT", "5": "SPAM"}
        if opt in m:
            self.cur_folder = m[opt]; self.list_top = 0; self.view = _LIST
            return self._list_panel()
        if opt == "2":
            self.comp_to = self.comp_subj = ""; self.comp_body = []
            self.view = _COMP; self._message = "Compose a note, PF6 to send."
            return self._comp_panel()
        if opt == "6":
            self.view = _CONF; return self._conf_panel()
        if opt == "7":
            new, status = tx.poll(self.store.config)
            for msg in new:
                self.store.add("INBOX", msg)
            self._message = status
            return self._menu_panel()
        if opt == "8":
            self.view = _DIR
            return self._dir_panel()
        if opt == "9":
            self.view = _CAL
            return self._cal_panel()
        if opt:
            self._message = f"Invalid option '{opt}'.  Enter 1-9, or PF3 to exit."
        return self._menu_panel()

    def _dir_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        self._titlebar(s, "Directory")
        s.put(3, 2, "Internal users you can mail (from the RACF directory):", _GRN)
        users = self.store.internal_users()
        dom = self.store.config.get("INTERNAL_DOMAIN", "GIBSON.LOCAL")
        r = 5
        for u in users[: 16]:
            s.put(r, 5, u.ljust(10), _BTURQ)
            s.put(r, 18, f"{u.lower()}@{dom.lower()}", _TURQ)
            r += 1
        if not users:
            s.put(5, 5, "(no users found in the RACF directory)", _BLUE)
        s.put(r + 1, 2, "To send internally, put a userid (e.g. GUEST) in the To field.", _BLUE)
        s.put(r + 2, 2, f"Mail mode: {self.store.config.get('MAIL_MODE','BOTH')}   "
                        f"Internal domain: {dom}", _YEL)
        self._pf(s, "PF3=Back to menu")
        return s

    # ----------------------------------------------------------- calendar
    _MONTHS = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
    _DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def _cal_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        store = self._cal()
        y, m = self.cal_year, self.cal_month
        n = store.month_count(y, m)
        self._titlebar(s, f"Calendar  {self._MONTHS[m]} {y}")
        # weekday header (Sunday-first)
        hdr = "  Sun   Mon   Tue   Wed   Thu   Fri   Sat"
        s.put(3, 3, hdr, _BTURQ)
        marked = store.days_with_appts(y, m)
        sel_day = int(self.cal_sel[8:10]) if self.cal_sel.startswith(f"{y:04d}-{m:02d}-") else -1
        today = cal.today_iso()
        row = 4
        for week in cal.month_weeks(y, m):
            col = 3
            for d in week:
                if d != 0:
                    iso = f"{y:04d}-{m:02d}-{d:02d}"
                    colour = _BYEL if d in marked else _TURQ
                    inten = (d == sel_day)
                    cell = f"{d:>2}"
                    if iso == today:
                        cell = f"[{d:>2}]" if d >= 10 else f"[ {d}]"
                        s.put(row, col, cell, colour, intensified=True)
                    else:
                        mark = "*" if d in marked else " "
                        s.put(row, col + 1, f"{d:>2}{mark}", colour, intensified=inten)
                col += 6
            row += 1
        # selected-day appointments
        s.put(row + 1, 2, "-" * 77, _BLUE)
        day_appts = store.for_day(self.cal_sel)
        try:
            import datetime as _dt
            dd = _dt.date.fromisoformat(self.cal_sel)
            label = f"{self._DOW[dd.weekday()]} {dd.day:02d} {self._MONTHS[dd.month]} {dd.year}"
        except Exception:
            label = self.cal_sel
        s.put(row + 2, 2, f"Appointments on {label}:", _GRN)
        ar = row + 3
        if day_appts:
            for a in day_appts[:4]:
                s.put(ar, 4, f"{a.time:<6}", _BYEL)
                s.put(ar, 11, a.desc[:60], _TURQ)
                ar += 1
        else:
            s.put(ar, 4, "(no appointments \u2014 PF6 to add one)", _BLUE)
        # day selector field
        s.add_field("DAY", 21, 16, 4, value="", colour=_TURQ, role="entry", numeric=True)
        s.put(21, 2, "Go to day ===>", _GRN)
        s.put(21, 30, f"({n} this month)", _BLUE)
        self._message = f"Calendar for {self._MONTHS[m]} {y}."
        self._pf(s, "PF7=Prev mon  PF8=Next mon  PF6=Add  ENTER=go to day  PF3=Back")
        s.set_cursor(21, 16)
        return s

    def _cal_handle(self, pi: PanelInput) -> ScreenBuffer:
        if pi.key in ("PF3", "PF15"):
            self.view = _MENU
            return self._menu_panel()
        if pi.key in ("PF7",):
            self.cal_month -= 1
            if self.cal_month < 1:
                self.cal_month = 12; self.cal_year -= 1
            return self._cal_panel()
        if pi.key in ("PF8",):
            self.cal_month += 1
            if self.cal_month > 12:
                self.cal_month = 1; self.cal_year += 1
            return self._cal_panel()
        if pi.key in ("PF6",):
            self.view = _CALADD
            return self._caladd_panel()
        # ENTER: select a day in the displayed month
        day = (pi.field("DAY", "") or "").strip()
        if day.isdigit():
            d = int(day)
            import calendar as _c
            last = _c.monthrange(self.cal_year, self.cal_month)[1]
            if 1 <= d <= last:
                self.cal_sel = f"{self.cal_year:04d}-{self.cal_month:02d}-{d:02d}"
            else:
                self._message = f"Day must be 1-{last} for this month."
        return self._cal_panel()

    def _caladd_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        self._titlebar(s, "Calendar  Add Appointment")
        # default the date to the selected day, shown DD/MM/YYYY
        try:
            y, m, d = self.cal_sel.split("-")
            default_date = f"{d}/{m}/{y}"
        except Exception:
            default_date = ""
        s.put(4, 4, "Date (DD/MM/YYYY) ===>", _GRN)
        s.add_field("ADATE", 4, 27, 10, value=default_date, colour=_TURQ, role="entry")
        s.put(6, 4, "Time (HH:MM)      ===>", _GRN)
        s.add_field("ATIME", 6, 27, 5, value="", colour=_TURQ, role="entry")
        s.put(8, 4, "Description       ===>", _GRN)
        s.add_field("ADESC", 8, 27, 48, value="", colour=_TURQ, role="entry")
        s.put(10, 4, "Stored in your private calendar (" + self.userid + ".MAIL.CALENDAR).", _BLUE)
        self._message = "Fill in the appointment and press PF6 to save."
        self._pf(s, "PF6=Save   PF3=Cancel")
        s.set_cursor(4, 27)
        return s

    def _caladd_handle(self, pi: PanelInput) -> ScreenBuffer:
        if pi.key in ("PF3", "PF15"):
            self.view = _CAL
            return self._cal_panel()
        if pi.key in ("PF6",):
            raw_date = (pi.field("ADATE", "") or "").strip()
            time_str = (pi.field("ATIME", "") or "").strip()
            desc = (pi.field("ADESC", "") or "").strip()
            iso = self._parse_date(raw_date)
            if not iso:
                self._message = "Date must be DD/MM/YYYY."
                return self._caladd_panel()
            if not desc:
                self._message = "Enter a description for the appointment."
                return self._caladd_panel()
            self._cal().add(iso, time_str, desc)
            self.cal_sel = iso
            self.cal_year = int(iso[0:4]); self.cal_month = int(iso[5:7])
            self._message = f"Appointment saved for {raw_date}."
            self.view = _CAL
            return self._cal_panel()
        return self._caladd_panel()

    @staticmethod
    def _parse_date(raw: str):
        raw = (raw or "").strip().replace("-", "/").replace(".", "/")
        parts = raw.split("/")
        if len(parts) != 3:
            return None
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
            import datetime as _dt
            return _dt.date(y, m, d).isoformat()
        except Exception:
            return None

    def _list_handle(self, pi: PanelInput) -> ScreenBuffer:
        if pi.key in ("PF3", "PF15"):
            self.view = _MENU; return self._menu_panel()
        msgs = self.store.folder(self.cur_folder)
        if pi.key in ("PF8", "PF11"):
            if self.list_top + _BODY_ROWS < len(msgs):
                self.list_top += _BODY_ROWS
            return self._list_panel()
        if pi.key in ("PF7", "PF10"):
            self.list_top = max(0, self.list_top - _BODY_ROWS)
            return self._list_panel()
        sel = (pi.stripped("SEL") or "").strip()
        if sel.isdigit():
            idx = int(sel) - 1
            if 0 <= idx < len(msgs):
                self.read_idx = idx; self.read_scroll = None
                self.store.mark_read(self.cur_folder, idx)
                self.view = _READ; return self._read_panel()
            self._message = f"No note {sel} in {self.cur_folder}."
        return self._list_panel()

    def _read_handle(self, pi: PanelInput) -> ScreenBuffer:
        msgs = self.store.folder(self.cur_folder)
        if pi.key in ("PF3", "PF15"):
            self.view = _LIST; return self._list_panel()
        if pi.key in ("PF8", "PF11") and self.read_scroll:
            self.read_scroll.page_down(); return self._read_panel()
        if pi.key in ("PF7",):
            if self.read_scroll: self.read_scroll.page_up()
            return self._read_panel()
        if not (0 <= self.read_idx < len(msgs)):
            self.view = _LIST; return self._list_panel()
        m = msgs[self.read_idx]
        if pi.key in ("PF6",):   # reply
            self.comp_to = m.frm
            self.comp_subj = m.subj if m.subj.upper().startswith("RE:") else f"Re: {m.subj}"
            self.comp_body = ["", "", "----- original note -----"] + list(m.body)
            self.view = _COMP; self._message = "Reply - edit and PF6 to send."
            return self._comp_panel()
        if pi.key in ("PF5",):   # forward
            self.comp_to = ""
            self.comp_subj = f"Fw: {m.subj}"
            self.comp_body = ["", "", "----- forwarded note -----", f"From: {m.frm}"] + list(m.body)
            self.view = _COMP; self._message = "Forward - set a recipient and PF6."
            return self._comp_panel()
        if pi.key in ("PF10",):  # mark important
            if self.cur_folder != "IMPORTANT":
                self.store.move(self.cur_folder, self.read_idx, "IMPORTANT")
                self._message = "Moved to IMPORTANT."
                self.view = _LIST; return self._list_panel()
            self._message = "Already in IMPORTANT."
            return self._read_panel()
        if pi.key in ("PF4",):   # delete -> spam/trash
            self.store.delete(self.cur_folder, self.read_idx)
            self._message = "Note deleted (moved to SPAM)."
            self.view = _LIST; return self._list_panel()
        # PF10 is used for both scroll-up and important above; default redisplay
        return self._read_panel()

    def _comp_handle(self, pi: PanelInput) -> ScreenBuffer:
        # capture current field contents
        self.comp_to = (pi.field("TO", self.comp_to) or "").strip()
        self.comp_subj = (pi.field("SUBJ", self.comp_subj) or "").strip()
        body = [(pi.field(f"B{i:02d}", "") or "").rstrip() for i in range(10)]
        while body and body[-1] == "":
            body.pop()
        self.comp_body = body
        if pi.key in ("PF3", "PF15"):
            self.view = _MENU; return self._menu_panel()
        if pi.key in ("PF6",):
            if not self.comp_to:
                self._message = "Enter a recipient in the To field."
                return self._comp_panel()
            from .mail_store import _now
            cfg = self.store.config
            mode = str(cfg.get("MAIL_MODE", "BOTH")).upper()
            frm_disp = self.userid
            internal, external = [], []
            for r in [x.strip() for x in self.comp_to.split(",") if x.strip()]:
                kind, who = self.store.classify(r)
                (internal if kind == "internal" else external).append(who)
            statuses = []
            if internal and mode in ("INTERNAL", "BOTH"):
                for u in internal:
                    ok = self.store.deliver_internal(
                        u, Message(frm_disp, u, self.comp_subj or "(no subject)",
                                   _now(), "NEW", list(self.comp_body)))
                    statuses.append(f"DELIVERED TO {u}" if ok else f"FAILED {u}")
            if internal and mode == "EXTERNAL":
                statuses.append("INTERNAL BLOCKED (MAIL_MODE=EXTERNAL)")
            if external and mode in ("EXTERNAL", "BOTH"):
                ok, status = tx.send_smtp(cfg, ",".join(external),
                                          self.comp_subj, self.comp_body)
                statuses.append(status)
            if external and mode == "INTERNAL":
                statuses.append("EXTERNAL BLOCKED (MAIL_MODE=INTERNAL)")
            # always keep a copy in our own SENT
            self.store.sent(Message(cfg.get("FROM", frm_disp), self.comp_to,
                                    self.comp_subj or "(no subject)", _now(),
                                    "SENT", list(self.comp_body)))
            self._message = (" | ".join(statuses) or "NOTHING SENT")[:76]
            self.comp_to = self.comp_subj = ""; self.comp_body = []
            self.view = _MENU; return self._menu_panel()
        return self._comp_panel()

    def _conf_handle(self, pi: PanelInput) -> ScreenBuffer:
        if pi.key in ("PF3", "PF15"):
            self.view = _MENU; return self._menu_panel()
        keys = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "FROM", "TLS",
                "CREDS_B64", "RECV_PROTO", "IMAP_HOST", "IMAP_PORT", "POP_HOST",
                "POP_PORT", "RECV_USER", "RECV_PASS")
        cfg = {key: (pi.field(key, "") or "").strip() for key in keys}
        ok = self.store.save_config(cfg)
        self._message = ("Configuration saved to SYS1.EMAIL." if ok
                         else "Saved in this session (SYS1.EMAIL not writable).")
        if pi.key in ("PF6",):
            self.view = _MENU; return self._menu_panel()
        return self._conf_panel()
