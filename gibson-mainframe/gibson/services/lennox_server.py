"""Telnet listener for the LENNOX standalone training system."""
from __future__ import annotations

import socketserver
import threading

from gibson.apps.lennox.system import LennoxSession, HOSTNAME
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.render.input import SocketInputDriver

_USERS = {"training": "training"}     # local LENNOX accounts (not RACF)


class ClientDisconnected(Exception):
    pass


def _send(conn, text: str) -> None:
    try:
        conn.sendall(text.encode("utf-8", errors="ignore"))
    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
        raise ClientDisconnected() from exc


class GibsonLennoxSession:
    def __init__(self, state: GibsonState, conn, addr):
        self.state = state
        self.conn = conn
        self.addr = addr
        self.input = SocketInputDriver(conn, echo=True)

    def send(self, text: str) -> None:
        _send(self.conn, text)

    def read(self, prompt: str = "", hidden: bool = False):
        return self.input.read_line(prompt, hidden=hidden, mask=hidden)

    def login(self) -> bool:
        self.send(f"\nGIBSON training network - {HOSTNAME} (Ubuntu 22.04 LTS)\n\n")
        for _ in range(3):
            ures = self.read(f"{HOSTNAME} login: ")
            if getattr(ures, "key", "") == "EOF":
                return False
            user = ures.text.strip()
            pres = self.read("Password: ", hidden=True)
            if getattr(pres, "key", "") == "EOF":
                return False
            if _USERS.get(user.lower()) == pres.text.strip():
                self.user = user.lower()
                try:
                    self.state.record_security_event(user.lower(), "LOGON", "PASSWORD",
                                                     service="LENNOX", addr=self.addr[0], terminal="LENNOX")
                except Exception:
                    pass
                return True
            self.send("\nLogin incorrect\n\n")
        return False

    def run(self) -> None:
        if not self.login():
            return
        sess = LennoxSession(self.state, self.addr[0])
        self.send("\n" + sess.banner() + "\n")
        while True:
            res = self.read(sess.prompt())
            if getattr(res, "key", "") == "EOF":
                return
            line = res.text.rstrip("\n")
            try:
                out = sess.handle(line)
            except Exception as exc:  # never crash the box
                out = f"lennox: internal error: {exc}"
            if out is None:           # exit/logout
                self.send("logout\n")
                return
            if out:
                self.send(out + "\n")


class _Handler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0],
                                       getattr(self.state.config, "lennox_port", 2380), service="LENNOX")
        except Exception:
            pass
        try:
            GibsonLennoxSession(self.state, self.request, self.client_address).run()
        except ClientDisconnected:
            return
        except Exception as exc:
            if is_expected_disconnect(exc):
                return
            if self.state.issue_log is not None:
                self.state.issue_log.record_traceback("LENNOX", self.client_address, exc)
            return


class ThreadedLennoxServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_lennox(state: GibsonState) -> ThreadedLennoxServer:
    _Handler.state = state
    port = getattr(state.config, "lennox_port", 2380)
    server = ThreadedLennoxServer((state.config.host, port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonLennox").start()
    return server
