from __future__ import annotations
from datetime import datetime
from typing import Any
import uuid


def _corr() -> str:
    return "TCAT-" + uuid.uuid4().hex[:10].upper()


def record_event(state: Any, event: str, message: str, *, user: str = "tomcat", severity: str = "INFO", port: int | None = None, addr: str = "", component: str = "TOMCAT", record_type: str = "119", extra: dict | None = None) -> str:
    cid = (extra or {}).get("CORRID") or _corr()
    detail = message
    data = {
        "EVENT": event.upper(),
        "SERVICE": component.upper(),
        "RESOURCE": f"PORT{port}" if port else component.upper(),
        "DETAIL": detail,
        "CORRID": cid,
        "TIME": datetime.now().strftime("%H:%M:%S"),
        "DATE": datetime.now().strftime("%Y-%m-%d"),
        "ADDR": addr,
        "SEVERITY": severity.upper(),
    }
    if extra:
        data.update({str(k).upper(): str(v) for k, v in extra.items() if v is not None})
    try:
        if record_type == "80":
            state.record_security_event(user, event, detail, result="SUCCESS", service=component.upper(), addr=addr)
        elif getattr(state, "audit", None) is not None:
            state.audit.record(user, f"SMF TYPE {record_type} {event.upper()}", detail, f"SMF{record_type}", extra=data)
    except Exception:
        pass
    try:
        state.notify_console(message, severity=severity)
    except Exception:
        pass
    try:
        state.raise_dashboard_alert(message, severity=severity, addr=addr, port=port, event_type=event.upper())
    except Exception:
        pass
    try:
        events = getattr(state, "tomcat_evidence", None)
        if events is None:
            events = []
            state.tomcat_evidence = events
        events.append({"event_id": cid, "timestamp": datetime.now().isoformat(timespec="seconds"), "event": event.upper(), "message": message, "user": user, "severity": severity.upper(), "port": port, "addr": addr, "component": component.upper()})
    except Exception:
        pass
    return cid


def record_login(state: Any, user: str, addr: str = "") -> None:
    msg = f"ICH70001I TOMCAT MANAGER LOGON USER({user.upper()}) DEFAULT-CREDENTIAL LAB ACCESS ACCEPTED"
    record_event(state, "TOMCAT_LOGON", msg, user=user, severity="ALERT", port=8080, addr=addr, component="TOMCAT/SMF80", record_type="80")


def record_upload(state: Any, dep: Any, addr: str = "") -> None:
    msg = f"GTC119I TOMCAT WAR UPLOAD USER({dep.uploaded_by}) FILE({dep.filename}) CONTEXT({dep.context}) SHA256({dep.sha256[:12]})"
    record_event(state, "TOMCAT_WAR_UPLOAD", msg, user=dep.uploaded_by, severity="WARNING", port=8080, addr=addr, component="TOMCAT", record_type="119", extra={"CONTEXT": dep.context, "SHA256": dep.sha256})


def record_deploy(state: Any, dep: Any, addr: str = "") -> None:
    msg = f"GTC120W UNAPPROVED TOMCAT APPLICATION DEPLOYED CONTEXT({dep.context}) USER({dep.uploaded_by})"
    record_event(state, "TOMCAT_WAR_DEPLOY", msg, user=dep.uploaded_by, severity="ALERT", port=8080, addr=addr, component="TOMCAT", record_type="119", extra={"CONTEXT": dep.context})


def record_payload_trigger(state: Any, sess: Any, addr: str = "") -> None:
    msg = f"GTC31337A TOMCAT SIMULATED BIND SESSION ACTIVE CONTEXT({sess.context}) PORT({sess.port}) USER({sess.user})"
    record_event(state, "TOMCAT_BIND_OPEN", msg, user=sess.user, severity="ALERT", port=int(sess.port), addr=addr, component="TOMCAT", record_type="119", extra={"SESSION": sess.session_id, "CONTEXT": sess.context})


def record_session_command(state: Any, sess: Any, cmd: str, result: str) -> None:
    msg = f"GTC31338I TOMCAT SESSION({sess.session_id}) COMMAND({cmd[:32]}) RESULT({result[:40]})"
    record_event(state, "TOMCAT_SESSION_COMMAND", msg, user=sess.user, severity="INFO", port=int(sess.port), component="TOMCAT", record_type="119", extra={"SESSION": sess.session_id})
