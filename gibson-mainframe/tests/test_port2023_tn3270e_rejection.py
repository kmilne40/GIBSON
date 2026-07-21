from tests.helpers_port2023_tn3270 import *


def test_will_tn3270e_receives_dont(tmp_path):
    sess = make_session(tmp_path)
    sess._process_negotiation_bytes(bytes([IAC, WILL, TN3270E]), bytearray())
    assert bytes([IAC, DONT, TN3270E]) in sess.conn.sent
    assert sess.tn3270e_rejected is True
    assert sess.tn3270e_active is False


def test_do_tn3270e_receives_wont(tmp_path):
    sess = make_session(tmp_path)
    sess._process_negotiation_bytes(bytes([IAC, DO, TN3270E]), bytearray())
    assert bytes([IAC, WONT, TN3270E]) in sess.conn.sent
    assert sess.tn3270e_rejected is True
    assert sess.tn3270e_active is False
