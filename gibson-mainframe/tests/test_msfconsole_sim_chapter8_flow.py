from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.msfconsole_sim import run_msfconsole_sim
from gibson.apps.tomcat_sim.state import active_sessions


def test_msfconsole_sim_chapter8_creates_session(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    out=run_msfconsole_sim(state,['chapter8'])
    assert 'tomcat_mgr_upload' in out
    assert 'Command shell session' in out
    assert active_sessions(state)
    out=run_msfconsole_sim(state,['-x','set HttpPassword bad; run'])
    assert 'Authentication failed' in out
