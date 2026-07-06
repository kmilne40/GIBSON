from types import SimpleNamespace
import tempfile

from gibson.cli import build_state
from gibson.core.state import GibsonState
from gibson.core import dvcapin
from gibson.apps.master_console import MasterConsoleController
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.cics import CicsSimulator
from gibson.apps.master_console_curses import ZeroMatrixAnimator
from gibson.apps.racf_services.menu import racf_services_command


def test_dvca_brute_force_is_single_panel_tick_animation():
    st = GibsonState.create()
    dvcapin.set_pin(st, '1234', actor='TEST')
    st.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    st.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', '0000\n0001\n1111\n1234\n9999\n')
    out = execute_dvca(st, 'IBMUSER', 'BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert out.count('DVCA MCAD PIN BRUTE FORCE') == 1
    assert 'STATUS       ===> RUNNING' in out
    sess = [x for x in st.pin_brute_sessions.values() if x.app == 'DVCA MCAD'][0]
    now = sess.last_tick_time
    for i in range(1, 6):
        sess.maybe_tick(st, now=now + i * 1.1)
    final = sess.render_frame(final=True)
    assert 'PIN FIELD    ===> 1234' in final
    assert 'PIN MATCH FOUND' in final


def test_r06_ipl_prompt_and_d_display_reveals_training_pin():
    st = GibsonState.create(); mc = MasterConsoleController(st)
    mc.execute('R 01,CLPA'); mc.execute('R 02,U'); mc.execute('R 03,Y'); mc.execute('R 04,1111')
    out = mc.execute('R 05,GIBSON1').text
    assert 'R 06 DEFINE 4-DIGIT DVCAPIN' in out
    assert 'R 06 DEFINE 4-DIGIT DVCAPIN' in mc.execute('D R,L').text
    assert 'GIBPIN006I DVCAPIN SET' in mc.execute('R 06,DVCAPIN=1234').text
    assert 'DVCAPIN = 1234' in mc.execute('D DVCAPIN').text


def test_omen_requires_auth_pin_and_single_panel_bruteforce_by_default(tmp_path):
    args = SimpleNamespace(gacf=None, sim_root=str(tmp_path), secure=False, vuln=False, cbsa_vuln=True, split_console=False, logon_panel=False, host='127.0.0.1', port=None, ftp_port=None, uss_port=None, tn3270_port=None, db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False, with_web_terminal=False, web_terminal_port=None, cbsa_api_port=18080)
    st = build_state(args); c = CicsSimulator(st, 'IBMUSER')
    assert 'CBPP SIGNON REQUIRED' in c.execute('OMEN')
    assert 'PIN REQUIRED' in c.execute('IBMUSER SYS1')
    out = c.execute('BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert out.count('CBSA OMEN PIN BRUTE FORCE') == 1
    assert 'STATUS       ===> RUNNING' in out


def test_racf_services_never_unavailable_and_options_populate():
    st = GibsonState.create()
    assert 'RACF SERVICES NOT AVAILABLE' not in racf_services_command(st, 'IBMUSER', 'RACFSERV')
    for opt, title in [('1','DATASET'), ('2','GENERAL RESOURCE'), ('3','GROUP'), ('4','USER PROFILE'), ('5','SYSTEM SECURITY'), ('6','REMOTE SHARING'), ('7','DIGITAL CERTIFICATES')]:
        out = racf_services_command(st, 'IBMUSER', 'RACFSERV ' + opt)
        assert 'RACF SERVICES NOT AVAILABLE' not in out
        assert 'RACF' in out
        assert title.split()[0] in out.upper()


def test_processor_activity_ratios_and_idle_motion():
    anim = ZeroMatrixAnimator(seed=1)
    idle1 = anim.frame(40, 5, False); idle_hot = len(anim.hot_cells())
    idle2 = anim.frame(40, 5, False)
    assert idle1 != idle2
    assert 6 <= idle_hot <= 18
    active = anim.frame(40, 5, True); active_hot = len(anim.hot_cells())
    assert 90 <= active_hot <= 110
    # no ordinary command burst should become a fully joined red block
    for row in range(5):
        red_cols = sorted(c for (r, c), col in anim._cells.items() if r == row and col == 'red')
        assert all((b - a) > 1 for a, b in zip(red_cols, red_cols[1:]))


def test_master_console_full_layout_survives_r05_r06_and_d_dvcapin():
    st = GibsonState.create(); mc = MasterConsoleController(st)
    initial = mc.render_full_console()
    assert 'GIBSON MASTER CONSOLE' in initial
    assert 'OPERLOG / ALERT STREAM' in initial
    assert 'SYSTEM PROCESSING' in initial
    assert 'COMMAND ===>' in initial

    mc.execute('R 01,CLPA'); mc.execute('R 02,U'); mc.execute('R 03,Y'); mc.execute('R 04,1111')
    r05 = mc.execute('R 05,GIBSON1')
    screen05 = mc.render_full_console(r05.text)
    assert 'GIBSON MASTER CONSOLE' in screen05
    assert 'OPERLOG / ALERT STREAM' in screen05
    assert 'SYSTEM PROCESSING' in screen05
    assert 'COMMAND ===>' in screen05
    assert 'R 06 DEFINE 4-DIGIT DVCAPIN' in screen05
    assert 'MASTER CONSOLE REPLAY' not in screen05.upper()

    r06 = mc.execute('R 06,DVCAPIN=1234')
    screen06 = mc.render_full_console(r06.text)
    assert 'GIBSON MASTER CONSOLE' in screen06
    assert 'OPERLOG / ALERT STREAM' in screen06
    assert 'SYSTEM PROCESSING' in screen06
    assert 'COMMAND ===>' in screen06
    assert 'GIBPIN006I DVCAPIN SET' in screen06
    assert 'MASTER CONSOLE REPLAY' not in screen06.upper()

    dd = mc.execute('D DVCAPIN')
    screen_dd = mc.render_full_console(dd.text)
    assert 'GIBSON MASTER CONSOLE' in screen_dd
    assert 'OPERLOG / ALERT STREAM' in screen_dd
    assert 'SYSTEM PROCESSING' in screen_dd
    assert 'COMMAND ===>' in screen_dd
    assert 'DVCAPIN = 1234' in screen_dd
    assert 'MASTER CONSOLE REPLAY' not in screen_dd.upper()
