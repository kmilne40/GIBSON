from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SECURE = "secure"
VULN = "vuln"
NORACF = "noracf"


@dataclass(frozen=True)
class CisControl:
    control_id: str
    title: str
    gibson_component: str
    secure_behavior: str
    status: str = "simulated"


CIS_CONTROLS: tuple[CisControl, ...] = (
    CisControl("1.1.1", "PASSWORD(INTERVAL) <= 90", "RACF SETROPTS", "SETROPTS LIST reports 90 day interval"),
    CisControl("1.1.2", "PASSWORD(HISTORY) >= 4", "RACF SETROPTS", "password history is represented in secure profile"),
    CisControl("1.1.5", "PASSWORD(REVOKE)", "RACF logon", "failed logons can revoke users; revoked users cannot log on"),
    CisControl("1.2.6", "OPERCMDS active/RACLISTed", "RACF classes", "OPERCMDS active and RACLISTed in secure profile"),
    CisControl("1.2.8", "FACILITY active/RACLISTed", "RACF classes", "FACILITY active and RACLISTed in secure profile"),
    CisControl("1.3.1", "SPECIAL justified", "RACF users", "SPECIAL use is audited; IBMUSER is break-glass"),
    CisControl("2.1.8", "RACF security datasets protected", "DATASET", "SYS1.RACFDS* protected UACC(NONE)"),
    CisControl("2.2.5", "PARMLIB protected", "DATASET", "SYS1.PARMLIB protected; UPDATE+ audited"),
    CisControl("2.2.13", "PROCLIB protected", "DATASET", "SYS1.PROCLIB protected; UPDATE+ audited"),
    CisControl("2.2.15", "LINKLIB protected", "DATASET", "SYS1.LINKLIB protected; UPDATE+ audited"),
    CisControl("2.3.3", "PROTECTALL(FAIL)", "RACF SETROPTS/DATASET", "unprofiled protected access fails in secure mode"),
    CisControl("3.1", "CMDVIOL logging", "Audit", "command violations create SMF80/security events"),
    CisControl("3.2", "SPECIAL activity logging", "Audit", "SPECIAL and IBMUSER break-glass events audited"),
    CisControl("3.3", "AUDIT classes", "Audit", "DATASET/USER/GROUP/FACILITY/OPERCMDS audit simulated"),
    CisControl("6.2.4", "AT-TLS for FTP", "Network", "plaintext FTP is disabled in secure mode unless explicitly re-enabled"),
    CisControl("6.6.4", "AT-TLS for TN3270", "Network", "secure VTAM/TSO listener uses TLS on port 1023"),
    CisControl("6.6.5", "TN3270 SMF recording", "Audit", "TN3270/TLS startup and logons are audited"),
    CisControl("9.23", "USS Telnet server not active", "Network", "USS plaintext listener is disabled by default in secure mode"),
)


def normalise_mode(value: str | None) -> str:
    v = (value or VULN).strip().lower()
    if v in {"secure", "hardening", "hardened"}:
        return SECURE
    if v in {"noracf", "no-racf", "racf-off", "off"}:
        return NORACF
    return VULN


def is_secure_mode(config_or_state: Any) -> bool:
    cfg = getattr(config_or_state, "config", config_or_state)
    return normalise_mode(getattr(cfg, "security_mode", VULN)) == SECURE


def is_noracf_mode(config_or_state: Any) -> bool:
    cfg = getattr(config_or_state, "config", config_or_state)
    return normalise_mode(getattr(cfg, "security_mode", VULN)) == NORACF

def is_vuln_mode(config_or_state: Any) -> bool:
    cfg = getattr(config_or_state, "config", config_or_state)
    return normalise_mode(getattr(cfg, "security_mode", VULN)) == VULN


def security_mode_banner(config_or_state: Any) -> str:
    if is_secure_mode(config_or_state):
        return (
            "GIBSON SECURE MODE ACTIVE\n"
            "CIS-ALIGNED SIMULATOR PROFILE LOADED\n"
            "TSO/TN3270 TLS PORT=1023 HTTPS PORT=8443\n"
            "IBMUSER BREAK-GLASS ACCOUNT ENABLED AND AUDITED"
        )
    if is_noracf_mode(config_or_state):
        return "GIBSON NORACF MODE ACTIVE - RACF AUTHORIZATION CHECKING DISABLED"
    return "GIBSON VULNERABLE TRAINING MODE ACTIVE"


def secure_block_message(reason: str) -> str:
    return (
        "GIBSON SECURE MODE ACTIVE\n"
        "REQUEST BLOCKED BY ACTIVE SECURITY PROFILE\n"
        f"REASON: {reason}"
    )


def audit_mode_event(state: Any, event: str, detail: str = "") -> None:
    try:
        state.record_security_event("SYSTEM", event, detail, service="SECURITY-MODE")
    except Exception:
        pass
    try:
        state.notify_console(f"GIBSON {event.upper()} {detail}".strip(), severity="INFO")
    except Exception:
        pass
    try:
        state.raise_dashboard_alert(f"GIBSON {event.upper()} {detail}".strip(), severity="INFO", event_type="SECURITY_MODE")
    except Exception:
        pass


def require_secure_control(state: Any, control_id: str) -> bool:
    if not is_secure_mode(state):
        return False
    return any(c.control_id == control_id for c in CIS_CONTROLS)
