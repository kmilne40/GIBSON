from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from urllib.request import urlopen, Request

from gibson.apps.editor import InteractiveEditor
from gibson.apps.omvs import OmvsShellSession
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult
from gibson.services.web_terminal import serve_web_terminal
from gibson.services.telnet_server import serve_telnet


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close(); return port


class _DummyTerminal:
    def __init__(self, port: int):
        self.port = port
        self.received = bytearray()
        self.stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start(); time.sleep(0.05)

    def _run(self):
        srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", self.port)); srv.listen(5); srv.settimeout(0.25)
        self.srv = srv
        while not self.stop:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        with conn:
            conn.sendall(b"GIBSON TEST LOGIN\nLOGON Type:")
            conn.settimeout(1)
            while not self.stop:
                try:
                    data = conn.recv(1024)
                except socket.timeout:
                    continue
                if not data:
                    break
                self.received.extend(data)
                conn.sendall(b"\nECHO:" + data)

    def close(self):
        self.stop = True
        try:
            socket.create_connection(("127.0.0.1", self.port), timeout=0.1).close()
        except Exception:
            pass
        try:
            self.srv.close()
        except Exception:
            pass


def _post(url: str, payload: dict) -> dict:
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
    return json.loads(urlopen(req, timeout=3).read().decode())


