from pathlib import Path
import tempfile
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.tools.nmap_menu_engine import render_menu, run_action, NmapMenuState


def make_shell():
    root=Path(tempfile.mkdtemp())
    cfg=GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    st=GibsonState.create(cfg)
    return OmvsShellSession(st,'IBMUSER',TsoCommandProcessor(st,'IBMUSER'))


def test_nmap_menu_lists_full_uploaded_options():
    menu=render_menu()
    assert 'Quick screen grab' in menu
    assert 'TSO user enumeration' in menu
    assert 'CICSPWN simulation' in menu
    assert 'Export last results' in menu


def test_omvs_nmap_m_option_2_runs_tso_enum():
    shell=make_shell()
    out=shell.execute('nmap -M 2')
    assert 'NMAP MENU OPTION 2' in out
    assert 'tso-enum' in out
    assert 'IBMUSER' in out
    assert 'Transport mode: FALLBACK' in out
    assert 'interactive nmap-sim menu mode is not available' not in out


def test_nmap_menu_export_last_results_to_safe_path():
    st=NmapMenuState()
    out=run_action('2', state=st)
    assert 'tso-enum' in out
    tmp=Path(tempfile.mkdtemp())/'last.txt'
    out=run_action('9', ['-oN', str(tmp)], state=st)
    assert 'EXPORTED' in out
    assert 'tso-enum' in tmp.read_text()
