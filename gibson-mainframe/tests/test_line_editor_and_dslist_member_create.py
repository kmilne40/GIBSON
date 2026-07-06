from pathlib import Path

from gibson.apps.ispf import IspfApp
from gibson.apps.tso_line_editor import TsoLineEditorSession
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult


class FakeLineDriver:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False):
        self.prompts.append(prompt)
        if not self.responses:
            return InputResult("", "EOF")
        return self.responses.pop(0)


class FakePanelDriver:
    def __init__(self, responses):
        self.responses = list(responses)

    def read_line_at(self, row: int, col: int, hidden: bool = False):
        if not self.responses:
            return InputResult("", "EOF")
        return self.responses.pop(0)

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False):
        if not self.responses:
            return InputResult("", "EOF")
        return self.responses.pop(0)


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def test_tso_line_editor_numbers_input_lines_and_end_saves_new_dataset():
    saved: list[str] = []
    output: list[str] = []
    driver = FakeLineDriver([
        InputResult("FIRST LINE"),
        InputResult("SECOND LINE"),
        InputResult(""),
        InputResult("END"),
    ])
    session = TsoLineEditorSession(
        "IBMUSER.NEW.DATA",
        "",
        exists=False,
        save_callback=saved.append,
        type_prompt_callback=lambda: InputResult("TEXT"),
    )

    session.run(driver, output.append)

    assert saved == ["FIRST LINE\nSECOND LINE"]
    assert "00010 " in driver.prompts
    assert "00020 " in driver.prompts
    assert "00030 " in driver.prompts
    assert any("DATASET OR MEMBER NOT FOUND, ASSUMED TO BE NEW" in line for line in output)
    assert output[-1] == "EDIT\n"


def test_dslist_command_field_can_create_new_pds_member(monkeypatch, tmp_path: Path):
    st = make_state(tmp_path)
    st.datasets.allocate("IBMUSER", "IBMUSER.TEST.PDS", org="PO")
    app = IspfApp(st, "IBMUSER", lambda _cmd: "")
    opened: list[str] = []

    def fake_run(self, driver, send):
        opened.append(self.dataset)

    monkeypatch.setattr("gibson.apps.ispf.InteractiveEditor.run", fake_run)
    driver = FakePanelDriver([
        InputResult("TEST.PDS(MEMBER.NEW)"),
        InputResult("F3"),
    ])

    app.dslist_loop(driver, lambda _text: None, "IBMUSER.TEST")

    assert opened == ["IBMUSER.TEST.PDS(MEMBER.NEW)"]
    assert st.datasets.read("IBMUSER", "IBMUSER.TEST.PDS(MEMBER.NEW)") == ""
