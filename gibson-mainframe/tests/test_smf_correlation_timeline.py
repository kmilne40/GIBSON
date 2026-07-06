from gibson.core.state import GibsonState
from gibson.core.smf.records.type80 import racf_event
from gibson.core.smf.records.type110 import cics_monitor
from gibson.apps.tso import TsoCommandProcessor


def test_smf_timeline_by_correlation_id():
    st = GibsonState.create()
    racf_event(st, userid="IBMUSER", event_name="DATASET_ACCESS", result="FAILURE", correlation_id="ABC123", detail="DENIED")
    cics_monitor(st, userid="IBMUSER", transaction_id="MCAD", program="DVCA", result="WARNING", correlation_id="ABC123", detail="PIN BRUTE")
    out = TsoCommandProcessor(st, "IBMUSER").run("SMF TIMELINE ABC123")
    assert "ABC123" in out
    assert "DATASET_ACCESS" in out
    assert "CICS_TRANSACTION" in out
