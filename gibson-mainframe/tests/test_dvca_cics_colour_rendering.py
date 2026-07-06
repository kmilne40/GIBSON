from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.dvca.cics_session import execute_dvca


def test_canbuy_revealed_and_changed_is_yellow():
    state = GibsonState.create(GibsonConfig())
    for cmd in ['DVCA','PF5','1','HACK ON','SHOW HIDDEN','CANBUY=Y BUY=N']:
        out = execute_dvca(state, 'IBMUSER', cmd)
    assert '\x1b[33mY\x1b[0m' in out


def test_canbuy_hidden_when_hack_off():
    state = GibsonState.create(GibsonConfig())
    for cmd in ['DVCA','PF5','1']:
        out = execute_dvca(state, 'IBMUSER', cmd)
    assert 'Can buy hidden    :' in out
    assert '\x1b[33m' not in out
