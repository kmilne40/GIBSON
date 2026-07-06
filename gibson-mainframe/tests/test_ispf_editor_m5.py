"""M5 - ISPF Editor in 3270: display/edit/save, line+block commands, FIND/CHANGE/EXCLUDE."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270.editor import Ispf3270Editor
from gibson.apps.ispf3270 import Ispf3270Session


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


def _editor():
    st = GibsonState.create()
    text = "\n".join(f"line {i}" for i in range(8)) + "\n"
    return st, Ispf3270Editor(st, "IBMUSER", "T.D(M)", text)


def test_editor_display_and_inplace_edit():
    st, ed = _editor()
    s = ed.initial_screen()
    _noansi(s)
    assert "EDIT" in _W(s) and "LINE 0" in _W(s)
    s2 = ed.handle(_inbound(s, LD00000="CHANGED LINE"))
    assert ed.lines[0] == "CHANGED LINE"


def test_editor_line_and_block_commands():
    st, ed = _editor()
    s = ed.initial_screen()
    ed.handle(_inbound(s, LP00000="i2")); assert len(ed.lines) == 10
    st, ed = _editor(); s = ed.initial_screen()
    ed.handle(_inbound(s, LP00000="d2")); assert len(ed.lines) == 6
    st, ed = _editor(); s = ed.initial_screen()
    ed.handle(_inbound(s, LP00002="r3")); assert len(ed.lines) == 11
    st, ed = _editor(); s = ed.initial_screen()
    ed.handle(_inbound(s, LP00001="dd", LP00003="dd")); assert len(ed.lines) == 5
    st, ed = _editor(); s = ed.initial_screen()
    ed.handle(_inbound(s, LP00000="cc", LP00001="cc", LP00005="a")); assert len(ed.lines) == 10
    st, ed = _editor(); s = ed.initial_screen()
    ed.handle(_inbound(s, LP00000="mm", LP00001="mm", LP00006="a"))
    assert len(ed.lines) == 8 and ed.lines.index("line 0") > ed.lines.index("line 6")


def test_editor_find_change_exclude_reset():
    st, ed = _editor()
    s = ed.initial_screen()
    s = ed.handle(_inbound(s, COMMAND="CHANGE line ROW ALL"))
    assert all("ROW" in l for l in ed.lines)
    s = ed.handle(_inbound(s, COMMAND="EXCLUDE ROW ALL"))
    _noansi(s)
    assert "NOT DISPLAYED" in _W(s) and len(ed.excluded) == 8
    s = ed.handle(_inbound(s, COMMAND="RESET"))
    assert len(ed.excluded) == 0 and "NOT DISPLAYED" not in _W(s)
    s = ed.handle(_inbound(s, LP00002="x"))
    assert 2 in ed.excluded and "NOT DISPLAYED" in _W(s)


def test_editor_save_persists_and_wired_in_ispf():
    st = GibsonState.create(); st.racf.load()
    app = Ispf3270Session(st, peer_addr="203.0.113.10", userid="IBMUSER")
    pm = app.initial_screen()
    de = app.handle(_inbound(pm, OPTION="3.4"))
    dl = app.handle(_inbound(de, DSLEVEL="IBMUSER"))
    rows = app.dsl_rows
    ps_idx = [i for i, r in enumerate(rows) if r.org == "PS"][0]
    ed = app.handle(_inbound(dl, **{f"LC{ps_idx:04d}": "E"}))
    assert "EDIT" in _W(ed)
    ld = [f.name for f in ed.fields if f.name.startswith("LD")][0]
    ed2 = app.handle(_inbound(ed, **{ld: "EDITOR PERSIST TEST"}))
    ed3 = app.handle(_inbound(ed2, COMMAND="SAVE"))
    back = app.handle(_inbound(ed3, key="PF3"))
    assert back is not None and "DSLIST" in _W(back)
    saved = st.datasets.read("IBMUSER", rows[ps_idx].name)
    assert "EDITOR PERSIST TEST" in saved.upper()


def test_empty_buffer_insert_via_top_of_data():
    st = GibsonState.create()
    ed = Ispf3270Editor(st, "IBMUSER", "GUEST.4CHAR.PIN", "")
    s = ed.initial_screen()
    assert any(f.name == "LPTOP" for f in s.fields), "no insertable Top-of-Data prefix"
    assert "TOP OF DATA" in _W(s) and "BOTTOM OF DATA" in _W(s)
    s2 = ed.handle(_inbound(s, LPTOP="I"))
    assert len(ed.lines) == 1 and any(f.name == "LD00000" for f in s2.fields)
    # cursor on the new data line, on a writable position
    ld = [f for f in s2.fields if f.name == "LD00000"][0]
    assert s2._effective_cursor() == (ld.row, ld.col + 1)
    s3 = ed.handle(_inbound(s2, LD00000="FIRST LINE"))
    assert ed.lines[0] == "FIRST LINE"
    # clear ALL lines, then recover via Top-of-Data insert
    ed.lines.clear(); ed.top = 0
    s4 = ed._render()
    assert any(f.name == "LPTOP" for f in s4.fields)
    ed.handle(_inbound(s4, LPTOP="I3"))
    assert len(ed.lines) == 3


def test_workstream_c_quote_prefix_renumber_rchange_tabbing():
    st = GibsonState.create()
    ed = Ispf3270Editor(st, "IBMUSER", "IBMUSER.TEST(M)", "alpha\nbravo\ncharlie\n")
    s = ed.initial_screen()
    lp = [f for f in s.fields if f.name.startswith("LP") and f.name != "LPTOP"]
    assert all("'" not in f.text for f in lp), "loaded lines should be numbered"
    # insert -> new line shows '''''' ; SAVE -> renumbered
    s2 = ed.handle(_inbound(s, LP00000="i"))
    assert "''''''" in _W(s2)
    s3 = ed.handle(_inbound(s2, COMMAND="SAVE"))
    lp3 = [f for f in s3.fields if f.name.startswith("LP") and f.name != "LPTOP"]
    assert all("'" not in f.text for f in lp3), "SAVE should renumber"
    # UNNUM / RENUM
    s4 = ed.handle(_inbound(s3, COMMAND="UNNUM"))
    assert all(f.text == "''''''" for f in s4.fields if f.name.startswith("LP") and f.name != "LPTOP")
    s5 = ed.handle(_inbound(s4, COMMAND="RENUM"))
    assert all("'" not in f.text for f in s5.fields if f.name.startswith("LP") and f.name != "LPTOP")
    # CHANGE + F6 RCHANGE
    ed2 = Ispf3270Editor(st, "IBMUSER", "T(M)", "foo one\nfoo two\nfoo three\n")
    a = ed2.initial_screen()
    b = ed2.handle(_inbound(a, COMMAND="CHANGE foo bar"))
    assert ed2.lines[0] == "bar one"
    ed2.handle(_inbound(b, key="PF6"))
    assert ed2.lines[1] == "bar two"
    # authentic legend + correct 3270 field protection for tabbing
    assert "F4=EXPAND" in _W(s5) and "F6=RCHANGE" in _W(s5)
    lds = [f for f in s5.fields if f.name.startswith("LD")]
    assert lds and all(not f.protected and f.tab_order is not None for f in lds)
    labels = [f for f in s5.fields if f.role == "label"]
    assert labels and all(f.protected for f in labels)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all M5 tests passed")
