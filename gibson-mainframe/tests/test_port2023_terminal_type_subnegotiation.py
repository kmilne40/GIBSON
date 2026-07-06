from tests.helpers_port2023_tn3270 import *


def test_terminal_type_send_only_after_will_ttype(tmp_path):
    sess = make_session(tmp_path)
    sess.negotiate()
    assert bytes([IAC, SB, TTYPE, SEND, IAC, SE]) not in sess.conn.sent
    sess._process_negotiation_bytes(bytes([IAC, WILL, TTYPE]), bytearray())
    assert bytes([IAC, SB, TTYPE, SEND, IAC, SE]) in sess.conn.sent


def test_parses_supported_terminal_types(tmp_path):
    for ttype in (b"IBM-3278-2-E", b"IBM-3279-2-E", b"IBM-DYNAMIC"):
        sess = make_session(tmp_path)
        sess._process_negotiation_bytes(bytes([IAC, WILL, TTYPE, IAC, SB, TTYPE, IS]) + ttype + bytes([IAC, SE]), bytearray())
        assert sess.terminal_type == ttype.decode()
