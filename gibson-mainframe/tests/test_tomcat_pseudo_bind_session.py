from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tomcat_sim.state import deploy_war, create_session, active_sessions
from gibson.apps.tomcat_sim.session import run_command
from gibson.apps.tomcat_sim.events import record_payload_trigger


def test_safe_session_allowlist_and_alerts(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    ok,_,dep=deploy_war(state,'/shell_exploit','ws_shell_exploit.war',b'payload LPORT=31337','tomcat',update=True)
    assert ok and dep
    sess=create_session(state,'/shell_exploit','tomcat')
    record_payload_trigger(state,sess)
    assert active_sessions(state)
    assert run_command(state,sess.session_id,'id') == 'uid=12345(tomcat) gid=1000(tomcat)'
    assert 'denied' in run_command(state,sess.session_id,'sh -i').lower()
    assert any(a['port']==31337 for a in state.dashboard_alerts)
    assert any('31337' in text for _sev,text in state.console_events)
