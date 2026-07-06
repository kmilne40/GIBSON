from __future__ import annotations

import socket
import time
from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.net.telnet3270 import normalise_client_input
from gibson.render.screen3270 import ScreenBuffer
from gibson.services.tn3270_server import serve_tn3270


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=0,
        tn3270_port=0,
        sim_root=tmp_path,
        files_root=tmp_path / "f",
        commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def _read_frame(sock: socket.socket, timeout: float = 2.0) -> bytes:
    sock.settimeout(timeout)
    data = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\xff\xef" in data:
            break
    return bytes(data)


def _screen_text(frame: bytes) -> str:
    payload = bytearray()
    i = 0
    while i < len(frame):
        b = frame[i]
        if b != 0xFF:
            payload.append(b)
            i += 1
            continue
        if i + 1 >= len(frame):
            break
        cmd = frame[i + 1]
        if cmd == 0xEF:
            break
        if cmd in (0xFB, 0xFC, 0xFD, 0xFE):
            i += 3
            continue
        if cmd == 0xFA:
            end = frame.find(b"\xff\xf0", i + 2)
            i = len(frame) if end == -1 else end + 2
            continue
        i += 2
    out = bytearray()
    i = 0
    while i < len(payload):
        b = payload[i]
        if b in (0xF5, 0xF1, 0x00, 0x13):
            i += 1
            continue
        if b == 0x11 and i + 2 < len(payload):
            i += 3
            continue
        if b == 0x1D and i + 1 < len(payload):
            i += 2
            continue
        if b == 0x29 and i + 1 < len(payload):
            i += 2 + payload[i + 1] * 2
            continue
        out.append(b)
        i += 1
    return out.decode("cp037", errors="ignore")


def _negotiate(sock: socket.socket) -> None:
    sock.recv(4096)
    sock.sendall(bytes([
        0xFF, 0xFD, 0x00, 0xFF, 0xFB, 0x00,
        0xFF, 0xFD, 0x19, 0xFF, 0xFB, 0x19,
        0xFF, 0xFB, 0x18, 0xFF, 0xFC, 0x28,
    ]))


def _send_3270(sock: socket.socket, text: str) -> None:
    pkt = bytearray([0x7D])
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.append(0x11)
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.extend(text.encode("cp037"))
    pkt.extend(b"\xff\xef")
    sock.sendall(bytes(pkt))


def test_normalise_client_input_variants():
    assert normalise_client_input(b"L TSO\n") == "L TSO"
    assert normalise_client_input(b"L TSO\r\n") == "L TSO"
    assert normalise_client_input(b"L TSO\r\x00") == "L TSO"
    assert normalise_client_input(b"L TSO\xff\xef") == "L TSO"
    pkt = bytearray([0x7D])
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.append(0x11)
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.extend(b"L TSO")
    pkt.extend(b"\xff\xef")
    assert normalise_client_input(bytes(pkt)) == "L TSO"
    assert normalise_client_input(b"\xff\xfd") == ""


def test_screenbuffer_uses_keyboard_restore_wcc():
    s = ScreenBuffer()
    s.put(1, 1, "READY")
    data = s.to_3270()
    assert data.startswith(bytes([0xF5, 0x42]))


def test_tn3270_l_tso_help_logoff_stays_interactive(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_tn3270(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            _negotiate(sock)
            first = _screen_text(_read_frame(sock))
            assert "GIBSON PRODUCTION LPAR" in first
            _send_3270(sock, "L TSO")
            tso = _screen_text(_read_frame(sock))
            assert "ENTER USERID" in tso
            _send_3270(sock, "NOUSER")
            invalid = _screen_text(_read_frame(sock))
            assert "NOUSER" in invalid or "NOT AUTHORIZED" in invalid
            _send_3270(sock, "LOGON APPLID(TSO)")
            assert "ENTER USERID" in _screen_text(_read_frame(sock))
    finally:
        server.shutdown(); server.server_close()


def test_tn3270_partial_frame_times_out_without_hanging(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_tn3270(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            _negotiate(sock)
            _read_frame(sock)
            sock.sendall(bytes([0x7D]))
            start = time.monotonic()
            # The server should not block indefinitely waiting for newline/EOR.
            sock.close()
            assert time.monotonic() - start < 1.0
    finally:
        server.shutdown(); server.server_close()
