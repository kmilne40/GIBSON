from __future__ import annotations

from typing import Any
from gibson.core.security.racf_authorization import check_access
from gibson.core.smf import record_smf

RESOURCES = {
    "TRANSACTION": {"FIBS": {"PROGRAM": "FIBSPGM", "GROUP": "FIBS", "SECURITY": "TCICSTRN.FIBS"}, "CEMT": {"PROGRAM": "DFHEMTA", "GROUP": "DFHOPER", "SECURITY": "OPER"}, "DVCA": {"PROGRAM": "DVCAPGM", "GROUP": "DVCA", "SECURITY": "TCICSTRN.DVCA"}},
    "PROGRAM": {"FIBSPGM": {"LANG": "COBOL", "STATUS": "ENABLED"}, "DVCAPGM": {"LANG": "COBOL", "STATUS": "ENABLED"}, "CBSAAPI": {"LANG": "COBOL", "STATUS": "ENABLED"}},
    "FILE": {"FIBSCUST": {"DSNAME": "FIBS.CUSTOMER.DATA", "STATUS": "OPEN ENABLED"}, "DVCACUST": {"DSNAME": "DVCA.CUSTOMER.DATA", "STATUS": "OPEN ENABLED"}},
}


def _display(kind: str, name: str | None = None) -> str:
    k = kind.upper()
    rows = RESOURCES.get(k, {})
    lines = [f"CICS RESOURCE DISPLAY {k}", "NAME       ATTRIBUTES"]
    for rname, attrs in sorted(rows.items()):
        if name and name not in {rname, "*"}:
            continue
        lines.append(f"{rname:<10} " + " ".join(f"{a}={v}" for a, v in attrs.items()))
    if len(lines) == 2:
        lines.append("NO MATCHING RESOURCES")
    return "\n".join(lines)


def cics_resource_command(state: Any, userid: str, cmd: str) -> str | None:
    u = (cmd or "").strip().upper()
    if u.startswith("CEDA DISPLAY GROUP"):
        return "CEDA DISPLAY GROUP(FIBS)\n" + _display("TRANSACTION") + "\n" + _display("PROGRAM") + "\n" + _display("FILE")
    if u.startswith("CEDA DISPLAY TRANSACTION") or u.startswith("CEMT INQUIRE TRANSACTION"):
        name = u.split()[-1].strip("()") if len(u.split()) > 2 else None
        dec = check_access(state, userid, "CICS", name or "FIBS", "READ")
        record_smf(state, "110", userid, "CICS RESOURCE DISPLAY", f"TRANSACTION={name or '*'} RESULT={'ALLOW' if dec.allowed else 'DENY'}")
        return _display("TRANSACTION", name)
    if u.startswith("CEDA DISPLAY PROGRAM") or u.startswith("CEMT INQUIRE PROGRAM"):
        return _display("PROGRAM", u.split()[-1].strip("()") if len(u.split()) > 2 else None)
    if u.startswith("CEMT INQUIRE FILE"):
        return _display("FILE", u.split()[-1].strip("()") if len(u.split()) > 2 else None)
    return None
