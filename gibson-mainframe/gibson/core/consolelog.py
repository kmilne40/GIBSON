from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ConsoleLog:
    operlog_path: Path
    syslog_path: Path
    console_name: str = "CONS01"

    def _append(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)

    def record(self, text: str, include_syslog: bool = True) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        block = []
        for raw in (text or "").splitlines() or [""]:
            if raw.strip():
                block.append(f"{stamp} {raw}\n")
            else:
                block.append("\n")
        payload = "".join(block)
        self._append(self.operlog_path, payload)
        if include_syslog:
            self._append(self.syslog_path, payload)

    def command(self, cmd: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        entry = f"{stamp} {self.console_name}  {cmd}\n"
        self._append(self.operlog_path, entry)
        self._append(self.syslog_path, entry)
