from __future__ import annotations

from dataclasses import dataclass

@dataclass
class IndFileRecord:
    direction: str
    userid: str
    dataset: str
    local: str
    mode: str = "ASCII"
    bytes_count: int = 0
    result: str = "SUCCESS"
    correlation_id: str = ""
