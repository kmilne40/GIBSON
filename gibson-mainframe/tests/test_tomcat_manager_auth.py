from __future__ import annotations
import base64, tempfile, threading, urllib.request, urllib.error
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.cbsa_rest8080 import Cbsa8080Handler, ThreadedHTTPServer


def _server(secure=False):
    cfg=GibsonConfig(host='127.0.0.1', cbsa_api_port=0, sim_root=Path(tempfile.mkdtemp()))
    state=GibsonState.create(cfg)
    state.tomcat_sim_config = __import__('gibson.apps.tomcat_sim.config', fromlist=['TomcatSimConfig']).TomcatSimConfig(secure_mode=secure)
    Cbsa8080Handler.state=state
    srv=ThreadedHTTPServer(('127.0.0.1',0), Cbsa8080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state,srv,f'http://127.0.0.1:{srv.server_address[1]}'

def _auth(user,pw):
    return {'Authorization':'Basic '+base64.b64encode(f'{user}:{pw}'.encode()).decode()}

def test_required_credentials_and_alerts():
    state,srv,base=_server()
    try:
        for pw in ['tomcat','manager']:
            req=urllib.request.Request(base+'/manager/html', headers=_auth('tomcat', pw))
            assert urllib.request.urlopen(req).status == 200
        req=urllib.request.Request(base+'/manager/html', headers=_auth('tomcat', 'bad'))
        try:
            urllib.request.urlopen(req); assert False
        except urllib.error.HTTPError as e:
            assert e.code == 401
        assert any('TOMCAT MANAGER LOGON' in a['message'] for a in state.dashboard_alerts)
        assert any('TOMCAT MANAGER LOGON' in text for _sev,text in state.console_events)
        assert any(ev.component == 'SMF80' and 'TOMCAT' in ev.result.upper() for ev in state.audit.events)
    finally:
        srv.shutdown()

def test_secure_mode_rejects_default_credentials():
    _state,srv,base=_server(True)
    try:
        req=urllib.request.Request(base+'/manager/html', headers=_auth('tomcat','tomcat'))
        try:
            urllib.request.urlopen(req); assert False
        except urllib.error.HTTPError as e:
            assert e.code == 401
    finally:
        srv.shutdown()
