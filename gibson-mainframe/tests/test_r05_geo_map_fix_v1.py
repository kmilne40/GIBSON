from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.master_console import MasterConsoleController
from gibson.net.vtam_frontend import coloured_ascii_vtam_screen, tn3270_vtam_screen
from gibson.services.dashboard import _DashboardHandler
from gibson.core.geo.providers import FreeIpApiGeoProvider


def make_state():
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root)
    cfg.files_root = root / "f"; cfg.commands_dir = cfg.files_root / "commands"; cfg.transfer_root = root / "transfers"; cfg.gacf_path = root / "GACF.DB"
    return GibsonState.create(cfg)


def test_r05_binky_reaches_live_ascii_and_3270_vtam_paths():
    s = make_state()
    ctl = MasterConsoleController(s)
    for cmd in ["R 01,CLPA", "R 02,U", "R 03,Y", "R 04,1234"]:
        ctl.execute(cmd)
    out = ctl.execute("R 05,BINKY").text
    assert "HOSTNAME BINKY ACCEPTED" in out
    assert s.get_system_hostname() == "BINKY"
    ascii_screen = coloured_ascii_vtam_screen(addr=("192.168.0.97", 12345), system_name=s.get_system_hostname())
    assert "BINKY PRODUCTION LPAR" in ascii_screen
    assert "GIBSON PRODUCTION LPAR" not in ascii_screen
    buf = tn3270_vtam_screen(addr=("192.168.0.97", 12345), system_name=s.get_system_hostname())
    text = buf.render_plain()
    assert "BINKY PRODUCTION LPAR" in text
    assert "GIBSON PRODUCTION LPAR" not in text
    assert buf.rows == 24 and buf.cols == 80


def test_geo_public_4_180_9_35_fixture_marker_and_alert_context():
    s = make_state()
    event = s.record_geo_connection("4.180.9.35", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    assert event["geo"]["city"]
    assert event["geo"]["country_code"] == "GB"
    assert event["geo"]["asn"] == "AS8075"
    assert event["geo"]["latitude"] is not None
    msg = s.recent_dashboard_alerts()[-1]["message"]
    assert "USER(IBMUSER)" in msg
    assert "CITY(" in msg and "COUNTRY(GB)" in msg
    assert "SMF(GEO-" in msg
    _DashboardHandler.state = s
    snap = _DashboardHandler._snapshot(_DashboardHandler)
    assert any(c[2] == "4.180.9.35" and c[0] is not None and c[1] is not None for c in snap["coords"])


def test_geo_home_network_livingston_override_no_external_warning():
    s = make_state()
    event = s.record_geo_connection("192.168.0.97", port=2023, service="TN3270", userid="GUEST", action="LOGON")
    geo = event["geo"]
    assert geo["city"] == "Livingston"
    assert geo["region"] == "West Lothian"
    assert geo["country_code"] == "GB"
    assert geo["classification"] == "private_home_network"
    assert geo["source"] == "local-override"
    assert event["marker_colour"] == "neutral"
    assert not any("EXTERNAL LOGON GEOLOCATED" in a["message"] and "192.168.0.97" in a["message"] for a in s.recent_dashboard_alerts())
    _DashboardHandler.state = s
    snap = _DashboardHandler._snapshot(_DashboardHandler)
    assert any(c[2] == "192.168.0.97" for c in snap["coords"])


def test_unknown_public_ip_has_no_fake_marker():
    s = make_state()
    event = s.record_geo_connection("9.9.9.9", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    assert str(event["geo"].get("confidence", "")).startswith(("unavailable", "online-error", "online-no-geo"))
    assert event["geo"].get("latitude") is None
    _DashboardHandler.state = s
    snap = _DashboardHandler._snapshot(_DashboardHandler)
    assert not any(c[2] == "9.9.9.9" for c in snap["coords"])


def test_freeipapi_provider_is_optional_and_normalises_schema_without_private_lookup():
    class Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"cityName":"Test City","regionName":"Test Region","countryName":"Testland","countryCode":"TS","latitude":1.25,"longitude":2.5,"asn":"AS64555","organization":"Example Org","timeZone":"UTC"}
    class Session:
        calls=[]
        def get(self, url, timeout):
            self.calls.append((url, timeout)); return Resp()
    sess = Session()
    provider = FreeIpApiGeoProvider(session=sess, timeout=3)
    result = provider.lookup("8.8.8.8")
    assert result.city == "Test City" and result.latitude == 1.25
    private = provider.lookup("192.168.0.97")
    assert private.city == "Livingston"
    assert len(sess.calls) == 1
