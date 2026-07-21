from tests.helpers_port2023_tn3270 import *


def test_terminal_type_send_order_after_will(tmp_path):
    sess = make_session(tmp_path)
    sess.negotiate()
    before = bytes(sess.conn.sent)
    send_seq = bytes([IAC, SB, TTYPE, SEND, IAC, SE])
    assert send_seq not in before
    sess._process_negotiation_bytes(bytes([IAC, DO, BINARY, IAC, WILL, TTYPE]), bytearray())
    after = bytes(sess.conn.sent)
    assert after.find(bytes([IAC, WILL, BINARY])) < after.find(send_seq)
