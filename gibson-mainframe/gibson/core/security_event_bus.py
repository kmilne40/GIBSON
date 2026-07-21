from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
import uuid


@dataclass
class SecurityTrainingEvent:
    event_id: str
    timestamp: str
    severity: str
    subsystem: str
    smf_type: str
    user: str
    channel: str
    action: str
    result: str
    resource: str = ""
    transaction: str = ""
    program: str = ""
    endpoint: str = ""
    table: str = ""
    payload: str = ""
    correlation_id: str = ""
    detail: str = ""

    def row(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


def _ts() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _corr(prefix: str = "SMF") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _save(state: Any, ev: SecurityTrainingEvent) -> None:
    events = getattr(state, "security_training_events", None)
    if events is None:
        events = []
        setattr(state, "security_training_events", events)
    events.append(ev.row())


def _console(state: Any, severity: str, message: str) -> None:
    try:
        state.notify_console(message, severity=severity)
    except Exception:
        pass


def emit_training_security_event(
    state: Any,
    *,
    event: str,
    user: str = "DVCAUSR",
    channel: str = "HACK3270",
    result: str = "SUCCESS",
    severity: str = "ALERT",
    smf_type: str = "110",
    subsystem: str = "CICS",
    resource: str = "",
    transaction: str = "DVCA",
    program: str = "",
    endpoint: str = "",
    table: str = "",
    payload: str = "",
    correlation_id: str = "",
    detail: str = "",
) -> SecurityTrainingEvent:
    """Emit one bounded Gibson training event.

    The generated messages deliberately say SIMULATED.  They are console/audit
    evidence for Gibson labs; they are not real IBM SMF records.
    """
    correlation_id = correlation_id or _corr("GIB")
    event_id = _corr("EVT")
    ev = SecurityTrainingEvent(
        event_id=event_id,
        timestamp=_ts(),
        severity=severity.upper(),
        subsystem=subsystem.upper(),
        smf_type=str(smf_type),
        user=(user or "UNKNOWN").upper(),
        channel=channel.upper(),
        action=event.upper(),
        result=result.upper(),
        resource=(resource or "")[:160],
        transaction=(transaction or "")[:16],
        program=(program or "")[:24],
        endpoint=(endpoint or "")[:160],
        table=(table or "")[:64],
        payload=(payload or "")[:220],
        correlation_id=correlation_id,
        detail=(detail or "")[:220],
    )
    _save(state, ev)

    smf = str(smf_type)
    if smf == "80":
        _console(
            state,
            severity,
            f"GIBSMF80I SIMULATED SMF80 RACF EVENT USER={ev.user} "
            f"RESOURCE={ev.resource or ev.transaction} ACTION={ev.action} "
            f"RESULT={ev.result} CORRID={ev.correlation_id}",
        )
    elif smf == "102":
        _console(
            state,
            severity,
            f"GIBSMF102I SIMULATED SMF102 DB2 AUDIT EVENT DB2=GIBD "
            f"PLAN=CBSAWEB AUTHID={ev.user} STMT={ev.action} "
            f"OBJECT={ev.table or ev.resource} RESULT={ev.result} "
            f"CORRID={ev.correlation_id}",
        )
    elif smf == "110":
        _console(
            state,
            severity,
            f"GIBSMF110I SIMULATED SMF110 CICS MONITOR EVENT APPLID=GIBCICS "
            f"TRAN={ev.transaction or 'DVCA'} PROGRAM={ev.program or 'UNKNOWN'} "
            f"EVENT={ev.action} RESULT={ev.result} CORRID={ev.correlation_id}",
        )
    else:
        _console(
            state,
            severity,
            f"GIBSMF{smf}I SIMULATED SMF{smf} {ev.subsystem} EVENT "
            f"ACTION={ev.action} RESULT={ev.result} CORRID={ev.correlation_id}",
        )

    if ev.action in {"SQLI", "SQLI_SEARCH"}:
        _console(
            state,
            severity,
            f"GIBSQLI01W SQLI TRAINING PAYLOAD DETECTED CHANNEL={ev.channel} "
            f"ENDPOINT={ev.endpoint or '/labs/sqli'} CORRID={ev.correlation_id}",
        )
    elif "PIN" in ev.action:
        _console(
            state,
            severity,
            f"GIBDVCA13W DVCA SUPERVISOR PIN TRAINING EVENT CHANNEL={ev.channel} "
            f"USER={ev.user} RESULT={ev.result} {ev.detail} CORRID={ev.correlation_id}",
        )
    elif "IDOR" in ev.action or "BOLA" in ev.action:
        _console(
            state,
            severity,
            f"GIBAPI401W API AUTHZ TRAINING EVENT TYPE=BOLA USER={ev.user} "
            f"OBJECT={ev.resource} RESULT={ev.result} CORRID={ev.correlation_id}",
        )
    elif "METHOD" in ev.action:
        _console(
            state,
            severity,
            f"GIBAPI405W UNSAFE METHOD OVERRIDE TRAINING EVENT "
            f"ACTION={ev.action} RESULT={ev.result} CORRID={ev.correlation_id}",
        )
    return ev


def emit_smf80(state: Any, **kwargs: Any) -> SecurityTrainingEvent:
    return emit_training_security_event(state, smf_type="80", subsystem="RACF", **kwargs)


def emit_smf110(state: Any, **kwargs: Any) -> SecurityTrainingEvent:
    return emit_training_security_event(state, smf_type="110", subsystem="CICS", **kwargs)


def emit_smf102(state: Any, **kwargs: Any) -> SecurityTrainingEvent:
    return emit_training_security_event(state, smf_type="102", subsystem="DB2", **kwargs)

# --- FIBS WEB9080 teller trace support ---------------------------------

def _clip(value: Any, limit: int = 240) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 3] + "..."


