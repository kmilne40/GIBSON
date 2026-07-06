from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tomcat_sim.state import deploy_war, get_state


def test_war_upload_metadata_only_and_validation(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    ok,msg,dep=deploy_war(state,'/shell_exploit','ws_shell_exploit.war',b'payload LPORT=31337','tomcat',update=True)
    assert ok and dep is not None
    assert dep.sha256 and dep.raw == b''
    assert get_state(state).deployments['/shell_exploit'].filename == 'ws_shell_exploit.war'
    ok,msg,dep=deploy_war(state,'/bad','notwar.txt',b'x','tomcat')
    assert not ok and dep is None
    ok,msg,dep=deploy_war(state,'/../bad','x.war',b'x','tomcat')
    assert not ok
