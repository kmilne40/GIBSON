from __future__ import annotations

from typing import Any, Iterable, List
from .base import SmfRecord, make_record


class SmfWriter:
    def __init__(self, state: Any):
        self.state = state
        if not hasattr(state, "smf_records"):
            setattr(state, "smf_records", [])

    @property
    def records(self) -> list[SmfRecord]:
        return getattr(self.state, "smf_records")

    def write(self, record: SmfRecord) -> SmfRecord:
        self.records.append(record)
        if len(self.records) > 2000:
            del self.records[:-2000]
        try:
            from gibson.core.smf.recording import append_to_active_store
            append_to_active_store(self.state, record)
        except Exception:
            pass
        try:
            audit = getattr(self.state, "audit", None)
            if audit is not None:
                f = record.to_flat_fields()
                typ = f.get("RECORD_TYPE", str(record.header.record_type))
                event = f.get("EVENT_NAME", f.get("EVENT", "SMF EVENT"))
                result = f.get("RESULT", "INFO")
                detail = record.summary or f.get("DETAIL", "")
                audit.record(record.userid, f"SMF TYPE {typ} {event}", f"{result} {detail}".strip(), f"SMF{typ}", extra=f)
        except Exception:
            pass
        return record

    def query(self, *, record_type: int | str | None = None, subtype: str | None = None, userid: str | None = None, correlation_id: str | None = None) -> list[SmfRecord]:
        out: list[SmfRecord] = list(self.records)
        if record_type is not None:
            rt = str(record_type).upper().replace("TYPE", "")
            out = [r for r in out if str(r.header.record_type).upper() == rt]
        if subtype:
            st = str(subtype).upper()
            out = [r for r in out if str(r.header.subtype).upper() == st]
        if userid:
            u = str(userid).upper()
            out = [r for r in out if str(r.userid).upper() == u]
        if correlation_id:
            c = str(correlation_id).upper()
            out = [r for r in out if str(r.correlation_id).upper() == c]
        return out

    def timeline(self, correlation_id: str) -> list[SmfRecord]:
        return sorted(self.query(correlation_id=correlation_id), key=lambda r: r.header.timestamp)


def get_smf_writer(state: Any) -> SmfWriter:
    w = getattr(state, "smf_writer", None)
    if w is None:
        w = SmfWriter(state)
        setattr(state, "smf_writer", w)
    return w

def record_generic(state: Any, record_type: int | str, userid: str, event: str, detail: str = "", *, subtype: str = "", result: str = "SUCCESS", extra: dict | None = None, subsystem: str = "SYSTEM", source_component: str = "GIBSON") -> SmfRecord:
    fields = {str(k).upper(): v for k, v in (extra or {}).items()}
    fields.setdefault("EVENT_NAME", str(event).upper())
    fields.setdefault("EVENT", str(event).upper())
    fields.setdefault("RESULT", str(result).upper())
    fields.setdefault("DETAIL", detail)
    corr = fields.get("CORRELATION_ID") or fields.get("CORRID") or ""
    job = fields.get("JOBNAME") or (subsystem[:8] if subsystem else "GIBSON")
    try:
        rt = int(str(record_type).replace("SMF", ""))
    except Exception:
        rt = 0
    rec = make_record(rt, subtype=subtype or str(fields.get("SUBTYPE", "")), userid=userid, jobname=job, subsystem=subsystem, source_component=source_component, correlation_id=str(corr or ""), summary=detail, system_id=str(fields.get("SYSTEM") or getattr(getattr(state, 'network', None), 'hostname', 'GIBSON')), raw_fields=fields)
    return get_smf_writer(state).write(rec)
