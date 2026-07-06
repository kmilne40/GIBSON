from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class IOC:
    value: str
    type: str = "ip"
    tags: tuple[str, ...] = ()
    severity: str = "INFO"
    confidence: int = 50
    source: str = "local-fixture"
    description: str = ""
    expires: str = ""
    allowlist: bool = False

    def to_dict(self) -> dict[str, object]:
        d = asdict(self); d["tags"] = list(self.tags); return d

@dataclass(frozen=True)
class CTIMatch:
    matched: bool
    severity: str = "INFO"
    tags: tuple[str, ...] = ()
    confidence: int = 0
    source: str = ""
    description: str = ""
    ioc: str = ""

    def to_dict(self) -> dict[str, object]:
        d = asdict(self); d["tags"] = list(self.tags); return d
