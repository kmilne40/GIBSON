from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_cics_resource_display_and_security_evidence():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    out = tso.run("CEDA DISPLAY GROUP(FIBS)")
    assert "CICS RESOURCE DISPLAY TRANSACTION" in out
    assert "FIBSPGM" in out
    tran = tso.run("CEMT INQUIRE TRANSACTION FIBS")
    assert "FIBS" in tran
    assert any(e.component == "SMF110" for e in state.audit.events)
