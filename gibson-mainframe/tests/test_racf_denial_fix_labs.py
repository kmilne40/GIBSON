from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_racf_denial_fix_lab_flow():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    start = tso.run("RACFLAB START DATASET")
    assert "ICH408I" in start
    fixed = tso.run("RACFLAB FIX DATASET")
    assert "ACCESS ALLOWED" in fixed
    assert "SDSF SMF80" in fixed
