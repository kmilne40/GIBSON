from __future__ import annotations

import argparse
from gibson.cli import build_state
from gibson.net.telnet3270 import initial_tn3270_negotiation, normalise_client_input
from gibson.net.fingerprints import http_fingerprint_headers, ftp_greeting


def test_secure_and_vuln_switches_are_preserved(tmp_path):
    def args(path, *, secure=False, vuln=False):
        return argparse.Namespace(secure=secure, vuln=vuln, gacf=None, sim_root=str(path), host=None, port=None, ftp_port=None, uss_port=None, tn3270_port=None, rest_port=None, db2_tcp_port=None, db2_ws_port=None)
    secure = build_state(args(tmp_path / "secure", secure=True))
    vuln = build_state(args(tmp_path / "vuln", vuln=True))
    assert secure.config.port == 1023
    assert secure.config.dashboard_port == 8443
    assert vuln.config.port == 23


def test_live_tn3270_prologue_and_ascii_compatibility():
    assert initial_tn3270_negotiation().startswith(bytes([0xFF, 0xFB, 0x00]))
    assert bytes([0xFF, 0xFD, 0x28]) not in initial_tn3270_negotiation()
    assert normalise_client_input(b"L TSO\r\n") == "L TSO"
    assert normalise_client_input(b"\x7d\x40\x40\x11\x00\x00L CICS\xff\xef") == "L CICS"
    assert normalise_client_input("L TSO".encode("cp037")) != "L TSO"


def test_runtime_fingerprinting_disabled():
    assert http_fingerprint_headers() == {}
    assert "IBM" not in ftp_greeting("SYS1")
