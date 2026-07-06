from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tomcat_sim.state import deploy_war, create_session
from gibson.apps.tomcat_sim.events import record_upload, record_deploy, record_payload_trigger
from gibson.apps.zsecure_engine import zsecure_command


def test_zsecure_tomcat_report_reflects_state(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    ok,_,dep=deploy_war(state,'/shell_exploit','ws_shell_exploit.war',b'LPORT=31337','tomcat',update=True)
    assert ok and dep
    record_upload(state, dep); record_deploy(state, dep)
    sess=create_session(state,'/shell_exploit','tomcat')
    record_payload_trigger(state,sess)
    out=zsecure_command(state,'IBMUSER','ZSEC TOMCAT')
    assert 'ZSECURE TOMCAT REVIEW' in out
    assert 'TOMCAT' in out
    assert 'WAR' in out or '31337' in out
