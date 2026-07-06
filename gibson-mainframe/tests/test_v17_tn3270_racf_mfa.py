from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest

from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.services.telnet_server import serve_telnet


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
    cfg.gacf_path.write_text(
        "IBMUSER:SYS1:SPECIAL:OMVS:SYS1\n"
        "GUEST:GUEST:NONE:NOOMVS:STUDENT\n"
        "SARCHER:SYSADM:NONE:OMVS:STUDENT\n",
        encoding="utf-8",
    )
    return GibsonState.create(cfg)


def _recv_available(sock: socket.socket, timeout: float = 0.4) -> bytes:
    sock.settimeout(timeout)
    chunks = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def _recv_until(sock: socket.socket, needle: bytes, limit: int = 65536) -> bytes:
    sock.settimeout(2)
    data = bytearray()
    while len(data) < limit and needle not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def test_vtam_does_not_send_eor_to_netcat_style_client(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_telnet(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            first = _recv_available(sock, 0.4)
            assert b"\xff\xef" not in first
            data = _recv_until(sock, b"Logon Type:")
            assert b"\xff\xef" not in data
            assert "GIBSON PRODUCTION LPAR" in data.decode("utf-8", "ignore")
    finally:
        server.shutdown(); server.server_close()


def test_tn3270_eor_sent_only_after_binary_eor_negotiation(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_telnet(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            initial = sock.recv(4096)
            assert b"\xff\xef" not in initial
            sock.sendall(bytes([
                0xFF, 0xFD, 0x00, 0xFF, 0xFB, 0x00,
                0xFF, 0xFD, 0x19, 0xFF, 0xFB, 0x19,
                0xFF, 0xFB, 0x18, 0xFF, 0xFC, 0x28,
            ]))
            frame = _recv_until(sock, b"\xff\xef")
            assert b"\xff\xef" in frame
            assert b"\xf5" in frame  # Erase/Write command
    finally:
        server.shutdown(); server.server_close()


def test_racf_warning_special_and_group_dataset_access(tmp_path: Path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    guest = TsoCommandProcessor(st, "GUEST")
    st.datasets.allocate("IBMUSER", "IBMUSER.SECRET.DATA")
    st.datasets.write("IBMUSER", "IBMUSER.SECRET.DATA", "SECRET")
    assert "PROFILE IBMUSER.SECRET.DATA ALTERED" in admin.run("ALTDSD IBMUSER.SECRET.DATA UACC(NONE)")
    with pytest.raises(PermissionError):
        st.datasets.read("GUEST", "IBMUSER.SECRET.DATA")
    assert "PROFILE IBMUSER.SECRET.DATA ALTERED" in admin.run("ALTDSD IBMUSER.SECRET.DATA WARNING")
    assert st.datasets.read("GUEST", "IBMUSER.SECRET.DATA") == "SECRET"
    assert "WARNING" in admin.run("LISTDSD DATASET('IBMUSER.SECRET.DATA') ALL")
    assert "GROUP LAB DEFINED" in admin.run("ADDGROUP LAB")
    assert "CONNECTED" in admin.run("CONNECT GUEST GROUP(LAB) AUTHORITY(USE)")
    assert "PERMIT SUCCESSFUL" in admin.run("PERMIT IBMUSER.SECRET.DATA CLASS(DATASET) ID(LAB) ACCESS(UPDATE)")
    st.datasets.write("GUEST", "IBMUSER.SECRET.DATA", "UPDATED")
    assert st.datasets.read("IBMUSER", "IBMUSER.SECRET.DATA") == "UPDATED"
    assert st.datasets.read("IBMUSER", "SYS1.RACFDS")


def test_sys1_library_realism_seeded_and_protected(tmp_path: Path):
    st = make_state(tmp_path)
    names = {row.name for row in st.datasets.listcat("IBMUSER", prefix="SYS1")}
    for required in ["SYS1.PARMLIB", "SYS1.LPALIB", "SYS1.NUCLEUS", "SYS1.JCLLIB", "SYS1.DB2.PROCLIB", "SYS1.CICS.PROCLIB"]:
        assert required in names
    members = st.datasets.read("GUEST", "SYS1.PARMLIB")
    assert "IEASYS00" in members and "SMFPRM00" in members and "LOAD00" in members
    with pytest.raises(PermissionError):
        st.datasets.write("GUEST", "SYS1.PARMLIB(ZZTEST)", "SHOULD NOT WRITE")


def test_mfa_mode_uses_host_time_token_and_ibmuser_bypass(tmp_path: Path, monkeypatch):
    st = make_state(tmp_path)
    monkeypatch.setattr(time, "strftime", lambda fmt: "0904" if fmt == "%H%M" else "")
    admin = TsoCommandProcessor(st, "IBMUSER")
    guest = TsoCommandProcessor(st, "GUEST")
    assert "DISABLED" in admin.run("MFA STATUS")
    assert admin.run("MFA") == "MFA ENABLED"
    assert st.mfa_required_for("GUEST") is True
    assert st.mfa_required_for("IBMUSER") is False
    assert st.validate_mfa_token("0904") is True
    assert st.validate_mfa_token("904") is False
    assert "NOT AUTHORISED" in guest.run("MFA OFF")
    assert admin.run("MFA OFF") == "MFA DISABLED"
