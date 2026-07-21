from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.screens.vtam_model import VtamScreenModel
from gibson.apps.welcome.routes import render_page, is_welcome_route


def state():
    return GibsonState.create(GibsonConfig())


def test_r05_hostname_renders_live_vtam_not_static_gibson():
    s = state()
    s.set_system_hostname("BANKSYS1")
    lines = VtamScreenModel.from_addr(("127.0.0.1", 12345), system_name=s.network.hostname).full_lines()
    text = "\n".join(lines)
    assert "BANKSYS1 PRODUCTION LPAR" in text
    assert "GIBSON PRODUCTION LPAR" not in text
    assert len(lines) <= 24
    assert max(len(line) for line in lines) <= 80


def test_dns_fixture_ping_and_tracerte_resolution():
    s = state()
    assert "PING example.com (93.184.216.34)" in s.network.ping("example.com")
    assert "EZZ3210I Unknown host bad.invalid" in s.network.ping("bad.invalid")
    tr = s.network.traceroute("example.com")
    assert "example.com (93.184.216.34)" in tr
    assert "EZZ3115I Trace complete" in tr


def test_geo_master_console_alert_is_enriched():
    s = state()
    s.record_geo_connection("203.0.113.10", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    message = s.recent_dashboard_alerts()[-1]["message"]
    assert "USER(IBMUSER)" in message
    assert "CITY(Berlin)" in message
    assert "COUNTRY(DE)" in message
    assert "SMF(GEO-" in message


def test_dashboard_snapshot_uses_geo_events_markers():
    from gibson.services.dashboard import _DashboardHandler
    s = state()
    s.record_geo_connection("198.51.100.66", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    _DashboardHandler.state = s
    snap = _DashboardHandler._snapshot(_DashboardHandler)
    coords = snap["coords"]
    assert coords
    assert any(c[2] == "198.51.100.66" and c[4] == "red" for c in coords)


def test_cti_routes_are_rich_and_sidebar_driven():
    s = state()
    s.record_geo_connection("198.51.100.66", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    for route in ["/cti/dashboard", "/cti/feed", "/cti/ioc-search", "/cti/threat-actors", "/cti/c2-tracker", "/cti/investigations", "/cti/reports", "/cti/settings", "/cti/documentation"]:
        assert is_welcome_route(route)
        code, ctype, body = render_page(route, s)
        assert code == 200
        assert "GIBSON SENTRY" in body
    code, _, body = render_page("/cti/dashboard", s)
    assert "Threat Dashboard" in body
    assert "IOC Severity Distribution" in body
    assert "Active Investigations" in body
    assert "Tracked Threat Actors" in body
    code, _, settings = render_page("/cti/settings", s)
    assert "API key" in settings or "API-key" in settings
    assert "Disabled by default" in settings
