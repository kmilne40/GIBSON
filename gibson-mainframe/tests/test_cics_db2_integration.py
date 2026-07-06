from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator
from gibson.apps.db2 import Db2Simulator
from gibson.services.db2_server import build_db2das_response


def test_cics_uploaded_assets_available():
    state = GibsonState.create()
    assert "WELCOME TO GICS" in state.templates.render("cics-screen.txt", "IBMUSER")
    assert "Inquire" in state.templates.render("CEMT.txt", "IBMUSER") or "INQUIRE" in state.templates.render("CEMT.txt", "IBMUSER").upper()


def test_cics_transactions():
    state = GibsonState.create()
    cics = CicsSimulator(state, "IBMUSER")
    assert "INQUIRE FILE" in cics.execute("CEMT I FILE")
    assert "INQUIRE PROGRAM" in cics.execute("CEMT I PROG")
    assert "DISPLAY PROGRAM" in cics.execute("CEDA DISPLAY PROGRAM")
    assert "SIMULATED EXECUTION OF SEND" in cics.execute("CECI SEND TEXT('HELLO')")


def test_db2_catalog_and_das():
    state = GibsonState.create()
    db2 = Db2Simulator(state)
    out = db2.format_spufi("SELECT * FROM SYSIBM.SYSTABLES", "IBMUSER")
    assert "DSNE616I" in out and "SYSTABLES" in out
    das = build_db2das_response(state)
    assert b"DB2DAS" in das and b"DB2System=DB2A" in das
