"""Port 3023 - simple EBCDIC (3270) z/VM logon.

Verifies the dedicated z/VM listener:
  * serves a 3270 EraseWrite logon panel whose text decodes from CP037 and
    contains USERID / PASSWORD (i.e. it is genuinely EBCDIC, not ASCII),
  * never emits ANSI escapes in the 3270 datastream,
  * lets a plain ASCII/NVT (nc-style) client log straight on to z/VM CP/CMS.
"""
import socket
import threading
import time

from gibson.core.state import GibsonState
from gibson.services.zvm3270_server import serve_zvm3270


def _serve():
    st = GibsonState.create()
    st.config.zvm_port = 0  # ephemeral
    srv = serve_zvm3270(st)
    return srv, srv.server_address


def test_3023_serves_ebcdic_3270_logon_panel():
    srv, (host, port) = _serve()
    try:
        c = socket.create_connection((host, port), timeout=3)
        c.settimeout(3)
        time.sleep(0.2)
        try:
            c.recv(4096)  # drain server telnet negotiation
        except Exception:
            pass
        IAC = 255
        # Present as a 3270 terminal.
        c.sendall(bytes([IAC, 251, 24, IAC, 251, 0, IAC, 251, 25, IAC, 253, 0, IAC, 253, 25]))
        c.sendall(bytes([IAC, 250, 24, 0]) + b"IBM-3278-2-E" + bytes([IAC, 240]))
        time.sleep(0.6)
        buf = b""
        try:
            while True:
                b = c.recv(4096)
                if not b:
                    break
                buf += b
                if b"\xff\xef" in b:
                    break
        except Exception:
            pass
        f5 = buf.find(b"\xf5")  # 3270 Erase/Write
        assert f5 >= 0, "no 3270 EraseWrite in panel"
        ds = buf[f5:]
        assert b"\x1b[" not in ds, "ANSI escape leaked into 3270 datastream"
        decoded = ds.decode("cp037", errors="ignore").upper()
        assert "USERID" in decoded
        assert "PASSWORD" in decoded or "Z/VM" in decoded
        c.close()
    finally:
        srv.shutdown()


def test_3023_ascii_fallback_logs_on_to_zvm():
    srv, (host, port) = _serve()
    try:
        c = socket.create_connection((host, port), timeout=3)
        c.settimeout(3)
        buf = bytearray()

        def reader():
            try:
                while True:
                    b = c.recv(4096)
                    if not b:
                        break
                    buf.extend(b)
            except Exception:
                pass

        threading.Thread(target=reader, daemon=True).start()
        time.sleep(1.1)  # let 3270 negotiation time out -> NVT fallback
        c.sendall(b"DEMO\r\n")
        time.sleep(0.3)
        c.sendall(b"DEMO\r\n")          # DEMO's CP directory password (auth now enforced)
        time.sleep(0.3)
        out = bytes(buf).decode("utf-8", "ignore")
        assert "USERID" in out and "z/VM" in out
        assert "LOGON AT" in out  # reached the logged-on state
        c.close()
    finally:
        srv.shutdown()


def test_3023_blank_password_rejected_in_text_mode():
    srv, (host, port) = _serve()
    try:
        c = socket.create_connection((host, port), timeout=3)
        c.settimeout(3)
        buf = bytearray()

        def reader():
            try:
                while True:
                    b = c.recv(4096)
                    if not b:
                        break
                    buf.extend(b)
            except Exception:
                pass

        threading.Thread(target=reader, daemon=True).start()
        time.sleep(1.1)
        c.sendall(b"DEMO\r\n")
        time.sleep(0.3)
        c.sendall(b"\r\n")  # blank password
        time.sleep(0.3)
        out = bytes(buf).decode("utf-8", "ignore")
        assert "LOGON REJECTED" in out
        c.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_3023_serves_ebcdic_3270_logon_panel()
    test_3023_ascii_fallback_logs_on_to_zvm()
    test_3023_blank_password_rejected_in_text_mode()
    print("all 3023 tests passed")
