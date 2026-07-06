"""Compatibility wrapper for the enhanced Gibson ISPF/PDF simulator.

The historical Gibson frontend imports run_ispf(conn, username, get_jobs=...).
In the upgraded package, ISPF lives in gibson.apps.ispf and is backed by shared
GibsonState. This wrapper keeps the old import path working.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.ispf import IspfApp
from gibson.apps.tso import TsoCommandProcessor
from gibson.render.input import SocketInputDriver
from gibson.apps.sdsf import SdsfApp


def run_ispf(conn, username, get_jobs=None, term_size: Optional[Tuple[int, int]] = None, tso_runner: Optional[Callable[[str], str]] = None):
    """Run enhanced ISPF over an existing socket-like connection.

    If the caller supplies tso_runner it is used for option 6. Otherwise a
    temporary GibsonState rooted at ~/mfsim is created for compatibility.
    """
    state = GibsonState.create(GibsonConfig())
    userid = (username or "IBMUSER").upper()
    processor = TsoCommandProcessor(state, userid)
    runner = tso_runner or processor.run
    driver = SocketInputDriver(conn, echo=True)

    def send(text: str) -> None:
        conn.sendall(text.encode("utf-8", errors="ignore"))

    def sdsf_loop(initial: str = "MENU") -> None:
        app = SdsfApp(state, userid)
        current = initial if initial else "MENU"
        page = 0
        msg = ""
        while True:
            send(app.render_main(page, msg) if current == "MENU" else app.render_panel(current, page, msg))
            msg = ""
            res = driver.read_line()
            u = (res.key or res.text).strip().upper()
            if u in ("F3", "PF3", "END", "EXIT", "X"):
                if current == "MENU":
                    return
                current = "MENU"; page = 0; continue
            if u in ("F7", "PF7"):
                page = max(0, page - 1); continue
            if u in ("F8", "PF8"):
                page += 1; continue
            if not u:
                continue
            new_panel, msg = app.apply_sdsf_command(u)
            if new_panel:
                current = new_panel; page = 0

    IspfApp(state, userid, runner).run(driver, send, sdsf_loop)
