from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.master_console import MasterConsoleController
from gibson.core import v26_features
from gibson.services.telnet_server import GibsonTelnetSession


def test_v26_core_commands_and_split_console():
    state = GibsonState.create()
    proc = TsoCommandProcessor(state, 'IBMUSER')
    assert 'NOT AVAILABLE' in proc.run('SPLITCON ON')
    assert 'NOT AVAILABLE' in proc.run('D SPLITCON')


def test_v26_security_smf_racf_explainers():
    state = GibsonState.create(); proc = TsoCommandProcessor(state, 'IBMUSER')
    assert 'ACCESS CHECK' in proc.run('WHYACCESS IBMUSER SYS1.PARMLIB UPDATE')
    assert 'RACF TRACE ENABLED' in proc.run('RACFTRACE ON')
    assert 'not available' in proc.run('EXPLAIN SPLITCON').lower()
    state.audit.record_smf7('SYSTEM', 'BUFFER FULL', count_lost=3)
    assert 'TYPE 7' in proc.run('SMF LIST TYPE(7)')
    assert 'SMF SIMULATED RECORD SUMMARY' in proc.run('SMF SUMMARY')


def test_v26_port_scan_alerts_console_and_dashboard():
    state = GibsonState.create()
    for port in [2023, 2022, 2111, 8443]:
        state.note_port_touch('198.51.100.77', port, 'TEST')
    alerts = list(state.dashboard_alerts)
    assert any(a.get('event_type') == 'PORT_SCAN' for a in alerts)
    events = state.drain_console_events()
    assert any('PORT SCAN' in text for _sev, text in events)


def test_v26_network_apf_detection_pf_scenario_evidence(tmp_path):
    state = GibsonState.create(); state.config.sim_root = tmp_path
    proc = TsoCommandProcessor(state, 'IBMUSER')
    assert 'NETWORK SESSION DISPLAY' in proc.run('D NET')
    assert 'APF AUTHORIZATION RISK DISPLAY' in proc.run('D APF,RISK')
    assert 'DETECTION RULES' in proc.run('D DETECTION')
    assert 'PF KEY DEFINITIONS' in proc.run('KEYS')
    assert 'AVAILABLE GIBSON SCENARIOS' in proc.run('SCENARIO LIST')
    out = proc.run('EXPORT EVIDENCE ALL SINCE(30M)')
    assert 'EVIDENCE BUNDLE EXPORTED' in out


def test_v26_master_console_split_and_service():
    state = GibsonState.create(); ctl = MasterConsoleController(state, 'IBMUSER')
    assert 'NOT AVAILABLE' in ctl.execute('SPLITCON ON').text
    assert 'NOT AVAILABLE' in ctl.execute('D SPLITCON').text
    assert 'STARTED' in ctl.execute('S FTPD').text or 'ALREADY ACTIVE' in ctl.execute('S FTPD').text


def test_v26_tsoe_panel_and_ispf_right_panel():
    panel = v26_features.tsoe_logon_panel('IBMUSER')
    assert 'TSO/E LOGON' in panel
    assert 'Command    ===> ispf' in panel
    right = v26_features.ispf_right_panel('IBMUSER')
    plain = '\n'.join(right)
    assert 'Time. . .' in plain
    assert 'System ID' in plain and 'S0W1' in plain
