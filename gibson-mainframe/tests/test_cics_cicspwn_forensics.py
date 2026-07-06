from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from gibson.apps.cics import CicsSimulator
from gibson.apps.sdsf import SdsfApp
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState


def make_state(tmp_path: Path) -> GibsonState:
    sim_root = tmp_path / "mfsim"
    cfg = GibsonConfig(
        host="127.0.0.1",
        sim_root=sim_root,
        files_root=sim_root / "f",
        commands_dir=sim_root / "f" / "commands",
        gacf_path=sim_root / "GACF.DB",
        console_security_audit=True,
    )
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:OMVS\n", encoding="utf-8")
    return GibsonState.create(cfg)


def test_cics_region_define_install_and_inquire_shared_state(tmp_path):
    st = make_state(tmp_path)
    cics = CicsSimulator(st, "IBMUSER")
    assert "SUCCESSFULLY" in cics.execute("CESN")
    defined = cics.execute("CEDA DEFINE PROGRAM(ZZZ1) GROUP(TEST) LANGUAGE(COBOL)")
    assert "INSTALL REQUIRED" in defined
    trans = cics.execute("CEDA DEFINE TRANSACTION(Z123) PROGRAM(ZZZ1) GROUP(TEST)")
    assert "TRANSACTION Z123" in trans
    installed = cics.execute("CEDA INSTALL GROUP(TEST)")
    assert "PROGRAM(ZZZ1)" in installed and "TRANSACTION(Z123)" in installed
    cics2 = CicsSimulator(st, "IBMUSER")
    assert "Tra(Z123" in cics2.execute("CEMT I TRAN")


def test_cics_security_denial_generates_smf80_and_console_evidence(tmp_path):
    st = make_state(tmp_path)
    # Protect CECI from GUEST while leaving sign-on possible.
    st.dynamic_racf.define("TCICSTRN", "CECI", "IBMUSER", "NONE")
    st.dynamic_racf.save()
    cics = CicsSimulator(st, "GUEST")
    cics.execute("CESN")
    denied = cics.execute("CECI ASSIGN")
    assert "NOT AUTHORIZED" in denied
    smf = [e for e in st.audit.events if e.component == "SMF80"]
    assert any(e.extra.get("TRANSID") == "CECI" and e.extra.get("RESULT") == "FAILURE" for e in smf)
    operlog = st.console_log.operlog_path.read_text(encoding="utf-8", errors="ignore")
    assert "TRANSID=CECI" in operlog and "RESULT=FAILURE" in operlog


def test_cicspwn_probe_writes_corrid_and_is_visible_in_sdsf_smf80(tmp_path):
    st = make_state(tmp_path)
    cics = CicsSimulator(st, "IBMUSER")
    cics.execute("CESN")
    out = cics.execute("CICSPWN PROBE")
    assert "CICSPWN STAGED DISCOVERY SUMMARY" in out
    assert "CORRID=" in out
    panel = SdsfApp(st, "IBMUSER").build_panel("SMF80")
    assert "CORRID" in panel.columns
    assert any("CICSPWN" in r.cells.get("EVENT", "") or r.cells.get("TRANSID") == "PWN" for r in panel.rows)
    screen, msg = SdsfApp(st, "IBMUSER").perform_action("SMF80", "S", len(panel.rows))
    assert screen is not None
    assert "SMF TYPE 80 SECURITY RECORD DETAIL" in screen


def test_enhanced_nmap_sim_module_is_importable_and_classifies_transactions():
    path = Path(__file__).resolve().parents[1] / "legacy" / "nmap-sim.py"
    spec = importlib.util.spec_from_file_location("nmap_sim_enhanced", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    f1 = mod.classify_transaction("CECI", "DFHXS1111 USER GUEST NOT AUTHORIZED FOR TRANSACTION CECI")
    assert f1.state == "denied"
    f2 = mod.classify_transaction("CEMT", "INQUIRE SYSTEM APPLID(CICS)")
    assert f2.state == "available"
