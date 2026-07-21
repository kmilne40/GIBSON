"""Workstream E - split-screen, horizontal scroll, and DB2I breadth (DCLGEN)."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270 import IspfSplitManager
from gibson.apps.ispf3270.editor import Ispf3270Editor
from gibson.apps.db2i3270 import Db2i3270Session


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _noansi(s):
    assert b"\x1b" not in s.to_3270(), "ANSI leaked into 3270 datastream"


def test_split_screen_f2_f9_independent_state():
    st = GibsonState.create(); st.racf.load()
    mgr = IspfSplitManager(st, userid="IBMUSER")
    s = mgr.initial_screen()
    assert "PRIMARY OPTION MENU" in _W(s)
    de = mgr.handle(_inbound(s, OPTION="3.4"))
    dl = mgr.handle(_inbound(de, DSLEVEL="IBMUSER"))
    assert "DSLIST" in _W(dl)
    # F2 split -> fresh second session
    b = mgr.handle(_inbound(dl, key="PF2"))
    assert "PRIMARY OPTION MENU" in _W(b) and mgr.active == 1
    se = mgr.handle(_inbound(b, OPTION="0"))
    assert "SETTINGS" in _W(se)
    # F9 swap -> session A still in DSLIST
    a = mgr.handle(_inbound(se, key="PF9"))
    assert "DSLIST" in _W(a) and mgr.active == 0
    # F9 swap -> session B still in SETTINGS
    b2 = mgr.handle(_inbound(a, key="PF9"))
    assert "SETTINGS" in _W(b2) and mgr.active == 1
    # exit B -> returns to A; single session again
    p = mgr.handle(_inbound(b2, key="PF3"))
    end = mgr.handle(_inbound(p, key="PF3"))
    assert end is not None and "DSLIST" in _W(end) and len(mgr.sessions) == 1


def test_editor_horizontal_scroll():
    st = GibsonState.create()
    wide = "A" * 40 + "B" * 40 + "C" * 40
    ed = Ispf3270Editor(st, "IBMUSER", "T(M)", wide + "\n")
    s = ed.initial_screen()
    assert "Columns 00001 00072" in s.to_3270().decode("cp037", "ignore")
    s2 = ed.handle(_inbound(s, key="PF11"))
    ld = [f for f in s2.fields if f.name == "LD00000"][0]
    assert ed.hoff == 71 and ld.text[0] == "B"
    # edit at offset, splice preserved into the full record
    ed.handle(_inbound(s2, LD00000="ZZZ"))
    assert ed.lines[0][:40] == "A" * 40 and "ZZZ" in ed.lines[0]
    s4 = ed.handle(_inbound(s2, key="PF10"))
    assert ed.hoff == 0


def test_db2i_dclgen_from_catalog():
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    m = db.initial_screen()
    dg = db.handle(_inbound(m, OPTION="2"))
    _noansi(dg)
    assert "DCLGEN" in _W(dg)
    out = db.handle(_inbound(dg, OWNER="GIBSON", TABLE="EMPLOYEES", LANG="COBOL"))
    _noansi(out)
    w = _W(out)
    assert "DECLARE GIBSON.EMPLOYEES TABLE" in w and "END-EXEC" in w and "EMPNO" in w and "PIC X" in w
    back = db.handle(_inbound(out, key="PF3"))
    assert "DB2I PRIMARY OPTION MENU" in _W(back)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all Workstream E tests passed")
