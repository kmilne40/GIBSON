from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_db2_catalog_grant_revoke_and_smf101():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    cat = tso.run("RUN SQL SELECT * FROM SYSIBM.SYSTABLES")
    assert "SYSTABLES" in cat
    grant = tso.run("RUN SQL GRANT SELECT ON SYSIBM.SYSTABLES TO TRAINEE")
    assert "GRANT SELECT" in grant
    revoke = tso.run("RUN SQL REVOKE SELECT ON SYSIBM.SYSTABLES FROM TRAINEE")
    assert "REVOKE SELECT" in revoke
    assert any(e.component == "SMF101" for e in state.audit.events)
