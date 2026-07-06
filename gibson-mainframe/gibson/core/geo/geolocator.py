from __future__ import annotations
from .cache import GeoCache
from .model import GeoResult
from .providers import FixtureGeoProvider

class Geolocator:
    def __init__(self, provider=None, cache: GeoCache | None = None):
        self.provider = provider or FixtureGeoProvider()
        self.cache = cache or GeoCache()
    def lookup(self, ip: str, hostname: str = "") -> GeoResult:
        cached = self.cache.get(ip)
        if cached:
            return cached
        return self.cache.set(ip, self.provider.lookup(ip, hostname))
