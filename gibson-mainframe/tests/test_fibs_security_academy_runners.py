from __future__ import annotations
import http.cookiejar, json, tempfile, threading, urllib.request, urllib.parse
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.fibs_web9080 import FibsWeb9080Handler, ThreadedHTTPServer


def _server(secure=False):
    cfg = GibsonConfig(host='127.0.0.1', fibs_web_port=0, sim_root=Path(tempfile.mkdtemp()), security_mode='secure' if secure else 'vuln')
    state = GibsonState.create(cfg)
    FibsWeb9080Handler.state = state
    srv = ThreadedHTTPServer(('127.0.0.1',0), FibsWeb9080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state, srv, f'http://127.0.0.1:{srv.server_address[1]}'


def _opener(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def _post(op,url,data): return op.open(urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),method='POST'))


def test_lab_run_secure_compare_and_export():
    state, srv, base = _server(False)
    try:
        op=_opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        res=json.loads(_post(op, base+'/webapi/labs/sqli/run', {'payload':"1001' OR '1'='1"}).read().decode())
        assert res['lab']=='sqli'
        assert res['evidence_id']
        assert res['request'] and res['response'] and res['trace_events']
        assert 'CBSA.ACCOUNT' in ','.join(res['db2_tables'])
        assert any(str(e.get('smf_type')) == '102' for e in res['smf_events'])
        sec=json.loads(_post(op, base+'/webapi/labs/sqli/secure-compare', {'payload':"1001' OR '1'='1"}).read().decode())
        assert 'Secure mode' in sec['secure_comparison'] or sec['mode']=='secure-compare'
        exp=json.loads(op.open(base+'/webapi/labs/sqli/export/'+res['evidence_id']).read().decode())
        assert exp['lab']=='sqli' and 'events' in exp and 'trace_events' in exp
    finally:
        srv.shutdown()


def test_identity_lab_runners_emit_smf80():
    state, srv, base = _server(False)
    try:
        op=_opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        for slug in ['jwt','oauth']:
            res=json.loads(_post(op, base+f'/webapi/labs/{slug}/run', {'payload':'alg_none'}).read().decode())
            assert res['lab']==slug
            assert any(e.get('smf_type') == '80' for e in res['smf_events'])
            assert 'identity_result' in res['response']
    finally:
        srv.shutdown()
