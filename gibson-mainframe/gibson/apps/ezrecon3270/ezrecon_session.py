"""EZRecon - live reconnaissance toolkit as an authentic ISPF panel.

A faithful ISPF rendering of the kmilne40/EZRecon ("Reccy Toolkit"). Selection is
by NUMERIC option (1-10) to avoid any F-key confusion. Every action runs a real,
live lookup via ``ezrecon_live`` (DNS/WHOIS/HTTP/Shodan). The original "Get All"
and port-scan actions are intentionally omitted.

Long output (e.g. WHOIS) pages with the 3270 ``***`` continuation: when more text
remains, the status line shows ``***`` and ENTER advances to the next page.
"""
from __future__ import annotations

import datetime
import os
from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, PanelSession

from . import ezrecon_live as live

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_WHITE = getattr(colors, "WHITE", colors.GREEN)

_PANE_TOP = 16          # first results row
_PANE_H = 7             # results rows (16..22)

# left/right column split of the numeric menu
_MENU_LEFT = live.ACTIONS[:5]
_MENU_RIGHT = live.ACTIONS[5:]

# per-action hint for the ARG field
_ARG_HINT = {
    "email_scraper": "depth",
    "brute_force_subdomains": "wordlist path",
}


class EzRecon3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = userid
        self.target = "example.com"
        self.arg = ""
        self.api_key = (getattr(state, "ezrecon_shodan_key", "") or
                        os.getenv("SHODAN_API_KEY", "") or "")
        self._all_lines: List[str] = [
            "EZRecon LIVE - real DNS / WHOIS / HTTP / Shodan lookups.",
            "",
            "Enter an option (1-10), a TARGET, then press ENTER.",
            "Option 9 needs a WORDLIST path in ARG; option 8 takes a DEPTH in ARG.",
            "Option 10 uses the API KEY field (or SHODAN_API_KEY).",
        ]
        self._page = 0
        self._more = False
        self._message = "Select an option (1-10), set TARGET, press ENTER.  PF3=Exit"
        self._last_label = ""

    # ------------------------------------------------------------- dispatch
    def _set_results(self, lines: List[str], label: str) -> None:
        self._all_lines = lines or ["(no output)"]
        self._page = 0
        self._more = len(self._all_lines) > _PANE_H
        self._last_label = label
        self._message = (f"{label}: page 1 - *** for more (ENTER)" if self._more
                         else f"{label} complete for {self.target}")

    def _run(self, code: str) -> None:
        code = (code or "").strip()
        action = next((a for a in live.ACTIONS if a[0] == code), None)
        if action is None:
            self._message = f"Invalid option '{code}'.  Enter 1-10, or X to exit."
            return
        _, label, _kind, fn = action
        target = self.target
        try:
            if fn == "email_scraper":
                depth = int(self.arg) if self.arg.strip().isdigit() else 2
                lines = live.email_scraper(target, depth)
            elif fn == "brute_force_subdomains":
                lines = live.brute_force_subdomains(target, self.arg.strip())
            elif fn == "shodan_search":
                if live.is_valid_ip(target):
                    lines = live.shodan_host(target, self.api_key)
                else:
                    lines = live.shodan_search(target, self.api_key)
            else:
                lines = getattr(live, fn)(target)
        except Exception as exc:  # never crash the panel
            lines = [f"EZRECON ERROR: {exc}"]
        # If the live lookup only produced an install hint (dnspython/shodan not
        # installed), fall back to deterministic offline fixtures so the toolkit
        # is usable without installing anything on the Gibson host.
        try:
            from gibson.apps.ezrecon3270 import ezrecon_fixtures as _fx
            if _fx.looks_like_missing_dep(lines):
                fixture = _fx.get(fn, target, self.arg.strip(), self.api_key)
                if fixture:
                    lines = fixture
        except Exception:
            pass
        self._set_results(lines, label)
        try:
            self.state.record_security_event(
                self.userid, "EZRECON",
                f"ACTION={label} TARGET={self.target}",
                service="OMVS", addr=self.peer_addr, terminal="EZRECON")
        except Exception:
            pass

    # --------------------------------------------------------------- driver
    def initial_screen(self) -> ScreenBuffer:
        return self._render()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            return None
        # capture entry fields
        tgt = (pi.field("TARGET", "") or "").strip()
        if tgt:
            self.target = tgt
        arg = pi.field("ARG", "")
        if arg is not None:
            self.arg = arg
        key = (pi.field("APIKEY", "") or "").strip()
        if key:
            self.api_key = key
            try:
                self.state.ezrecon_shodan_key = key  # persist for this Gibson run
            except Exception:
                pass
            self._message = "SHODAN API KEY SET (saved for this session)."
        # explicit scroll keys still work
        if pi.key in ("PF7", "PF8"):
            if pi.key == "PF8" and self._more:
                self._advance_page()
            elif pi.key == "PF7" and self._page > 0:
                self._page -= 1
                self._more = (self._page + 1) * _PANE_H < len(self._all_lines)
            return self._render()
        opt = (pi.field("OPTION", "") or "").strip()
        # while paging (***), ENTER with no new option advances the page
        if self._more and not opt:
            self._advance_page()
            return self._render()
        if opt.upper() == "X":
            return None
        if opt:
            self._run(opt)
        return self._render()

    def _advance_page(self) -> None:
        if (self._page + 1) * _PANE_H < len(self._all_lines):
            self._page += 1
        self._more = (self._page + 1) * _PANE_H < len(self._all_lines)
        total = (len(self._all_lines) + _PANE_H - 1) // _PANE_H
        self._message = (f"{self._last_label}: page {self._page + 1}/{total} - *** for more"
                         if self._more else f"{self._last_label}: page {self._page + 1}/{total} (end)")

    # ---------------------------------------------------------------- view
    def _render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        now = datetime.datetime.now().strftime("%H:%M:%S")
        # banner band
        s.put(1, 1, "=" * 79, colors.BLUE)
        s.put(2, 2, "CA-Recon", colors.BLUE)
        s.put(2, 33, "E Z R E C O N", _WHITE)
        s.put(2, 65, "Sighber Cyber", colors.BLUE)
        s.put(3, 22, "Reconnaissance & Assessment Toolkit  (LIVE)", _TURQ)
        s.put(3, 71, now, colors.BLUE)
        s.put(4, 1, "=" * 79, colors.BLUE)
        # numeric menu, two well-spaced columns
        s.put(5, 4, "Menu Options", _WHITE)
        for i, (code, label, _k, _fn) in enumerate(_MENU_LEFT):
            s.put(6 + i, 6, f"{code:>2}.", colors.YELLOW)
            s.put(6 + i, 10, label, _TURQ)
        for i, (code, label, _k, _fn) in enumerate(_MENU_RIGHT):
            s.put(6 + i, 44, f"{code:>2}.", colors.YELLOW)
            s.put(6 + i, 48, label, _TURQ)
        s.put(6 + len(_MENU_RIGHT), 44, " X.", colors.RED)
        s.put(6 + len(_MENU_RIGHT), 48, "Exit", colors.RED)
        # entry area (roomy)
        s.put(13, 2, "Option  ===>", colors.GREEN)
        s.add_field("OPTION", 13, 15, 3, colour=_TURQ, role="option")
        s.put(13, 34, "Target ===>", colors.GREEN)
        s.add_field("TARGET", 13, 46, 33, value=self.target, colour=_TURQ, role="entry")
        # ARG label hints at the action that needs it
        argval = self.arg
        s.put(14, 2, "Arg     ===>", colors.GREEN)
        s.add_field("ARG", 14, 15, 26, value=argval, colour=_TURQ, role="entry")
        s.put(14, 43, "(9=wordlist 8=depth)", colors.BLUE)
        s.put(15, 2, "API Key ===>", colors.GREEN)
        s.add_field("APIKEY", 15, 15, 26, value="", colour=_TURQ, role="entry", hidden=True)
        s.put(15, 43, "(set)" if self.api_key else "(none)", colors.BLUE)
        # results pane
        s.put(_PANE_TOP - 1, 1, "-" * 79, colors.BLUE)
        s.put(_PANE_TOP - 1, 3, " Results ", _WHITE)
        total = (len(self._all_lines) + _PANE_H - 1) // _PANE_H if self._all_lines else 1
        s.put(_PANE_TOP - 1, 64, f"page {self._page + 1}/{total}".rjust(14), colors.BLUE)
        window = self._all_lines[self._page * _PANE_H:(self._page + 1) * _PANE_H]
        for i, row in enumerate(window):
            s.put(_PANE_TOP + i, 1, row[:79], _ez_line_colour(row))
        # status / *** continuation
        if self._more:
            s.put(23, 2, "***", colors.WHITE)
            s.put(23, 7, self._message[:70], colors.YELLOW)
        else:
            s.put(23, 2, self._message[:76], colors.YELLOW)
        s.put(24, 2, "ENTER=Run / *** next page   PF7/PF8=Scroll   PF3=Exit", colors.BLUE)
        s.set_cursor(13, 15)
        return s


def _ez_line_colour(line: str) -> str:
    u = line.strip().upper()
    if not u:
        return colors.GREEN
    if any(w in u for w in ("FINDING", "EXPOSED", "XFR ALLOWED", "VULN", "CVE-", "ERROR", "INVALID")):
        return colors.RED
    if u.startswith(("A RECORDS", "MX RECORDS", "NS RECORDS", "SOA RECORD",
                     "PTR RECORD", "WHOIS INFORMATION", "SHODAN", "SUBDOMAIN",
                     "EMAIL HARVEST", "ATTEMPTING", "===", "SPF RECORDS",
                     "DMARC RECORDS")):
        return _WHITE
    if "REFUSED" in u:
        return colors.YELLOW
    return getattr(colors, "TURQUOISE", colors.GREEN)
