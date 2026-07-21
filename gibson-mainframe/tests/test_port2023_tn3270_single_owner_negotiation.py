import inspect
from tests.helpers_port2023_tn3270 import *
from gibson.net import vtam_frontend


def test_frontend_contains_no_active_tn3270_sendall_probe():
    src = inspect.getsource(vtam_frontend.negotiate_tn3270_or_ascii)
    assert 'sendall' not in src
    assert '_terminal_type_send' not in src
    assert 'initial_tn3270_negotiation' not in src


def test_session_negotiates_once(tmp_path):
    sess = make_session(tmp_path)
    sess.negotiate(); first = bytes(sess.conn.sent)
    sess.negotiate(); second = bytes(sess.conn.sent)
    assert first == second
    assert sess.negotiated_once is True
