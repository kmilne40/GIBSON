from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator


def _cics():
    return CicsSimulator(GibsonState.create(GibsonConfig()), "IBMUSER")


def test_dvca_pf5_pf7_pf8_are_contextual_aids():
    c = _cics()
    assert "DVCA STARTED" in c.execute("DVCA")
    out = c.execute("PF5")
    assert "MAIN MENU" in out
    out = c.execute("1")
    assert "ORDER SCREEN" in out or "Buy item" in out
    out = c.execute("PF8")
    assert "SCROLLED FORWARD" in out
    assert "Catalog page" in out and "2/5" in out
    out = c.execute("PF7")
    assert "SCROLLED BACKWARD" in out
    assert "Catalog page" in out and "1/5" in out
