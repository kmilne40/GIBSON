from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Access = Literal["READ", "UPDATE", "ALTER"]


@dataclass
class IcsfState:
    icsf_started: bool = True
    master_key_version: int = 1
    master_key_last_refresh_time: str = "NEVER"
    ckds_version: int = 1
    ckds_last_refresh_time: str = "NEVER"
    pkds_version: int = 1
    pkds_last_refresh_time: str = "NEVER"
    tkds_version: int = 1
    tkds_last_refresh_time: str = "NEVER"
    last_operator: str = "SYSTEM"
    last_operation: str = "INITIALISE"
    last_result: str = "SUCCESS"
    audit_sequence: int = 0


_RESOURCE_ACCESS = {
    "STATUS": ("CSF.STATUS", "READ"),
    "DISPLAY": ("CSF.STATUS", "READ"),
    "REFRESH": ("CSF.REFRESH", "UPDATE"),
    "REFRESH.MASTERKEY": ("CSF.REFRESH.MASTERKEY", "ALTER"),
    "REFRESH.CKDS": ("CSF.REFRESH.CKDS", "UPDATE"),
    "REFRESH.PKDS": ("CSF.REFRESH.PKDS", "UPDATE"),
    "REFRESH.TKDS": ("CSF.REFRESH.TKDS", "UPDATE"),
}


def get_state(state) -> IcsfState:
    st = getattr(state, "icsf_state", None)
    if st is None:
        st = IcsfState()
        setattr(state, "icsf_state", st)
    return st


def _user(state, userid: str) -> str:
    return (userid or "UNKNOWN").upper()


def _is_ibmuser(userid: str) -> bool:
    return _user(None, userid) == "IBMUSER"


def _audit(state, userid: str, event: str, detail: str, *, result: str = "SUCCESS") -> None:
    who = _user(state, userid)
    try:
        state.record_security_event(who, "ICSF " + event, detail, result=result, service="ICSF")
    except Exception:
        pass
    try:
        sev = "INFO" if result.upper() == "SUCCESS" else "ALERT"
        state.notify_console(f"CSF9000I ICSF {event} USER={who} RESULT={result.upper()} {detail}", severity=sev)
    except Exception:
        pass
    try:
        state.raise_dashboard_alert(f"ICSF {event}: {detail}", severity="INFO" if result.upper() == "SUCCESS" else "ALERT", event_type="ICSF")
    except Exception:
        pass


def check_authority(state, userid: str, operation: str):
    who = _user(state, userid)
    op = operation.upper()
    resource, required = _RESOURCE_ACCESS.get(op, ("CSF.ADMIN", "ALTER"))
    decision = state.dynamic_racf.access_decision("FACILITY", resource, who, required, state.racf)
    if decision.allowed:
        if who == "IBMUSER" and decision.reason in {"SPECIAL", "OWNER"}:
            try:
                state.record_break_glass("IBMUSER", f"ICSF {op}")
            except Exception:
                pass
        return True, resource, required, decision
    detail = f"{resource} CL(FACILITY) ACCESS INTENT({required}) ACCESS ALLOWED({decision.effective})"
    _audit(state, who, op, detail, result="FAILURE")
    return False, resource, required, decision


def status(state, userid: str = "UNKNOWN") -> str:
    allowed, resource, required, decision = check_authority(state, userid, "STATUS")
    if not allowed:
        return _denied(userid, resource, required, getattr(decision, "effective", "NONE"), "ICSF STATUS")
    st = get_state(state)
    _audit(state, userid, "STATUS", "DISPLAY STATUS")
    return "\n".join([
        "CSF0001I ICSF SIMULATED STATUS",
        "ICSF STATUS: " + ("ACTIVE" if st.icsf_started else "INACTIVE"),
        f"MASTER KEY VERSION: {st.master_key_version:08d}",
        f"CKDS VERSION: {st.ckds_version:08d}",
        f"PKDS VERSION: {st.pkds_version:08d}",
        f"TKDS VERSION: {st.tkds_version:08d}",
        f"MASTER KEY LAST REFRESH: {st.master_key_last_refresh_time}",
        f"CKDS LAST REFRESH: {st.ckds_last_refresh_time}",
        f"PKDS LAST REFRESH: {st.pkds_last_refresh_time}",
        f"TKDS LAST REFRESH: {st.tkds_last_refresh_time}",
        f"LAST OPERATOR: {st.last_operator}",
        f"LAST OPERATION: {st.last_operation}",
        "CSF9999I GIBSON ICSF IS A SIMULATED CONTROL PLANE",
        "REAL CRYPTOGRAPHIC KEY MATERIAL IS NOT GENERATED OR ROTATED",
    ])


def _denied(userid: str, resource: str, required: str, effective: str, action: str) -> str:
    who = _user(None, userid)
    return "\n".join([
        f"ICH408I USER({who}) GROUP(SYS1) NAME(GIBSON USER)",
        f"  {resource} CL(FACILITY)",
        "  INSUFFICIENT ACCESS AUTHORITY",
        f"  ACCESS INTENT({required}) ACCESS ALLOWED({effective or 'NONE'})",
        f"CSF9001E {action} DENIED BY RACF",
        "SECURITY EVENT RECORDED",
    ])


