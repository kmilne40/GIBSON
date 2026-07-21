from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_zsecure_reports_state_findings():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    out = tso.run("ZSEC APF")
    assert "ZSECURE APF REVIEW" in out
    assert "APF" in out
    assert "SYS1.VULNLIB" in out or "SYS1.PARMLIB" in out
