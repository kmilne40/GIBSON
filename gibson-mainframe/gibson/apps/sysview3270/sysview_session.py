"""CA SYSVIEW Performance & Operations Monitor - full-screen 3270 session.

The line-mode SYSVIEW engine (``gibson.apps.sysview_engine``) supplies the panel
content; this module renders it as an authentic full-screen 3270 application so
SYSVIEW is fully usable over the EBCDIC/TN3270 path (x3270), with a primary
option menu, a COMMAND line, PF-key navigation and scrolling.  It is launched
from the ISPF primary menu as option SV and PF3 returns to ISPF.
"""
from __future__ import annotations

import datetime
from typing import Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.sysview_engine import sysview_command

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_WHITE = getattr(colors, "WHITE", colors.GREEN)
_BODY_ROWS = 15

# option code -> (menu title, engine topic)
_PANELS = [
    ("1", "System Overview",          "SYSTEM"),
    ("2", "Active Jobs / Address Spaces", "JOBS"),
    ("3", "CICS Region Monitor",      "CICS"),
    ("4", "DB2 Subsystem Monitor",    "DB2"),
    ("5", "TCP/IP Service Summary",   "TCPIP"),
    ("6", "USS Process Summary",      "USS"),
    ("7", "Storage and CPU",          "STORAGE"),
    ("8", "Alerts and Thresholds",    "ALERTS"),
    ("9", "CPU Detail",               "CPU"),
    ("A", "RSS Task",                 "RSS"),
    ("B", "Dataset / Spool Activity", "DATASETS"),
]
_TOPIC_BY_CODE = {c: t for c, _, t in _PANELS}
_TITLE_BY_TOPIC = {t: ttl for c, ttl, t in _PANELS}
_VALID = {t for _, _, t in _PANELS} | {"MENU", "LOG", "REFRESH", "STATUS", "THRESHOLDS", "SPOOL"}


class Sysview3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = (userid or "IBMUSER").upper()
        self.mode = "MENU"          # MENU | PANEL
        self.topic = "MENU"
        self._scroll: Optional[ScrollList] = None
        self._message = ""

    # ----------------------------------------------------------------- entry
    def initial_screen(self) -> ScreenBuffer:
        return self._render()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        key = pi.key
        if key in ("PF3", "PF15"):
            if self.mode == "PANEL":
                self.mode = "MENU"; self.topic = "MENU"; self._scroll = None; self._message = ""
                return self._render()
            return None             # leave SYSVIEW -> back to ISPF
        if key in ("PF7", "PF8", "PF10", "PF11") and self._scroll is not None:
            self._scroll.scroll(key)
            return self._render()
        cmd = (pi.field("CMD", "") or "").strip().upper()
        self._message = ""
        if cmd:
            if cmd.startswith("SYSVIEW "):
                cmd = cmd.split(None, 1)[1].strip()
            if cmd in ("=X", "EXIT", "END", "RETURN", "=0"):
                return None
            topic = _TOPIC_BY_CODE.get(cmd, cmd if cmd in _VALID else None)
            if topic is None:
                self._message = f"INVALID OPTION/COMMAND '{cmd}'"
                return self._render()
            if topic in ("MENU",):
                self.mode = "MENU"; self.topic = "MENU"; self._scroll = None
            elif topic == "REFRESH":
                if self.mode == "PANEL":
                    self._load_topic(self.topic)
                self._message = "REFRESHED"
            else:
                self.topic = topic
                self.mode = "PANEL"
                self._load_topic(topic)
        return self._render()

    # --------------------------------------------------------------- content
    def _load_topic(self, topic: str) -> None:
        body = sysview_command(self.state, self.userid, f"SYSVIEW {topic}") or ""
        lines = [l.rstrip() for l in text_to_lines(body)]
        self._scroll = ScrollList(lines, height=_BODY_ROWS)

    # ---------------------------------------------------------------- render
    def _render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        now = datetime.datetime.now().strftime("%H:%M:%S")
        title = ("PRIMARY OPTION MENU" if self.mode == "MENU"
                 else _TITLE_BY_TOPIC.get(self.topic, self.topic))
        s.put(1, 1, "SYSVIEW   Display  Monitor  Action  Filter  Options  Help", _WHITE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        s.put(3, 1, f"CA SYSVIEW 15.0   GIBSON   LPAR SIM1   {title}"[:58], colors.GREEN)
        s.put(3, 60, f"{now}", colors.GREEN)
        s.put(4, 1, "COMMAND ===>", _WHITE)
        s.add_field("CMD", 4, 14, 46, colour=_TURQ, role="command")
        s.put(4, 62, "SCROLL ===> CSR", colors.BLUE)

        if self.mode == "MENU":
            s.put(6, 3, "Select an option, or enter a command on the COMMAND line:", _TURQ)
            r = 8
            for code, ttl, _ in _PANELS:
                s.put(r, 5, code, colors.YELLOW)
                s.put(r, 9, ttl, colors.GREEN)
                r += 1
            s.put(r + 1, 3, "Cmds: SYSTEM JOBS CICS DB2 TCPIP USS STORAGE CPU ALERTS RSS DATASETS", colors.BLUE)
            s.put(r + 2, 3, "      LOG  REFRESH    (mode SIMULATED - Gibson-owned resources only)", colors.BLUE)
        else:
            rows = self._scroll.visible() if self._scroll else []
            r = 6
            for ln in rows:
                if r > 21:
                    break
                s.put(r, 2, ln[:78], colors.GREEN)
                r += 1
            if self._scroll is not None:
                total = len(self._scroll.items)
                s.put(22, 1, f"Row {self._scroll.top + 1} of {total}".ljust(20), colors.BLUE)

        if self._message:
            s.put(22, 26, self._message[:53], colors.YELLOW)
        s.put(23, 1, "F1=Help  F3=Exit  F7=Up  F8=Down  F12=Cancel", colors.BLUE)
        s.put(24, 1, "Enter SYSVIEW command or option number above", colors.BLUE)
        s.set_cursor(4, 14)
        return s
