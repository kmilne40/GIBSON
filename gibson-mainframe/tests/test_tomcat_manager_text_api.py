from __future__ import annotations
import base64, tempfile, threading, urllib.request, urllib.error
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.cbsa_rest8080 import Cbsa8080Handler, ThreadedHTTPServer


def _server():
    cfg=GibsonConfig(host='127.0.0.1', cbsa_api_port=0, sim_root=Path(tempfile.mkdtemp()))
    state=GibsonState.create(cfg)
    Cbsa8080Handler.state=state
    srv=ThreadedHTTPServer(('127.0.0.1',0), Cbsa8080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state,srv,f'http://127.0.0.1:{srv.server_address[1]}'

def _auth(): return {'Authorization':'Basic '+base64.b64encode(b'tomcat:tomcat').decode()}

def test_text_api_deploy_list_undeploy():
    state,srv,base=_server()
    try:
        req=urllib.request.Request(base+'/manager/text/list', headers=_auth())
        assert urllib.request.urlopen(req).read().decode().startswith('OK - Listed')
        data=b'GIBSON-SAFE-WAR LPORT=31337'
        req=urllib.request.Request(base+'/manager/text/deploy?path=/shell_exploit&update=true', data=data, headers=_auth(), method='PUT')
        assert 'OK - Deployed' in urllib.request.urlopen(req).read().decode()
        req=urllib.request.Request(base+'/manager/text/list', headers=_auth())
        body=urllib.request.urlopen(req).read().decode()
        assert '/shell_exploit:running' in body
        req=urllib.request.Request(base+'/manager/text/serverinfo', headers=_auth())
        assert 'z/OS UNIX' in urllib.request.urlopen(req).read().decode()
        req=urllib.request.Request(base+'/manager/text/undeploy?path=/shell_exploit', headers=_auth())
        assert 'OK - Undeployed' in urllib.request.urlopen(req).read().decode()
    finally:
        srv.shutdown()
