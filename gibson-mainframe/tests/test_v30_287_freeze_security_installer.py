from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.cics import CicsSimulator


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/"f", commands_dir=tmp_path/"f"/"commands", transfer_root=tmp_path/"transfers", gacf_path=tmp_path/"GACF.DB")
    cfg.gacf_path.write_text("IBMUSER:{KDFAES}KAAAAAAAAAAAAAAAAAAAAA==$1$bad:SPECIAL:OMVS:SYS1\nGUEST:SYS1:NONE:NOOMVS:STUDENT\n")
    st = GibsonState.create(cfg)
    # reset IBMUSER to a valid password through repository
    st.racf.altuser("IBMUSER", password="Sys1Pass!")
    st.racf.save()
    st.uads.sync_from_racf(st.racf, st.password_policy)
    return st


def test_setropts_password_policy_and_list(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("SETROPTS PASSWORD(ALGORITHM(KDFAES)) MINLENGTH(12) HISTORY(7) REVOKE(4) INTERVAL(60) MIXEDCASE SPECIALCHARS")
    assert "UPDATED" in out
    listed = tso.run("SETROPTS LIST")
    assert "ALGORITHM       KDFAES" in listed
    assert "MINLENGTH       12" in listed
    assert "HISTORY         7" in listed
    assert "SPECIALCHARS    ACTIVE" in listed


def test_adduser_creates_uads_and_forces_change(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    st.password_policy.minlength = 8
    st.password_policy.mixedcase = False
    out = tso.run("ADDUSER TESTUSR PASS(initial1) DFLTGRP(SYS1)")
    assert "DEFINED" in out
    ent = st.uads.get("TESTUSR")
    assert ent is not None
    assert ent.password_change_required is True
    assert "initial1" not in ent.password_hash
    assert "TESTUSR" in tso.run("UADS LIST")


def test_password_command_updates_uads(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    st.password_policy.minlength = 8
    st.password_policy.mixedcase = True
    st.password_policy.specialchars = True
    out = tso.run("PASSWORD Sys1Pass! NewPass1!")
    assert "PASSWORD CHANGED" in out
    assert st.racf.verify_password("IBMUSER", "NewPass1!")
    assert st.uads.get("IBMUSER").password_change_required is False


def test_mfa_enroll_and_zsec_visible(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    out = tso.run("MFA ENROLL IBMUSER TYPE(TOTP)")
    assert "ENROLLED" in out
    assert st.uads.get("IBMUSER").mfa_required is True
    assert "GLOBAL" in tso.run("MFA STATUS")


def test_cics_security_defaults_and_set(tmp_path):
    st = make_state(tmp_path)
    cics = CicsSimulator(st, "IBMUSER")
    out = cics.execute("CICS DISPLAY SECURITY")
    assert "SEC      : YES" in out
    assert "XTRAN    : YES" in out
    assert "XCMD     : YES" in out
    assert "XPCT     : YES" in out
    assert "XFCT     : YES" in out
    assert "DFLTUSER : CICSUSER" in out
    out2 = cics.execute("CICS SET SIT DFLTUSER(CICSUSER)")
    assert "DFLTUSER SET TO CICSUSER" in out2


def test_freeze_scripts_include_kali_repo_guardrail():
    text = Path("install-docker-for-gibson.sh").read_text()
    assert "download.docker.com" in text
    assert "kali" in text.lower()
    assert "docker.io" in text
    helper = Path("web-terminal/bin/gibson-web-terminal.sh").read_text()
    assert "install-docker-for-gibson.sh" in helper
