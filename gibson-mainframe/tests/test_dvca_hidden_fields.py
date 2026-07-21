from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.dvca import hack3270_bridge as h


def test_hidden_fields_not_spoiled_then_revealed_in_yellow_class():
    st = GibsonState.create(GibsonConfig())
    snap = h.start(st); sid = snap['session_id']
    h.send_aid(st, sid, 'PF5')
    off = h.snapshot(st, sid)
    assert 'Hidden option 99 exists' not in off['rendered']
    assert 'field-hidden-revealed' not in off['rendered_html']
    h.hack_on(st, sid)
    h.toggle(st, sid, {'enable_hidden_fields': True})
    on = h.snapshot(st, sid)
    assert 'field-hidden-revealed' in on['rendered_html']
    assert '99' in on['rendered_html']
