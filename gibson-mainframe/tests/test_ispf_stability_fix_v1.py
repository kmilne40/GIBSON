from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.ispf import IspfApp
from gibson.render.input import InputResult, panel_input_value


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
        return self.read_line_at(0, 0, hidden=hidden)


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(
        sim_root=root,
        files_root=root / "files",
        gacf_path=root / "GACF.DB",
        transfer_root=root / "transfers",
        security_mode="vuln",
    )
    st = GibsonState.create(cfg)
    st.racf.adduser("IBMUSER", "pass", special=True, omvs=True)
    # Stable low-noise catalogue used by DSLIST tests.
    st.datasets.allocate("IBMUSER", "IBMUSER.AAA.DATA", org="PS")
    st.datasets.write("IBMUSER", "IBMUSER.AAA.DATA", "LINE1\n")
    st.datasets.allocate("IBMUSER", "IBMUSER.PDS.CODE", org="PO")
    st.datasets.write("IBMUSER", "IBMUSER.PDS.CODE(TEST)", "//TEST JOB\n")
    return st


def test_panel_input_contract_preserves_typed_text_and_pf_actions():
    typed = panel_input_value(InputResult("E 1"), context="ISPF")
    assert typed.text == "E 1"
    assert typed.command == "E 1"
    assert not typed.key

    pf3 = panel_input_value(InputResult("", "F3"), context="ISPF")
    assert pf3.text == ""
    assert pf3.key == "F3"
    assert pf3.command == "END"

    leaked = panel_input_value(InputResult("^[OR"), context="ISPF")
    assert leaked.text == ""
    assert leaked.key == "F3"
    assert leaked.command == "END"


def test_dslist_e_1_preserves_raw_text_and_does_not_crash():
    st = make_state()
    app = IspfApp(st, "IBMUSER", lambda c: "OK")
    actions = []

    def fake_action(driver, send, action, row):
        actions.append((action, row.name))
        return "ACTION OK"

    app._dslist_action = fake_action  # type: ignore[method-assign]
    driver = FakeDriver([InputResult("E 1"), InputResult("", "F3")])
    output = []
    app.dslist_loop(driver, lambda text: output.append(text), "IBMUSER")

    assert actions
    assert actions[0][0] == "E"
    # Command cursor must be placed on Command ===> row, not the message/help row.
    assert driver.reads[0][:2] == (3, 13)
    assert "ACTION OK" in "".join(output)


def test_dslist_common_line_commands_stable_without_nameerror():
    for cmd in ["B 1", "V 1", "S 1", "M 1", "D 1", "R 1", "SORT", "REFRESH", "XYZ"]:
        st = make_state()
        app = IspfApp(st, "IBMUSER", lambda c: "OK")
        calls = []
        app._dslist_action = lambda driver, send, action, row, calls=calls: calls.append(action) or "OK"  # type: ignore[method-assign]
        driver = FakeDriver([InputResult(cmd), InputResult("", "F3")])
        app.dslist_loop(driver, lambda _text: None, "IBMUSER")
        assert driver.reads[0][:2] == (3, 13)


def test_pf_sequences_do_not_pollute_dslist_command_field():
    st = make_state()
    app = IspfApp(st, "IBMUSER", lambda c: "OK")
    driver = FakeDriver([InputResult("^[[18~"), InputResult("^[[19~"), InputResult("^[OR")])
    app.dslist_loop(driver, lambda _text: None, "IBMUSER")
    # All reads should target the command field. The helper converts the leaked
    # sequences to UP/DOWN/END, so no line-command action is attempted.
    assert all(r[:2] == (3, 13) for r in driver.reads)
