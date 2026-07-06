from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.master_console_events import MasterConsoleEventPoller, normalize_audit_line


def make_state(tmp_path: Path):
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", transfer_root=tmp_path / "transfers", gacf_path=tmp_path / "GACF.DB")
    return GibsonState.create(cfg)


def test_poller_handles_missing_and_empty_logs(tmp_path):
    state = make_state(tmp_path)
    p = MasterConsoleEventPoller(state, include_existing=False)
    assert p.poll() == []


def test_smf80_logon_success_reaches_poller(tmp_path):
    state = make_state(tmp_path)
    p = MasterConsoleEventPoller(state, include_existing=False)
    state.record_security_event("IBMUSER", "LOGON", "PASSWORD", service="VTAM/TSO", addr="10.0.2.15")
    events = p.poll()
    messages = "\n".join(e.message for e in events)
    assert "ICH70001I USER IBMUSER LOGGED ON" in messages
    assert any(e.smf_type == "80" and e.category == "LOGON" for e in events)
    assert any(e.smf_type == "30" for e in events)


def test_smf80_logon_failure_reaches_poller_as_alert(tmp_path):
    state = make_state(tmp_path)
    p = MasterConsoleEventPoller(state, include_existing=False)
    state.record_security_event("GUEST", "LOGON", "PASSWORD FAILURE", result="FAILURE", service="VTAM/TSO", addr="10.0.2.15")
    events = p.poll()
    assert any("LOGON FAILED" in e.message and e.severity == "ALERT" for e in events)


def test_unknown_high_port_reaches_poller_as_alert(tmp_path):
    state = make_state(tmp_path)
    p = MasterConsoleEventPoller(state, include_existing=False)
    state.register_open_port(40001, component="UNITTEST")
    events = p.poll()
    assert any(e.category == "HIGH_PORT" and e.severity == "ALERT" for e in events)
    assert any("UNKNOWN HIGH PORT" in e.message for e in events)


def test_known_high_port_does_not_emit_false_alert(tmp_path):
    state = make_state(tmp_path)
    state.allowed_high_ports.add(40001)
    p = MasterConsoleEventPoller(state, include_existing=False)
    state.register_open_port(40001, component="KNOWN")
    assert not [e for e in p.poll() if e.category == "HIGH_PORT"]


def test_poller_deduplicates_repeated_polls(tmp_path):
    state = make_state(tmp_path)
    p = MasterConsoleEventPoller(state, include_existing=False)
    state.record_security_event("IBMUSER", "LOGON", "PASSWORD", service="TSO")
    assert p.poll()
    assert p.poll() == []


def test_normalize_direct_smf30_line():
    line = "2026-05-18T10:00:00 SMF30 IBMUSER: SMF TYPE 30 SESSION START => SUCCESS SERVICE=TSO [EVENT=SESSION START SERVICE=TSO RESULT=SUCCESS]"
    ev = normalize_audit_line(line, 1)
    assert ev is not None
    assert ev.smf_type == "30"
    assert ev.message.startswith("SMF030I SESSION START")
