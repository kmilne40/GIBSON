from __future__ import annotations
from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.master_console import MasterConsoleController
from gibson.screens.vtam_model import VtamScreenModel
from gibson.apps.welcome import render_page


def make_state() -> GibsonState:
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root)
    cfg.files_root = root / "f"; cfg.commands_dir = cfg.files_root / "commands"; cfg.transfer_root = root / "transfers"; cfg.gacf_path = root / "GACF.DB"
    return GibsonState.create(cfg)


def test_r05_sets_hostname_and_vtam_logo():
    state = make_state()
    ctl = MasterConsoleController(state)
    for cmd in ["R 01,CLPA", "R 02,U", "R 03,Y", "R 04,1337"]:
        ctl.execute(cmd)
    out = ctl.execute("R 05,BANKSYS1").text
    assert "HOSTNAME BANKSYS1 ACCEPTED" in out
    # Current IPL flow requires R 06 to set/skip DVCAPIN before boot completion.
    assert ctl._state_obj()["boot_complete"] is False
    ctl.execute("R 06,1337")
    assert ctl._state_obj()["boot_complete"] is True
    assert state.network.hostname == "BANKSYS1"
    lines = VtamScreenModel.from_addr(("127.0.0.1", 12345), system_name=state.network.hostname).full_lines()
    joined = "\n".join(lines)
    assert "BANKSYS1 PRODUCTION LPAR" in joined
    assert "GIBSON PRODUCTION LPAR" not in joined
    assert all(len(line) <= 132 for line in lines)
    assert len([line for line in lines if line.strip()]) <= 24


def test_r05_rejects_invalid_hostname():
    state = make_state(); ctl = MasterConsoleController(state)
    for cmd in ["R 01,CLPA", "R 02,U", "R 03,Y", "R 04,1337"]:
        ctl.execute(cmd)
    out = ctl.execute("R 05,BAD.NAME!").text
    assert "INVALID HOSTNAME" in out
    assert ctl._state_obj()["boot_complete"] is False


def test_hostname_propagates_to_netstat_and_aliases():
    state = make_state(); state.set_system_hostname("BANKSYS1")
    assert state.network.display_ip_for("BANKSYS1") == "127.0.0.1"
    assert state.network.display_ip_for("mainframe") == "127.0.0.1"
    home = state.network.format("HOME")
    assert "BANKSYS1" in home
    assert "127.0.0.1" in home


def test_geo_cti_severity_rules_and_alerts():
    state = make_state()
    us = state.record_geo_connection("8.8.8.8", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    de = state.record_geo_connection("203.0.113.10", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    ru = state.record_geo_connection("5.188.10.10", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    c2 = state.record_geo_connection("198.51.100.66", port=8080, service="TOMCAT", userid="TOMCAT", action="CONNECTION")
    local = state.record_geo_connection("127.0.0.1", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    assert us["marker_colour"] == "orange"
    assert de["marker_colour"] == "orange"
    assert ru["marker_colour"] == "red"
    assert c2["marker_colour"] == "red"
    assert local["marker_colour"] == "neutral"
    assert any("GIBGEO080W" in a["message"] or "GIBCTI119A" in a["message"] for a in state.dashboard_alerts)
    assert any(e.component == "SMF119" for e in state.audit.events)


def test_welcome80_cti_routes_render():
    state = make_state(); state.record_geo_connection("198.51.100.66", port=8080, service="TOMCAT", userid="TOMCAT")
    for route in ["/cti", "/cti/dashboard", "/cti/events", "/cti/iocs", "/cti/research?ip=198.51.100.66", "/cti/stats", "/cti/feeds", "/cti/export", "/cti/help"]:
        code, ctype, body = render_page(route, state=state)
        assert code == 200
        assert "TFTP" not in body.upper()
        assert "CTI" in body.upper() or route == "/cti/export"
