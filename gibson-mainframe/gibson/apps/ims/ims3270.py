"""IMS message-region terminal as a full-screen 3270 panel app (EBCDIC path).

Reached from VTAM via ``L IMS`` / ``LOGON APPLID(IMS1)`` on the TN3270 port.
Renders the IMS DFS terminal as a 3270 screen with a scrolling output area and a
command line, reusing :class:`ImsTerminalSession` for all logic (so the ASCII
and EBCDIC paths behave identically).  PF3 or ``/SIGN OFF`` returns to VTAM.
"""
from __future__ import annotations

import datetime
from typing import Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.ims.ims_terminal import ImsTerminalSession, _IMSID

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_WHITE = getattr(colors, "WHITE", colors.GREEN)
_BODY_ROWS = 16


class Ims3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.term = ImsTerminalSession(state, peer_addr=peer_addr)
        self._lines = [
            "DFS3650I  *** IMS/VS CONTROL REGION ***",
            f"DFS3650I  {_IMSID}  MESSAGE-REGION TERMINAL READY",
            "DFS3649A  /SIGN COMMAND REQUIRED FOR THIS TERMINAL",
            "",
            "Enter:  /SIGN ON userid password   then a transaction code.",
            "        /DIS A  display regions    /SIGN OFF  exit    /HELP",
        ]
        self._scroll = ScrollList(list(self._lines), height=_BODY_ROWS)
        self._message = ""

    def initial_screen(self) -> ScreenBuffer:
        return self._render()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        key = pi.key
        if key in ("PF3", "PF15"):
            return None
        if key in ("PF7", "PF8") and self._scroll is not None:
            self._scroll.scroll(key)
            return self._render()
        cmd = (pi.field("CMD", "") or "").strip()
        self._message = ""
        if cmd:
            self._lines.append(f"{(self.term.user or 'IMS')} > {cmd}")
            out = self.term.command(cmd)
            if out is None:
                self._lines.append("DFS058I  SIGN OFF COMPLETED")
                return None
            for ln in out.split("\n"):
                self._lines.append(ln)
            self._scroll = ScrollList(list(self._lines), height=_BODY_ROWS)
            self._scroll.bottom() if hasattr(self._scroll, "bottom") else None
        return self._render()

    def _render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        now = datetime.datetime.now().strftime("%H:%M:%S")
        who = self.term.user or "*NOT SIGNED ON*"
        s.put(1, 1, f"IMS/VS  {_IMSID}  MESSAGE TERMINAL", _WHITE)
        s.put(1, 56, now, colors.BLUE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        rows = self._scroll.visible() if self._scroll else self._lines[-_BODY_ROWS:]
        r = 3
        for ln in rows:
            if r > 3 + _BODY_ROWS:
                break
            s.put(r, 1, (ln or "")[:79], colors.GREEN)
            r += 1
        s.put(21, 1, f"SIGNED ON: {who}"[:50], colors.BLUE)
        if self._message:
            s.put(21, 52, self._message[:27], colors.YELLOW)
        s.put(22, 1, "COMMAND ===>", _WHITE)
        s.add_field("CMD", 22, 14, 60, colour=_TURQ, role="command")
        s.put(23, 1, "F3=Exit  F7=Up  F8=Down    /SIGN ON userid pw | trancode | /DIS A | /SIGN OFF", colors.BLUE)
        s.set_cursor(22, 14)
        return s
