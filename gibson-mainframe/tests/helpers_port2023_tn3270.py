from pathlib import Path
import socket

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.tn3270_server import Tn3270Session
from gibson.net.vtam_frontend import VtamNegotiationResult

IAC = 0xFF
DO = 0xFD
WILL = 0xFB
WONT = 0xFC
DONT = 0xFE
SB = 0xFA
SE = 0xF0
BINARY = 0x00
TTYPE = 0x18
EOR_OPT = 0x19
TN3270E = 0x28
SEND = 0x01
IS = 0x00


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        host="127.0.0.1", port=0, tn3270_port=0, sim_root=tmp_path,
        files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


class FakeConn:
    def __init__(self, chunks=None):
        self.chunks = list(chunks or [])
        self.sent = bytearray()
        self.timeout = None
        self.closed = False
    def sendall(self, data: bytes):
        self.sent.extend(data)
    def recv(self, n: int, flags: int = 0):
        if not self.chunks:
            raise socket.timeout()
        data = self.chunks.pop(0)
        return data[:n]
    def settimeout(self, timeout):
        self.timeout = timeout
    def gettimeout(self):
        return self.timeout
    def setsockopt(self, *args, **kwargs):
        return None


def client_ready_bytes(ttype=b"IBM-3278-2-E"):
    return bytes([
        IAC, DO, BINARY,
        IAC, WILL, BINARY,
        IAC, DO, EOR_OPT,
        IAC, WILL, EOR_OPT,
        IAC, WILL, TTYPE,
        IAC, SB, TTYPE, IS,
    ]) + ttype + bytes([IAC, SE])


def make_session(tmp_path, chunks=None, initial=b""):
    init = VtamNegotiationResult(use_tn3270=True, client_bytes=initial)
    return Tn3270Session(make_state(tmp_path), FakeConn(chunks), ("127.0.0.1", 1), initial_negotiation=init)
