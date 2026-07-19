"""z/TPF prime CRAS terminal as a full-screen 3270 panel app (EBCDIC path).

Reached from VTAM via ``L TPF`` on the TN3270 port.  Renders the CRAS console as
a 3270 screen with a scrolling output area and a command line, reusing
:class:`ZtpfTerminalSession` for all logic.  PF3 or ``OFF`` returns to VTAM.
"""
from __future__ import annotations

import datetime
from typing import Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.ztpf.ztpf_terminal import ZtpfTerminalSession, _BANNER
from gibson.apps.ztpf.ztpf_engine import get_ztpf_state

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_WHITE = getattr(colors, "WHITE", colors.GREEN)
_BODY = 16


class Ztpf3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.term = ZtpfTerminalSession(state, peer_addr=peer_addr)
        st = get_ztpf_state(state)
        self._lines = [
            _BANNER,
            f"CPU-{st.cpu} SS-BSS  SYSTEM STATE {st.sys_state}  ONLINE {'YES' if st.online else 'NO'}",
            "CSMP0097I PRIME CRAS READY - ENTER Z-MESSAGE OR TRANSACTION",
            "          (ZSTAT ZDLOK ZDPGM ZACES ZTPTRACE ZLINE ZNETW ZPERF; ZDORD CC01 1; ZLAB lab; AVL DFWLAX; AUTH pan amt; OFF)",
        ]
        self._scroll = ScrollList(list(self._lines), height=_BODY)

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
        if cmd:
            self._lines.append(f"TPF > {cmd}")
            out = self.term.command(cmd)
            if out is None:
                self._lines.append("CSMP0096I CRAS TERMINAL SESSION ENDED")
                return None
            self._lines.extend(out.split("\n"))
            self._scroll = ScrollList(list(self._lines), height=_BODY)
            if hasattr(self._scroll, "bottom"):
                self._scroll.bottom()
        return self._render()

    def _render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        now = datetime.datetime.now().strftime("%H:%M:%S")
        st = get_ztpf_state(self.state)
        s.put(1, 1, f"z/TPF  PRIME CRAS   CPU-{st.cpu}  STATE {st.sys_state}", _WHITE)
        s.put(1, 60, now, colors.BLUE)
        s.put(2, 1, "-" * 79, colors.BLUE)
        rows = self._scroll.visible() if self._scroll else self._lines[-_BODY:]
        r = 3
        for ln in rows:
            if r > 3 + _BODY:
                break
            s.put(r, 1, (ln or "")[:79], colors.GREEN)
            r += 1
        s.put(21, 1, f"ECBS DISPATCHED: {len(st.ecbs)}   ONLINE: {'YES' if st.online else 'NO'}"[:50], colors.BLUE)
        s.put(22, 1, "ENTER ===>", _WHITE)
        s.add_field("CMD", 22, 12, 62, colour=_TURQ, role="command")
        s.put(23, 1, "F3=Exit  F7=Up  F8=Down   Z-message | transaction | OFF", colors.BLUE)
        s.set_cursor(22, 12)
        return s
