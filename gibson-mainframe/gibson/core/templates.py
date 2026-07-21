from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import socket

class TemplateRegistry:
    def __init__(self, *roots: Path):
        self.roots = [Path(r) for r in roots if r]

    def _norm(self, value: str) -> str:
        # Match operator commands to command-template filenames even when the
        # file uses underscores, spaces, mixed case, or punctuation.
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

    def find(self, name: str) -> Optional[Path]:
        raw = str(name).strip()
        candidates = [
            raw,
            raw.upper(),
            raw.lower(),
            raw.replace(" ", "_"),
            raw.replace("_", " "),
        ]
        for root in self.roots:
            for c in candidates:
                p = root / c
                if p.exists() and p.is_file():
                    return p

        wanted = self._norm(raw)
        if not wanted:
            return None
        for root in self.roots:
            if not root.exists() or not root.is_dir():
                continue
            try:
                for p in root.iterdir():
                    if p.is_file() and self._norm(p.name) == wanted:
                        return p
            except Exception:
                continue
        return None

    def render(self, name: str, userid: str = "IBMUSER", attrib: str = "NONE", extra: Optional[Dict[str, str]] = None) -> Optional[str]:
        p = self.find(name)
        if not p:
            return None
        text = p.read_text(encoding="utf-8", errors="ignore")
        now = datetime.now()
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
        repl = {
            "xxxxxxx": userid,
            "xxxxxx": userid,
            "ATTRIB": attrib,
            "T1ME": now.strftime("%H:%M:%S"),
            "TIME": now.strftime("%H:%M:%S"),
            "D4TE": now.strftime("%Y-%m-%d"),
            "DATE": now.strftime("%Y-%m-%d"),
            "xxx.xxx.xxx.xxx": ip,
        }
        if extra:
            repl.update(extra)
        for k, v in repl.items():
            text = text.replace(k, str(v))
        return text
