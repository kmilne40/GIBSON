from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsEnvironment
from gibson.tools.omvs_nmap import run_omvs_nmap
from gibson.apps.tomcat_sim.state import create_session


def test_nmap_sim_shows_tomcat_and_31337_state(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    env=OmvsEnvironment(state)
    out=run_omvs_nmap(['mainframe','-p','8080','--script','http-title,http-auth,http-tomcat-manager'], env, '/u/ibmuser')
    assert 'Apache-Coyote' in out and 'tomcat:tomcat' in out
    closed=run_omvs_nmap(['mainframe','-p','31337'], env, '/u/ibmuser')
    assert 'closed' in closed
    create_session(state,'/shell_exploit','tomcat')
    openout=run_omvs_nmap(['mainframe','-p','31337'], env, '/u/ibmuser')
    assert 'open' in openout and 'tomcat-bind-safe' in openout
