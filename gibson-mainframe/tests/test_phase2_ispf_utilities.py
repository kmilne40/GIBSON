"""Phase 2 ISPF tests - A2 (3.2 Data Set), A3 (3.3 Move/Copy), A6 (editor
command/count audit) and A7 (full primary-option acceptance sweep)."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, PanelInput, KEY_TO_AID
from gibson.apps.ispf3270.ispf_session import Ispf3270Session
from gibson.apps.ispf3270.editor import Ispf3270Editor


def _inbound(screen, key="ENTER", **fv):
    fr = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for n, t in fv.items():
        f = [x for x in screen.fields if x.name == n][0]
        fr += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + t.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(fr, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _ispf(seed=False):
    st = GibsonState.create(); st.racf.load()
    if seed:
        st.datasets.allocate("IBMUSER", "IBMUSER.SRC", org="PS")
        st.datasets.write("IBMUSER", "IBMUSER.SRC", "LINE1\nLINE2\n")
    a = Ispf3270Session(st, userid="IBMUSER")
    return st, a, a.initial_screen()


# --- A2: 3.2 Data Set Utility -------------------------------------------
def test_a2_allocate_and_delete():
    st, a, m = _ispf()
    p = a.handle(_inbound(m, OPTION="3.2"))
    assert "DATA SET UTILITY" in _W(p)
    out = a.handle(_inbound(p, OPTION="A", DSNAME="IBMUSER.NEW.PDS", ORG="PO"))
    assert "ALLOCATED" in _W(out)
    assert any(i.name == "IBMUSER.NEW.PDS" for i in st.datasets.listcat("IBMUSER"))
    out = a.handle(_inbound(p, OPTION="D", DSNAME="IBMUSER.NEW.PDS"))
    assert "DELETED" in _W(out)


def test_a2_catalog_uncatalog_info():
    st, a, m = _ispf()
    st.datasets.allocate("IBMUSER", "IBMUSER.CAT.PS", org="PS")
    p = a.handle(_inbound(m, OPTION="3.2"))
    assert "UNCATALOGED" in _W(a.handle(_inbound(p, OPTION="U", DSNAME="IBMUSER.CAT.PS")))
    assert "CATALOGED" in _W(a.handle(_inbound(p, OPTION="C", DSNAME="IBMUSER.CAT.PS")))
    assert "DSORG" in _W(a.handle(_inbound(p, OPTION="S", DSNAME="IBMUSER.CAT.PS")))


def test_a2_rename():
    st, a, m = _ispf()
    st.datasets.allocate("IBMUSER", "IBMUSER.OLD", org="PS")
    st.datasets.write("IBMUSER", "IBMUSER.OLD", "DATA\n")
    p = a.handle(_inbound(m, OPTION="3.2"))
    out = a.handle(_inbound(p, OPTION="R", DSNAME="IBMUSER.OLD", NEWNAME="IBMUSER.RENAMED"))
    assert "RENAMED" in _W(out)
    names = [i.name for i in st.datasets.listcat("IBMUSER")]
    assert "IBMUSER.RENAMED" in names and "IBMUSER.OLD" not in names


def test_a2_missing_name_reprompts():
    st, a, m = _ispf()
    p = a.handle(_inbound(m, OPTION="3.2"))
    out = a.handle(_inbound(p, OPTION="D", DSNAME=""))
    assert "ENTER A DATA SET NAME" in _W(out)


# --- A3: 3.3 Move/Copy ---------------------------------------------------
def test_a3_copy_sequential():
    st, a, m = _ispf(seed=True)
    mc = a.handle(_inbound(m, OPTION="3.3"))
    assert "MOVE/COPY" in _W(mc)
    out = a.handle(_inbound(mc, OPTION="C", FROM="IBMUSER.SRC", TO="IBMUSER.DST"))
    assert "COPIED" in _W(out)
    assert st.datasets.read("IBMUSER", "IBMUSER.DST") == "LINE1\nLINE2\n"


def test_a3_move_deletes_source():
    st, a, m = _ispf(seed=True)
    mc = a.handle(_inbound(m, OPTION="3.3"))
    out = a.handle(_inbound(mc, OPTION="M", FROM="IBMUSER.SRC", TO="IBMUSER.MOVED"))
    assert "MOVED" in _W(out)
    names = [i.name for i in st.datasets.listcat("IBMUSER")]
    assert "IBMUSER.MOVED" in names and "IBMUSER.SRC" not in names


def test_a3_member_copy():
    st, a, m = _ispf()
    st.datasets.allocate("IBMUSER", "IBMUSER.LIB(ALPHA)", org="PO")
    st.datasets.write("IBMUSER", "IBMUSER.LIB(ALPHA)", "AAA\n")
    mc = a.handle(_inbound(m, OPTION="3.3"))
    out = a.handle(_inbound(mc, OPTION="C", FROM="IBMUSER.LIB(ALPHA)", TO="IBMUSER.LIB2"))
    assert "COPIED" in _W(out)
    assert st.datasets.read("IBMUSER", "IBMUSER.LIB2(ALPHA)") == "AAA\n"


def test_a3_missing_operand_reprompts():
    st, a, m = _ispf(seed=True)
    mc = a.handle(_inbound(m, OPTION="3.3"))
    out = a.handle(_inbound(mc, OPTION="C", FROM="IBMUSER.SRC", TO=""))
    assert "ENTER BOTH" in _W(out)


# --- A6: editor command / count audit -----------------------------------
def _editor():
    st = GibsonState.create(); st.racf.load()
    return Ispf3270Editor(st, "IBMUSER", "IBMUSER.T(M)", "AAA\nBBB\nCCC\n")


def test_a6_clean_prefix_strips_residue():
    ed = _editor()
    assert ed._clean_prefix("I20100", "000100") == "I2"
    assert ed._clean_prefix("I00100", "000100") == "I"
    assert ed._clean_prefix("D20200", "000200") == "D2"
    assert ed._clean_prefix("000100", "000100") == ""        # unchanged = no command
    assert ed._clean_prefix("I2", "000100") == "I2"          # clean input untouched
    assert ed._clean_prefix("I2''''", "''''''") == "I2"      # residue on a new line


def test_a6_insert_count_exact():
    ed = _editor()
    before = len(ed.lines)
    pi = PanelInput(aid=0x7D, key="ENTER",
                    fields={"LP00000": "I20100", "LD00000": "AAA", "LD00001": "BBB", "LD00002": "CCC"})
    ed.handle(pi)
    assert len(ed.lines) == before + 2          # I2 -> exactly 2, not 20
    assert ed.lines[1] == "" and ed.lines[2] == ""


def test_a6_delete_count_exact():
    ed = _editor()
    pi = PanelInput(aid=0x7D, key="ENTER",
                    fields={"LP00000": "D20100", "LD00000": "AAA", "LD00001": "BBB", "LD00002": "CCC"})
    ed.handle(pi)
    assert ed.lines == ["CCC"]                  # D2 -> delete exactly 2 from line 0


def test_a6_repeat_count_exact():
    ed = _editor()
    before = len(ed.lines)
    pi = PanelInput(aid=0x7D, key="ENTER",
                    fields={"LP00000": "R20100", "LD00000": "AAA", "LD00001": "BBB", "LD00002": "CCC"})
    ed.handle(pi)
    assert len(ed.lines) == before + 2          # R2 -> 2 copies of line 0
    assert ed.lines[:3] == ["AAA", "AAA", "AAA"]


def test_a6_single_insert_still_one():
    ed = _editor()
    before = len(ed.lines)
    pi = PanelInput(aid=0x7D, key="ENTER", fields={"LP00000": "I00100", "LD00000": "AAA"})
    ed.handle(pi)
    assert len(ed.lines) == before + 1          # bare I -> 1 line


# --- A7: full primary-option acceptance sweep ---------------------------
def test_a7_primary_option_sweep():
    expect = {
        "0": "ISPF SETTINGS|SETTINGS|TERMINAL",
        "3": "UTILITY SELECTION",
        "6": "COMMAND",
        "8": "OUTLIST UTILITY",
        "S": "SDSF",
        "12": "DB2I",
        "DB2": "DB2I",
    }
    for opt, needles in expect.items():
        _st, a, m = _ispf()
        out = a.handle(_inbound(m, OPTION=opt))
        assert out is not None, f"option {opt} returned no screen"
        w = _W(out)
        assert any(n in w for n in needles.split("|")), f"option {opt}: got {w[:80]!r}"


def test_a7_util_suboption_sweep():
    expect = {"3.2": "DATA SET UTILITY", "3.3": "MOVE/COPY", "3.4": "DATA SET LIST"}
    for opt, needle in expect.items():
        _st, a, m = _ispf()
        out = a.handle(_inbound(m, OPTION=opt))
        assert out is not None and needle in _W(out), f"{opt}: {_W(out)[:80]!r}"


def test_a7_exit_returns_none():
    _st, a, m = _ispf()
    assert a.handle(_inbound(m, OPTION="X")) is None


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
