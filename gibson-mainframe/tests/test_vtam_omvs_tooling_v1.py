from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.net.vtam_frontend import coloured_ascii_vtam_screen, tn3270_vtam_screen
from gibson.apps.omvs import OmvsShellSession


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root / 'f', commands_dir=root / 'f' / 'commands', gacf_path=root / 'GACF.DB', default_system_hostname='GIBSON')
    return GibsonState.create(cfg)


def test_live_vtam_r05_binky_render_path():
    st = make_state()
    st.set_system_hostname('BINKY')
    screen = coloured_ascii_vtam_screen(addr=('192.168.0.97', 10456), service_port=2023, system_name=st.get_system_hostname())
    assert 'BINKY PRODUCTION LPAR' in screen
    assert 'CLIENT IP: 192.168.0.97' in screen
    assert 'GIBSON PRODUCTION LPAR' not in screen
    buf = tn3270_vtam_screen(addr=('192.168.0.97', 10456), service_port=2023, system_name=st.get_system_hostname())
    text = '\n'.join(''.join(str(cell) for cell in row) for row in buf.lines)
    assert 'BINKY PRODUCTION LPAR' in text
    assert 'GIBSON PRODUCTION LPAR' not in text


def test_hosts_txt_and_r05_alias():
    st = make_state(); st.set_system_hostname('BINKY')
    sh = OmvsShellSession(st, 'IBMUSER')
    assert 'binky' in sh.execute('hosts list').lower()
    assert 'BINKY -> 127.0.0.1' in sh.execute('hosts resolve BINKY')


def test_omvs_nmap_chapter7_scripts():
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    assert 'Anonymous FTP login allowed' in sh.execute('nmap mainframe -p21 --script ftp-anon -sV')
    assert 'DB2 Version: DSN12015' in sh.execute('nmap mainframe -p50000 --script db2-das-info -sV')
    assert 'applid:TSO' in sh.execute('nmap mainframe -p2023 --script vtam-enum')


def test_omvs_osint_tools():
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    assert 'mainframe.sighberbank.com' in sh.execute('subfinder -d sighberbank.com -resolve')
    assert 'ANSWER SECTION' in sh.execute('dig any sighberbank.com')
    assert 'SIGHBERBANK.COM' in sh.execute('whois sighberbank.com')
    assert 'IKJ56700A ENTER USERID' in sh.execute('shodan search "IKJ56700A port:23"')
    assert 'Livingston' in sh.execute('geoloc 192.168.0.97')


def test_omvs_nikto_db2_task_tshocker():
    st = make_state(); sh = OmvsShellSession(st, 'IBMUSER')
    assert 'Supplied credentials accepted' in sh.execute('nikto -h http://mainframe:8080/manager/html -id tomcat:tomcat -C all')
    assert 'DB2 subsystem' in sh.execute('db2connect mainframe IBMUSER SYS1')
    assert 'Created task 1' in sh.execute('task add "Review SMF119 records" project:gibson pri:H +cti')
    assert 'Review SMF119 records' in sh.execute('task list')
    assert 'CATSO L 40000' in sh.execute('tshocker --print -p 21 -l --lport 40000 mainframe RUARIV SPRING26')
