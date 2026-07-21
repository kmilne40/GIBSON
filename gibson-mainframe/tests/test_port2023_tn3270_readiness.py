from tests.helpers_port2023_tn3270 import *


def test_tn3270_session_does_not_force_3270_after_timeout_without_eor(tmp_path):
    sess = make_session(tmp_path, chunks=[bytes([IAC, DO, BINARY, IAC, WILL, BINARY, IAC, WILL, TTYPE])])
    sess.negotiate()
    assert sess._wait_for_initial_negotiation(timeout=0.05) is False
    assert sess.in_3270_mode is False
    assert sess.sent_3270_bytes is False


def test_tn3270_session_ready_with_binary_eor_and_terminal_type(tmp_path):
    sess = make_session(tmp_path, initial=client_ready_bytes())
    sess.negotiate()
    assert sess._wait_for_initial_negotiation(timeout=0.05) is True
    assert sess.in_3270_mode is True
