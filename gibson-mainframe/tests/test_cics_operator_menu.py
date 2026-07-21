from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator


def test_cics_operator_menu_and_security_events_panel():
    c = CicsSimulator(GibsonState.create(GibsonConfig()), 'IBMUSER')
    out = c.execute('OPER')
    assert 'CICS OPERATOR FUNCTIONS' in out
    assert 'CEMT INQUIRE SYSTEM' in out
    assert 'DVCA LAB CONTROL' in out
    assert 'SECURITY / SMF EVENTS' in c.execute('SECURITY')
    assert 'DVCA LAB CONTROL' in c.execute('13')
