from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.dvca import hack3270_bridge as h


def make_state(vuln=True):
    return GibsonState.create(GibsonConfig(security_mode='vuln' if vuln else 'secure', dvca_vuln=vuln))


def _menu(st):
    snap = h.start(st); sid = snap['session_id']
    h.send_aid(st, sid, 'PF5')
    return sid


def test_normal_terminal_input_menu_options_work():
    st = make_state(True)
    sid = _menu(st)
    assert h.send_input(st, sid, '1')['screen_id'] == 'MCOR'
    sid = _menu(st)
    assert h.send_input(st, sid, '2')['screen_id'] == 'MCAD'
    sid = _menu(st)
    assert h.send_input(st, sid, '3')['screen_id'] == 'MCHI'
    sid = _menu(st)
    assert h.send_input(st, sid, 'H')['screen_id'] == 'HELP'


def test_hidden_99_vulnerable_and_secure():
    st = make_state(True); sid = _menu(st)
    out = h.send_input(st, sid, '99')
    assert 'HISTORY DELETED' in out['message']
    st = make_state(False); sid = _menu(st)
    out = h.send_input(st, sid, '99')
    assert 'BLOCKED' in out['message']
