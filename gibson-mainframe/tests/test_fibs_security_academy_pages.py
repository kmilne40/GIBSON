from __future__ import annotations
import http.cookiejar, tempfile, threading, urllib.request, urllib.parse
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.fibs_web9080 import FibsWeb9080Handler, ThreadedHTTPServer


def _server():
    cfg = GibsonConfig(host='127.0.0.1', fibs_web_port=0, sim_root=Path(tempfile.mkdtemp()), security_mode='vuln')
    state = GibsonState.create(cfg)
    FibsWeb9080Handler.state = state
    srv = ThreadedHTTPServer(('127.0.0.1',0), FibsWeb9080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state, srv, f'http://127.0.0.1:{srv.server_address[1]}'


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _post(op,url,data):
    return op.open(urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),method='POST'))


def test_academy_index_and_lab_pages_are_rich():
    state, srv, base = _server()
    try:
        op=_opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        page = op.open(base+'/labs').read().decode()
        assert 'FIBS Mainframe API Security Academy' in page
        assert 'z/OS Connect-style API' in page
        assert 'Run a controlled FIBS BANK training scenario' not in page
        assert page.count('academy-card') >= 10
        for slug in ['sqli','idor','mass-assignment','weak-auth','verbose-errors','business-logic','method-override','excessive-data','jwt','oauth']:
            lab = op.open(base+'/labs/'+slug).read().decode()
            assert 'Learning objectives' in lab
            assert 'Mainframe context' in lab
            assert 'Attack workbench' in lab
            assert 'CICS / Db2 / backend evidence' in lab
            assert 'Hidden solution' in lab
            assert 'Knowledge check' in lab
            assert 'lab-diagram-node' in lab
            assert 'z/OS Connect-style' in lab or slug in ['jwt','oauth']
    finally:
        srv.shutdown()
