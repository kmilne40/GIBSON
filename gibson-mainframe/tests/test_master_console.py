from pathlib import Path

from gibson.apps.master_console import MasterConsoleController
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.core.service_control import ManagedService


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        sim_root=tmp_path,
        files_root=tmp_path / 'f',
        commands_dir=tmp_path / 'f' / 'commands',
        gacf_path=tmp_path / 'GACF.DB',
    )
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\n', encoding='utf-8')
    st = GibsonState.create(cfg)
    st.service_manager.register(ManagedService('FTPD', port=2111, description='FTP service', state='STARTED', listener_tokens=('FTP',), start_msgs=('FTPD STARTED',), stop_msgs=('FTPD STOPPED',), pause_msgs=('FTPD PAUSED',)))
    st.service_manager.register(ManagedService('RACF', description='Security service', state='STARTED', start_msgs=('RACF STARTED',), stop_msgs=('RACF STOPPED',), pause_msgs=('RACF PAUSED',)))
    st.service_manager.register(ManagedService('OMVS', port=2022, description='USS', state='STARTED', listener_tokens=('OMVS', 'USS'), start_msgs=('OMVS STARTED',), stop_msgs=('OMVS STOPPED',), pause_msgs=('OMVS PAUSED',)))
    st.service_manager.register(ManagedService('JES2', description='JES2', state='STARTED', start_msgs=('JES2 STARTED',), stop_msgs=('JES2 STOPPED',), pause_msgs=('JES2 PAUSED',)))
    st.service_manager.register(ManagedService('TCPIP', description='TCPIP', state='STARTED', start_msgs=('TCPIP STARTED',), stop_msgs=('TCPIP STOPPED',), pause_msgs=('TCPIP PAUSED',)))
    return st


def test_master_console_boot_wtor_flow(tmp_path):
    st = make_state(tmp_path)
    c = MasterConsoleController(st)
    boot = c.boot_text()
    assert 'NUCLEUS INITIALIZATION PROGRAM ACTIVE' in boot
    assert 'R 01 IEA101A' in boot
    assert 'PENDING REQUESTS' in c.execute('D R,R').text
    step1 = c.execute('R 1,CLPA')
    assert 'SYSTEM PARAMETERS SET TO CLPA' in step1.text
    assert 'R 02 IEA347A' in step1.text
    step2 = c.execute('R 2,U')
    assert 'IEASYS MEMBER IEASYS00 SELECTED' in step2.text
    step3 = c.execute('R 3,Y')
    assert 'OPERATOR COMMAND PROCESSING ACTIVE' in step3.text
    assert 'NO OUTSTANDING REPLY REQUESTS' in c.execute('D R,R').text


def test_master_console_help_and_displays(tmp_path):
    st = make_state(tmp_path)
    c = MasterConsoleController(st)
    assert 'MASTER CONSOLE' in c.boot_text()
    assert 'PENDING REQUESTS' in c.execute('D R,L').text
    assert 'DISPLAY SERVICE STATUS' in c.execute('D SVC,L').text
    assert 'ACTIVITY DISPLAY' in c.execute('D A,L').text
    assert 'COMMAND / SYNTAX' in c.execute('?').text


def test_master_console_service_state_changes_and_shutdown_sequence(tmp_path):
    st = make_state(tmp_path)
    c = MasterConsoleController(st)
    assert 'FTPD STOPPED' in c.execute('P FTPD').text
    assert st.service_manager.get('FTPD').state == 'STOPPED'
    assert 'RACF PAUSED' in c.execute('PAUSE RACF').text
    assert st.service_manager.get('RACF').state == 'PAUSED'
    blocked = c.execute('Z EOD')
    assert blocked.action is None
    assert 'ACTIVE SERVICES' in blocked.text
    c.execute('P OMVS')
    c.execute('$P JES2')
    c.execute('P TCPIP')
    c.execute('P RACF')
    ok = c.execute('Z EOD')
    assert ok.action is None
    assert 'R ' in ok.text and 'CONFIRM END OF DAY' in ok.text
    reply_id = ok.text.split()[1]
    confirm = c.execute(f'R {reply_id},Y')
    assert confirm.action == 'shutdown'
    assert 'SYSTEM SHUTDOWN IN PROGRESS' in confirm.text


def test_service_manager_updates_listener_state(tmp_path):
    st = make_state(tmp_path)
    ftp = next(l for l in st.network.listeners if 'FTP' in l.name)
    assert ftp.state == 'LISTEN'
    st.service_manager.stop('FTPD')
    assert ftp.state == 'STOPPED'
    st.service_manager.start('FTPD')
    assert ftp.state == 'LISTEN'
