from __future__ import annotations

from pathlib import Path

from gibson.apps.sdsf import SdsfApp
from gibson.services.telnet_server import GibsonTelnetSession, ClientDisconnected

from tests.test_ftp_jes_rexx_rest_lab_upgrade import make_state


class BrokenConn:
    def sendall(self, _data):
        raise BrokenPipeError()
    def recv(self, _n):
        return b''
    def setsockopt(self, *_a):
        return None
    def settimeout(self, *_a):
        return None


class DummyConn:
    def sendall(self, _data):
        return None


def test_expected_disconnect_is_not_written_to_issue_log(tmp_path: Path):
    st = make_state(tmp_path)
    try:
        GibsonTelnetSession(st, BrokenConn(), ("127.0.0.1", 23)).send("x")
    except ClientDisconnected as exc:
        if st.issue_log is not None:
            st.issue_log.record("TELNET", ("127.0.0.1", 23), exc)
    if st.issue_log is not None:
        assert not st.issue_log.path.exists()


def test_smf80_panel_browse_shows_detailed_security_fields(tmp_path: Path):
    st = make_state(tmp_path)
    st.record_security_event("IBMUSER", "LOGON", "PASSWORD", service="TSO", addr="127.0.0.1", terminal="VTAM")
    app = SdsfApp(st, "IBMUSER")
    panel = app.build_panel("SMF80")
    assert panel.rows
    screen, msg = app.perform_action("SMF80", "S", 1)
    assert msg == ""
    assert screen is not None
    assert "SMF TYPE 80 SECURITY RECORD DETAIL" in screen
    assert "RESOURCE : TSO" in screen
    assert "MESSAGE  : ICH70001I" in screen