def refresh(state, userid: str, target: str = "ALL") -> str:
    tgt = (target or "ALL").upper().replace(" ", "")
    if tgt in {"", "ALL"}:
        operation = "REFRESH"
    elif tgt in {"MASTER", "MASTERKEY", "MASTER_KEY"}:
        operation = "REFRESH.MASTERKEY"
        tgt = "MASTERKEY"
    elif tgt in {"CKDS", "PKDS", "TKDS"}:
        operation = f"REFRESH.{tgt}"
    else:
        return "CSF9002E ICSF REFRESH TARGET NOT RECOGNISED - USE MASTERKEY, CKDS, PKDS, OR TKDS"
    allowed, resource, required, decision = check_authority(state, userid, operation)
    if not allowed:
        return _denied(userid, resource, required, getattr(decision, "effective", "NONE"), f"ICSF {operation}")
    st = get_state(state)
    now = datetime.now().isoformat(timespec="seconds")
    changed = []
    if tgt in {"ALL", "MASTERKEY"}:
        st.master_key_version += 1
        st.master_key_last_refresh_time = now
        changed.append(f"MASTER KEY VERSION: {st.master_key_version:08d}")
    if tgt in {"ALL", "CKDS"}:
        st.ckds_version += 1
        st.ckds_last_refresh_time = now
        changed.append(f"CKDS VERSION: {st.ckds_version:08d}")
    if tgt in {"ALL", "PKDS"}:
        st.pkds_version += 1
        st.pkds_last_refresh_time = now
        changed.append(f"PKDS VERSION: {st.pkds_version:08d}")
    if tgt in {"ALL", "TKDS"}:
        st.tkds_version += 1
        st.tkds_last_refresh_time = now
        changed.append(f"TKDS VERSION: {st.tkds_version:08d}")
    st.last_operator = _user(state, userid)
    st.last_operation = operation
    st.last_result = "SUCCESS"
    st.audit_sequence += 1
    _audit(state, userid, operation, f"TARGET={tgt} SEQ={st.audit_sequence}")
    try:
        from gibson.core.smf.records.typeicsf import master_key_refresh
        old_vp = f"VP{st.master_key_version-1:08d}"
        new_vp = f"VP{st.master_key_version:08d}"
        store = "CKDS" if tgt in {"ALL", "MASTERKEY"} else tgt
        master_key_refresh(state, userid=userid, key_type="AES", key_store=store,
                           result="SUCCESS", phase="COMPLETE", old_vp=old_vp,
                           new_vp=new_vp, reason_code="OK",
                           detail=f"TARGET={tgt} SEQ={st.audit_sequence}")
    except Exception:
        pass
    if tgt == "MASTERKEY":
        head = "CSF0100I ICSF SIMULATED MASTER KEY REFRESH COMPLETE"
    elif tgt in {"CKDS", "PKDS", "TKDS"}:
        head = f"CSF0110I ICSF SIMULATED {tgt} REFRESH COMPLETE"
    else:
        head = "CSF0101I ICSF SIMULATED REFRESH COMPLETE"
    return "\n".join([head, *changed, "SECURITY EVENT RECORDED"])


def help_text() -> str:
    return "\n".join([
        "ICSF SIMULATED COMMANDS",
        "  ICSF STATUS | ICSF DISPLAY STATUS | ICSF DISPLAY KEYSETS",
        "  ICSF REFRESH | ICSF REFRESH MASTERKEY | ICSF REFRESH CKDS | PKDS | TKDS",
        "  ICSF HELP",
        "NOTE: Gibson simulates ICSF control-plane evidence only; no real keys are generated.",
    ])


def handle_tso(state, userid: str, cmd: str) -> str:
    raw = (cmd or "").strip()
    parts = raw.split()
    if len(parts) == 1 or (len(parts) > 1 and parts[1].upper() in {"STATUS", "DISPLAY"}):
        if len(parts) > 2 and parts[1].upper() == "DISPLAY" and parts[2].upper() in {"HELP", "?"}:
            return help_text()
        return status(state, userid)
    if len(parts) > 1 and parts[1].upper() == "HELP":
        return help_text()
    if len(parts) > 1 and parts[1].upper() == "REFRESH":
        target = parts[2] if len(parts) > 2 else "ALL"
        return refresh(state, userid, target)
    return help_text()


def handle_console(state, userid: str, cmd: str) -> str:
    raw = (cmd or "").strip().upper()
    if raw in {"D ICSF", "DISPLAY ICSF", "F ICSF,STATUS", "F ICSF,DISPLAY", "F ICSF,DISPLAY,STATUS", "F ICSF,DISPLAY,KEYSETS"}:
        return status(state, userid)
    if raw.startswith("F ICSF,REFRESH"):
        parts = [p.strip() for p in raw.split(",")]
        target = parts[2] if len(parts) > 2 else "ALL"
        return refresh(state, userid, target)
    if raw in {"F ICSF,HELP", "ICSF HELP"}:
        return help_text()
    return "CSF9002E ICSF CONSOLE COMMAND NOT RECOGNISED"
