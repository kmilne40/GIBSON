from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from gibson.cli import build_state
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.security_mode import is_secure_mode, is_vuln_mode, security_mode_banner
from gibson.core.state import GibsonState
from gibson.security.secure_profile import apply_secure_profile


def _args(tmp_path: Path, *, secure=False, vuln=False):
    return argparse.Namespace(
        secure=secure, vuln=vuln, gacf=None, sim_root=str(tmp_path), host=None, port=None,
        ftp_port=None, uss_port=None, tn3270_port=None, rest_port=None, db2_tcp_port=None,
        db2_ws_port=None,
    )


def test_runtime_switches_secure_vuln_and_conflict(tmp_path):
    secure = build_state(_args(tmp_path / "secure", secure=True))
    assert is_secure_mode(secure)
    assert secure.config.port == 1023
    assert secure.config.dashboard_port == 8443
    assert "SECURE MODE" in security_mode_banner(secure)

    vuln = build_state(_args(tmp_path / "vuln", vuln=True))
    assert is_vuln_mode(vuln)
    assert vuln.config.port == 2023

    with pytest.raises(SystemExit):
        build_state(_args(tmp_path / "bad", secure=True, vuln=True))


def test_secure_profile_applies_cis_dataset_controls(tmp_path):
    state = build_state(_args(tmp_path, secure=True))
    out = TsoCommandProcessor(state, "IBMUSER").run("SETROPTS LIST")
    assert "PROTECT-ALL FAIL OPTION IS IN EFFECT" in out
    assert "OPERAUDIT" in out
    prof = state.dynamic_racf._find_profile("DATASET", "SYS1.RACFDS")
    assert prof is not None
    assert prof.uacc == "NONE"
    assert prof.warning is False
    assert prof.permits.get("IBMUSER") == "ALTER"


def test_altuser_revoke_resume_and_deluser_secure_breakglass(tmp_path):
    state = build_state(_args(tmp_path, secure=True))
    proc = TsoCommandProcessor(state, "IBMUSER")
    assert "DEFINED" in proc.run("ADDUSER TEMPUSR PASS(TEMP123)")
    out = proc.run("ALTUSER TEMPUSR REVOKE")
    assert "REVOKE COMPLETE" in out
    assert state.racf.get("TEMPUSR").revoked is True
    assert state.racf.verify_password("TEMPUSR", "TEMP123") is False
    assert "REVOKED" in proc.run("LISTUSER TEMPUSR")
    out = proc.run("ALTUSER TEMPUSR RESUME")
    assert "RESUME COMPLETE" in out
    assert state.racf.get("TEMPUSR").revoked is False
    assert "DELETED" in proc.run("DELUSER TEMPUSR")
    assert state.racf.get("TEMPUSR") is None
    assert "REJECTED" in proc.run("ALTUSER IBMUSER REVOKE")
    assert "REJECTED" in proc.run("DELUSER IBMUSER")


def test_secure_blocks_vulnerable_training_commands_but_vuln_keeps_them(tmp_path):
    secure = build_state(_args(tmp_path / "s", secure=True))
    out = TsoCommandProcessor(secure, "IBMUSER").run("PTKTGEN USER(GUEST) APPL(TSO)")
    assert "REQUEST BLOCKED" in out
    vuln = build_state(_args(tmp_path / "v", vuln=True))
    out = TsoCommandProcessor(vuln, "IBMUSER").run("PTKTSTAT")
    assert "PTKTDATA" in out or "PASSTICKET" in out


def test_secure_mfa_and_ibmuser_breakglass_audited(tmp_path):
    state = build_state(_args(tmp_path, secure=True))
    assert state.mfa_required_for("GUEST") is True
    assert state.mfa_required_for("IBMUSER") is False
    events = "\n".join(e.result for e in state.audit.events[-20:])
    assert "break-glass" in events.lower()
