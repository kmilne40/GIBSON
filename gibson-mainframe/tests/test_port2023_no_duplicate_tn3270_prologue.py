from tests.helpers_port2023_tn3270 import *


def test_duplicate_prologue_not_sent_from_session(tmp_path):
    sess = make_session(tmp_path)
    sess.negotiate(); sess.negotiate()
    prologue = bytes([IAC, WILL, BINARY, IAC, DO, BINARY, IAC, WILL, EOR_OPT, IAC, DO, EOR_OPT, IAC, DO, TTYPE])
    assert bytes(sess.conn.sent).count(prologue) == 1
