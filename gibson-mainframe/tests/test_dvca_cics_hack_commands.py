from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator


def test_cics_dvca_hack_commands_and_pin_bruteforce():
    st = GibsonState.create(GibsonConfig(security_mode='vuln', dvca_vuln=True))
    c = CicsSimulator(st, 'IBMUSER')
    c.execute('DVCA')
    assert 'HACK ON' in c.execute('HACK ON')
    assert 'HIDDEN FIELDS' in c.execute('SHOW HIDDEN')
    out = c.execute('BRUTE FORCE PIN')
    assert 'DVCA MCAD PIN BRUTE FORCE' in out
    assert 'STATUS       ===> RUNNING' in out or 'PIN MATCH FOUND' in out
    assert 'ADDRESS SCREEN' in c.execute('MCAD')
    assert 'HACK OFF' in c.execute('HACK OFF')


def test_cics_dvca_bruteforce_blocked_secure():
    st = GibsonState.create(GibsonConfig(security_mode='secure', dvca_vuln=False))
    c = CicsSimulator(st, 'IBMUSER')
    c.execute('DVCA')
    c.execute('HACK ON')
    assert 'BLOCKED' in c.execute('BRUTE FORCE PIN')
