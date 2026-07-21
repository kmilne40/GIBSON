from __future__ import annotations

from typing import Any
from gibson.core.security.racf_authorization import check_access, permit
from gibson.apps.racf_admin import get_racf_store

LABS = {
    "DATASET": ("DATASET", "FIBS.CUSTOMER.DATA", "UPDATE", "PERMIT FIBS.CUSTOMER.DATA CLASS(DATASET) ID(TRAINEE) ACCESS(UPDATE)"),
    "CICS": ("CICS", "FIBS", "READ", "PERMIT FIBS CLASS(CICS) ID(TRAINEE) ACCESS(READ)"),
    "JESSPOOL": ("JESSPOOL", "LOCAL.TRAINEE.JOB00001", "READ", "PERMIT LOCAL.TRAINEE.JOB00001 CLASS(JESSPOOL) ID(TRAINEE) ACCESS(READ)"),
    "DB2": ("DSNR", "DB2A.FIBS.CUSTOMER", "READ", "PERMIT DB2A.FIBS.CUSTOMER CLASS(DSNR) ID(TRAINEE) ACCESS(READ)"),
    "OMVS": ("FACILITY", "BPX.SERVER", "READ", "PERMIT BPX.SERVER CLASS(FACILITY) ID(TRAINEE) ACCESS(READ)"),
    "OPERCMDS": ("OPERCMDS", "MVS.DISPLAY", "READ", "PERMIT MVS.DISPLAY CLASS(OPERCMDS) ID(TRAINEE) ACCESS(READ)"),
}


def _seed_lab(state: Any, name: str) -> tuple[str, str, str, str]:
    cls, res, acc, fix = LABS[name]
    st = get_racf_store(state)
    st.profiles.setdefault(cls, {}).setdefault(res, {"UACC": "NONE", "PERMITS": {}})
    st.profiles[cls][res]["UACC"] = "NONE"
    st.profiles[cls][res].setdefault("PERMITS", {}).pop("TRAINEE", None)
    return cls, res, acc, fix


def racf_lab_command(state: Any, userid: str, cmd: str) -> str | None:
    u = (cmd or "").strip().upper()
    if not (u == "RACFLAB" or u.startswith("RACFLAB ")):
        return None
    parts = u.split()
    if len(parts) == 1 or parts[1] in {"MENU", "HELP", "?"}:
        return "RACF DENIAL/FIX LABS\n" + "\n".join(f" {k:<9} {v[0]} {v[1]}" for k, v in LABS.items()) + "\nCommands: RACFLAB START <name>, RACFLAB FIX <name>, RACFLAB RESET <name>"
    action = parts[1]
    name = parts[2] if len(parts) > 2 else "DATASET"
    if name not in LABS:
        return f"RACFLAB UNKNOWN LAB {name}"
    if action in {"START", "RESET"}:
        cls, res, acc, fix = _seed_lab(state, name)
        dec = check_access(state, "TRAINEE", cls, res, acc)
        return "\n".join([
            f"RACF LAB {name} STARTED",
            f"OBJECTIVE: observe denial, inspect profile, apply fix, retry.",
            f"TRY: {cls} {res} ACCESS({acc}) as TRAINEE",
            dec.message,
            f"INVESTIGATE: RACFADMIN RLIST {cls} {res}",
            f"FIX: {fix}",
            "VERIFY: RACFLAB FIX " + name,
        ])
    if action == "FIX":
        cls, res, acc, fix = LABS[name]
        permit(state, res, cls, "TRAINEE", acc)
        dec = check_access(state, "TRAINEE", cls, res, acc)
        return "\n".join([
            f"RACF LAB {name} FIX APPLIED",
            fix,
            dec.message,
            "EVIDENCE: SDSF SMF80 / ZSEC EVENTS will show the denial and successful retry.",
        ])
    return f"RACFLAB UNKNOWN ACTION {action}"
