from __future__ import annotations

import argparse
import socket
import ssl
import time

from gibson.cli import build_state
from gibson.services.telnet_server import serve_telnet
from gibson.net.telnet3270 import initial_tn3270_negotiation, normalise_client_input


def _args(tmp_path, *, secure: bool, port: int = 0):
    return argparse.Namespace(
        secure=secure,
        vuln=not secure,
        gacf=None,
        sim_root=str(tmp_path),
        host="127.0.0.1",
        port=port,
        ftp_port=None,
        uss_port=None,
        tn3270_port=None,
        rest_port=None,
        db2_tcp_port=None,
        db2_ws_port=None,
    )


def _recv_until(sock, marker: bytes, timeout: float = 5.0) -> bytes:
    sock.settimeout(0.5)
    end = time.time() + timeout
    data = b""
    while time.time() < end:
        try:
            chunk = sock.recv(8192)
        except socket.timeout:
            continue
        if not chunk:
            break
        data += chunk
        if marker in data:
            break
    return data


def test_secure_tls_terminal_sends_selector_and_routes_l_tso(tmp_path):
    st = build_state(_args(tmp_path, secure=True, port=0))
    server = serve_telnet(st)
    host, port = server.server_address
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=5.0) as raw:
            with ctx.wrap_socket(raw, server_hostname="127.0.0.1") as client:
                banner = _recv_until(client, b"Logon Type:")
                assert b"GIBSON" in banner
                assert b"Logon Type:" in banner
                client.sendall(b"L TSO\r\n")
                response = _recv_until(client, b"USERID")
                assert b"USERID" in response or b"LOGON" in response or b"READY" in response
    finally:
        server.shutdown()
        server.server_close()


def test_vulnerable_plaintext_terminal_still_sends_selector_and_routes(tmp_path):
    st = build_state(_args(tmp_path, secure=False, port=0))
    server = serve_telnet(st)
    host, port = server.server_address
    try:
        with socket.create_connection((host, port), timeout=5.0) as client:
            banner = _recv_until(client, b"Logon Type:")
            assert b"GIBSON" in banner
            client.sendall(b"L TSO\r\n")
            response = _recv_until(client, b"USERID")
            assert b"USERID" in response or b"LOGON" in response or b"READY" in response
    finally:
        server.shutdown()
        server.server_close()


def test_tn3270_negotiation_and_ascii_regression():
    # Port 2023 is now dual-mode: idle x3270/c3270 clients may be offered
    # classic TN3270 negotiation, while ASCII input remains unchanged.
    assert initial_tn3270_negotiation().startswith(bytes([0xFF, 0xFB, 0x00]))
    assert bytes([0xFF, 0xFD, 0x28]) not in initial_tn3270_negotiation()
    assert normalise_client_input(b"L TSO\r\n") == "L TSO"
    assert normalise_client_input("L TSO".encode("cp037")) != "L TSO"
