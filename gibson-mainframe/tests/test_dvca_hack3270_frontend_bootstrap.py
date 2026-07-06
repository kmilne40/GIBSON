from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080
import http.client, json


def _state():
    return GibsonState.create(GibsonConfig(host='127.0.0.1', cbsa_api_port=0, security_mode='vuln', cbsa_vuln=True, dvca_vuln=True))


def test_hack3270_frontend_uses_terminal_screen_not_window_screen():
    st = _state(); srv = serve_cbsa_rest8080(st); port = srv.server_address[1]
    try:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET','/dvca/hack3270')
        res = conn.getresponse(); body = res.read().decode(); conn.close()
        assert res.status == 200
        assert 'terminalScreen' in body
        assert 'screen.innerHTML' not in body
        assert "document.getElementById('terminalScreen')" in body
        assert 'DOMContentLoaded' in body
        assert 'Connection failed' in body
    finally:
        srv.shutdown(); srv.server_close()


def test_hack3270_session_start_and_pf_keys_return_rendered_html():
    st = _state(); srv = serve_cbsa_rest8080(st); port = srv.server_address[1]
    try:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('POST','/api/v1/hack3270/session/start','{}',{'Content-Type':'application/json'})
        d = json.loads(conn.getresponse().read().decode())
        sid = d['session_id']
        assert 'rendered_html' in d and 'Starting...' not in d['rendered_html']
        for aid, marker in [('PF1','HELP'), ('PF5','MAIN MENU')]:
            conn.request('POST',f'/api/v1/hack3270/session/{sid}/send-aid',json.dumps({'aid': aid}),{'Content-Type':'application/json'})
            out = json.loads(conn.getresponse().read().decode())
            assert marker in (out.get('rendered_html','') + out.get('rendered','')).upper()
        conn.close()
    finally:
        srv.shutdown(); srv.server_close()
