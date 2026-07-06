from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator


def sim():
    return CicsSimulator(GibsonState.create(GibsonConfig()), 'IBMUSER')


def test_operation_cics_cemt_inquire_connection_by_menu():
    c = sim()
    assert 'OPERATION CICS' in c.execute('OPER')
    c.execute('1')  # CEMT
    c.execute('1')  # INQUIRE
    out = c.execute('6')
    assert 'INQUIRE CONNECTION' in out
    assert 'DB2A' in out


def test_operation_cics_cemt_inquire_terminal_tsq_tdq_by_menu():
    c = sim(); c.execute('CEMT'); c.execute('1')
    assert 'INQUIRE TERMINAL' in c.execute('7')
    c.execute('CEMT'); c.execute('1')
    assert 'INQUIRE TSQUEUE' in c.execute('9')
    c.execute('CEMT'); c.execute('1')
    assert 'INQUIRE TDQUEUE' in c.execute('10')


def test_direct_command_still_works():
    c = sim()
    assert 'INQUIRE CONNECTION' in c.execute('CEMT I CONNECTION')
