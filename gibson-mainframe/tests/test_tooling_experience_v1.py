from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.fibs_training.lab_catalog import get_lab
from gibson.apps.fibs_training.lab_rendering import render_lab_detail


def make_shell():
    root=Path(tempfile.mkdtemp())
    cfg=GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    st=GibsonState.create(cfg)
    return OmvsShellSession(st,'IBMUSER',TsoCommandProcessor(st,'IBMUSER'))


def test_hosts_aliases_are_simulated_and_scope_limited():
    sh=make_shell()
    assert 'mainframe 127.0.0.1' in sh.execute('hosts list')
    assert 'added mf' in sh.execute('hosts add mf 127.0.0.1')
    assert 'mf -> 127.0.0.1' in sh.execute('hosts resolve mf')
    assert 'denied' in sh.execute('nmap evil.com -p2023').lower()


def test_nmap_tso_enum_alias_and_port_compatibility():
    sh=make_shell()
    sh.env.write_text('/u/ibmuser/tso_users.txt','IBMUSER\nGUEST\n9BAD\n')
    out=sh.execute('nmap mainframe -p23 --script=tso-enum --script-args userdb=tso_users.txt,tso-enum.commands="logon applid(TSO)"')
    assert 'tso-enum' in out
    assert 'IBMUSER' in out
    assert 'INVALID_TSO_USERID' in out or 'GUEST' in out
    assert 'Transport mode:' in out


def test_cicspwn_command_safe_stages():
    sh=make_shell()
    out=sh.execute('CICSPWN mainframe --port 2023 --mode forensic --safe')
    assert 'CICSPWN' in out
    assert 'transaction-access' in out
    assert 'capability-assessment' in out
    assert 'No real exploit' in out or 'safe Gibson' in out


def test_msfconsole_alias_tomcat_flow_and_session():
    sh=make_shell()
    out=sh.execute("msfconsole -x 'search tomcat; use exploit/multi/http/tomcat_mgr_upload; show options; run; sessions; sessions -i 1'")
    assert 'tomcat_mgr_upload' in out
    assert 'Command shell session' in out
    assert 'uid=12345(tomcat) gid=1000(tomcat)' in out
    nmap=sh.execute('nmap mainframe -p31337')
    assert 'open' in nmap and '31337/tcp' in nmap


def test_cobol_bo_page_contains_annotated_source():
    lab=get_lab('cobol-buffer-overflow')
    html=render_lab_detail(lab,'test')
    assert 'Annotated COBOL/CICS source' in html
    assert 'vuln-line' in html
    assert 'MOVE USER-INPUT TO CUSTOMER-RECORD' in html
    assert 'Unchecked MOVE into smaller record' in html
