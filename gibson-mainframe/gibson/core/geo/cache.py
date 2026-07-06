from __future__ import annotations
from .model import GeoResult

class GeoCache:
    def __init__(self):
        self._items: dict[str, GeoResult] = {}
    def get(self, ip: str) -> GeoResult | None:
        return self._items.get(str(ip))
    def set(self, ip: str, result: GeoResult) -> GeoResult:
        self._items[str(ip)] = result
        return result
    def rows(self) -> list[dict[str, object]]:
        return [v.to_dict() for v in self._items.values()]