def _ws_handshake(port: int):
    import base64, os
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    req = (
        "GET /ws/terminal HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    data = b""
    while b"\r\n\r\n" not in data:
        data += sock.recv(1024)
    assert b"101 Switching Protocols" in data
    return sock


def _ws_client_frame(payload: bytes) -> bytes:
    import os
    mask = os.urandom(4)
    length = len(payload)
    if length < 126:
        hdr = bytes([0x81, 0x80 | length])
    elif length <= 0xFFFF:
        hdr = bytes([0x81, 0x80 | 126]) + length.to_bytes(2, "big")
    else:
        hdr = bytes([0x81, 0x80 | 127]) + length.to_bytes(8, "big")
    data = bytearray(payload)
    for i in range(len(data)):
        data[i] ^= mask[i % 4]
    return hdr + mask + bytes(data)


def _ws_send_json(sock, payload: dict):
    sock.sendall(_ws_client_frame(json.dumps(payload).encode()))


def _read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return data


def _ws_recv_json(sock, timeout=5):
    sock.settimeout(timeout)
    hdr = _read_exact(sock, 2)
    opcode = hdr[0] & 0x0F
    length = hdr[1] & 0x7F
    if length == 126:
        length = int.from_bytes(_read_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(sock, 8), "big")
    payload = _read_exact(sock, length) if length else b""
    if opcode == 8:
        return {"type":"close"}
    return json.loads(payload.decode())


def _collect_ws_until(sock, needle: str, timeout=6):
    deadline = time.time() + timeout
    text = ""
    messages = []
    while time.time() < deadline:
        msg = _ws_recv_json(sock, timeout=max(0.2, deadline-time.time()))
        messages.append(msg)
        if msg.get("type") == "output":
            text += msg.get("data") or ""
            if needle in text:
                return text, messages
    return text, messages


def test_web_terminal_uses_direct_websocket_session_adapter(tmp_path):
    web_port = _free_port()
    cfg = GibsonConfig(host="127.0.0.1", port=_free_port(), web_terminal_port=web_port, sim_root=tmp_path)
    state = GibsonState.create(cfg)
    telnet = serve_telnet(state)
    srv = serve_web_terminal(state)
    try:
        html = urlopen(f"http://127.0.0.1:{web_port}/", timeout=3).read().decode()
        assert "PF3" in html and "Gibson Browser Terminal" in html and "Command/input" in html
        assert "/ws/terminal" in html and "xtermjs-websocket-bridge" in html
        diag = json.loads(urlopen(f"http://127.0.0.1:{web_port}/api/diagnostics", timeout=3).read().decode())
        assert diag["mode"] == "xtermjs-websocket-bridge"
        assert diag["raw_telnet_port"] == cfg.port
        sock = _ws_handshake(web_port)
        try:
            text, messages = _collect_ws_until(sock, "GIBSON PRODUCTION", timeout=5)
            assert "GIBSON PRODUCTION" in text
            assert any(m.get("type") == "status" and m.get("state") == "CONNECTED" for m in messages)
            _ws_send_json(sock, {"type":"input", "data":"L TSO\r"})
            text, _messages = _collect_ws_until(sock, "ENTER USERID", timeout=5)
            assert "ENTER USERID" in text
            _ws_send_json(sock, {"type":"key", "key":"PF3"})
            _ws_send_json(sock, {"type":"ping"})
            pong = _ws_recv_json(sock, timeout=3)
            assert pong.get("type") in {"pong", "output", "status"}
        finally:
            sock.close()
        time.sleep(0.2)
        diag2 = json.loads(urlopen(f"http://127.0.0.1:{web_port}/api/diagnostics", timeout=3).read().decode())
        assert diag2["mode"] == "xtermjs-websocket-bridge"
    finally:
        srv.shutdown(); srv.server_close(); telnet.shutdown(); telnet.server_close()


def test_editor_preserves_fb80_line_and_rejects_81():
    ed = InteractiveEditor("IBMUSER.TEST.DATA", "", mode="EDIT", recfm="FB", lrecl=80)
    seventy = "A" * 70
    eighty = "B" * 80
    assert ed._replace_line(1, seventy) == "LINE UPDATED"
    assert ed.lines[0] == seventy
    assert ed._replace_line(1, eighty) == "LINE UPDATED"
    assert ed.lines[0] == eighty
    msg = ed._replace_line(1, "C" * 81)
    assert "LINE EXCEEDS LRECL 80" in msg
    assert ed.lines[0] == eighty


class _FakeIO:
    def __init__(self, inputs):
        self.inputs = list(inputs)
    def read_line(self, prompt="", hidden=False, mask=False):
        if not self.inputs:
            return InputResult("", "EOF")
        item = self.inputs.pop(0)
        if item == "<EOF>":
            return InputResult("", "EOF")
        return InputResult(item)


def test_uss_vi_line_mode_create_write_quit(tmp_path):
    cfg = GibsonConfig(sim_root=tmp_path)
    state = GibsonState.create(cfg)
    shell = OmvsShellSession(state, "IBMUSER")
    out = []
    shell._vi_interactive(["test.txt"], _FakeIO(["i", "hello", "world", ".", ":wq"]), out.append)
    assert shell.env.read_text("/u/ibmuser/test.txt") == "hello\nworld\n"


def test_uss_vi_unsaved_q_and_force_quit(tmp_path):
    cfg = GibsonConfig(sim_root=tmp_path)
    state = GibsonState.create(cfg)
    shell = OmvsShellSession(state, "IBMUSER")
    out = []
    shell._vi_interactive(["discard.txt"], _FakeIO(["i", "temp", ".", ":q", ":q!"]), out.append)
    joined = "".join(out)
    assert "No write since last change" in joined
    assert not shell.env.exists("/u/ibmuser/discard.txt")

import subprocess


def test_gibsonctl_start_enables_web_terminal_by_default():
    out = subprocess.check_output(["bash", "gibsonctl.sh", "start", "--dry-run"], text=True)
    assert "--with-web-terminal" in out
    assert "--web-terminal-port 8023" in out


def test_gibsonctl_can_disable_or_report_custom_web_terminal_port():
    out = subprocess.check_output(["bash", "gibsonctl.sh", "start", "--dry-run", "--no-web-terminal"], text=True)
    assert "--with-web-terminal" not in out
    custom = subprocess.check_output(["bash", "gibsonctl.sh", "start", "--dry-run", "--web-terminal-port", "8024"], text=True)
    assert "--web-terminal-port 8024" in custom
