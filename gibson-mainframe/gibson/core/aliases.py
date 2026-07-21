from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
import json

DEFAULT_ALIASES = {
    "LU": "LISTUSER",
    "LG": "LISTGRP",
    "SD": "LISTDSD",
    "RL": "RLIST",
    "SE": "SETROPTS",
    "SR": "SEARCH",
    "X": "EXIT",
    "S": "SDSF",
}

@dataclass
class AliasRegistry:
    aliases: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ALIASES))
    path: Optional[Path] = None

    @classmethod
    def load(cls, path: Path) -> "AliasRegistry":
        reg = cls(path=path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    reg.aliases[k.upper()] = str(v)
            except Exception:
                pass
        return reg

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.aliases, indent=2, sort_keys=True), encoding="utf-8")

    def expand(self, command: str) -> str:
        raw = command.strip()
        if not raw:
            return raw
        first, *rest = raw.split(maxsplit=1)
        alias = self.aliases.get(first.upper())
        if not alias:
            return raw
        return alias + ((" " + rest[0]) if rest else "")

    def command(self, cmd: str) -> Optional[str]:
        parts = cmd.strip().split(maxsplit=2)
        if not parts or parts[0].upper() != "ALIAS":
            return None
        if len(parts) == 1 or (len(parts) >= 2 and parts[1].upper() in ("LIST", "L")):
            lines = ["GIBSON COMMAND ALIASES", "ALIAS    EXPANDS TO", "------   ----------------------------------------"]
            for k in sorted(self.aliases):
                lines.append(f"{k:<8} {self.aliases[k]}")
            return "\n".join(lines)
        if len(parts) >= 3 and parts[1].upper() in ("DELETE", "DEL"):
            key = parts[2].strip().upper()
            if key in self.aliases:
                del self.aliases[key]
                self.save()
                return f"ALIAS {key} DELETED"
            return f"ALIAS {key} NOT FOUND"
        if len(parts) >= 3:
            self.aliases[parts[1].upper()] = parts[2].strip().strip('"')
            self.save()
            return f"ALIAS {parts[1].upper()} DEFINED"
        return "USAGE: ALIAS LIST | ALIAS name expansion | ALIAS DELETE name"
