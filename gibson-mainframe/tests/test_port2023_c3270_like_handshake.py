from tests.helpers_port2023_tn3270 import *


def test_c3270_like_handshake_ready_and_no_tn3270e_header(tmp_path):
    sess = make_session(tmp_path, initial=client_ready_bytes(b'IBM-3278-2-E'))
    sess.negotiate()
    assert sess._wait_for_initial_negotiation(timeout=0.05) is True
    screen = sess.vtam_screen().to_3270()
    assert not screen.startswith(bytes([0, 0, 0, 0, 0]))
    assert screen.endswith(bytes([IAC, 0xEF]))
