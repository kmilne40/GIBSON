from types import SimpleNamespace

from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.master_console import MasterConsoleController
from gibson.apps.racf_services.menu import racf_services_command
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.cli import build_state
from gibson.apps.cics import CicsSimulator


def test_racf_services_handler_returns_none_for_non_owned_commands():
    st = GibsonState.create()
    for cmd in [
        'HELP', 'LISTUSER IBMUSER', 'LU IBMUSER', 'NETSTAT HOME',
        'DISPLAY TCPIP,,NETSTAT,HOME', 'SUBMIT TEST USER(IBMUSER)',
        'OMVS', 'SDSF', 'DB2', 'PTKTSTAT', 'ZSEC EVENTS', 'F3', 'END', 'CANCEL'
    ]:
        assert racf_services_command(st, 'IBMUSER', cmd) is None, cmd


def test_tso_core_commands_are_not_hijacked_by_racf_services():
    st = GibsonState.create(); tso = TsoCommandProcessor(st, 'IBMUSER')
    probes = {
        'HELP': 'TSO HELP FACILITY',
        'LISTUSER IBMUSER': 'USER=IBMUSER',
        'LU IBMUSER': 'USER=IBMUSER',
        'NETSTAT HOME': 'EZZ2350I',
        'DISPLAY TCPIP,,NETSTAT,HOME': 'EZZ2350I',
        'SUBMIT TEST USER(IBMUSER)': 'SUBMITTED',
        'OMVS': 'GIBSON-INTERACTIVE:OMVS',
        'SDSF': 'SDSF',
        'DB2': 'GIBSON-INTERACTIVE:DB2',
        'PTKTSTAT': 'PTKTDATA',
        'ZSEC EVENTS': 'ZSECURE',
    }
    for cmd, expected in probes.items():
        out = tso.run(cmd)
        assert 'RACF - SERVICES OPTION MENU' not in out, cmd
        assert 'RACF PANEL INPUT NOT RECOGNISED' not in out, cmd
        assert expected in out, (cmd, out[:300])


def test_racf_services_explicit_commands_still_work():
    st = GibsonState.create(); tso = TsoCommandProcessor(st, 'IBMUSER')
    for cmd in ['RACFSERV', 'RACFSERV 1', 'RACFSERV 2', 'RACFSERV 3', 'RACFSERV 4', 'RACFSERV 5', 'RACFSERV 6', 'RACFSERV 7', 'RACFSERV 99']:
        out = tso.run(cmd)
        assert 'RACF' in out, (cmd, out)


def test_master_console_netstat_does_not_inject_racf_services():
    st = GibsonState.create(); mc = MasterConsoleController(st)
    res = mc.execute('NETSTAT HOME')
    screen = mc.render_full_console(res.text)
    assert 'GIBSON MASTER CONSOLE' in screen
    assert 'EZZ2350I' in screen
    assert 'RACF - SERVICES OPTION MENU' not in screen


def test_dvca_and_omen_pin_bruteforce_frames_change_and_are_coloured(tmp_path):
    st = GibsonState.create()
    out1 = execute_dvca(st, 'IBMUSER', 'BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    sess = [x for x in st.pin_brute_sessions.values() if x.app == 'DVCA MCAD'][0]
    sess.maybe_tick(st, now=sess.last_tick_time + 1.1)
    out2 = sess.render_frame()
    assert out1.count('DVCA MCAD PIN BRUTE FORCE') == 1
    assert out2.count('DVCA MCAD PIN BRUTE FORCE') == 1
    assert out1 != out2
    assert '\x1b[' in out1 or '▪' in out1

    args = SimpleNamespace(gacf=None, sim_root=str(tmp_path), secure=False, vuln=False, cbsa_vuln=True, split_console=False, logon_panel=False, host='127.0.0.1', port=None, ftp_port=None, uss_port=None, tn3270_port=None, db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False, with_web_terminal=False, web_terminal_port=None, cbsa_api_port=18080)
    st2 = build_state(args); c = CicsSimulator(st2, 'IBMUSER')
    assert 'CBPP SIGNON REQUIRED' in c.execute('OMEN')
    assert 'PIN REQUIRED' in c.execute('IBMUSER SYS1')
    cb1 = c.execute('BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    sess = [x for x in st2.pin_brute_sessions.values() if x.app == 'CBSA OMEN'][0]
    sess.maybe_tick(st2, now=sess.last_tick_time + 1.1)
    cb2 = sess.render_frame()
    assert cb1.count('CBSA OMEN PIN BRUTE FORCE') == 1
    assert cb2.count('CBSA OMEN PIN BRUTE FORCE') == 1
    assert cb1 != cb2
    assert '\x1b[' in cb1 or '▪' in cb1
