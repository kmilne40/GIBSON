from pathlib import Path
import tempfile
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.core.v26_features import dispatch_tso


def make_state():
    root=Path(tempfile.mkdtemp())
    cfg=GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_tso_nmap_menu_and_option_2():
    st=make_state()
    menu=dispatch_tso(st,'IBMUSER','NMAP MENU')
    assert 'M.10 NMAP' in menu
    out=dispatch_tso(st,'IBMUSER','NMAP 2')
    assert 'NMAP MENU OPTION 2' in out
    assert 'tso-enum' in out
    assert 'IBMUSER' in out
