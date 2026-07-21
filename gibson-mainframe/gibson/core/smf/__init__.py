from __future__ import annotations

from typing import Any
from .writer import get_smf_writer, record_generic
from .formatters import format_list, format_detail, format_timeline, export_unload

def record_smf(state: Any, record_type: str, userid: str, event: str, detail: str, *, result: str = "SUCCESS", extra: dict | None = None) -> None:
    # Compatibility helper: preserve old audit-style call while also writing a structured record.
    rec = str(record_type).replace("SMF", "")
    try:
        rt = int(rec)
    except Exception:
        rt = 0
    subsystem = {"80":"RACF","30":"JES","7":"SMF","92":"OMVS","101":"DB2","102":"DB2","110":"CICS","119":"TCPIP","123":"API"}.get(rec, "SMF")
    record_generic(state, rt, userid, event, detail, result=result, extra=extra or {}, subsystem=subsystem, source_component=subsystem)

def events_by_type(state: Any, record_type: str) -> list[Any]:
    return get_smf_writer(state).query(record_type=record_type)
