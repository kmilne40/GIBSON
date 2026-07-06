from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_dynamic_racf_alias_catalog_jes_nje_smoke():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    assert "USER=IBMUSER" in tso.run("LISTUSER IBMUSER")
    assert "USER=IBMUSER" in tso.run("LU IBMUSER")
    assert "IBMUSER.SUBMIT" in tso.run("SEARCH CLASS(SURROGAT)")
    assert "DEFINED" in tso.run("RDEFINE SURROGAT TEST.SUBMIT UACC(NONE)")
    assert "PERMIT SUCCESSFUL" in tso.run("PERMIT TEST.SUBMIT CLASS(SURROGAT) ID(SARCHER) ACCESS(READ)")
    assert "SARCHER" in tso.run("RLIST SURROGAT TEST.SUBMIT")
    assert "GROUP=SYS1" in tso.run("LISTGRP *")
    assert "ALIAS KEV" in tso.run("DEFINE ALIAS(NAME(KEV) RELATE(USERCAT.USER))")
    assert "USERCAT.USER" in tso.run("LISTCAT ALIAS")
    assert "Job submitted" in tso.run("JES SUBMIT TESTJOB")
    assert "JOB00001" in tso.run("$D Q")
    assert "NJE NODE DISPLAY" in tso.run("$D NODE")
