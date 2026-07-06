from __future__ import annotations

import socket
from pathlib import Path

from gibson.apps.editor import InteractiveEditor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.services.tn3270_server import serve_tn3270


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=2023,
        tn3270_port=0,
        sim_root=tmp_path,
        files_root=tmp_path / "f",
        commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def _read_frame(sock: socket.socket) -> bytes:
    sock.settimeout(2)
    data = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\xff\xef" in data:
            break
    return bytes(data)


def _tn3270_screen_text(frame: bytes) -> str:
    # Strip telnet commands, then interpret a small subset of the 3270 datastream.
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
        if cmd == 0xFF:
            payload.append(0xFF)
            i += 2
            continue
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
        if b in (0x00, 0xF5, 0xF1, 0x05, 0x13):  # EW/W/WCC/IC
            i += 1
            continue
        if b == 0x11 and i + 2 < len(payload):  # SBA
            i += 3
            continue
        if b == 0x1D and i + 1 < len(payload):  # SF attr
            i += 2
            continue
        out.append(b)
        i += 1
    try:
        return out.decode("cp037", errors="ignore")
    except Exception:
        return ""


def _send_cursor(sock: socket.socket, text: str) -> None:
    pkt = bytearray([0x7D])
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.extend(text.encode("cp037"))
    pkt.extend(b"\xff\xef")
    sock.sendall(bytes(pkt))


def _send_aid(sock: socket.socket, aid: int) -> None:
    pkt = bytearray([aid])
    pkt.extend(ScreenBuffer.encode_baddr(0))
    pkt.extend(b"\xff\xef")
    sock.sendall(bytes(pkt))


def test_screenbuffer_exports_tn3270_erase_write_record():
    s = ScreenBuffer()
    s.put(1, 1, "GIBSON")
    s.set_cursor(2, 10)
    data = s.to_3270()
    assert data.startswith(bytes([0xF5, 0x42]))
    assert data.endswith(b"\xff\xef")
    assert b"\x11" in data  # SBA
    assert b"\x13" in data  # IC




