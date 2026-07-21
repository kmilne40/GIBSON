from types import SimpleNamespace

from gibson.apps.pin_bruteforce import start_pin_bruteforce
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.cics import CicsSimulator
from gibson.apps.welcome.routes import render_page
from gibson.cli import build_state
from gibson.core.state import GibsonState
from gibson.core import dvcapin


def _state_with_pin(pin='2468'):
    st = GibsonState.create()
    dvcapin.set_pin(st, pin, actor='TEST')
    st.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    st.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', f'0000\n1337\n{pin}\n9999\n')
    return st


def test_pin_brute_session_auto_ticks_on_elapsed_second_not_enter():
    st = _state_with_pin('2468')
    sess = start_pin_bruteforce(st, 'IBMUSER', 'DVCA MCAD', 'IBMUSER.4CHAR.PIN', now=100.0)
    first = sess.render_frame()
    assert sess.attempts == 0
    changed = sess.maybe_tick(st, now=100.5)
    assert changed is False
    assert sess.attempts == 0
    changed = sess.maybe_tick(st, now=101.1)
    assert changed is True
    assert sess.attempts == 1
    second = sess.render_frame()
    assert first != second


def test_dvca_uses_ipl_configured_dvcapin_not_legacy_1337():
    st = _state_with_pin('2468')
    assert 'ACCESS GRANTED' in execute_dvca(st, 'IBMUSER', 'PIN 2468')
    assert 'ACCESS DENIED' in execute_dvca(st, 'IBMUSER', 'PIN 1337')
    out = execute_dvca(st, 'IBMUSER', 'BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert 'DVCA MCAD PIN BRUTE FORCE' in out
    # Simulate elapsed seconds; no ENTER semantics are needed to advance the engine.
    sess = [s for s in st.pin_brute_sessions.values() if s.app == 'DVCA MCAD'][0]
    now = sess.last_tick_time
    for i in range(1, 6):
        sess.maybe_tick(st, now=now + i * 1.1)
    final = sess.render_frame(final=True)
    assert '2468' in final
    assert 'PIN MATCH FOUND' in final
    assert 'PIN FOUND 1337' not in final


def test_omen_uses_ipl_configured_dvcapin_not_legacy_1337(tmp_path):
    args = SimpleNamespace(gacf=None, sim_root=str(tmp_path), secure=False, vuln=False, cbsa_vuln=True, split_console=False, logon_panel=False, host='127.0.0.1', port=None, ftp_port=None, uss_port=None, tn3270_port=None, db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False, with_web_terminal=False, web_terminal_port=None, cbsa_api_port=18080)
    st = build_state(args)
    dvcapin.set_pin(st, '2468', actor='TEST')
    st.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    st.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', '0000\n1337\n2468\n9999\n')
    c = CicsSimulator(st, 'IBMUSER')
    assert 'CBPP SIGNON REQUIRED' in c.execute('OMEN')
    assert 'PIN REQUIRED' in c.execute('IBMUSER SYS1')
    assert 'PIN INVALID' in c.execute('PIN 1337')
    assert 'OMEN READY' in c.execute('PIN 2468')
    # reset and test brute force path
    c.execute('CBPP RESET')
    c.execute('OMEN')
    c.execute('IBMUSER SYS1')
    out = c.execute('BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert 'CBSA OMEN PIN BRUTE FORCE' in out
    sess = [s for s in st.pin_brute_sessions.values() if s.app == 'CBSA OMEN'][0]
    now = sess.last_tick_time
    for i in range(1, 6):
        sess.maybe_tick(st, now=now + i * 1.1)
    final = sess.render_frame(final=True)
    assert '2468' in final
    assert 'PIN MATCH FOUND' in final


def test_welcome_page_contains_updated_gibson_overview():
    code, ctype, body = render_page('/')
    assert code == 200
    assert 'Welcome to Gibson' in body
    assert 'safe educational IBM mainframe simulator' in body
    for term in ['TSO', 'ISPF', 'CICS', 'Db2', 'RACF', 'PassTickets']:
        assert term in body
    assert 'How it came into being' in body
    assert 'What it is useful for' in body
    assert 'OffensiveSec Gibson project page' in body
    assert 'TODO' not in body.upper()
