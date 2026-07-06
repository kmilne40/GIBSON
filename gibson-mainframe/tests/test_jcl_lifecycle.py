from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.jes import JobStatus


def test_jcl_submit_creates_spool_and_sdsf_output():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    out = tso.run("SUBMIT HELLO")
    assert "SUBMITTED" in out.upper()
    assert state.jes.jobs
    job = list(state.jes.jobs.values())[-1]
    assert any(sp.ddname == "JESMSGLG" for sp in job.spool)
    sdsf = tso.run("SDSF ST")
    assert job.jobid in sdsf
