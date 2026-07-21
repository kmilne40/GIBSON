from __future__ import annotations
import ipaddress
from .model import IOC

class IOCStore:
    def __init__(self, iocs: list[IOC] | None = None):
        self.iocs = list(iocs or [])

    @classmethod
    def seeded(cls) -> "IOCStore":
        return cls([
            IOC("198.51.100.66", tags=("C2","BOTNET"), severity="RED", confidence=95, description="Gibson fixture C2/botnet host"),
            IOC("5.188.10.0/24", type="cidr", tags=("SCANNER","ABUSE"), severity="RED", confidence=80, description="Gibson fixture RU scanner net"),
            IOC("2.176.1.1", tags=("ABUSE",), severity="RED", confidence=70, description="Gibson fixture suspicious IR host"),
            IOC("1.2.3.4", tags=("BOTNET",), severity="RED", confidence=85, description="Gibson fixture suspicious CN host"),
        ])

    def rows(self) -> list[dict[str, object]]:
        return [ioc.to_dict() for ioc in self.iocs]
