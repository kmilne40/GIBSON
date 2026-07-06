from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator
from gibson.apps.dvca.hack3270_bridge import start, send_aid, toggle


def make_state():
    return GibsonState.create(GibsonConfig(security_mode='vuln', dvca_vuln=True))


def test_mcor_pf7_pf8_scrolls_catalog():
    st=make_state(); c=CicsSimulator(st,'IBMUSER')
    c.execute('DVCA'); c.execute('PF5')
    out=c.execute('1')
    assert '00001' in out
    out=c.execute('PF8')
    assert '00002' in out and 'SCROLLED FORWARD' in out
    out=c.execute('PF7')
    assert '00001' in out and 'SCROLLED BACKWARD' in out


def test_hack3270_fields_update_after_scroll():
    st=make_state(); s=start(st); sid=s['session_id']
    s=send_aid(st,sid,'PF5')
    # move to MCOR via SELECT=1 and ENTER
    from gibson.apps.dvca.hack3270_bridge import send_field
    send_field(st,sid,'SELECT','1'); s=send_aid(st,sid,'ENTER')
    s=send_aid(st,sid,'PF8')
    fields={f['name']:f for f in s['fields']}
    assert fields['ITEM']['value'] == '00002'
    s=toggle(st,sid,{'enable_hidden_fields':True})
    fields={f['name']:f for f in s['fields']}
    assert fields['CANBUY']['value'] in {'Y','N'}
