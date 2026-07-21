from pathlib import Path
import tempfile
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor


def make_shell():
    root=Path(tempfile.mkdtemp())
    cfg=GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    st=GibsonState.create(cfg)
    return OmvsShellSession(st,'IBMUSER',TsoCommandProcessor(st,'IBMUSER'))


def test_tso_enum_default_and_script_args():
    shell=make_shell()
    out=shell.execute("nmap -p 2023 --script tso-enum --script-args tso-enum.commands='L TSO' mainframe")
    assert 'tso-enum' in out
    assert 'IBMUSER' in out
    assert 'Starting Nmap' in out
    assert 'Transport mode:' not in out


def test_tso_enum_userdb_and_outputs():
    shell=make_shell()
    shell.env.write_text('/u/ibmuser/users.txt', 'IBMUSER\n9BAD\nTOOLONG1\n')
    out=shell.execute('nmap -p 2023 --script tso-enum -u users.txt -oN tso.txt -oJ tso.json mainframe')
    assert 'IBMUSER' in out
    assert 'INVALID_TSO_USERID' in out
    assert 'tso-enum' in shell.env.read_text('/u/ibmuser/tso.txt')
    assert '"script": "tso-enum"' in shell.env.read_text('/u/ibmuser/tso.json')


def test_tso_enum_output_traversal_rejected():
    shell=make_shell()
    out=shell.execute('nmap -p 2023 --script tso-enum -oN ../../escape.txt mainframe')
    assert 'escapes OMVS workspace' in out
