from __future__ import annotations

import socketserver
import threading
from typing import Optional

from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.render.input import SocketInputDriver


class ClientDisconnected(Exception):
    """Connection dropped while servicing a USS session."""


def _send(conn, text: str) -> None:
    try:
        conn.sendall(text.encode("utf-8", errors="ignore"))
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        raise ClientDisconnected() from exc


class GibsonUssSession:
    def __init__(self, state: GibsonState, conn, addr):
        self.state = state
        self.conn = conn
        self.addr = addr
        self.input = SocketInputDriver(conn, echo=True)
        self.userid: Optional[str] = None

    def send(self, text: str) -> None:
        _send(self.conn, text)

    def read(self, prompt: str = "", hidden: bool = False):
        return self.input.read_line(prompt, hidden=hidden, mask=hidden)

    def login(self) -> bool:
        self.send("GIBSON USS terminal on port 2022\n")
        self.send("Use PF6 from OMVS/3270 or exit here to leave the shell.\n\n")
        while True:
            user_res = self.read("login: ")
            if getattr(user_res, "key", "") == "EOF":
                return False
            username = user_res.text.strip().upper()
            if not username:
                continue
            mgr = getattr(self.state, "service_manager", None)
            if mgr is not None and not mgr.is_available("RACF"):
                self.send("IRR555I RACF SUBSYSTEM NOT ACTIVE\n")
                continue
            self.state.racf.load(merge=True)
            rec = self.state.racf.get(username)
            if not rec:
                self.send("Login incorrect\n")
                continue
            pw_res = self.read("Password: ", hidden=True)
            if getattr(pw_res, "key", "") == "EOF":
                return False
            if not self.state.racf.verify_password(username, pw_res.text.strip()):
                self.send("Login incorrect\n")
                continue
            if not rec.has_omvs:
                self.send("FSUM6003 user does not have an OMVS segment\n")
                continue
            self.userid = username
            self.state.sessions.add(username, self.addr[0], notifier=lambda msg, self=self: self.send("\n" + msg + "\n"))
            self.state.record_security_event(username, "LOGON", "PASSWORD", service="USS", addr=self.addr[0], terminal="USS")
            return True

    def run(self) -> None:
        try:
            if not self.login():
                return
            assert self.userid is not None
            mgr = getattr(self.state, "service_manager", None)
            if mgr is not None and not mgr.is_available("OMVS"):
                self.send("BPXM010I OMVS NOT AVAILABLE\n")
                return
            shell = OmvsShellSession(self.state, self.userid, TsoCommandProcessor(self.state, self.userid), mode="USS")
            shell.run_interactive(self.input, self.send)
        finally:
            if self.userid:
                self.state.sessions.remove(self.userid)


class _Handler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.uss_port, service="OMVS")
        except Exception:
            pass
        try:
            GibsonUssSession(self.state, self.request, self.client_address).run()
        except ClientDisconnected:
            return
        except Exception as exc:
            if is_expected_disconnect(exc):
                return
            if self.state.issue_log is not None:
                self.state.issue_log.record_traceback("USS", self.client_address, exc)
            return


class ThreadedUssServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_uss(state: GibsonState) -> ThreadedUssServer:
    _Handler.state = state
    server = ThreadedUssServer((state.config.host, state.config.uss_port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonUSS").start()
    return server
