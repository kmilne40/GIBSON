from __future__ import annotations
import http.cookiejar, json, tempfile, threading, urllib.parse, urllib.request, urllib.error
from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.fibs_web9080 import FibsWeb9080Handler, ThreadedHTTPServer


def _server(secure: bool = False):
    cfg = GibsonConfig(host='127.0.0.1', fibs_web_port=0, sim_root=Path(tempfile.mkdtemp()), security_mode='secure' if secure else 'vuln')
    state = GibsonState.create(cfg)
    FibsWeb9080Handler.state = state
    srv = ThreadedHTTPServer(('127.0.0.1',0), FibsWeb9080Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    return state, srv, f'http://127.0.0.1:{srv.server_address[1]}'


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _post(opener, url, data):
    return opener.open(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method='POST'))


def test_teller_search_page_split_trace_and_architecture():
    state, srv, base = _server(False)
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        page = op.open(base+'/teller/search').read().decode()
        assert 'Live backend trace' in page
        assert 'arch-node' in page and 'FIBSWEB9080' in page and 'Db2 / CBSA Tables' in page
        assert 'Search customers and accounts' in op.open(base+'/teller').read().decode()
        try:
            op2 = _opener(); _post(op2, base+'/login', {'username':'alice','password':'training1'})
            op2.open(base+'/teller/search')
            assert False, 'customer should be forbidden'
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()


def test_teller_search_sqli_trace_and_console_events():
    state, srv, base = _server(False)
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        payload = "1001' OR '1'='1"
        data = op.open(base+'/webapi/teller/search?'+urllib.parse.urlencode({'type':'all','q':payload})).read().decode()
        res = json.loads(data)
        assert res['result'] == 'ROWSET_EXPANDED'
        assert res['rows_returned'] >= 2
        assert 'SIMULATED SMF102' in '\n'.join(m for _s,m in state.console_events)
        assert state.cbsa_store.sqli_events
        events = json.loads(op.open(base+'/webapi/teller/events').read().decode())['events']
        comps = {e['component'] for e in events}
        assert {'WEB9080','CBSA','SQL','DB2','SMF','CONSOLE'} <= comps
        sse = op.open(base+'/webapi/teller/live-events').read().decode()
        assert 'event: trace' in sse or 'event: heartbeat' in sse
    finally:
        srv.shutdown()


def test_teller_search_secure_mode_treats_payload_as_data():
    state, srv, base = _server(True)
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        payload = "1001' OR '1'='1"
        res = json.loads(op.open(base+'/webapi/teller/search?'+urllib.parse.urlencode({'type':'all','q':payload})).read().decode())
        assert res['result'] in {'NO_ROWS','BLOCKED_SECURE_MODE','OK'}
        assert res['rows_returned'] == 0
        assert 'ROWSET_EXPANDED' not in json.dumps(res)
    finally:
        srv.shutdown()
