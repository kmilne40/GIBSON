"""Workstream D - consistent keys/tabbing/legends across the subsystems.

Checks the shared discipline that makes every panel behave like real ISPF:
labels are protected (Tab skips them), input fields are unprotected with a
tab order, the F-key legends are the authentic two-line set, and PA2 reshows.
"""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270 import Ispf3270Session
from gibson.apps.db2i3270 import Db2i3270Session
from gibson.apps.sdsf3270 import Sdsf3270Session


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _protection_ok(s):
    labels = [f for f in s.fields if f.role == "label"]
    inputs = [f for f in s.fields if not f.protected]
    assert labels and all(f.protected for f in labels), "labels must be protected"
    assert inputs, "screen must have at least one unprotected input field"
    assert b"\x1b" not in s.to_3270(), "ANSI leaked into 3270 datastream"


def test_ispf_legends_and_protection():
    st = GibsonState.create(); st.racf.load()
    app = Ispf3270Session(st, userid="IBMUSER")
    pm = app.initial_screen()
    _protection_ok(pm)
    assert "F2=SPLIT" in _W(pm) and "F10=ACTIONS" in _W(pm) and "F12=CANCEL" in _W(pm)
    # OPTION field carries a tab order and is unprotected
    opt = [f for f in pm.fields if f.name == "OPTION"][0]
    assert opt.tab_order is not None and not opt.protected
    de = app.handle(_inbound(pm, OPTION="3.4"))
    dl = app.handle(_inbound(de, DSLEVEL="IBMUSER"))
    _protection_ok(dl)
    w = _W(dl)
    assert "F5=RFIND" in w and "F11=RIGHT" in w and "F12=CANCEL" in w
    assert "ENTER LINE COMMAND AT LEFT" in w


def test_pa2_reshow_returns_same_panel():
    st = GibsonState.create(); st.racf.load()
    app = Ispf3270Session(st, userid="IBMUSER")
    pm = app.initial_screen()
    again = app.handle(_inbound(pm, key="PA2"))
    assert "PRIMARY OPTION MENU" in _W(again)


def test_db2i_and_sdsf_protection_and_legends():
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    ds = db.initial_screen()
    _protection_ok(ds)
    assert "F3=EXIT" in _W(ds)
    sd = Sdsf3270Session(st, userid="IBMUSER")
    ss = sd.initial_screen()
    _protection_ok(ss)
    assert "F8=DOWN" in _W(ss)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all Workstream D tests passed")
