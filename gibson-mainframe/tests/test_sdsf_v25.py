from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.sdsf import SdsfApp
from gibson.render.input import PF_KEY_MAP


def test_sdsf_v25_inventory_and_pf_keys():
    state = GibsonState.create()
    app = SdsfApp(state, "IBMUSER")
    commands = {item.command for item in app.MENU_ITEMS}
    for cmd in [
        "AD", "AS", "DA", "I", "ST", "O", "H", "INIT", "JC", "JES", "JG", "J0", "JRI", "JRJ",
        "MAS", "PR", "PROC", "PUN", "RDR", "RM", "RMA", "SO", "SP", "LOG", "SR", "ULOG",
        "DEV", "SMSG", "SMSV", "CS", "CSR", "MEM", "VMAP", "LINE", "NA", "NC", "NODE", "NS",
        "BPXO", "FS", "PS", "CFC", "CFD", "CFS", "EMCS", "ENQD", "XCFM", "APF", "CK",
        "DYNX", "ENQ", "ENQC", "GT", "LLS", "LNK", "LPA", "LPD", "PAG", "PARM", "PC", "SSI",
        "SVC", "SYM", "SYS", "SYSP", "ENC", "REPC", "RES", "RGRP", "SE", "SRVC", "WKLD", "WLM", "VER",
    ]:
        assert cmd in commands
    assert PF_KEY_MAP[b"\x1bOR"] == "F3"
    assert PF_KEY_MAP[b"\x1b[18~"] == "F7"
    assert PF_KEY_MAP[b"\x1b[19~"] == "F8"


def test_sdsf_job_actions():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    assert "SUBMITTED" in tso.run("SUBMIT TEST")
    app = SdsfApp(state, "IBMUSER")
    assert "SDSF MENU V2R5M0" in app.render_main()
    assert "SDSF STATUS OF JOBS" in app.render_panel("ST")
    screen, msg = app.perform_action("ST", "?", 1)
    assert screen and "SDSF JOB DATA SETS" in screen
    screen, msg = app.perform_action("ST", "S", 1)
    assert screen and "SDSF OUTPUT DISPLAY" in screen
    screen, msg = app.perform_action("ST", "P", 1)
    assert "PURGED" in msg


def test_sdsf_ver_panel_available():
    state = GibsonState.create()
    app = SdsfApp(state, 'IBMUSER')
    panel = app.render_panel('VER')
    assert 'SDSF VERSION INFORMATION' in panel
    assert 'V2R5M0' in panel
