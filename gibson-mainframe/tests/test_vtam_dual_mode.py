from pathlib import Path
import socket

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.telnet_server import serve_telnet


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=0,
        sim_root=tmp_path,
        files_root=tmp_path / "f",
        commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def _recv_until(sock: socket.socket, needle: bytes, limit: int = 65536) -> bytes:
    data = bytearray(); sock.settimeout(3)
    while len(data) < limit and needle not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def test_telnet_frontend_falls_back_to_ascii_for_nvt_clients(tmp_path: Path):
    st = make_state(tmp_path); server = serve_telnet(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            data = _recv_until(sock, b"Logon Type:")
            text = data.decode("utf-8", errors="ignore")
            assert "GIBSON PRODUCTION LPAR" in text
            assert "LOGON using L TSO, L CICS or L DB2." in text
    finally:
        server.shutdown(); server.server_close()


def test_telnet_frontend_does_not_emit_tn3270_prologue_before_ascii(tmp_path: Path):
    # Port 2023 is the legacy raw telnet/ncat/nmap-sim path.  It must not
    # push a TN3270 negotiation prologue before the ASCII VTAM screen, because
    # that breaks nmap-sim user enumeration and the Guacamole web terminal.
    st = make_state(tmp_path); server = serve_telnet(st)
    try:
        port = server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            data = _recv_until(sock, b"Logon Type:")
            assert not data.startswith(b"\xff")
            assert b"\xff\xfd\x28" not in data[:64]
            text = data.decode("utf-8", errors="ignore")
            assert "GIBSON PRODUCTION LPAR" in text
            assert "Logon Type:" in text
    finally:
        server.shutdown(); server.server_close()
