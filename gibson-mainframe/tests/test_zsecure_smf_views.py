from gibson.core.state import GibsonState
from gibson.core.passticket import get_passticket_service
from gibson.apps.tso import TsoCommandProcessor


def test_zsecure_smf_and_passticket_views_show_structured_records():
    st = GibsonState.create()
    svc = get_passticket_service(st)
    gen = svc.generate("IBMUSER", "TSO", "IBMUSER")
    svc.validate("IBMUSER", "TSO", gen["ticket"], consumer="TSO")
    tso = TsoCommandProcessor(st, "IBMUSER")
    assert "ZSECURE SMF" in tso.run("ZSEC SMF")
    out = tso.run("ZSEC PASSTICKET")
    assert "PASSTICKET" in out and ("82" in out or "PASSTICKET_GENERATE" in out)
