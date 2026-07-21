import socket

from gibson.net.vtam_frontend import negotiate_tn3270_or_ascii
from gibson.net.datastream3270 import encode_3270_address, SBA
from gibson.services.tn3270_server import IAC, EOR, AID_ENTER
from tests.helpers_port2023_tn3270 import make_session, client_ready_bytes


class TimeoutThenFrameConn:
    def __init__(self, frame: bytes):
        self.items = [socket.timeout(), frame]
        self.timeout = None
        self.sent = bytearray()
    def recv(self, n: int):
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item
    def sendall(self, data: bytes):
        self.sent.extend(data)
    def settimeout(self, timeout):
        self.timeout = timeout
    def gettimeout(self):
        return self.timeout


def test_idle_raw_socket_routes_to_ascii_not_3270():
    a, b = socket.socketpair()
    try:
        result = negotiate_tn3270_or_ascii(a, timeout=0.03)
        assert result.use_tn3270 is False
        assert result.reason == "ASCII_IDLE_FALLBACK"
    finally:
        a.close()
        b.close()


def test_tn3270_recv_timeout_does_not_close_while_operator_types(tmp_path):
    # TAB and text entry are local in 3270 emulators.  The host may see no
    # socket bytes until ENTER.  A timeout before ENTER must not be treated as
    # disconnect/EOF.
    cursor = encode_3270_address(23 * 80 + 12)
    field = encode_3270_address(23 * 80 + 12)
    frame = bytes([AID_ENTER]) + cursor + bytes([SBA]) + field + b"L TSO" + bytes([IAC, EOR])
    sess = make_session(tmp_path)
    sess.conn = TimeoutThenFrameConn(frame)
    assert sess.recv_packet().startswith(bytes([AID_ENTER]))


def test_enter_l_tso_from_vtam_field_opens_tso_user_screen(tmp_path):
    field_addr = 23 * 80 + 12
    frame = (
        bytes([AID_ENTER])
        + encode_3270_address(field_addr)
        + bytes([SBA])
        + encode_3270_address(field_addr)
        + "L TSO".encode("cp037")
        + bytes([IAC, EOR])
    )
    sess = make_session(tmp_path, chunks=[frame], initial=client_ready_bytes())
    sess.negotiate()
    assert sess._wait_for_initial_negotiation(timeout=0.05)
    sess._send_screen(sess.vtam_screen())
    packet = sess.recv_packet()
    aid, entries = sess._parse_packet(packet)
    assert sess._text_from_entries(entries).upper() == "L TSO"
    sess.handle_vtam(sess._text_from_entries(entries))
    assert sess.mode == "TSO_USER"
    assert "IKJ56700A".encode("cp037")[:4] in bytes(sess.conn.sent)
