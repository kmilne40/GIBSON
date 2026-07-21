from __future__ import annotations
import ipaddress
from .ioc_store import IOCStore
from .model import CTIMatch

_SEV_RANK = {"INFO":0,"YELLOW":1,"ORANGE":2,"RED":3,"CRITICAL":4}

def max_severity(a: str, b: str) -> str:
    au=(a or "INFO").upper(); bu=(b or "INFO").upper()
    return au if _SEV_RANK.get(au,0) >= _SEV_RANK.get(bu,0) else bu

class CTIMatcher:
    def __init__(self, store: IOCStore | None = None):
        self.store = store or IOCStore.seeded()

    def match_ip(self, ip: str) -> CTIMatch:
        tags: set[str] = set(); severity="INFO"; confidence=0; source=""; desc=[]; ioc_value=""
        try:
            obj = ipaddress.ip_address(str(ip))
        except Exception:
            return CTIMatch(False)
        for ioc in self.store.iocs:
            if ioc.allowlist:
                continue
            matched=False
            try:
                if ioc.type.lower() == "cidr":
                    matched = obj in ipaddress.ip_network(ioc.value, strict=False)
                elif ioc.type.lower() == "ip":
                    matched = obj == ipaddress.ip_address(ioc.value)
            except Exception:
                matched=False
            if matched:
                tags.update(t.upper() for t in ioc.tags)
                severity = max_severity(severity, ioc.severity)
                confidence = max(confidence, int(ioc.confidence))
                source = source or ioc.source
                ioc_value = ioc_value or ioc.value
                if ioc.description: desc.append(ioc.description)
        return CTIMatch(bool(tags), severity=severity, tags=tuple(sorted(tags)), confidence=confidence, source=source, description="; ".join(desc), ioc=ioc_value)
