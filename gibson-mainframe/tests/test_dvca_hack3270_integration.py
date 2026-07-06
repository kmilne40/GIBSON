from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator
from gibson.apps.dvca.hack3270_bridge import start, send_aid, send_field, toggle, batch_pin
from gibson.apps.dvca.store import get_dvca_store

def state(vuln=True):
    cfg=GibsonConfig(security_mode='vuln' if vuln else 'secure', cbsa_vuln=vuln, dvca_vuln=vuln)
    return GibsonState.create(cfg)

def test_dvca_cics_transaction_and_pa3():
    st=state(True); c=CicsSimulator(st, 'IBMUSER')
    out=c.execute('DVCA')
    assert 'DAMN VULNERABLE CICS APPLICATION' in out
    out=c.execute('PA3')
    assert 'SECRET' in out

def test_hack3270_hidden_and_protected_fields():
    st=state(True); s=start(st); sid=s['session_id']
    s=send_aid(st,sid,'PF5')
    s=send_field(st,sid,'SELECT','1')
    s=send_aid(st,sid,'ENTER')
    assert s['screen_id']=='MCOR'
    fields={f['name']:f for f in s['fields']}
    assert fields['CANBUY']['hidden'] is True
    denied=send_field(st,sid,'PRICE','0.01')
    assert 'error' in denied
    s=toggle(st,sid,{'disable_field_protection':True,'enable_hidden_fields':True})
    s=send_field(st,sid,'PRICE','0.01')
    s=send_field(st,sid,'CANBUY','Y')
    s=send_field(st,sid,'BUY','Y')
    s=send_aid(st,sid,'ENTER')
    assert 'ORDER ACCEPTED' in s['message']

def test_batch_pin_finds_1337_and_logs():
    st=state(True); sid=start(st)['session_id']
    res=batch_pin(st,sid,1500)
    assert res['found']=='1337'
    assert any(e.action=='BATCH_PIN' for e in get_dvca_store(st).events)

def test_secure_blocks_pa3():
    st=state(False); sid=start(st)['session_id']
    res=send_aid(st,sid,'PA3')
    assert 'BLOCKED' in res['message']
