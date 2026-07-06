from tests.helpers_port2023_tn3270 import *


def test_failed_negotiation_sends_no_3270_screen(tmp_path):
    sess = make_session(tmp_path, chunks=[bytes([IAC, DO, BINARY])])
    sess.negotiate()
    assert sess._wait_for_initial_negotiation(timeout=0.05) is False
    assert sess.sent_3270_bytes is False
    assert 'not-ready' in sess.failure_reason
