from __future__ import annotations
from .model import GeoResult, now_iso, expiry_iso
from .ip_classifier import classify_ip

# Offline lab fixtures. These are explicit fixtures, not fake production geo.
GEO_FIXTURES: dict[str, dict[str, object]] = {
    # User-observed public source from the Gibson dashboard. The fixture is
    # intentionally labelled best-effort/offline: it gives Gibson a stable
    # city-level marker even when the online provider is unavailable.
    "4.180.9.35": {"city":"London", "region":"England", "country":"United Kingdom", "country_code":"GB", "continent":"Europe", "latitude":51.507, "longitude":-0.128, "asn":"AS8075", "org":"Microsoft Corporation", "timezone":"Europe/London", "confidence":"best-effort-fixture", "source":"offline-fixture-best-effort"},
    "8.8.8.8": {"city":"Mountain View", "region":"California", "country":"United States", "country_code":"US", "continent":"North America", "latitude":37.386, "longitude":-122.084, "asn":"AS15169", "org":"Google LLC", "timezone":"America/Los_Angeles"},
    "203.0.113.10": {"city":"Berlin", "region":"Berlin", "country":"Germany", "country_code":"DE", "continent":"Europe", "latitude":52.520, "longitude":13.405, "asn":"AS64500", "org":"Gibson Fixture ISP", "timezone":"Europe/Berlin"},
    "198.51.100.25": {"city":"New York", "region":"New York", "country":"United States", "country_code":"US", "continent":"North America", "latitude":40.713, "longitude":-74.006, "asn":"AS64501", "org":"Gibson Fixture ISP", "timezone":"America/New_York"},
    "198.51.100.66": {"city":"Amsterdam", "region":"North Holland", "country":"Netherlands", "country_code":"NL", "continent":"Europe", "latitude":52.367, "longitude":4.904, "asn":"AS64566", "org":"Fixture C2 Hosting", "timezone":"Europe/Amsterdam"},
    "5.188.10.10": {"city":"Moscow", "region":"Moscow", "country":"Russia", "country_code":"RU", "continent":"Europe", "latitude":55.755, "longitude":37.617, "asn":"AS64510", "org":"Fixture RU Net", "timezone":"Europe/Moscow"},
    "2.176.1.1": {"city":"Tehran", "region":"Tehran", "country":"Iran", "country_code":"IR", "continent":"Asia", "latitude":35.689, "longitude":51.389, "asn":"AS64520", "org":"Fixture IR Net", "timezone":"Asia/Tehran"},
    "1.2.3.4": {"city":"Beijing", "region":"Beijing", "country":"China", "country_code":"CN", "continent":"Asia", "latitude":39.904, "longitude":116.407, "asn":"AS64530", "org":"Fixture CN Net", "timezone":"Asia/Shanghai"},
}

_LOCAL_CLASSIFICATIONS = {"localhost", "private", "link-local", "cgnat", "reserved", "multicast", "invalid"}


def _unknown_result(ip_s: str, hostname: str = "", *, source: str = "offline-fixture", confidence: str = "unavailable", classification: str | None = None) -> GeoResult:
    return GeoResult(ip=ip_s, hostname=hostname, source=source, confidence=confidence, classification=classification or classify_ip(ip_s), lookup_time=now_iso(), cache_expiry=expiry_iso())


class FixtureGeoProvider:
    source = "offline-fixture"

    def lookup(self, ip: str, hostname: str = "") -> GeoResult:
        classification = classify_ip(ip)
        ip_s = str(ip or "")
        # User-requested home/LAN override. RFC1918 addresses cannot be
        # publicly geolocated, so this stays local and never reaches an online
        # provider. Coordinates are city-level approximate only.
        if ip_s.startswith("192.168.0."):
            return GeoResult(
                ip=ip_s, hostname=hostname, city="Livingston", region="West Lothian",
                country="United Kingdom", country_code="GB", continent="Europe",
                latitude=55.884, longitude=-3.522, asn="LOCAL", org="Home / Gibson lab network",
                timezone="Europe/London", source="local-override", confidence="configured-local",
                classification="private_home_network", lookup_time=now_iso(), cache_expiry=expiry_iso(30),
            )
        data = GEO_FIXTURES.get(ip_s)
        if data:
            # Explicit offline fixtures are allowed to use TEST-NET ranges for
            # deterministic lab/research examples. They are labelled as fixtures.
            data = dict(data)
            source = str(data.pop("source", self.source))
            confidence = str(data.pop("confidence", "fixture"))
            return GeoResult(ip=ip_s, hostname=hostname, source=source, confidence=confidence, classification="fixture", lookup_time=now_iso(), cache_expiry=expiry_iso(), **data)
        if classification in _LOCAL_CLASSIFICATIONS:
            return GeoResult(ip=ip_s, hostname=hostname, city="Local/Lab", region="Gibson", country="Lab", country_code="LAB", continent="Local", latitude=None, longitude=None, source="local-classifier", confidence="lab", classification=classification, lookup_time=now_iso(), cache_expiry=expiry_iso())
        return _unknown_result(ip_s, hostname, source="offline-fixture", confidence="unavailable", classification=classification)


