from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import traceback


def is_expected_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
        return True
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    if isinstance(exc, AttributeError) and "settimeout" in text:
        return True
    return name in {"clientdisconnected"} or any(token in text or token in name for token in (
        "broken pipe",
        "connection reset",
        "connection aborted",
        "client disconnected",
        "connection closed",
        "transport endpoint is not connected",
    ))


@dataclass
class IssueLog:
    path: Path

    def _append(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(text)

    def record(self, service: str, addr: tuple[str, int] | tuple | str, exc: BaseException, *, detail: str = "") -> None:
        if is_expected_disconnect(exc):
            return
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(addr, tuple):
            addr_text = f"{addr[0]}:{addr[1]}" if len(addr) >= 2 else ":".join(str(x) for x in addr)
        else:
            addr_text = str(addr)
        header = f"[{stamp}] SERVICE={service} ADDR={addr_text} EXC={type(exc).__name__}: {exc}\n"
        body = detail.rstrip("\n") + "\n" if detail else ""
        self._append(header + body + "-" * 80 + "\n")

    def record_traceback(self, service: str, addr: tuple[str, int] | tuple | str, exc: BaseException) -> None:
        self.record(service, addr, exc, detail=traceback.format_exc())
