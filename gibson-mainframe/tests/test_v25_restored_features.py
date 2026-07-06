from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.sdsf import SdsfApp
from gibson.apps.master_console import MasterConsoleController


def test_v25_listds_members_status_history_and_catalog_cycle():
    s = GibsonState.create()
    s.datasets.allocate('IBMUSER', 'IBMUSER.V25.PDS', org='PO')
    s.datasets.write('IBMUSER', 'IBMUSER.V25.PDS(NEWMEM)', 'HELLO\n')
    tso = TsoCommandProcessor(s, 'IBMUSER')
    assert 'NEWMEM' in tso.run('LISTDS IBMUSER.V25.PDS MEMBERS')
    out = tso.run('LISTDS IBMUSER.V25.PDS STATUS HISTORY')
    assert 'STATUS/HISTORY' in out and 'MEMBER COUNT' in out
    assert 'UNCATALOGED' in s.datasets.uncatalog('IBMUSER', 'IBMUSER.V25.PDS')
    assert all(r.name != 'IBMUSER.V25.PDS' for r in s.datasets.listcat('IBMUSER', 'IBMUSER.V25'))
    assert 'CATALOGED' in s.datasets.catalog('IBMUSER', 'IBMUSER.V25.PDS')
    assert any(r.name == 'IBMUSER.V25.PDS' for r in s.datasets.listcat('IBMUSER', 'IBMUSER.V25'))


def test_v25_service_commands_and_sdsf_slash_operator_routing():
    s = GibsonState.create()
    tso = TsoCommandProcessor(s, 'IBMUSER')
    assert 'FTPD' in tso.run('S FTPD')
    assert 'FTPD' in tso.run('P FTPD')
    app = SdsfApp(s, 'IBMUSER')
    _panel, msg = app.apply_sdsf_command('SETPROG APF,ADD,DSNAME=IBMUSER.V25.LOAD,VOLUME=WORK01')
    assert 'APF' in msg.upper() or 'CSV' in msg.upper()
    assert any('IBMUSER.V25.LOAD' in x for x in s.apf_libraries)


def test_v25_secure_sys1_write_denied_and_noracf_bypasses():
    s = GibsonState.create(); s.config.security_mode = 'secure'
    try:
        s.datasets.write('GUEST', 'SYS1.PROCLIB(ZZZ)', 'bad')
        allowed = True
    except PermissionError:
        allowed = False
    assert not allowed
    assert 'NORACF' in TsoCommandProcessor(s, 'IBMUSER').run('NORACF')
    s.datasets.write('GUEST', 'SYS1.PROCLIB(ZZZ)', 'allowed in noracf')
    assert 'ZZZ' in s.datasets.members('GUEST', 'SYS1.PROCLIB')


def test_v25_send_now_live_and_smf7_and_warnings():
    s = GibsonState.create()
    inbox = []
    s.sessions.add('GUEST', '127.0.0.1', notifier=inbox.append)
    assert 'immediately' in TsoCommandProcessor(s, 'IBMUSER').run("SEND 'HELLO' USER(GUEST) NOW")
    assert any('HELLO' in msg for msg in inbox)
    s.audit.record_smf7(reason='SMF BUFFER FULL', affected_record_types='80', count_lost=2)
    assert any(e.component == 'SMF7' for e in s.audit.events)
    s.config.port_scan_threshold = 4
    s.note_port_touch('10.0.0.5', 23); s.note_port_touch('10.0.0.5', 21); s.note_port_touch('10.0.0.5', 175); s.note_port_touch('10.0.0.5', 446)
    assert any(a['event_type'] == 'PORT_SCAN' for a in s.dashboard_alerts)
    s.register_open_port(65000, component='UNITTEST')
    assert any(a['event_type'] == 'UNKNOWN_HIGH_PORT' for a in s.dashboard_alerts)


def test_v25_console_status_box_power_and_warning_search():
    s = GibsonState.create()
    ctl = MasterConsoleController(s)
    boot = ctl.boot_text()
    assert 'GIBSON HERCULES-STYLE CONTROL' in boot
    assert 'TIME' in boot and 'LOADED VOLUMES' in boot
    assert 'SYS1.PARMLIB' in TsoCommandProcessor(s, 'IBMUSER').run('SEARCH ALL WARNING NOMASK')
