from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

@dataclass(frozen=True)
class GeoResult:
    ip: str
    hostname: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    country_code: str = ""
    continent: str = ""
    latitude: float | None = None
    longitude: float | None = None
    asn: str = ""
    org: str = ""
    timezone: str = ""
    source: str = "unknown"
    confidence: str = "unknown"
    accuracy_radius: str = ""
    classification: str = "unknown"
    lookup_time: str = ""
    cache_expiry: str = ""
    privacy: str = "city-level approximate"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def expiry_iso(days: int = 7) -> str:
    return (datetime.utcnow() + timedelta(days=days)).replace(microsecond=0).isoformat() + "Z"
