from __future__ import annotations

from gibson.core.security_mode import CIS_CONTROLS, audit_mode_event, is_secure_mode

SENSITIVE_DATASETS = {
    "SYS1.*": "READ",
    "SYS1.PARMLIB": "READ",
    "SYS1.PROCLIB": "READ",
    "SYS1.LINKLIB": "READ",
    "SYS1.LPALIB": "READ",
    "SYS1.SVCLIB": "READ",
    "SYS1.NUCLEUS": "READ",
    "SYS1.APFLIB": "NONE",
    "SYS1.RACFDS": "NONE",
    "SYS1.RACFDS.BACKUP": "NONE",
    "SYS1.UADS": "NONE",
    "SYS1.SDSF": "READ",
    "SYS1.DB2.PROCLIB": "READ",
    "SYS1.CICS.PROCLIB": "READ",
    "SYS1.TCPPARMS": "READ",
    "SYS1.VTAMLST": "READ",
    "SYS1.MAN*": "NONE",
    "SYS1.TRACE*": "NONE",
    "SYS1.DUMP*": "NONE",
    "SYS1.BACKUP*": "NONE",
}

ACTIVE_CLASSES = ("OPERCMDS", "CONSOLE", "FACILITY", "TEMPDSN", "STARTED", "PROPCNTL", "SURROGAT", "JESSPOOL", "JESJOBS", "TSOAUTH", "SDSF", "UNIXPRIV", "APPL", "DATASET")
RACLIST_CLASSES = ("OPERCMDS", "FACILITY", "STARTED", "PROPCNTL", "SURROGAT", "JESSPOOL", "JESJOBS", "TSOAUTH", "SDSF", "UNIXPRIV", "APPL")


def apply_secure_profile(state) -> None:
    if not is_secure_mode(state):
        return
    cfg = state.config
    cfg.mfa_required = True
    cfg.console_security_audit = True
    cfg.strict_tso_ptkt = True
    cfg.secure_disable_plain_uss = True
    cfg.secure_disable_plain_ftp = True
    cfg.protectall_fail = True
    cfg.password_interval = 90
    cfg.password_history = 4
    cfg.password_minchange = 1
    cfg.password_warning = 5
    cfg.password_revoke = 6
    cfg.password_algorithm = "KDFAES"
    cfg.racf_attributes = {"INITSTATS", "SAUDIT", "CMDVIOL", "OPERAUDIT", "WHEN(PROGRAM)", "TERMINAL(NONE)", "PROTECTALL(FAIL)"}
    cfg.audit_classes = {"DATASET", "USER", "GROUP", "OPERCMDS", "TSOAUTH", "SDSF", "FACILITY", "UNIXPRIV", "APPL"}
    cfg.active_classes = set(ACTIVE_CLASSES)
    cfg.raclist_classes = set(RACLIST_CLASSES)

    state.mfa_enabled = True
    for clsname in ACTIVE_CLASSES:
        state.dynamic_racf.raclist_active.setdefault(clsname, clsname in RACLIST_CLASSES)
    for dsn, uacc in SENSITIVE_DATASETS.items():
        prof = state.dynamic_racf._find_profile("DATASET", dsn)
        if prof is None or prof.name != dsn.upper():
            prof = state.dynamic_racf.define("DATASET", dsn, "IBMUSER", uacc, volume="SBSYS1")
        prof.owner = "IBMUSER"
        prof.uacc = uacc
        prof.warning = False
        prof.audit = "ALL(READ)"
        prof.permits.setdefault("IBMUSER", "ALTER")
        # Preserve explicitly-granted lab permits only outside sensitive system profiles.
        if dsn.startswith("SYS1.RACFDS") or dsn in {"SYS1.UADS", "SYS1.APFLIB"}:
            for ident in list(prof.permits):
                if ident != "IBMUSER":
                    prof.permits.pop(ident, None)
    for name in ("OPER", "CONSOLE", "PARMLIB", "TESTAUTH", "ACCT"):
        prof = state.dynamic_racf._find_profile("TSOAUTH", name) or state.dynamic_racf.define("TSOAUTH", name, "IBMUSER", "NONE")
        prof.uacc = "NONE"; prof.warning = False; prof.audit = "ALL(READ)"; prof.permits.setdefault("IBMUSER", "READ")
    for name in ("MVS.DISPLAY", "MVS.SETPROG", "MVS.START", "MVS.STOP", "MVS.CANCEL"):
        prof = state.dynamic_racf._find_profile("OPERCMDS", name) or state.dynamic_racf.define("OPERCMDS", name, "IBMUSER", "NONE")
        prof.uacc = "NONE"; prof.warning = False; prof.audit = "ALL(READ)"; prof.permits.setdefault("IBMUSER", "READ")
    state.dynamic_racf.save()
    for control in CIS_CONTROLS:
        audit_mode_event(state, "CIS CONTROL APPLIED", f"{control.control_id} {control.title} STATUS={control.status}")
