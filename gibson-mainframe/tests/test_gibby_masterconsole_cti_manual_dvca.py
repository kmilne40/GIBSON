from gibson.apps.welcome.routes import render_page
from gibson.apps.master_console_curses import format_bar, ZeroMatrixAnimator
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.core.state import GibsonState
from gibson.core import dvcapin


def test_welcome_contains_neuro_offensive_and_what_is_gibson():
    code, ctype, body = render_page('/welcome')
    assert code == 200
    assert 'What is Gibson?' in body
    assert 'Neuro Training Ltd' in body
    assert 'OffensiveSec.org' in body
    assert 'Mainframe Pen Test Training' in body


def test_cti_provider_routes_and_mitre_export():
    for path in ['/cti/providers','/cti/api-keys','/cti/enrichment?q=198.51.100.66','/cti/m4m','/cti/honeypot']:
        code, ctype, body = render_page(path)
        assert code == 200, path
        assert '<html' in body.lower()
    code, ctype, body = render_page('/cti/mitre?format=json')
    assert code == 200
    assert 'Gibson Mainframe Training Layer' in body


def test_manual_tables_render_as_tables_not_pre_blocks():
    code, ctype, body = render_page('/manual/full')
    assert code == 200
    assert 'manual-article' in body
    assert 'docs-layout' in body
    # A rendered manual should include scroll wrappers if it contains pipe tables.
    assert 'manual-table-wrap' in body or '<table' in body


def test_master_console_bar_and_zero_matrix():
    b = format_bar('HOST CPU', 100, 28)
    assert '100%' in b
    assert len(b) <= 40
    z = ZeroMatrixAnimator()
    idle = z.frame(16, 2, False)
    active = z.frame(16, 2, True)
    assert idle == ['0'*16, '0'*16]
    assert active == ['0'*16, '0'*16]
    assert z.hot_cells()


def test_dvca_hack_on_foreground_no_reverse_background():
    state = GibsonState.create()
    dvcapin.set_pin(state, '1234', actor='TEST')
    state.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    state.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', '0000\n0001\n1111\n1234\n9999\n')
    execute_dvca(state, userid='IBMUSER', command='DVCA')
    execute_dvca(state, userid='IBMUSER', command='MCOR')
    execute_dvca(state, userid='IBMUSER', command='HACK ON')
    out = execute_dvca(state, userid='IBMUSER', command='PRICE=20 SHIP=1 BUY=Y')
    assert '\x1b[31m' in out or '\x1b[91m' in out
    assert '\x1b[7m' not in out
    assert 'TRAINING LEGEND HACK ON' in out


def test_dvca_pin_brute_logs_evidence():
    state = GibsonState.create()
    dvcapin.set_pin(state, '1234', actor='TEST')
    state.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    state.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', '0000\n0001\n1111\n1234\n9999\n')
    execute_dvca(state, userid='IBMUSER', command='DVCA')
    execute_dvca(state, userid='IBMUSER', command='MCAD')
    execute_dvca(state, userid='IBMUSER', command='HACK ON')
    out = execute_dvca(state, userid='IBMUSER', command='BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert 'PIN FOUND 1337' not in out
    sess = [x for x in state.pin_brute_sessions.values() if x.app == 'DVCA MCAD'][0]
    now = sess.last_tick_time
    for i in range(1, 6):
        sess.maybe_tick(state, now=now + i * 1.1)
    final = sess.render_frame(final=True)
    assert 'PIN FIELD    ===> 1234' in final
    assert 'PIN MATCH FOUND' in final
