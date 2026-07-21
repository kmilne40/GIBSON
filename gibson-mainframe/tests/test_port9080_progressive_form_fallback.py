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


def test_lab_page_has_non_js_forms_and_post_fallback_works():
    state, srv, base = _server()
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        page = op.open(base+'/labs/excessive-data').read().decode()
        assert "form method='post' action='/labs/excessive-data/run'" in page
        assert "form method='post' action='/labs/excessive-data/secure-compare'" in page
        assert "form method='post' action='/labs/excessive-data/reset'" in page
        html = _post(op, base+'/labs/excessive-data/run', {'payload':'1001','trace_id':'TRACE-FORM-1'}).read().decode()
        assert 'EXCESSIVE_DATA_RETURNED' in html
        assert 'TRACE-FORM-1' in html
        assert 'Latest evidence' in html
        html2 = _post(op, base+'/labs/excessive-data/secure-compare', {'payload':'1001','trace_id':'TRACE-FORM-1'}).read().decode()
        assert 'MINIMAL_DATA_RETURNED' in html2 or 'Secure comparison complete' in html2
        html3 = _post(op, base+'/labs/excessive-data/reset', {'trace_id':'TRACE-FORM-1'}).read().decode()
        assert 'Lab reset complete' in html3
    finally:
        srv.shutdown()


def test_export_evidence_without_javascript():
    state, srv, base = _server()
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        _post(op, base+'/labs/sqli/run', {'payload':"1001' OR '1'='1", 'trace_id':'TRACE-EXPORT-1'}).read()
        exp = op.open(base+'/labs/sqli/export?trace_id=TRACE-EXPORT-1').read().decode()
        assert 'Evidence export' in exp
        assert 'TRACE-EXPORT-1' in exp
        assert 'trace_events' in exp
    finally:
        srv.shutdown()
