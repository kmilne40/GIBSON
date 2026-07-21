from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_racf_services_menu_and_options():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    menu = tso.run("RACFSERV")
    assert "RACF - SERVICES OPTION MENU" in menu
    assert "DATA SET PROFILES" in menu
    assert "DIGITAL CERTIFICATES" in menu
    ds = tso.run("RACFSERV 1")
    assert "RACF SERVICES - DATASET PROFILES" in ds
    assert "FIBS.**" in ds
    assert "RACF SERVICES ENDED" in tso.run("RACFSERV 99")
