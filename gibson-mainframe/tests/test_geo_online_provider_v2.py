from pathlib import Path
import tempfile

from gibson.core.config import GibsonConfig
from gibson.core.geo.providers import FallbackGeoProvider, FixtureGeoProvider, FreeIpApiGeoProvider
from gibson.core.state import GibsonState


def test_unknown_public_ip_uses_online_provider_when_enabled_and_normalises():
    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "cityName": "Seattle",
                "regionName": "Washington",
                "countryName": "United States",
                "countryCode": "US",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "asn": "AS8075",
                "organization": "Microsoft Corporation",
                "timeZone": "America/Los_Angeles",
            }
    class Session:
        def __init__(self):
            self.calls = []
        def get(self, url, timeout):
            self.calls.append((url, timeout))
            return Resp()
    sess = Session()
    provider = FallbackGeoProvider(FixtureGeoProvider(), FreeIpApiGeoProvider(session=sess, timeout=2), online_enabled=True)
    result = provider.lookup("4.180.9.36")
    assert result.city == "Seattle"
    assert result.country_code == "US"
    assert result.latitude == 47.6062
    assert result.source == "freeipapi"
    assert len(sess.calls) == 1
    assert "4.180.9.36" in sess.calls[0][0]


def test_unknown_public_ip_stays_unknown_when_online_disabled():
    provider = FallbackGeoProvider(FixtureGeoProvider(), online=None, online_enabled=False)
    result = provider.lookup("4.180.9.36")
    assert result.classification == "public"
    assert result.confidence == "unavailable"
    assert result.latitude is None


def test_private_and_home_addresses_never_call_online_provider():
    class Session:
        calls = []
        def get(self, url, timeout):
            self.calls.append((url, timeout))
            raise AssertionError("private IP must not be sent to online provider")
    provider = FallbackGeoProvider(FixtureGeoProvider(), FreeIpApiGeoProvider(session=Session(), timeout=2), online_enabled=True)
    home = provider.lookup("192.168.0.97")
    assert home.city == "Livingston"
    assert home.source == "local-override"
    private = provider.lookup("10.1.2.3")
    assert private.classification == "private"
    assert private.source == "local-classifier"


def test_state_default_enables_online_provider_and_cache_can_resolve_mocked_unknown(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"cityName": "Paris", "countryName": "France", "countryCode": "FR", "latitude": 48.8566, "longitude": 2.3522, "organization": "Fixture ISP"}
    calls = []
    def fake_get(url, timeout):
        calls.append((url, timeout))
        return Resp()
    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root)
    cfg.files_root = root / "f"; cfg.commands_dir = cfg.files_root / "commands"; cfg.transfer_root = root / "transfers"; cfg.gacf_path = root / "GACF.DB"
    # Defaults should now permit public-IP FreeIPAPI fallback. The request is mocked.
    state = GibsonState.create(cfg)
    event = state.record_geo_connection("4.180.9.36", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    assert event["geo"]["city"] == "Paris"
    assert event["geo"]["country_code"] == "FR"
    assert event["geo"]["source"] == "freeipapi"
    # Cache prevents a second outbound provider hit for the same IP.
    state.record_geo_connection("4.180.9.36", port=2023, service="TN3270", userid="IBMUSER", action="LOGON")
    assert len(calls) == 1