class FreeIpApiGeoProvider:
    """Optional online provider inspired by the uploaded geoloc.py tool.

    The provider sends only the public IP address to freeipapi.com. User IDs,
    service names and session metadata are never sent. Private, local and
    reserved addresses are returned via the local fixture/classifier path.
    """
    source = "freeipapi"

    def __init__(self, session=None, timeout: float = 10.0):
        self.session = session
        self.timeout = timeout

    def lookup(self, ip: str, hostname: str = "") -> GeoResult:
        import ipaddress
        ip_s = str(ip or "").strip()
        obj = ipaddress.ip_address(ip_s)
        # Never send local/private/lab addresses to the online provider.
        if obj.is_private or obj.is_loopback or obj.is_link_local or obj.is_reserved or obj.is_multicast:
            return FixtureGeoProvider().lookup(ip_s, hostname=hostname)
        import requests
        sess = self.session or requests
        resp = sess.get(f"https://freeipapi.com/api/json/{ip_s}", timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # freeipapi commonly returns cityName, regionName, countryName,
        # countryCode, latitude and longitude. Keep a few alternate keys for
        # compatibility with similar providers and older tests.
        lat = data.get("latitude") or data.get("lat")
        lon = data.get("longitude") or data.get("lon") or data.get("lng")
        city = str(data.get("cityName") or data.get("city") or "")
        country = str(data.get("countryName") or data.get("country") or "")
        country_code = str(data.get("countryCode") or data.get("country_code") or "")
        region = str(data.get("regionName") or data.get("region") or "")
        continent = str(data.get("continent") or data.get("continentName") or "")
        if not city and not country and lat is None and lon is None:
            return _unknown_result(ip_s, hostname, source=self.source, confidence="online-no-geo", classification=classify_ip(ip_s))
        return GeoResult(
            ip=ip_s, hostname=hostname, city=city, region=region,
            country=country, country_code=country_code,
            continent=continent,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            asn=str(data.get("asn") or data.get("asnOrg") or ""),
            org=str(data.get("organization") or data.get("org") or data.get("isp") or ""),
            timezone=str(data.get("timeZone") or data.get("timezone") or ""),
            source=self.source, confidence="online-provider", classification=classify_ip(ip_s),
            lookup_time=now_iso(), cache_expiry=expiry_iso(),
        )


class FallbackGeoProvider:
    """Fixture/cache first, optional online lookup second.

    Unknown public IPs remain unknown only when online lookup is disabled or the
    online provider fails/returns no geolocation. Local/private IPs are handled
    locally and are never sent to an online provider.
    """

    def __init__(self, fixture: FixtureGeoProvider | None = None, online: FreeIpApiGeoProvider | None = None, online_enabled: bool = False):
        self.fixture = fixture or FixtureGeoProvider()
        self.online = online
        self.online_enabled = bool(online_enabled)

    def lookup(self, ip: str, hostname: str = "") -> GeoResult:
        ip_s = str(ip or "").strip()
        first = self.fixture.lookup(ip_s, hostname=hostname)
        classification = first.classification or classify_ip(ip_s)
        if first.confidence != "unavailable" or classification in _LOCAL_CLASSIFICATIONS or classification == "private_home_network":
            return first
        if not self.online_enabled or self.online is None or classification != "public":
            return first
        try:
            result = self.online.lookup(ip_s, hostname=hostname)
            # If the provider had no useful lat/lon/country/city, keep an honest
            # unknown with a clear online failure reason.
            if result.latitude is None and result.longitude is None and not (result.city or result.country_code or result.country):
                return _unknown_result(ip_s, hostname, source="freeipapi", confidence="online-no-geo", classification=classification)
            return result
        except Exception as exc:
            return _unknown_result(ip_s, hostname, source="freeipapi", confidence=f"online-error:{exc.__class__.__name__}", classification=classification)
