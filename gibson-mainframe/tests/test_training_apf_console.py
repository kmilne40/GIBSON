from pathlib import Path

from gibson.apps.editor import EditorModel, EditorCommandProcessor
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:OMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def test_failed_logons_raise_console_alert(tmp_path):
    st = make_state(tmp_path)
    st.note_failed_logon("GUEST", "127.0.0.1")
    st.note_failed_logon("GUEST", "127.0.0.1")
    st.note_failed_logon("GUEST", "127.0.0.1")
    events = st.drain_console_events()
    assert any("MULTIPLE FAILED LOGON ATTEMPTS" in text for _sev, text in events)


def test_apf_add_logs_console_and_elv_apf_elevates_standard_user(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    guest = TsoCommandProcessor(st, "GUEST")
    out = admin.run("SETPROG APF,ADD,DSNAME='GUEST.APF.LIB',VOLUME=WORK01")
    assert "CSV410I DATA SET GUEST.APF.LIB" in out
    events = st.drain_console_events()
    assert any("APF LIBRARY GUEST.APF.LIB" in text for _sev, text in events)
    exploit = guest.run("EX 'ELV.APF'")
    assert "SPECIAL ATTRIBUTE NOW ACTIVE FOR GUEST" in exploit
    assert st.racf.get("GUEST").special is True


def test_alloc_and_oget_apply_userid_prefix(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "GUEST")
    alloc = tso.run("ALLOC TEST.DATA")
    assert "GUEST.TEST.DATA" in alloc
    env_dir = st.config.sim_root / "uss" / "u" / "guest"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "sample.txt").write_text("hello", encoding="utf-8")
    out = tso.run("OGET '/u/guest/sample.txt' TEST.COPY")
    assert "GUEST.TEST.COPY" in out
    assert st.datasets.read("GUEST", "GUEST.TEST.COPY") == "hello"


def test_editor_supports_rfind_profile_and_stacked_commands():
    model = EditorModel(["alpha", "beta alpha", "gamma alpha"], recfm="FB", lrecl=80)
    proc = EditorCommandProcessor(model)
    assert proc.execute("find alpha") == "CHARS 'alpha' FOUND"
    assert proc.execute("RFIND").startswith("CHARS 'alpha'")
    assert "CAPS OFF" in proc.execute("CAPS OFF; PROFILE")