def test_tn3270_defers_first_screen_until_3270_negotiation(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_tn3270(st)
    try:
        port = server.server_address[1]
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            sock.settimeout(0.2)
            initial = sock.recv(4096)
            assert b"\xff\xef" not in initial
            assert b"\xff\xfb\x00" in initial  # WILL BINARY
            assert b"\xff\xfd\x00" in initial  # DO BINARY

            # Negotiate classic TN3270 and decline TN3270E so the server can
            # switch cleanly into 3270 mode before sending the first screen.
            sock.sendall(bytes([
                0xFF, 0xFD, 0x00,  # DO BINARY
                0xFF, 0xFB, 0x00,  # WILL BINARY
                0xFF, 0xFD, 0x19,  # DO EOR
                0xFF, 0xFB, 0x19,  # WILL EOR
                0xFF, 0xFB, 0x18,  # WILL TTYPE
                0xFF, 0xFC, 0x28,  # WONT TN3270E
                0xFF, 0xFA, 0x18, 0x01, 0xFF, 0xF0,  # SB TTYPE SEND
            ]))

            frame = _read_frame(sock)
            assert b"\xff\xef" in frame
            assert "GIBSON PRODUCTION LPAR" in _tn3270_screen_text(frame)
        finally:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()




def test_tn3270e_request_is_backed_out_before_classic_screen(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_tn3270(st)
    try:
        port = server.server_address[1]
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            sock.settimeout(0.5)
            initial = sock.recv(4096)
            assert b"\xff\xef" not in initial

            # Accept classic TN3270 and also accept TN3270E, but deliberately
            # do not complete the TN3270E subnegotiation. The server must back
            # out TN3270E before it sends the first classic 3270 screen.
            sock.sendall(bytes([
                0xFF, 0xFD, 0x00,  # DO BINARY
                0xFF, 0xFB, 0x00,  # WILL BINARY
                0xFF, 0xFD, 0x19,  # DO EOR
                0xFF, 0xFB, 0x19,  # WILL EOR
                0xFF, 0xFB, 0x18,  # WILL TTYPE
                0xFF, 0xFB, 0x28,  # WILL TN3270E
                0xFF, 0xFA, 0x18, 0x01, 0xFF, 0xF0,  # SB TTYPE SEND
            ]))

            frame = _read_frame(sock)
            assert b"\xff\xfe\x28" in frame  # DONT TN3270E before fallback
            assert b"\xff\xef" in frame
            assert "GIBSON PRODUCTION LPAR" in _tn3270_screen_text(frame)
        finally:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()

def test_tn3270_listener_supports_vtam_to_tso_and_cics(tmp_path: Path):
    st = make_state(tmp_path)
    server = serve_tn3270(st)
    try:
        port = server.server_address[1]
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            first = _tn3270_screen_text(_read_frame(sock))
            assert "GIBSON PRODUCTION LPAR" in first
            _send_cursor(sock, "LOGON APPLID(TSO)")
            tso = _tn3270_screen_text(_read_frame(sock))
            assert "ENTER USERID -" in tso
            _send_cursor(sock, "NOUSER")
            invalid = _tn3270_screen_text(_read_frame(sock))
            assert "Userid NOUSER not authorized to use TSO" in invalid
            _send_cursor(sock, "LOGON APPLID(CICS)")
            cics = _tn3270_screen_text(_read_frame(sock))
            assert "WELCOME TO CICS" in cics
            _send_aid(sock, 0x6D)  # CLEAR
            blank = _tn3270_screen_text(_read_frame(sock))
            assert blank.strip() == ""
            _send_cursor(sock, "CESF")
            signed_off = _tn3270_screen_text(_read_frame(sock))
            assert "SIGN-OFF IS COMPLETE" in signed_off.upper()
        finally:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()


def test_editor_overlay_line_commands_work_like_ispf_style_ops():
    ed = InteractiveEditor("IBMUSER.TEST", "AAA\nBBB\nCCC\nDDD\n", save_callback=lambda _t: None)
    assert ed._process_data_command("O2", 0) == "2 LINE(S) OVERLAY READY"
    assert ed._process_data_command("B", 2) == "2 LINE(S) OVERLAID"
    assert ed.lines[:4] == ["AAA", "BBB", "AAA", "BBB"]


def test_cli_serve_starts_tn3270_listener_when_enabled(monkeypatch, tmp_path: Path):
    from gibson import cli

    started = []

    class DummyServer:
        def __init__(self, host, port):
            self.server_address = (host, port)
        def shutdown(self):
            return None
        def server_close(self):
            return None

    def fake_serve_telnet(state):
        return DummyServer(state.config.host, state.config.port)

    def fake_serve_uss(state):
        return DummyServer(state.config.host, state.config.uss_port)

    def fake_serve_tn3270(state):
        started.append(state.config.tn3270_port)
        return DummyServer(state.config.host, state.config.tn3270_port)

    monkeypatch.setattr('gibson.services.telnet_server.serve_telnet', fake_serve_telnet)
    monkeypatch.setattr('gibson.services.uss_server.serve_uss', fake_serve_uss)
    monkeypatch.setattr('gibson.services.tn3270_server.serve_tn3270', fake_serve_tn3270)

    def fake_register(state, servers, args):
        state.service_manager.register

    monkeypatch.setattr(cli, '_register_services', lambda state, servers, args: None)
    monkeypatch.setattr(cli.time, 'sleep', lambda _x: None)

    cfgdir = tmp_path
    gacf = cfgdir / 'GACF.DB'
    gacf.write_text('IBMUSER:SYS1:SPECIAL:OMVS\n', encoding='utf-8')

    calls = {'n': 0}
    def fake_signal(_sig, handler):
        calls['n'] += 1
        if calls['n'] == 2:
            handler(None, None)
        return None
    monkeypatch.setattr(cli.signal, 'signal', fake_signal)

    argv = ['prog', '--serve', '--with-tn3270', '--gacf', str(gacf), '--sim-root', str(cfgdir), '--no-dashboard', '--no-db2']
    monkeypatch.setattr('sys.argv', argv)
    cli.main()
    assert started == [3270]


def test_disconnects_do_not_raise_tracebacks_on_initial_banner_send(tmp_path: Path):
    st = make_state(tmp_path)
    from gibson.services.telnet_server import GibsonTelnetSession
    from gibson.services.uss_server import GibsonUssSession
    from gibson.services.tn3270_server import Tn3270Session

    class BrokenConn:
        def sendall(self, _data):
            raise BrokenPipeError()
        def recv(self, _n):
            return b''
        def setsockopt(self, *_a):
            return None
        def settimeout(self, *_a):
            return None

    # Session methods may abort, but expected disconnects should be typed and catchable.
    import pytest
    from gibson.services.telnet_server import ClientDisconnected as TelnetGone
    from gibson.services.uss_server import ClientDisconnected as UssGone
    from gibson.services.tn3270_server import ClientDisconnected as TnGone

    with pytest.raises(TelnetGone):
        GibsonTelnetSession(st, BrokenConn(), ('127.0.0.1', 1)).send('x')
    with pytest.raises(UssGone):
        GibsonUssSession(st, BrokenConn(), ('127.0.0.1', 1)).send('x')
    with pytest.raises(TnGone):
        Tn3270Session(st, BrokenConn(), ('127.0.0.1', 1)).send(b'x')


def test_tab_from_text_moves_focus_to_line_command_field():
    events: list[str] = []

    class Driver:
        def __init__(self):
            self.calls = 0
        def read_key(self):
            self.calls += 1
            if self.calls == 1:
                from gibson.render.input import InputResult
                return InputResult('', 'TAB')
            from gibson.render.input import InputResult
            return InputResult('', 'EOF')

    ed = InteractiveEditor('IBMUSER.TEST', 'AAA\nBBB\n', save_callback=lambda _t: None)
    ed.cur_row = ed.DATA_AREA_START
    ed.cur_col = ed.COMMAND_FIELD_WIDTH
    assert ed._focus_name() == 'TEXT'
    ed.run(Driver(), lambda s: events.append(s))
    assert ed._focus_name() == 'LINECMD'
    assert ed.cur_row == ed.DATA_AREA_START
    assert ed.cur_col == 0


def test_tso_line_editor_creates_persistent_dataset_visible_to_listcat(tmp_path: Path):
    st = make_state(tmp_path)
    from gibson.apps.tso import TsoCommandProcessor
    from gibson.services.telnet_server import GibsonTelnetSession
    from gibson.render.input import InputResult

    class DummyConn:
        def sendall(self, _data):
            return None

    session = GibsonTelnetSession(st, DummyConn(), ('127.0.0.1', 1))
    session.userid = 'IBMUSER'
    session.processor = TsoCommandProcessor(st, 'IBMUSER')
    transcript: list[str] = []
    session.send = lambda text: transcript.append(text)

    class Driver:
        def __init__(self):
            self.responses = iter([
                InputResult('TEXT'),
                InputResult('/* REXX SCRIPT */'),
                InputResult("SAY 'HELLO'"),
                InputResult(''),
                InputResult('SAVE'),
                InputResult('END'),
            ])
        def read_line(self, prompt=''):
            if prompt:
                transcript.append(prompt)
            return next(self.responses, InputResult('', 'EOF'))

    session.input = Driver()
    session.read = lambda prompt='', hidden=False: session.input.read_line(prompt)
    session.tso_line_editor_loop('REXX.TEXT')

    saved = st.datasets.read('IBMUSER', 'IBMUSER.REXX.TEXT')
    assert "SAY 'HELLO'" in saved
    assert any('ENTER DATASET TYPE-' in item for item in transcript)
    assert any('DATASET OR MEMBER NOT FOUND, ASSUMED TO BE NEW' in item for item in transcript)
    names = [info.name for info in st.datasets.listcat('IBMUSER', 'IBMUSER')]
    assert 'IBMUSER.REXX.TEXT' in names


def test_issue_log_suppresses_expected_connection_reset_from_handler(tmp_path: Path):
    st = make_state(tmp_path)
    from gibson.services import telnet_server

    class ResetConn:
        def sendall(self, _data):
            return None
        def recv(self, _n):
            raise ConnectionResetError(104, 'Connection reset by peer')
        def setsockopt(self, *_a):
            return None

    handler = object.__new__(telnet_server._Handler)
    handler.state = st
    handler.request = ResetConn()
    handler.client_address = ('127.0.0.1', 9999)
    handler.handle()

    assert not st.issue_log.path.exists()


def test_tn3270e_minimal_negotiation_and_data_header(tmp_path: Path):
    st = make_state(tmp_path)
    from gibson.services.tn3270_server import (
        Tn3270Session, WILL, TN3270E, TN3270E_DEVICE_TYPE, TN3270E_FUNCTIONS,
        TN3270E_REQUEST, TN3270E_HEADER_LEN
    )

    class CaptureConn:
        def __init__(self):
            self.sent: list[bytes] = []
        def sendall(self, data):
            self.sent.append(bytes(data))

    conn = CaptureConn()
    sess = Tn3270Session(st, conn, ('127.0.0.1', 1))
    sess._reply_telnet(WILL, TN3270E)
    assert any(pkt.startswith(b'\xff\xfd(') for pkt in conn.sent)
    assert any(b'\xff\xfa(' in pkt and bytes([TN3270E_DEVICE_TYPE]) in pkt for pkt in conn.sent)

    sess._handle_tn3270e_subnegotiation(bytes([TN3270E, TN3270E_DEVICE_TYPE, TN3270E_REQUEST]) + b'IBM-3278-2-E')
    sess._handle_tn3270e_subnegotiation(bytes([TN3270E, TN3270E_FUNCTIONS, TN3270E_REQUEST]))
    assert sess.tn3270e_active is True

    conn.sent.clear()
    screen = ScreenBuffer()
    screen.put(1, 1, 'GIBSON')
    sess.send(screen.to_3270())
    assert conn.sent
    frame = conn.sent[-1]
    assert frame[:TN3270E_HEADER_LEN] == bytes([0, 0, 0, 0, 0])
    assert frame.endswith(b'\xff\xef')
