from tests.test_fibs_teller_search_trace import _server, _opener, _post
import json


def test_teller_login_and_open_teller_seed_trace_events():
    st, srv, base = _server(False)
    try:
        op = _opener(); _post(op, base+'/login', {'username':'teller','password':'cics'})
        op.open(base+'/teller').read()
        events = json.loads(op.open(base+'/webapi/teller/events').read().decode())['events']
        actions = {e['action'] for e in events}
        assert 'LOGIN' in actions
        assert 'OPEN_TELLER' in actions
    finally:
        srv.shutdown()
