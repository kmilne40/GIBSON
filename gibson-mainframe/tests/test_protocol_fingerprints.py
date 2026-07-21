from __future__ import annotations

import socket
import time
from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.net.fingerprints import ftp_feat_response, ftp_greeting, http_fingerprint_headers, zos_ftp_syst
from gibson.net.telnet3270 import END_OF_RECORD, IAC, TN3270E, WILL, initial_tn3270_negotiation
from gibson.services.ftp_server import serve_ftp
from gibson.services.rest_gateway import _FallbackHandler


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=0,
        ftp_port=0,
        rest_port=0,
        sim_root=tmp_path,
        files_root=tmp_path / "f",
        commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def recv_text(sock: socket.socket, timeout: float = 1.0) -> str:
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
        if b"\r\n" in data:
            break
    return b"".join(chunks).decode("utf-8", "ignore")


def ftp_cmd(sock: socket.socket, cmd: str) -> str:
    sock.sendall((cmd + "\r\n").encode("ascii"))
    return recv_text(sock)


def test_runtime_fingerprint_helpers_are_plain_gibson():
    assert "Gibson FTP service" in ftp_greeting("GIBSON")
    assert "Gibson simulated FTP service" in zos_ftp_syst()
    assert "SITE FILETYPE=JES" in ftp_feat_response()
    prologue = initial_tn3270_negotiation()
    assert prologue.startswith(bytes([IAC, WILL, 0x00]))
    assert bytes([IAC, 0xFD, TN3270E]) not in prologue


def test_ftp_server_returns_zos_style_banner_and_syst(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_ftp(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            banner = recv_text(sock)
            assert "Gibson FTP service" in banner
            assert "Gibson simulated FTP service" in ftp_cmd(sock, "SYST")
            assert "SITE FILETYPE=JES" in ftp_cmd(sock, "FEAT")
            assert "recognized" in ftp_cmd(sock, "HELP")
            assert "ASCII" in ftp_cmd(sock, "TYPE A")
            assert "Image" in ftp_cmd(sock, "TYPE I")
            assert "Goodbye" in ftp_cmd(sock, "QUIT")
    finally:
        server.shutdown(); server.server_close()


def test_rest_gateway_does_not_use_ibm_http_fingerprint_identity():
    # Unit-level check: REST route/lifecycle behaviour is covered elsewhere.
    # This prevents accidental Werkzeug/Python banner leakage in the managed fallback server.
    assert _FallbackHandler.server_version == "GibsonHTTP"
    assert _FallbackHandler.sys_version == ""
    headers = http_fingerprint_headers()
    assert headers == {}
