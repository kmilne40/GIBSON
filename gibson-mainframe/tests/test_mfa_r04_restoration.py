from __future__ import annotations

from gibson.apps.master_console import MasterConsoleController
from gibson.core.state import GibsonState


def _pending_mfa_controller(tmp_path):
    from gibson.core.config import GibsonConfig
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n", encoding="utf-8")
    st = GibsonState.create(cfg)
    ctl = MasterConsoleController(st, "IBMUSER")
    ctl.boot_text()
    assert "R 02" in ctl.execute("R 01,00").text
    assert "R 03" in ctl.execute("R 02,U").text
    assert "DEFINE 4-DIGIT MFA PIN" in ctl.execute("R 03,Y").text
    return st, ctl


def test_mfa_r04_1234_accepted_variants(tmp_path):
    for cmd in ["r 04,1234", "R 04,1234", "r 04, 1234", "REPLY 04,1234", "REPLY 04, 1234"]:
        case_path = tmp_path / cmd.replace(" ", "_").replace(",", "_")
        case_path.mkdir()
        st, ctl = _pending_mfa_controller(case_path)
        out = ctl.execute(cmd).text
        assert "MFA PIN ACCEPTED" in out
        assert "IPLINFO" in out
        assert st.mfa_pin_set()


def test_mfa_r04_wrong_token_and_wrong_reply_rejected(tmp_path):
    st, ctl = _pending_mfa_controller(tmp_path / "wrong_token")
    wrong = ctl.execute("R 04,999").text
    assert "MFA PIN REJECTED" in wrong
    assert not st.mfa_pin_set()
    st, ctl = _pending_mfa_controller(tmp_path / "wrong_id")
    wrong_id = ctl.execute("R 05,1234").text
    assert "REPLY ID 05 NOT FOUND" in wrong_id
    st, ctl = _pending_mfa_controller(tmp_path / "no_pending")
    ok = ctl.execute("R 04,1234").text
    assert "MFA PIN ACCEPTED" in ok
    no_pending = ctl.execute("R 04,1234").text
    assert "REPLY ID 04 NOT FOUND" in no_pending
