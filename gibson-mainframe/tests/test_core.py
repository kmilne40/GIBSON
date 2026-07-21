from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.ispf import IspfApp
from gibson.apps.editor import EditorModel, EditorCommandProcessor
from gibson.languages.cobol import CobolSimulator


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(
        sim_root=tmp_path,
        files_root=tmp_path / "f",
        commands_dir=tmp_path / "f" / "commands",
        gacf_path=tmp_path / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def test_racf_and_tso_listuser(tmp_path):
    st = make_state(tmp_path)
    out = TsoCommandProcessor(st, "IBMUSER").run("LISTUSER IBMUSER")
    assert "USER=IBMUSER" in out
    assert "OMVS" in out


def test_ispf_option6_routes_to_tso(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    app = IspfApp(st, "IBMUSER", tso.run)
    out = app.option6_command("LISTUSER IBMUSER")
    assert "USER=IBMUSER" in out


def test_jes_submit_from_tso(tmp_path):
    st = make_state(tmp_path)
    st.datasets.write("IBMUSER", "IBMUSER.CNTL.TEST", "//TESTJOB JOB (ACCT),'GIBSON'\n//STEP1 EXEC PGM=IEFBR14\n")
    out = TsoCommandProcessor(st, "IBMUSER").run("SUBMIT 'IBMUSER.CNTL.TEST'")
    assert "SUBMITTED" in out
    assert st.jes.list_jobs()[0].jobname == "TESTJOB"


def test_editor_model_insert_delete_change():
    m = EditorModel(["HELLO WORLD"])
    p = EditorCommandProcessor(m)
    assert p.execute("CHANGE WORLD GIBSON") == "1 OCCURRENCES CHANGED"
    assert m.lines[0] == "HELLO GIBSON"
    p.execute("I2")
    assert len(m.lines) == 3
    p.execute("D1")
    assert len(m.lines) == 2


def test_cobol_simulator():
    src = "IDENTIFICATION DIVISION.\nPROGRAM-ID. X.\nPROCEDURE DIVISION.\nDISPLAY 'HELLO'.\nSTOP RUN."
    res = CobolSimulator().compile(src)
    assert res.rc == 0
    assert res.display_lines == ["HELLO"]
