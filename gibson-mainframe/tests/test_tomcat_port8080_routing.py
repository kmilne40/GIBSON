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
    return state, srv, f'http://127.0.0.1:{srv.server_address[1]}'

def _auth(user='tomcat', pw='tomcat'):
    return {'Authorization':'Basic '+base64.b64encode(f'{user}:{pw}'.encode()).decode()}

def test_tomcat_routes_and_existing_cbsa_health_coexist():
    state,srv,base=_server()
    try:
        assert 'CBSA8080' in urllib.request.urlopen(base+'/api/v1/cbsa/health').read().decode()
        try:
            urllib.request.urlopen(base+'/manager/html')
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 401
            assert 'Tomcat Manager Application' in e.headers.get('WWW-Authenticate','')
        req=urllib.request.Request(base+'/manager/html', headers=_auth())
        html=urllib.request.urlopen(req).read().decode()
        assert 'Apache Tomcat/9.0.x - Manager App' in html
        assert 'WAR file to deploy' in html
    finally:
        srv.shutdown()

def test_dvca_path_still_routes_before_tomcat():
    _state,srv,base=_server()
    try:
        try:
            urllib.request.urlopen(base+'/dvca')
        except urllib.error.HTTPError as e:
            # Either DVCA page or DVCA 404 is acceptable here; it must not become Tomcat.
            body=e.read().decode(errors='ignore')
            assert 'Tomcat' not in body
    finally:
        srv.shutdown()
