from __future__ import annotations

import base64
import json
import os
import socket
import time
from urllib.request import urlopen

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.telnet_server import serve_telnet
from gibson.services.web_terminal import serve_web_terminal


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close(); return port


def _read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return data


def _ws_connect(port: int):
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


def _ws_send(sock, msg: dict):
    sock.sendall(_ws_client_frame(json.dumps(msg).encode()))


def _ws_recv(sock, timeout=5):
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
        return {"type": "close"}
    return json.loads(payload.decode())


def _until(sock, predicate, timeout=6):
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        msg = _ws_recv(sock, max(0.2, deadline - time.time()))
        seen.append(msg)
        if predicate(msg, seen):
            return seen
    return seen


def _text(seen):
    return "".join(m.get("data") or "" for m in seen if m.get("type") == "output")


def test_websocket_tcp_bridge_delivers_vtam_and_input(tmp_path):
    web_port = _free_port()
    raw_port = _free_port()
    cfg = GibsonConfig(host="127.0.0.1", port=raw_port, web_terminal_port=web_port, sim_root=tmp_path)
    state = GibsonState.create(cfg)
    telnet = serve_telnet(state)
    web = serve_web_terminal(state)
    try:
        health = json.loads(urlopen(f"http://127.0.0.1:{web_port}/health").read().decode())
        assert health["mode"] == "xtermjs-websocket-bridge"
        diag = json.loads(urlopen(f"http://127.0.0.1:{web_port}/api/diagnostics").read().decode())
        assert diag["mode"] == "xtermjs-websocket-bridge"
        assert diag["backend_port"] == raw_port
        assert diag["backend_connectable"] is True

        sock = _ws_connect(web_port)
        try:
            seen = _until(sock, lambda m, s: m.get("type") == "status" and m.get("state") == "CONNECTED", timeout=3)
            assert any(m.get("state") == "CONNECTED" for m in seen)
            seen += _until(sock, lambda m, s: "GIBSON PRODUCTION" in _text(s), timeout=6)
            assert "GIBSON PRODUCTION" in _text(seen)
            _ws_send(sock, {"type": "input", "data": "L TSO\r"})
            seen2 = _until(sock, lambda m, s: "ENTER USERID" in _text(s), timeout=6)
            assert "ENTER USERID" in _text(seen2)
            _ws_send(sock, {"type": "key", "key": "PF3"})
            _ws_send(sock, {"type": "ping"})
            seen3 = _until(sock, lambda m, s: any(x.get("type") == "pong" for x in s), timeout=3)
            assert any(m.get("type") == "pong" for m in seen3)
        finally:
            sock.close()
    finally:
        web.shutdown(); web.server_close(); telnet.shutdown(); telnet.server_close()


def test_raw_telnet_port_still_works_with_bridge_present(tmp_path):
    web_port = _free_port()
    raw_port = _free_port()
    cfg = GibsonConfig(host="127.0.0.1", port=raw_port, web_terminal_port=web_port, sim_root=tmp_path)
    state = GibsonState.create(cfg)
    telnet = serve_telnet(state)
    web = serve_web_terminal(state)
    try:
        with socket.create_connection(("127.0.0.1", raw_port), timeout=3) as s:
            s.settimeout(3)
            data = ""
            deadline = time.time() + 3
            while time.time() < deadline and "GIBSON PRODUCTION" not in data and "LOGON" not in data:
                try:
                    data += s.recv(4096).decode("utf-8", errors="ignore")
                except socket.timeout:
                    break
            assert "GIBSON PRODUCTION" in data or "LOGON" in data
    finally:
        web.shutdown(); web.server_close(); telnet.shutdown(); telnet.server_close()
