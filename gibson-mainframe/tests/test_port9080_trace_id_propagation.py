from __future__ import annotations
import http.cookiejar, json, tempfile, threading, urllib.parse, urllib.request
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

def _opener(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def _post(op, url, data): return op.open(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method='POST'))


def test_trace_id_propagates_from_session_to_lab_events_and_clear_is_real():
    state, srv, base = _server()
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        session = json.loads(_post(op, base+'/webapi/trace/session', {'page':'/labs/sqli','lab_slug':'sqli'}).read().decode())
        tid = session['trace_id']
        res = json.loads(_post(op, base+'/webapi/labs/sqli/run', {'payload':"1001' OR '1'='1", 'trace_id':tid}).read().decode())
        assert res['trace_id'] == tid
        assert res['correlation_id'] == tid
        events = json.loads(op.open(base+f'/webapi/trace/{tid}/events').read().decode())['events']
        assert any(e['trace_id'] == tid and e['component'] == 'WEB9080' for e in events)
        assert any(e['component'] in {'DB2','SQL','CICS'} for e in events)
        other = json.loads(_post(op, base+'/webapi/labs/sqli/run', {'payload':'1001', 'trace_id':'TRACE-OTHER'}).read().decode())
        assert other['trace_id'] == 'TRACE-OTHER'
        events_other = json.loads(op.open(base+'/webapi/trace/TRACE-OTHER/events').read().decode())['events']
        assert events_other and all(e['trace_id'] == 'TRACE-OTHER' for e in events_other)
        _post(op, base+f'/webapi/trace/{tid}/clear', {})
        cleared = json.loads(op.open(base+f'/webapi/trace/{tid}/events').read().decode())['events']
        assert cleared == []
        still = json.loads(op.open(base+'/webapi/trace/TRACE-OTHER/events').read().decode())['events']
        assert still
    finally:
        srv.shutdown()
