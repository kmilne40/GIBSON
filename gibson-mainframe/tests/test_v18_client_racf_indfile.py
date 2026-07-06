from pathlib import Path
import socket
import threading

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.net.telnet3270 import IAC, EOR, WILL, BINARY, DO, END_OF_RECORD, TERMINAL_TYPE, SB, SE, IS
from gibson.net.vtam_frontend import negotiate_tn3270_or_ascii


def make_state(tmp_path):
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/"f", commands_dir=tmp_path/"f"/"commands", gacf_path=tmp_path/"GACF.DB", transfer_root=tmp_path/"transfers", console_security_audit=True)
    return GibsonState.create(cfg)


def test_tn3270_negotiation_no_eor_for_ascii_client():
    server, client = socket.socketpair()
    result = {}
    def run():
        result['mode'] = negotiate_tn3270_or_ascii(server, timeout=0.05)
    try:
        t = threading.Thread(target=run, daemon=True)
        t.start()
        data = client.recv(128)
        assert bytes([IAC, EOR]) not in data
        assert bytes([IAC, WILL, BINARY]) in data
        t.join(1)
    finally:
        server.close(); client.close()


def test_tn3270_synthetic_client_enters_3270_mode_after_binary_eor():
    server, client = socket.socketpair()
    result = {}
    def run():
        result['mode'] = negotiate_tn3270_or_ascii(server, timeout=0.4)
    t = threading.Thread(target=run, daemon=True); t.start()
    client.recv(128)
    client.sendall(bytes([IAC, DO, BINARY, IAC, WILL, BINARY, IAC, DO, END_OF_RECORD, IAC, WILL, END_OF_RECORD, IAC, WILL, TERMINAL_TYPE, IAC, SB, TERMINAL_TYPE, IS]) + b"IBM-3278-2-E" + bytes([IAC, SE]))
    t.join(1)
    assert result['mode'].use_tn3270 is True
    server.close(); client.close()


def test_warning_mode_allows_and_raises_evidence(tmp_path):
    state = make_state(tmp_path)
    state.dynamic_racf.define("DATASET", "LAB.SECRET", "IBMUSER", "NONE", warning=True)
    state.datasets.allocate("IBMUSER", "LAB.SECRET")
    state.datasets.write("IBMUSER", "LAB.SECRET", "secret")
    assert state.datasets.read("GUEST", "LAB.SECRET") == "secret"
    smf = [e for e in state.audit.events if e.component == "SMF80" and e.extra.get("WARNING") == "TRUE"]
    assert smf and "WARNING MODE" in smf[-1].extra.get("DETAIL", "")
    assert any("WARNING MODE" in msg for _sev, msg in state.console_events)
    assert any(a.get("event_type") == "WARNING_MODE" for a in state.dashboard_alerts)


def test_read_update_alter_enforcement_and_groups(tmp_path):
    state = make_state(tmp_path)
    state.dynamic_racf.define("DATASET", "GUEST.TEST.DATA", "IBMUSER", "NONE")
    state.datasets.allocate("IBMUSER", "GUEST.TEST.DATA")
    state.datasets.write("IBMUSER", "GUEST.TEST.DATA", "base")
    state.dynamic_racf.permit("DATASET", "GUEST.TEST.DATA", "GUEST", "READ")
    assert state.datasets.read("GUEST", "GUEST.TEST.DATA") == "base"
    try:
        state.datasets.write("GUEST", "GUEST.TEST.DATA", "bad")
        assert False, "READ-only write should fail"
    except PermissionError as exc:
        assert "NOT AUTHORIZED" in str(exc)
    state.dynamic_racf.groups["LABGRP"] = state.dynamic_racf.groups.get("LABGRP") or __import__('gibson.core.racf_dynamic', fromlist=['RacfGroup']).RacfGroup("LABGRP")
    state.dynamic_racf.connect_user("GUEST", "LABGRP")
    state.dynamic_racf.permit("DATASET", "GUEST.TEST.DATA", "LABGRP", "UPDATE")
    state.datasets.write("GUEST", "GUEST.TEST.DATA", "ok")
    try:
        state.datasets.delete("GUEST", "GUEST.TEST.DATA")
        assert False, "UPDATE delete should fail"
    except PermissionError:
        pass
    state.dynamic_racf.permit("DATASET", "GUEST.TEST.DATA", "LABGRP", "ALTER")
    assert "DELETED" in state.datasets.delete("GUEST", "GUEST.TEST.DATA")


def test_revoke_deluser_setropts_and_indfile(tmp_path):
    state = make_state(tmp_path)
    state.racf.adduser("TEMPUSR", "PASS", default_group="STUDENT")
    state.dynamic_racf.connect_user("TEMPUSR", "STUDENT")
    state.dynamic_racf.define("DATASET", "IBMUSER.IND.DATA", "IBMUSER", "NONE")
    state.datasets.allocate("IBMUSER", "IBMUSER.IND.DATA")
    state.datasets.write("IBMUSER", "IBMUSER.IND.DATA", "download")
    state.dynamic_racf.permit("DATASET", "IBMUSER.IND.DATA", "STUDENT", "READ")
    from gibson.core.transfers import get_transfer_manager
    mgr = get_transfer_manager(state)
    name, data = mgr.indfile_get("TEMPUSR", "IBMUSER.IND.DATA", note="pytest")
    assert data == b"download"
    try:
        mgr.indfile_put("TEMPUSR", "IBMUSER.IND.DATA", b"bad", note="pytest")
        assert False, "READ-only IND$FILE PUT should fail"
    except PermissionError:
        pass
    assert "DELETED" in state.dynamic_racf.revoke("DATASET", "IBMUSER.IND.DATA", "STUDENT")
    assert "REFRESH COMPLETE" in state.dynamic_racf.setropts("SETROPTS RACLIST(DATASET) REFRESH")
    state.dynamic_racf.cleanup_deleted_user("TEMPUSR")
    state.racf.deleteuser("TEMPUSR")
    assert not state.racf.exists("TEMPUSR")
    staged = mgr.write_local("upload.txt", b"upload")
    assert staged.exists()
    info = mgr.indfile_put("IBMUSER", "IBMUSER.NEW.UPLOAD", mgr.read_local("upload.txt"), note="pytest")
    assert info["target"] == "IBMUSER.NEW.UPLOAD"
    try:
        mgr.read_local("../../etc/passwd")
        assert False, "path traversal should fail"
    except ValueError:
        pass
