"""Simple EBCDIC (3270) z/VM logon listener on port 3023.

This is a deliberately small front door dedicated to z/VM.  Unlike the VTAM
port (2023) / TN3270 port (3270), which start at the VTAM application-selection
screen, this listener takes a TN3270 client **straight to the z/VM logon
panel** and, on a valid logon, into the CP/CMS session.  There is no ISPF and
no TSO on this port.

Everything is reused:
  * 3270 negotiation, inbound parsing and EBCDIC (CP037) datastream come from
    ``Tn3270Session`` (gibson/services/tn3270_server.py).
  * The z/VM logon panel and the CP/CMS state machine come from
    ``ZvmSession`` (gibson/apps/zvm/zvm_session.py) -- the very same object the
    TN3270 port drives once a user types ``L ZVM``.

A plain ASCII/NVT client (e.g. ``nc``) that does not negotiate 3270 falls back
to the line-mode z/VM logon (``ZvmSession.run_terminal``).
"""
from __future__ import annotations

import socket
import socketserver
import threading

from gibson.core.state import GibsonState
from gibson.apps.zvm.zvm_session import ZvmSession
from gibson.services.tn3270_server import (
    Tn3270Session,
    ClientDisconnected,
    is_expected_disconnect,
)


class Zvm3270Session(Tn3270Session):
    """A TN3270 session that lives entirely inside z/VM."""

    def run(self) -> None:
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.negotiate()
        if not self._wait_for_initial_negotiation():
            # Not a 3270 client -> give plain telnet/nc users the line-mode
            # z/VM logon instead of dropping them.
            self._run_ascii_fallback()
            return

        # Start directly at the z/VM logon panel (skip VTAM/TSO/CICS entirely).
        self.mode = "ZVM"
        self.zvm = ZvmSession(self.state, peer_addr=self.addr[0])
        self._send_screen(self.zvm.logon_screen())

        while True:
            packet = self.recv_packet()
            if not packet:
                return
            aid, entries = self._parse_packet(packet)
            text = self._text_from_entries(entries)
            screen = self.zvm.handle(aid, text)
            if screen is None:
                # LOGOFF / end of session: on a dedicated z/VM port there is no
                # VTAM to fall back to, so present a fresh logon panel.
                self.zvm = ZvmSession(self.state, peer_addr=self.addr[0])
                self._send_screen(self.zvm.logon_screen())
            else:
                self._send_screen(screen)

    def _run_ascii_fallback(self) -> None:
        from gibson.render.input import SocketInputDriver

        driver = SocketInputDriver(self.conn, echo=True)

        def _send(text: str) -> None:
            try:
                self.conn.sendall(text.encode("utf-8", errors="ignore"))
            except OSError:
                raise ClientDisconnected("client gone")

        ZvmSession(self.state, peer_addr=self.addr[0]).run_terminal(driver, _send)


class _ZvmHandler(socketserver.BaseRequestHandler):
    state: GibsonState

    def handle(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.zvm_port, service="ZVM/TN3270")
        except Exception:
            pass
        try:
            Zvm3270Session(self.state, self.request, self.client_address).run()
        except ClientDisconnected:
            return
        except Exception as exc:
            if is_expected_disconnect(exc):
                return
            if self.state.issue_log is not None:
                self.state.issue_log.record_traceback("ZVM3270", self.client_address, exc)
            return


class ThreadedZvm3270Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        import sys

        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_zvm3270(state: GibsonState) -> ThreadedZvm3270Server:
    _ZvmHandler.state = state
    server = ThreadedZvm3270Server((state.config.host, state.config.zvm_port), _ZvmHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonZVM3270").start()
    return server
