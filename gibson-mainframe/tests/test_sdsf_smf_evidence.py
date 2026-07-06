from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.smf import record_smf


def test_sdsf_smf_panels_show_evidence():
    state = GibsonState.create()
    record_smf(state, "101", "IBMUSER", "DB2 SELECT", "TABLE=SYSIBM.SYSTABLES")
    record_smf(state, "110", "IBMUSER", "CICS TRANSACTION", "TRANSID=FIBS")
    tso = TsoCommandProcessor(state, "IBMUSER")
    assert "SMF TYPE 101 EVENT LOG" in tso.run("SDSF SMF101")
    assert "DB2 SELECT" in tso.run("SDSF SMF101")
    assert "SMF TYPE 110 EVENT LOG" in tso.run("SDSF SMF110")
