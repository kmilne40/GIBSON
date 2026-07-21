"""Workstream A - port 2023 is server-initiated TN3270 with ASCII fallback.

The decisive fix: real TN3270 clients (c3270/x3270) connect and WAIT for the
host to start option negotiation.  The port-2023 front door now proactively
sends the TN3270 prologue, so a server-wait client lands in formatted EBCDIC
3270 (function keys arrive as AID bytes - never ANSI "ESC O R", never "^I"
tabs).  Clients that never negotiate (netcat) fall back to ASCII/NVT.
"""
import socket
import threading
import time
import select

from gibson.core.state import GibsonState

IAC, WILL, DO, SB, SE = 255, 251, 253, 250, 240
TTYPE, BINARY, EOR, IS, SEND = 24, 0, 25, 0, 1


def _serve_once():
    st = GibsonState.create(); st.racf.load()
    from gibson.services.telnet_server import GibsonTelnetSession
    ls = socket.socket()
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind(("127.0.0.1", 0)); ls.listen(1)

    def acc():
        try:
            conn, addr = ls.accept()
            GibsonTelnetSession(st, conn, addr).run()
        except Exception:
            pass

    threading.Thread(target=acc, daemon=True).start()
    return ls, ls.getsockname()


def test_server_wait_c3270_gets_formatted_3270():
    """Client sends nothing first; the host must initiate, then we complete."""
    ls, (host, port) = _serve_once()
    cli = socket.create_connection((host, port), timeout=5)
    cli.setblocking(False)
    buf = bytearray()
    sent_resp = False
    sent_ttype = False
    deadline = time.time() + 6
    try:
        while time.time() < deadline:
            r, _, _ = select.select([cli], [], [], 0.2)
            if r:
                try:
                    chunk = cli.recv(4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    break
                buf += chunk
                if b"\xf5" in buf:
                    break
            if (not sent_resp) and bytes([IAC, DO, TTYPE]) in buf:
                cli.sendall(bytes([IAC, DO, BINARY, IAC, WILL, BINARY,
                                   IAC, DO, EOR, IAC, WILL, EOR, IAC, WILL, TTYPE]))
                sent_resp = True
            if (not sent_ttype) and bytes([SB, TTYPE, SEND]) in buf:
                cli.sendall(bytes([IAC, SB, TTYPE, IS]) + b"IBM-3278-2-E" + bytes([IAC, SE]))
                sent_ttype = True
        data = bytes(buf)
        assert bytes([IAC, DO, TTYPE]) in data, "host did not server-initiate TN3270"
        f5 = data.find(b"\xf5")
        assert f5 >= 0, "server-wait client never reached formatted 3270"
        assert b"\x1b" not in data[f5:], "ANSI escape in 3270 datastream"
    finally:
        cli.close(); ls.close()


def test_netcat_falls_back_to_ascii():
    """A peer that never negotiates telnet must get ASCII/NVT, not 3270."""
    ls, (host, port) = _serve_once()
    cli = socket.create_connection((host, port), timeout=5)
    cli.setblocking(False)
    try:
        try:
            cli.sendall(b"HELP\r\n")
        except OSError:
            pass
        buf = bytearray()
        deadline = time.time() + 3.0
        while time.time() < deadline:
            r, _, _ = select.select([cli], [], [], 0.2)
            if r:
                try:
                    c = cli.recv(4096)
                except BlockingIOError:
                    continue
                if not c:
                    break
                buf += c
                if len(buf) > 2000:
                    break
        data = bytes(buf)
        assert b"\xf5\x42" not in data, "netcat wrongly received a 3270 datastream"
        assert b"\x1b" in data, "no ASCII/NVT screen delivered"
    finally:
        cli.close(); ls.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all Workstream A tests passed")
