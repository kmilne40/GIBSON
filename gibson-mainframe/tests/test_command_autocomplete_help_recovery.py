from pathlib import Path
import tempfile

from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.autocomplete import TsoAutocomplete
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', gacf_path=root/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:pass:SPECIAL:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_uss_command_discovery_contains_recovered_commands():
    st=make_state(); sh=OmvsShellSession(st,'IBMUSER',TsoCommandProcessor(st,'IBMUSER'))
    out=sh.execute('help')
    for cmd in ['rmdir','more','head','tail','chmod','chown','chgrp','date','grep','find','wc','sort','uniq','cut','tr','du','kill','set','umask','ln','tar','gzip','gunzip','od','hexdump','iconv','chtag','man','OPUT','OGET','OCOPY']:
        assert cmd in out
        assert 'not found' not in sh.execute(f'{cmd} ?').lower()


def test_tso_autocomplete_lists_zsec_subcommands():
    st=make_state(); ac=TsoAutocomplete(st)
    _completed, out = ac.complete('ZSEC SMF')
    assert 'ZSEC SMF30' in out and 'ZSEC SMF100' in out and 'ZSEC SMF80' in out
    _completed, out = ac.complete('ZSEC I')
    assert 'ZSEC ICSF' in out
