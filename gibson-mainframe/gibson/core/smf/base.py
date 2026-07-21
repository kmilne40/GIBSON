from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
import json
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


@dataclass
class SmfHeader:
    record_type: int
    subtype: str = ""
    version: str = "GIBSON-1"
    system_id: str = "GIBSON"
    sysplex: str = "GIBPLEX"
    lpar: str = "GIB1"
    timestamp: str = field(default_factory=_now)
    record_id: str = field(default_factory=lambda: "SMF-" + uuid.uuid4().hex[:10].upper())

    def to_dict(self) -> Dict[str, str]:
        return {
            "record_id": self.record_id,
            "record_type": str(self.record_type),
            "subtype": self.subtype,
            "version": self.version,
            "timestamp": self.timestamp,
            "system_id": self.system_id,
            "sysplex": self.sysplex,
            "lpar": self.lpar,
        }


@dataclass
class SmfRecord:
    header: SmfHeader
    userid: str = "UNKNOWN"
    jobname: str = "GIBSON"
    subsystem: str = "SYSTEM"
    source_component: str = "GIBSON"
    correlation_id: str = ""
    summary: str = ""
    raw_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        data.update(self.header.to_dict())
        data.update({
            "userid": self.userid.upper(),
            "jobname": self.jobname.upper(),
            "subsystem": self.subsystem.upper(),
            "source_component": self.source_component.upper(),
            "correlation_id": self.correlation_id,
            "summary": self.summary,
            "raw_fields": {str(k).upper(): _safe(v) for k, v in self.raw_fields.items()},
        })
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def to_flat_fields(self) -> Dict[str, str]:
        d = self.to_dict()
        raw = d.pop("raw_fields", {}) or {}
        out = {str(k).upper(): _safe(v) for k, v in d.items()}
        for k, v in raw.items():
            out[str(k).upper()] = _safe(v)
        return out

    def to_summary_line(self) -> str:
        f = self.to_flat_fields()
        return (f"{f.get('RECORD_ID',''):<14} TYPE={f.get('RECORD_TYPE','')} "
                f"SUB={f.get('SUBTYPE','') or '-'} USER={f.get('USERID','')} "
                f"JOB={f.get('JOBNAME','')} RESULT={f.get('RESULT','')} "
                f"EVENT={f.get('EVENT_NAME', f.get('EVENT',''))} CORR={f.get('CORRELATION_ID','')}").rstrip()

    def to_detail_lines(self) -> List[str]:
        f = self.to_flat_fields()
        keys = [
            "RECORD_ID", "RECORD_TYPE", "SUBTYPE", "TIMESTAMP", "SYSTEM_ID",
            "SYSPLEX", "LPAR", "USERID", "JOBNAME", "SUBSYSTEM",
            "EVENT_NAME", "RESULT", "REASON_CODE", "CLASS_NAME",
            "RESOURCE_NAME", "PROFILE_NAME", "ACCESS_REQUESTED",
            "ACCESS_ALLOWED", "CORRELATION_ID", "SUMMARY",
        ]
        lines = [f"SMF TYPE {f.get('RECORD_TYPE','?')} STRUCTURED RECORD DETAIL", ""]
        seen = set()
        for k in keys:
            if f.get(k):
                lines.append(f"{k:<18}: {f[k]}")
                seen.add(k)
        extra = [k for k in sorted(f) if k not in seen and f.get(k)]
        if extra:
            lines.append("")
            lines.append("ADDITIONAL FIELDS:")
            for k in extra:
                lines.append(f"{k:<18}: {f[k]}")
        return lines

    def to_unload_row(self) -> str:
        f = self.to_flat_fields()
        keys = ["RECORD_ID","RECORD_TYPE","SUBTYPE","TIMESTAMP","SYSTEM_ID","USERID","JOBNAME","EVENT_NAME","RESULT","CLASS_NAME","RESOURCE_NAME","CORRELATION_ID"]
        return "|".join(_safe(f.get(k,"")) for k in keys)


def make_record(record_type: int, *, subtype: str = "", userid: str = "UNKNOWN", jobname: str = "GIBSON", subsystem: str = "SYSTEM", source_component: str = "GIBSON", correlation_id: str = "", summary: str = "", system_id: str = "GIBSON", raw_fields: Dict[str, Any] | None = None) -> SmfRecord:
    header = SmfHeader(record_type=record_type, subtype=subtype, system_id=system_id)
    return SmfRecord(header=header, userid=userid or "UNKNOWN", jobname=jobname or "GIBSON", subsystem=subsystem or "SYSTEM", source_component=source_component or "GIBSON", correlation_id=correlation_id or header.record_id, summary=summary or "", raw_fields=raw_fields or {})
