from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from gibson.cli import build_state
from gibson.apps.tso import TsoCommandProcessor


def _args(tmp_path, *, vuln=True):
    return argparse.Namespace(
        secure=not vuln, vuln=vuln, gacf=None, sim_root=str(tmp_path), host=None,
        port=None, ftp_port=None, uss_port=None, tn3270_port=None, rest_port=None,
        db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False,
        with_web_terminal=False, web_terminal_port=None, split_console=False,
        logon_panel=False,
    )


def test_mfa_pin_persists_between_ipl_console_and_service_state(tmp_path):
    ipl_state = build_state(_args(tmp_path))
    ipl_state.set_mfa_pin("2468", "CONSOLE")

    service_state = build_state(_args(tmp_path))
    assert service_state.mfa_pin_set()
    assert service_state.validate_mfa_token("24680000") is False


def test_mfa_policy_persists_and_bare_mfa_command_enables_previous_behaviour(tmp_path):
    st = build_state(_args(tmp_path))
    proc = TsoCommandProcessor(st, "IBMUSER")
    assert proc.run("MFA") == "MFA ENABLED"

    restarted = build_state(_args(tmp_path))
    assert restarted.mfa_enabled is True
    assert "MFA STATUS: ENABLED" in "\n".join(restarted.mfa_status_lines())


def test_ipl_prestart_console_completes_before_curses_launch(tmp_path):
    cmd = [
        sys.executable, "-m", "gibson.cli",
        "--sim-root", str(tmp_path),
        "--ipl-prestart-console",
    ]
    replies = "R 01,CLPA\nR 02,U\nR 03,Y\nR 04,1357\n"
    res = subprocess.run(cmd, input=replies, text=True, capture_output=True, timeout=10)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "GIBMCS012I IPL REPLY SEQUENCE COMPLETE" in res.stdout

    st = build_state(_args(tmp_path))
    assert st.mfa_pin_set()


def test_gibsonctl_start_runs_ipl_before_service_and_master_console():
    text = Path("gibsonctl.sh").read_text(encoding="utf-8")
    assert "run_ipl_prestart_if_needed" in text
    assert "--ipl-prestart-console" in text
    start_body = text[text.index("start_service() {"):text.index("is_interactive_terminal() {")]
    ipl_pos = start_body.index("run_ipl_prestart_if_needed")
    start_pos = start_body.index("setsid \"$PYTHON_BIN\" -m \"$MODULE_CMD\"")
    launch_pos = start_body.rindex("launch_master_after_start")
    assert ipl_pos < start_pos < launch_pos
