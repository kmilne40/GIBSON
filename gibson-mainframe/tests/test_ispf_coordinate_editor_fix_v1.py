import re
from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.ispf import IspfApp
from gibson.apps.editor import InteractiveEditor
from gibson.render.coordinates import ansi_move_zero_based, ansi_move_one_based
from gibson.render.input import InputResult

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

def visible_len(s: str) -> int:
    return len(ANSI_RE.sub("", s))

class FakeDriver:
    def __init__(self, results):
        self.results = list(results)
        self.reads = []
    def read_line_at(self, row, col, hidden=False):
        self.reads.append((row, col, hidden))
        if self.results:
            return self.results.pop(0)
        return InputResult("", "EOF")
    def read_line(self, prompt="", hidden=False, mask=False, timeout=None):
        return self.read_line_at(0,0,hidden)

class FakeKeyDriver:
    def __init__(self, keys):
        self.keys = list(keys)
    def read_key(self):
        if self.keys:
            return self.keys.pop(0)
        return InputResult("", "EOF")

def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root/"files", gacf_path=root/"GACF.DB", transfer_root=root/"transfers", security_mode="vuln")
    st = GibsonState.create(cfg)
    st.racf.adduser("IBMUSER", "pass", special=True, omvs=True)
    # Use a broad catalogue so row-count is two digits and must not wrap.
    for i in range(35):
        st.datasets.allocate("IBMUSER", f"COORD.TEST{i:02d}.DATA", org="PS")
        st.datasets.write("IBMUSER", f"COORD.TEST{i:02d}.DATA", "DATA\n")
    return st

def test_coordinate_helpers_are_explicit():
    assert ansi_move_zero_based(0,0) == "\x1b[1;1H"
    assert ansi_move_zero_based(2,12) == "\x1b[3;13H"
    assert ansi_move_one_based(3,13) == "\x1b[3;13H"

def test_dslist_title_width_and_command_cursor_constants():
    st = make_state(); app = IspfApp(st, "IBMUSER", lambda c: "OK")
    title = app._dslist_title("COORD", "Row 1 of 35")
    assert visible_len(title) <= 79
    output=[]
    driver = FakeDriver([InputResult("Q"), InputResult("", "F3")])
    app.dslist_loop(driver, lambda text: output.append(text), "COORD")
    assert driver.reads[0][:2] == (app.DSLIST_COMMAND_ROW, app.DSLIST_COMMAND_COL)
    first_screen = output[0]
    for line in first_screen.splitlines()[:6]:
        assert visible_len(line) <= 79
    assert "Row 1 of 35" in first_screen

def test_dslist_e_1_b_1_stable_after_coordinate_fix():
    for cmd in ["E 1", "B 1", "V 1", "S 1", "M 1", "XYZ", "SORT", "REFRESH"]:
        st = make_state(); app = IspfApp(st, "IBMUSER", lambda c: "OK")
        calls=[]
        app._dslist_action = lambda driver, send, action, row, calls=calls: calls.append((action,row.name)) or "OK"  # type: ignore[method-assign]
        driver = FakeDriver([InputResult(cmd), InputResult("", "F3")])
        app.dslist_loop(driver, lambda _text: None, "COORD")
        assert driver.reads[0][:2] == (app.DSLIST_COMMAND_ROW, app.DSLIST_COMMAND_COL)

def test_editor_cursor_uses_zero_based_contract_and_no_row_plus_two():
    ed = InteractiveEditor("SYS1.BRODCAST", "HELLO", mode="EDIT", lrecl=80)
    assert ed._ansi_move(0,0) == "\x1b[1;1H"
    assert ed._ansi_move(ed.DATA_AREA_START, ed.COMMAND_FIELD_WIDTH) == f"\x1b[{ed.DATA_AREA_START+1};{ed.COMMAND_FIELD_WIDTH+1}H"
    ed.cur_row = ed.DATA_AREA_START
    ed.cur_col = ed.COMMAND_FIELD_WIDTH + ed._visible_width() + 10
    assert ed._physical_cursor_col() == ed.COMMAND_FIELD_WIDTH + ed._visible_width() - 1

def test_editor_typing_does_not_wrap_at_half_line_and_enter_moves_record():
    ed = InteractiveEditor("SYS1.BRODCAST", "", mode="EDIT", lrecl=80)
    sent=[]
    chars = [InputResult(ch) for ch in "A"*60]
    keys = chars + [InputResult("ENTER", "ENTER"), InputResult("CANCEL", "ENTER")]
    driver = FakeKeyDriver(keys)
    ed.run(driver, lambda text: sent.append(text))
    assert ed.lines[0].startswith("A"*60)
    assert ed.cur_row >= ed.DATA_AREA_START
    # Rendered lines must be width safe after ANSI stripping.
    ed._draw(lambda text: sent.append(text))
    for line in sent[-2].splitlines():
        assert visible_len(line) <= ed.SCREEN_WIDTH
