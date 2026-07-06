from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.sdsf import SdsfApp


def test_book_network_racf_apf_rexx_smoke():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    assert "EZZ2350I" in tso.run("NETSTAT HOME")
    assert "Home address" in tso.run("DISPLAY TCPIP,,NETSTAT,HOME")
    assert "SYS1.PARMLIB" in tso.run("SEARCH ALL WARNING NOMASK")
    assert "WARNING" in tso.run("LISTDSD DATASET('SYS1.PARMLIB') ALL")
    assert "BPX.SUPERUSER" in tso.run("RLIST FACILITY BPX.SUPERUSER AUTH")
    assert "PASSWORD PROCESSING" in tso.run("SETROPTS LIST")
    assert "SYS1.VULNLIB" in tso.run("D PROG,APF")
    assert "CSV410I" in tso.run("SETPROG APF,ADD,DSNAME=RUARIV.VULNAPF.LIB,VOLUME=SMS")
    assert "RUARIV.VULNAPF.LIB" in tso.run("D PROG,APF")
    assert "EZZ3218I" in tso.run("PING 127.0.0.1")
    assert "Trace complete" in tso.run("TRACERTE 127.0.0.1")
    assert "SYS1.VULNAPF.LIB" in tso.run("EX SYS0WN.RX")
    assert "Surrogate Access" in tso.run("EX 'IBMUSER.SEARCHRX.RX'")
    assert "Security Settings" in tso.run("EX 'RUARIV.ENUM' 'SEC'")


def test_surrogat_sdsf_nje_smoke():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "RUARIV")
    assert "SUBMITTED" in tso.run("SUBMIT TEST USER(IBMUSER)")
    sdsf = SdsfApp(state, "IBMUSER")
    assert "SYS1.VULNLIB" in sdsf.render_panel("APF")
    assert "HAL" in sdsf.render_panel("NODE")
    assert "LINE1" in sdsf.render_panel("LINE")
    assert "$HASP831 NJEDEF" in state.nje.command("$D NJEDEF")