@dataclass
class BackendTraceEvent:
    event_id: str
    timestamp: str
    trace_id: str
    correlation_id: str
    user: str
    channel: str
    component: str
    action: str
    route: str = ""
    cics_transaction: str = ""
    cics_program: str = ""
    sql: str = ""
    table: str = ""
    smf_type: str = ""
    result: str = ""
    rows_returned: int = 0
    message: str = ""
    severity: str = "INFO"

    def row(self) -> dict[str, str]:
        data = asdict(self)
        return {k: _clip(v, 260) for k, v in data.items()}


def emit_trace_event(
    state: Any,
    *,
    component: str,
    action: str,
    user: str = "SYSTEM",
    channel: str = "WEB9080",
    route: str = "",
    cics_transaction: str = "",
    cics_program: str = "",
    sql: str = "",
    table: str = "",
    smf_type: str = "",
    result: str = "OK",
    rows_returned: int = 0,
    message: str = "",
    severity: str = "INFO",
    correlation_id: str = "",
    trace_id: str = "",
) -> BackendTraceEvent:
    correlation_id = correlation_id or _corr("TRACE")
    trace_id = trace_id or correlation_id
    event_id = _corr("TRC")
    ev = BackendTraceEvent(
        event_id=event_id,
        timestamp=_ts(),
        trace_id=_clip(trace_id, 64),
        correlation_id=correlation_id,
        user=_clip(user, 32).upper(),
        channel=_clip(channel, 32).upper(),
        component=_clip(component, 32).upper(),
        action=_clip(action, 64).upper(),
        route=_clip(route, 160),
        cics_transaction=_clip(cics_transaction, 16),
        cics_program=_clip(cics_program, 32),
        sql=_clip(sql, 260),
        table=_clip(table, 80),
        smf_type=_clip(smf_type, 8),
        result=_clip(result, 80).upper(),
        rows_returned=int(rows_returned or 0),
        message=_clip(message, 240),
        severity=_clip(severity, 16).upper(),
    )
    buf = getattr(state, "backend_trace_events", None)
    if buf is None:
        buf = []
        setattr(state, "backend_trace_events", buf)
    buf.append(ev.row())
    del buf[:-500]
    return ev


def get_trace_events(state: Any, since: str | None = None, trace_id: str | None = None) -> list[dict[str, str]]:
    rows = list(getattr(state, "backend_trace_events", []) or [])
    if trace_id:
        rows = [r for r in rows if r.get("trace_id") == trace_id or r.get("correlation_id") == trace_id]
    if since:
        out = []
        seen = False
        for row in rows:
            if seen:
                out.append(row)
            elif row.get("event_id") == since:
                seen = True
        return out
    return rows[-100:]


def create_trace_session(state: Any, page: str = "", user: str = "WEBUSER", lab_slug: str = "") -> dict[str, str]:
    trace_id = _corr("TRACE")
    sessions = getattr(state, "trace_sessions", None)
    if sessions is None:
        sessions = {}; setattr(state, "trace_sessions", sessions)
    sessions[trace_id] = {"trace_id": trace_id, "page": page, "lab_slug": lab_slug, "user": user, "created_at": _ts()}
    ev = emit_trace_event(state, component="WEB9080", action="TRACE_SESSION_CREATED", user=user, route=page, result="OK", message="Trace session created", trace_id=trace_id, correlation_id=trace_id)
    return {"trace_id": trace_id, "event_id": ev.event_id, "created_at": sessions[trace_id]["created_at"]}


def clear_trace_events(state: Any, trace_id: str | None = None) -> None:
    if not trace_id:
        setattr(state, "backend_trace_events", [])
        return
    rows = list(getattr(state, "backend_trace_events", []) or [])
    rows = [r for r in rows if r.get("trace_id") != trace_id and r.get("correlation_id") != trace_id]
    setattr(state, "backend_trace_events", rows)


def emit_smf101(state: Any, **kwargs: Any) -> SecurityTrainingEvent:
    return emit_training_security_event(state, smf_type="101", subsystem="DB2", **kwargs)
