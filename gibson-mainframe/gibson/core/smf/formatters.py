from __future__ import annotations
from typing import Any
from .writer import get_smf_writer

def format_list(state: Any, record_type: str | None = None, limit: int = 50) -> str:
    if record_type and str(record_type).upper() == "ICSF":
        recs = [r for r in get_smf_writer(state).records if "ICSF" in (r.header.subtype + " " + str(r.raw_fields.get("EVENT_NAME", ""))).upper()]
    else:
        recs = get_smf_writer(state).query(record_type=record_type) if record_type else list(get_smf_writer(state).records)
    recs = recs[-limit:]
    lines = ["SMF STRUCTURED RECORD LIST", "RECORD-ID      TYPE SUBTYPE      USERID    JOBNAME   EVENT/RESULT"]
    if not recs:
        lines.append("NO STRUCTURED SMF RECORDS AVAILABLE")
    for r in recs:
        f = r.to_flat_fields()
        lines.append(f"{f.get('RECORD_ID','')[:14]:<14} {f.get('RECORD_TYPE',''):<4} {f.get('SUBTYPE','')[:12]:<12} {f.get('USERID','')[:8]:<8} {f.get('JOBNAME','')[:8]:<8} {f.get('EVENT_NAME', f.get('EVENT',''))[:22]} {f.get('RESULT','')}")
    return "\n".join(lines)

def format_detail(state: Any, record_id: str) -> str:
    rid = (record_id or '').upper()
    for r in get_smf_writer(state).records:
        if r.header.record_id.upper() == rid:
            return "\n".join(r.to_detail_lines())
    return f"SMF RECORD {record_id} NOT FOUND"

def format_timeline(state: Any, correlation_id: str) -> str:
    recs = get_smf_writer(state).timeline(correlation_id)
    lines = [f"SMF FORENSIC TIMELINE CORRELATION={correlation_id}", "TIME                  TYPE USERID    EVENT RESULT"]
    if not recs:
        lines.append("NO RELATED SMF RECORDS FOUND")
    for r in recs:
        f = r.to_flat_fields()
        lines.append(f"{f.get('TIMESTAMP',''):<21} {f.get('RECORD_TYPE',''):<4} {f.get('USERID','')[:8]:<8} {f.get('EVENT_NAME','')[:24]:<24} {f.get('RESULT','')}")
    return "\n".join(lines)

def export_unload(state: Any, record_type: str | None = None) -> str:
    recs = get_smf_writer(state).query(record_type=record_type) if record_type else list(get_smf_writer(state).records)
    header="RECORD_ID|RECORD_TYPE|SUBTYPE|TIMESTAMP|SYSTEM_ID|USERID|JOBNAME|EVENT_NAME|RESULT|CLASS_NAME|RESOURCE_NAME|CORRELATION_ID"
    return "\n".join([header] + [r.to_unload_row() for r in recs])
