from pathlib import Path

from gibson.apps.cics import CicsSimulator
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.dashboard import _DashboardHandler


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / 'f', commands_dir=tmp_path / 'f' / 'commands', gacf_path=tmp_path / 'GACF.DB')
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_dashboard_snapshot_contains_bruteforce_and_apf_alerts(tmp_path):
    st = make_state(tmp_path)
    st.note_failed_logon('IBMUSER', '10.0.0.55', port=st.config.port, service='VTAM/TSO')
    st.note_failed_logon('IBMUSER', '10.0.0.55', port=st.config.port, service='VTAM/TSO')
    st.note_failed_logon('IBMUSER', '10.0.0.55', port=st.config.port, service='VTAM/TSO')
    assert any(a['event_type'] == 'BRUTE_FORCE' and a['addr'] == '10.0.0.55' and a['port'] == st.config.port for a in st.recent_dashboard_alerts())

    from gibson.apps.tso import TsoCommandProcessor
    tso = TsoCommandProcessor(st, 'IBMUSER')
    tso.run("SETPROG APF,ADD,DSNAME='IBMUSER.APF.LIB',VOLUME=WORK01")
    snap = _DashboardHandler._snapshot(type('X', (), {'state': st})())
    assert any(a['event_type'] == 'APF_LIBRARY' for a in snap['alerts'])


def test_mcgm_bank_login_lookup_and_safe_admin_redirect(tmp_path, monkeypatch):
    st = make_state(tmp_path)
    cics = CicsSimulator(st, 'IBMUSER')
    login = cics.execute('GMVB LOGN IBMUSER SYS1')
    assert 'MENU - MAIN MENU' in login
    carg = cics.execute('GMVB CARG 00001')
    assert 'STEEL FASTENER CRATE' in carg
    blocked = cics.execute('GMVB ADMN')
    assert 'HIDDEN ADMIN FUNCTIONS' in blocked

    st2 = make_state(tmp_path / 'demo')
    monkeypatch.setenv('GIBSON_CICS_BANK_DEMO_ADMIN', '1')
    cics2 = CicsSimulator(st2, 'GUEST')
    cics2.execute('GMVB LOGN GUEST GUEST')
    redirected = cics2.execute('GMVB CARG 00001XXXXXXXXADMN')
    assert 'TRAINING DEMO CONTROL-FLOW REDIRECT ACTIVE' in redirected
    assert 'HIDDEN ADMIN FUNCTIONS' in redirected
