"""ISPF split-screen (F2=Split / F9=Swap).

Real ISPF lets a user run two independent logical sessions on one terminal.
This manager provides that workflow in a swap-based form: F2 starts (or
re-activates) a second logical ISPF session, F9 swaps focus between the two.
Each logical session keeps fully independent state (its own panel stack,
DSLIST, editor, etc.).  The focused session occupies the screen; the other is
retained verbatim and redisplayed on swap.

It exposes the same ``initial_screen()`` / ``handle()`` contract as a single
``Ispf3270Session`` so it drops into the existing dispatch unchanged.
"""
from __future__ import annotations

from typing import List, Optional

from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput
from gibson.apps.ispf3270.ispf_session import Ispf3270Session

_MAX_LOGICAL = 2


class IspfSplitManager:
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self._args = (state, peer_addr, userid)
        self.sessions: List[Ispf3270Session] = [self._new()]
        self.last: List[Optional[ScreenBuffer]] = [None, None]
        self.active = 0

    def _new(self) -> Ispf3270Session:
        state, peer_addr, userid = self._args
        return Ispf3270Session(state, peer_addr=peer_addr, userid=userid)

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        s = self.sessions[0].initial_screen()
        self.last[0] = s
        return s

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        key = getattr(pi, "key", "")

        if key == "PF2":  # Split: start the second logical screen, or swap to it
            if len(self.sessions) < _MAX_LOGICAL:
                self.sessions.append(self._new())
                self.active = len(self.sessions) - 1
                s = self.sessions[self.active].initial_screen()
                self.last[self.active] = s
                return s
            self.active = 1 - self.active
            return self._reshow()

        if key == "PF9":  # Swap focus between the two logical screens
            if len(self.sessions) >= _MAX_LOGICAL:
                self.active = 1 - self.active
            return self._reshow()

        screen = self.sessions[self.active].handle(pi)
        if screen is None:
            # the focused logical session ended
            if len(self.sessions) >= _MAX_LOGICAL:
                del self.sessions[self.active]
                del self.last[self.active]
                self.last.append(None)
                self.active = 0
                return self._reshow()
            return None  # the only logical session ended -> leave ISPF
        self.last[self.active] = screen
        return screen

    def _reshow(self) -> ScreenBuffer:
        s = self.last[self.active]
        if s is None:
            s = self.sessions[self.active].initial_screen()
            self.last[self.active] = s
        return s
