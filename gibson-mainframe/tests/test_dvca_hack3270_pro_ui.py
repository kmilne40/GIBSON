from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.dvca.hack3270_bridge import start, send_aid, send_field, toggle, batch_pin, hack_on, hack_off
from gibson.apps.dvca.store import get_dvca_store
from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080
import http.client, json


def state(vuln=True):
    cfg = GibsonConfig(host='127.0.0.1', cbsa_api_port=0, security_mode='vuln' if vuln else 'secure', cbsa_vuln=vuln, dvca_vuln=vuln)
    return GibsonState.create(cfg)


def test_hack_mode_authoritative_and_hidden_highlight():
    st = state(True)
    sid = start(st)['session_id']
    s = send_aid(st, sid, 'PF5')
    s = send_field(st, sid, 'SELECT', '1')
    s = send_aid(st, sid, 'ENTER')
    assert s['screen_id'] == 'MCOR'
    assert 'field-hidden-revealed' not in s['rendered_html']
    denied = send_field(st, sid, 'PRICE', '0.01')
    assert 'requires HACK ON' in denied.get('error','') or 'protected' in denied.get('error','')
    s = hack_on(st, sid)
    s = toggle(st, sid, {'enable_hidden_fields': True, 'disable_field_protection': True, 'start_field_extended': True})
    assert s['hack']['enabled'] is True
    assert 'field-hidden-revealed' in s['rendered_html']
    assert 'field-protected' in s['rendered_html']
    assert 'field-fset' in s['rendered_html']
    ok = send_field(st, sid, 'PRICE', '0.01')
    assert 'error' not in ok
    assert any('SIMULATED SMF80' in msg for _sev, msg in st.console_events)


def test_pin_masked_and_batch_pin_alerts():
    st = state(True)
    sid = start(st)['session_id']
    send_aid(st, sid, 'PF5')
    send_field(st, sid, 'SELECT', '2')
    s = send_aid(st, sid, 'ENTER')
    assert s['screen_id'] == 'MCAD'
    pin = [f for f in s['fields'] if f['name'] == 'PIN'][0]
    assert pin['value'] in {'####','****'}
    blocked = batch_pin(st, sid, 1500, require_hack=True)
    assert blocked['found'] == ''
    hack_on(st, sid)
    res = batch_pin(st, sid, 1500, require_hack=True)
    assert res['found'] == '1337'
    assert res['attempts'] == 1338
    console = '\n'.join(m for _s, m in st.console_events)
    assert 'SIMULATED SMF80' in console and 'SIMULATED SMF110' in console


def test_api_page_has_professional_controls_and_no_default_json():
    st = state(True)
    srv = serve_cbsa_rest8080(st)
    port = srv.server_address[1]
    try:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET','/dvca/hack3270')
        res = conn.getresponse(); body = res.read().decode('utf-8')
        conn.close()
        assert res.status == 200
        assert 'HACK OFF' in body and 'HACK ON' in body
        assert 'API Leakage' in body and 'field-hidden-revealed' in body
        assert '<pre id=\'apiJson\'' in body
        assert '"mode": "VULNERABLE"' not in body
    finally:
        srv.shutdown(); srv.server_close()


def test_secure_mode_blocks_pin_success():
    st = state(False)
    sid = start(st)['session_id']
    hack_on(st, sid)
    res = batch_pin(st, sid, 1500, require_hack=True)
    assert res['found'] == ''
    assert 'secure mode' in res.get('error','').lower()
