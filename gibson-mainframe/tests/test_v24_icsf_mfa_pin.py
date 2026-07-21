from __future__ import annotations

import argparse
from datetime import datetime

from gibson.cli import build_state
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.master_console import MasterConsoleController
from gibson.security import mfa_pin


def _args(tmp_path, *, secure=False):
    return argparse.Namespace(
        secure=secure, vuln=not secure, gacf=None, sim_root=str(tmp_path), host=None, port=None,
        ftp_port=None, uss_port=None, tn3270_port=None, rest_port=None, db2_tcp_port=None, db2_ws_port=None,
    )


def test_mfa_pin_setup_and_token_validation(tmp_path):
    st = build_state(_args(tmp_path))
    out = st.set_mfa_pin("1234", "CONSOLE")
    assert "PIN ACCEPTED" in out
    assert st.mfa_pin_set()
    assert st.validate_mfa_token("12341437") is False
    assert mfa_pin.validate_token(st, "12341437", now=datetime(2026, 5, 3, 14, 37)) is True
    assert mfa_pin.validate_token(st, "99991437", now=datetime(2026, 5, 3, 14, 37)) is False
    assert mfa_pin.validate_token(st, "12341436", now=datetime(2026, 5, 3, 14, 37)) is True  # default +/-1 minute
    status = "\n".join(st.mfa_status_lines())
    assert "PIN STATUS: SET" in status
    assert "1234" not in status


def test_mfa_pin_rejects_invalid_values(tmp_path):
    st = build_state(_args(tmp_path))
    for bad in ["123", "12345", "12A4", ""]:
        try:
            st.set_mfa_pin(bad, "CONSOLE")
        except ValueError as exc:
            assert "4 NUMERIC" in str(exc)
        else:
            raise AssertionError("invalid PIN accepted")


def test_master_console_r03_y_prompts_for_mfa_pin(tmp_path):
    st = build_state(_args(tmp_path))
    ctl = MasterConsoleController(st, "IBMUSER")
    assert "R 01" in ctl.boot_text()
    out1 = ctl.execute("R 01,00").text
    assert "R 02" in out1
    out2 = ctl.execute("R 02,U").text
    assert "R 03" in out2
    out3 = ctl.execute("R 03,Y").text
    assert "DEFINE 4-DIGIT MFA PIN" in out3
    out4 = ctl.execute("R 04,1234").text
    assert "MFA PIN ACCEPTED" in out4
    assert st.mfa_pin_set()
    assert "IPLINFO" in out4


def test_mfa_commands_preserve_status_and_use_pin(tmp_path):
    st = build_state(_args(tmp_path))
    st.set_mfa_pin("1234", "CONSOLE")
    admin = TsoCommandProcessor(st, "IBMUSER")
    assert admin.run("MFA ON") == "MFA ENABLED"
    status = admin.run("MFA STATUS")
    assert "MFA STATUS: ENABLED" in status
    assert "PIN STATUS: SET" in status
    assert "1234" not in status
    guest = TsoCommandProcessor(st, "GUEST")
    assert "NOT AUTHORISED" in guest.run("MFA OFF")


def test_icsf_status_and_refresh_authority(tmp_path):
    st = build_state(_args(tmp_path))
    ibm = TsoCommandProcessor(st, "IBMUSER")
    out = ibm.run("ICSF STATUS")
    assert "ICSF SIMULATED STATUS" in out
    before = st.icsf_state.master_key_version
    out = ibm.run("ICSF REFRESH MASTERKEY")
    assert "MASTER KEY REFRESH COMPLETE" in out
    assert st.icsf_state.master_key_version == before + 1
    out = ibm.run("ICSF REFRESH CKDS")
    assert "CKDS REFRESH COMPLETE" in out
    guest = TsoCommandProcessor(st, "GUEST")
    denied = guest.run("ICSF REFRESH MASTERKEY")
    assert "DENIED BY RACF" in denied
    assert any(e.extra.get("EVENT", "").startswith("ICSF") for e in st.audit.events if e.component == "SMF80")


def test_icsf_console_commands(tmp_path):
    st = build_state(_args(tmp_path))
    ctl = MasterConsoleController(st, "IBMUSER")
    assert "ICSF SIMULATED STATUS" in ctl.execute("D ICSF").text
    out = ctl.execute("F ICSF,REFRESH,TKDS").text
    assert "TKDS REFRESH COMPLETE" in out
