from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path):
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/'f', commands_dir=tmp_path/'f'/'commands', gacf_path=tmp_path/'GACF.DB')
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS:SYS1\nGUEST:SYS1:NONE:NOOMVS:STUDENT\n')
    return GibsonState.create(cfg)


def test_all_requested_zsec_commands_return_reports(tmp_path):
    st=make_state(tmp_path)
    tso=TsoCommandProcessor(st,'IBMUSER')
    topics = ['','HELP','?','PRIVILEGE','UID0','STARTED','SURROGAT','JES','TSOAUTH','SERVAUTH','PASSTICKET','CICS','DB2','ICSF','RACDCERT','RARE','DRIFT','FIRST30','RACFDS','SETROPTS','MFA','EVENTS','ALERTS','SMF','RACF','ACCESS','COMPLIANCE','REPORTS','APF','SMF80','SMF7','SMF30','SMF100']
    for topic in topics:
        cmd = 'ZSEC' if topic == '' else f'ZSEC {topic}'
        out = tso.run(cmd)
        assert out and 'UNKNOWN COMMAND' not in out.upper(), cmd
        assert 'ZSEC' in out.upper() or 'APF' in out.upper() or 'SETROPTS' in out.upper(), cmd
    assert 'SMF TYPE 30' in tso.run('ZSEC SMF30')
    assert 'SMF TYPE 100' in tso.run('ZSEC SMF100')
    assert 'HELP' in tso.run('ZSEC ?') or 'COMMANDS' in tso.run('ZSEC ?')
