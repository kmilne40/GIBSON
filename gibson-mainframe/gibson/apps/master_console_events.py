from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable, Optional


@dataclass(frozen=True)
class ConsoleEvent:
    event_id: str
    timestamp: str
    source: str
    severity: str
    category: str
    smf_type: str
    message_id: str
    message: str
    raw: str
    dedupe_key: str


def _mask(text: str) -> str:
    # Avoid rendering obvious secrets if a future event source includes them.
    s = str(text or "")
    s = re.sub(r"(?i)(PASSWORD|PASS|TOKEN|KEY|SECRET)=([^\s\]]+)", r"\1=MASKED", s)
    s = re.sub(r"(?i)(PASSWORD|PASSTICKET|TOKEN)\s+['\"]?[^\s,'\"]+", r"\1 MASKED", s)
    return s


def _kv(extra_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in re.findall(r"([A-Z0-9_]+)=([^\]\s]+)", extra_text or ""):
        out[key.upper()] = val
    return out


def _severity(component: str, command: str, result: str, extra: dict[str, str]) -> str:
    text = f"{component} {command} {result} {' '.join(extra.values())}".upper()
    if any(x in text for x in ("DENIED", "FAIL", "REVOKED", "VIOL", "ALERT", "UNKNOWN_HIGH_PORT", "PORT SCAN", "HIGH PORT", "INSUFFICIENT")):
        return "ALERT"
    if any(x in text for x in ("WARN", "WARNING", "KEYMASKED", "BROAD")):
        return "WARNING"
    if component.upper() in {"SMF30", "SMF80"}:
        return "INFO"
    return "EVENT"


def _msg_id(component: str, command: str, result: str, extra: dict[str, str]) -> str:
    mid = extra.get("MESSAGE_ID", "")
    if mid:
        return mid
    event = extra.get("EVENT", "").upper()
    text = f"{command} {result}".upper()
    if component.upper() == "SMF30":
        return "SMF030I"
    if "UNKNOWN_HIGH_PORT" in event or "HIGH PORT" in text:
        return "GIBW4001I"
    if "PORT_SCAN" in event or "PORT SCAN" in text:
        return "GIBS8001I"
    if event == "LOGON" and "SUCCESS" in text:
        return "ICH70001I"
    if event == "LOGON":
        return "ICH70002I"
    if component.upper() == "SMF80":
        return "SMF080I"
    return "IEE600I"


def _format_audit_message(component: str, userid: str, command: str, result: str, extra: dict[str, str]) -> tuple[str, str, str]:
    comp = component.upper()
    event = extra.get("EVENT", command.replace("SMF TYPE 80 ", "").replace("SMF TYPE 30 ", "")).upper()
    service = extra.get("SERVICE", extra.get("APPL", ""))
    addr = extra.get("ADDR", "")
    detail = extra.get("DETAIL", result)
    mid = _msg_id(comp, command, result, extra)
    if comp == "SMF30":
        if "SESSION END" in event:
            msg = f"{mid} SESSION END USER({userid}) APPL({service or 'TSO'})"
        elif "JOB" in event:
            msg = f"{mid} JOB ACTIVITY USER({userid}) {detail}"
        else:
            msg = f"{mid} SESSION START USER({userid}) APPL({service or 'TSO'})"
        if addr:
            msg += f" FROM {addr}"
        return mid, event or "SMF30", msg
    if "UNKNOWN_HIGH_PORT" in event or "UNKNOWN HIGH PORT" in event or "HIGH PORT" in command.upper():
        port = extra.get("RESOURCE", extra.get("PORT", ""))
        msg = f"{mid} UNKNOWN HIGH PORT {port or detail} OBSERVED"
        if addr:
            msg += f" FROM {addr}"
        return mid, "HIGH_PORT", msg
    if "PORT_SCAN" in event or "PORT SCAN" in command.upper():
        msg = f"{mid} PORT SCAN DETECTED"
        if addr:
            msg += f" FROM {addr}"
        if detail:
            msg += f" {detail}"
        return mid, "PORT_SCAN", msg
    if event == "LOGON" and extra.get("RESULT", result).upper().startswith("SUCCESS"):
        msg = f"{mid} USER {userid} LOGGED ON TO {service or 'TSO'}"
        if addr:
            msg += f" FROM {addr}"
        return mid, "LOGON", msg
    if event == "LOGON":
        msg = f"{mid} USER {userid} LOGON FAILED FOR {service or 'TSO'}"
        if addr:
            msg += f" FROM {addr}"
        if detail:
            msg += f" DETAIL({detail})"
        return mid, "LOGON", msg
    if comp == "SMF80":
        resource = extra.get("RESOURCE", "")
        result_word = extra.get("RESULT", result.split()[0] if result else "")
        msg = f"{mid} SECURITY EVENT USER({userid}) EVENT({event}) RESULT({result_word})"
        if resource:
            msg += f" RESOURCE({resource})"
        if detail:
            msg += f" DETAIL({detail})"
        return mid, event or "SMF80", msg
    return mid, comp or "OPERLOG", f"{mid} {_mask(result or command)}".strip()


def normalize_audit_line(line: str, seq: int) -> Optional[ConsoleEvent]:
    raw = (line or "").rstrip("\n")
    if not raw.strip():
        return None
    # 2026-05-18T12:00:00.123456 SMF80 IBMUSER: SMF TYPE 80 LOGON => SUCCESS ... [K=V]
    m = re.match(r"^(\S+)\s+(\S+)\s+([^:]+):\s+(.*?)\s+=>\s+(.*?)(?:\s+\[(.*)\])?$", raw)
    if not m:
        return normalize_operlog_line(raw, seq)
    ts, comp, userid, cmd, result, extra_text = m.groups()
    extra = _kv(extra_text or "")
    comp_u = comp.upper()
    mid, category, message = _format_audit_message(comp_u, userid.strip().upper(), cmd, result, extra)
    sev = _severity(comp_u, cmd, result, extra)
    safe_msg = _mask(message)
    key = f"audit:{ts}:{comp_u}:{userid}:{cmd}:{result}:{extra.get('EVENT','')}"
    return ConsoleEvent(
        event_id=f"AUD-{seq}", timestamp=ts, source="AUDIT", severity=sev,
        category=category, smf_type="80" if comp_u == "SMF80" else ("30" if comp_u == "SMF30" else ""),
        message_id=mid, message=safe_msg, raw=_mask(raw), dedupe_key=key,
    )


def normalize_operlog_line(line: str, seq: int) -> Optional[ConsoleEvent]:
    raw = (line or "").rstrip("\n")
    if not raw.strip():
        return None
    m = re.match(r"^(\d\d:\d\d:\d\d)\s+(.*)$", raw)
    ts = m.group(1) if m else datetime.now().isoformat(timespec="seconds")
    text = m.group(2) if m else raw
    upper = text.upper()
    sev = "ALERT" if any(x in upper for x in ("ICH408", "ICH70002", "ICH70004", "GIBW4001", "GIBS8001", "DENIED", "FAILED", "UNKNOWN HIGH PORT", "PORT SCAN")) else ("WARNING" if "WARN" in upper else "INFO")
    mid_match = re.match(r"^([A-Z]{3,5}\d{3,5}[A-Z]?)\s+", upper)
    mid = mid_match.group(1) if mid_match else "IEE600I"
    cat = "HIGH_PORT" if "HIGH PORT" in upper else ("PORT_SCAN" if "PORT SCAN" in upper else ("LOGON" if "LOGON" in upper else "OPERLOG"))
    safe = _mask(text)
    return ConsoleEvent(
        event_id=f"OPR-{seq}", timestamp=ts, source="OPERLOG", severity=sev,
        category=cat, smf_type="", message_id=mid, message=safe, raw=_mask(raw),
        dedupe_key=f"oper:{ts}:{safe}",
    )


class _TailState:
    def __init__(self) -> None:
        self.offset = 0
        self.inode: Optional[int] = None


class MasterConsoleEventPoller:
    """File-backed event adapter for the local master console.

    The services normally run in a separate process from the curses master
    console.  In-memory console_events are therefore not sufficient.  This
    poller tails the shared simulator audit/OPERLOG files under ~/mfsim and
    normalizes SMF80, SMF30, high-port, logon and ordinary OPERLOG messages
    into ConsoleEvent objects.
    """

    def __init__(self, state, *, include_existing: bool = True, max_initial_lines: int = 200) -> None:
        self.state = state
        cfg = getattr(state, "config", None)
        sim_root = Path(getattr(cfg, "sim_root", Path("~/mfsim").expanduser()))
        self.audit_path = sim_root / "audit.log"
        self.operlog_path = sim_root / "logs" / "OPERLOG.log"
        self._states = {"audit": _TailState(), "operlog": _TailState()}
        self._seen: set[str] = set()
        self._seq = 0
        if include_existing:
            self._prime_existing(max_initial_lines)
        else:
            for name, path in (("audit", self.audit_path), ("operlog", self.operlog_path)):
                self._seek_end(name, path)

    def _prime_existing(self, max_lines: int) -> None:
        # Mark old lines as unseen but start with offsets at EOF after returning
        # the initial tail on first poll via _initial buffer.
        self._initial: list[ConsoleEvent] = []
        for name, path in (("audit", self.audit_path), ("operlog", self.operlog_path)):
            lines = self._read_last(path, max_lines)
            for line in lines:
                ev = self._normalize(name, line)
                if ev and ev.dedupe_key not in self._seen:
                    self._seen.add(ev.dedupe_key)
                    self._initial.append(ev)
            self._seek_end(name, path)

    def _read_last(self, path: Path, max_lines: int) -> list[str]:
        try:
            if not path.exists():
                return []
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                return fh.readlines()[-max_lines:]
        except OSError:
            return []

    def _seek_end(self, name: str, path: Path) -> None:
        st = self._states[name]
        try:
            stat = path.stat()
            st.inode = getattr(stat, "st_ino", None)
            st.offset = stat.st_size
        except OSError:
            st.offset = 0
            st.inode = None

    def _read_new(self, name: str, path: Path) -> list[str]:
        st = self._states[name]
        try:
            stat = path.stat()
        except OSError:
            st.offset = 0
            st.inode = None
            return []
        inode = getattr(stat, "st_ino", None)
        if st.inode is not None and inode != st.inode:
            st.offset = 0
        if stat.st_size < st.offset:
            st.offset = 0
        st.inode = inode
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(st.offset)
                lines = fh.readlines()
                st.offset = fh.tell()
            return lines
        except OSError:
            return []

    def _normalize(self, name: str, line: str) -> Optional[ConsoleEvent]:
        self._seq += 1
        if name == "audit":
            return normalize_audit_line(line, self._seq)
        return normalize_operlog_line(line, self._seq)

    def poll(self) -> list[ConsoleEvent]:
        events: list[ConsoleEvent] = []
        initial = getattr(self, "_initial", None)
        if initial is not None:
            events.extend(initial)
            self._initial = []
        for name, path in (("audit", self.audit_path), ("operlog", self.operlog_path)):
            for line in self._read_new(name, path):
                ev = self._normalize(name, line)
                if not ev:
                    continue
                if ev.dedupe_key in self._seen:
                    continue
                self._seen.add(ev.dedupe_key)
                events.append(ev)
        return events
