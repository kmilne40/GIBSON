from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator


def make_state(vuln=True):
    return GibsonState.create(GibsonConfig(security_mode='vuln' if vuln else 'secure', dvca_vuln=vuln))


def start_menu(c):
    c.execute('DVCA')
    return c.execute('PF5')


def test_mcmm_numeric_and_help_actions():
    c=CicsSimulator(make_state(True),'IBMUSER')
    assert 'ORDER OFFICE SUPPLIES' in start_menu(c)
    assert 'ORDER SCREEN' in c.execute('1')
    start_menu(c); assert 'ADDRESS UPDATE' in c.execute('2')
    start_menu(c); assert 'ORDER HISTORY' in c.execute('3')
    start_menu(c); assert 'DVCA HELP' in c.execute('H')


def test_mcmm_hidden_99_vuln_and_secure():
    st=make_state(True); c=CicsSimulator(st,'IBMUSER'); start_menu(c)
    out=c.execute('99')
    assert 'HISTORY DELETED' in out
    st=make_state(False); c=CicsSimulator(st,'IBMUSER'); start_menu(c)
    out=c.execute('99')
    assert 'BLOCKED' in out
