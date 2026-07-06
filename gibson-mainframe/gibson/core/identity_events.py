from __future__ import annotations
from datetime import datetime
from typing import Any
from gibson.core.security_event_bus import emit_trace_event, emit_smf80

def emit_identity_event(state: Any, *, event_type: str, user: str = "WEBUSER", service: str = "IDENTITY", action: str = "", result: str = "INFO", resource: str = "", correlation_id: str = "", trace_id: str = "", severity: str = "INFO", detail: str = "") -> dict[str, str]:
    correlation_id = correlation_id or f"ID-{datetime.utcnow().strftime('%H%M%S')}"
    trace_id = trace_id or correlation_id
    action = action or event_type
    ev = emit_trace_event(state, component="IDENTITY", action=event_type, user=user, channel="WEB9080", route=f"/identity/{event_type.lower()}", result=result, correlation_id=correlation_id, trace_id=trace_id, message=detail or event_type, severity=severity, table=resource)
    smf = emit_smf80(state, event=event_type, user=user, channel="WEB9080", result=result, severity=severity, resource=resource or service, endpoint=f"/identity/{event_type.lower()}", correlation_id=correlation_id, detail=detail)
    row=ev.row(); row["smf_event_id"]=smf.event_id; row["service"]=service; row["resource"]=resource; row["event_type"]=event_type
    events=getattr(state,"identity_events",None)
    if events is None:
        events=[]; setattr(state,"identity_events",events)
    events.append(row)
    high={"PTKT_REPLAY_DENIED","PTKT_APPL_MISMATCH","PTKT_IRRPTAUTH_OVERBROAD","PTKT_DEBUG_LEAK","MFA_PASSTICKET_BYPASS","MFA_BREAKGLASS_USED","MFA_SERVICE_GAP"}
    if event_type in high:
        try: state.notify_console(f"GIBID001W {event_type} USER={user.upper()} RESOURCE={resource} CORRID={correlation_id}", severity="ALERT")
        except Exception: pass
        try: state.raise_dashboard_alert(f"{event_type} detected for {user.upper()} resource={resource}", severity="ALERT", event_type=event_type)
        except Exception: pass
    return row
