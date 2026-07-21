from __future__ import annotations

from typing import Any, Iterable
import datetime as dt
import random

from gibson.tools.host_aliases import resolve_host


def _corr() -> str:
    return "CICSPWN-" + dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-") + ''.join(random.choice('0123456789ABCDEF') for _ in range(4))


def run_omvs_cicspwn(argv: Iterable[str], env: Any, cwd: str) -> str:
    args = list(argv)
    if not args or any(a.lower() in {"-h", "--help", "help"} for a in args):
        return "\n".join([
            "CICSPWN Gibson safe CICS assessment simulator",
            "Usage: CICSPWN mainframe [--port 2023] [--applid CICS] [--mode forensic] [--safe]",
            "       CICSPWN 127.0.0.1 --port 2023",
            "Targets are limited to mainframe, localhost, 127.0.0.1 or safe Gibson host aliases.",
            "No JCL is submitted and no host code is executed.",
        ])
    if "--version" in args:
        return "CICSPWN Gibson training simulator 2.0"
    target = "mainframe"; port = 2023; applid = "CICS"; mode = "forensic"; safe = True
    i = 0
    while i < len(args):
        a = args[i]
        if a in {"--port", "-p"} and i + 1 < len(args):
            try: port = int(args[i+1])
            except Exception: port = 2023
            i += 2; continue
        if a.startswith("--port="):
            try: port = int(a.split("=",1)[1])
            except Exception: port = 2023
            i += 1; continue
        if a == "--applid" and i + 1 < len(args):
            applid = args[i+1].upper(); i += 2; continue
        if a.startswith("--applid="):
            applid = a.split("=",1)[1].upper(); i += 1; continue
        if a == "--mode" and i + 1 < len(args):
            mode = args[i+1].lower(); i += 2; continue
        if a.startswith("--mode="):
            mode = a.split("=",1)[1].lower(); i += 1; continue
        if a == "--unsafe":
            safe = False; i += 1; continue
        if a == "--safe":
            safe = True; i += 1; continue
        if not a.startswith("-"):
            target = a
        i += 1
    res = resolve_host(target, env, cwd)
    if not res.allowed:
        return "CICSPWN: target denied: " + res.reason + "\nAllowed targets: mainframe, localhost, 127.0.0.1 or configured Gibson aliases"
    if port in {23, 3270}:
        port = 2023
    if port != 2023:
        return "CICSPWN: only the Gibson terminal training service is supported (2023; 23/3270 accepted as compatibility aliases)"
    tx = [
        ("CESN", "CONFIRMED", "LOGON_TRANSACTION"),
        ("CESL", "CONFIRMED", "LOGON_TRANSACTION"),
        ("CEMT", "DENIED", "SECURITY_PROTECTED"),
        ("CEDA", "DENIED", "SECURITY_PROTECTED"),
        ("CECI", "DENIED", "SECURITY_PROTECTED"),
        ("CEBR", "DISABLED", "TRANSACTION_DISABLED"),
        ("CEDF", "DENIED", "SECURITY_PROTECTED"),
        ("CSMT", "CONFIRMED", "SYSTEM_LOG_TRANSACTION"),
        ("DSNC", "INFERRED", "DB2_INTERFACE_PRESENT"),
    ]
    try:
        probe = env.state.cics_region.cicspwn_probe("IBMUSER") if hasattr(env.state, "cics_region") else None
        if isinstance(probe, dict) and probe:
            tx = []
            for name in ["CESN","CESL","CEMT","CEDA","CECI","CEBR","CEDF","CSMT","DSNC"]:
                detail = str(probe.get(name) or probe.get(name.lower()) or "")
                if name == "CEBR" and not detail: status, detail = "DISABLED", "TRANSACTION_DISABLED"
                elif name in {"CEMT","CEDA","CECI","CEDF"}: status, detail = "DENIED", detail or "SECURITY_PROTECTED"
                elif detail: status = "DENIED" if "DEN" in detail.upper() else "CONFIRMED"
                else: status, detail = "INFERRED", "STATE_NOT_EXPLICIT"
                tx.append((name, status, detail))
    except Exception:
        pass
    corr = _corr()
    lines = [
        "CICSPWN Gibson Safe CICS Assessment",
        "====================================",
        f"Target: {res.display}",
        f"Port: {port}",
        f"APPLID: {applid}",
        f"Mode: {mode}",
        f"Safe mode: {str(safe).lower()}",
        f"Correlation ID: {corr}",
        "",
        "[1] Discovery",
        "-------------",
        "[+] VTAM/USSTAB front-door prompt observed",
        f"[+] APPLID {applid} accepted for safe assessment",
        "",
        "[2] Transaction access",
        "----------------------",
    ]
    for name, status, detail in tx:
        lines.append(f"{name:<6} {status:<12} {detail}")
    lines += [
        "",
        "[3] Region/resource summary",
        "---------------------------",
        "Region:          GIBCICS",
        "Security:        ENABLED",
        "Resource groups: FIBS,DVCA,CBSA",
        "Visible files:   GIBSON.CICS.DFHCSD,GIBSON.CICS.SDFHLOAD",
        "Visible queues:  CSMT,CSSL",
        "",
        "[4] Capability assessment",
        "-------------------------",
        "Administrative path: DENIED - CEMT/CEDA protected",
        "Define/install path: DENIED - no install action performed",
        "Command-level path:  DENIED - CECI protected",
        "Debug path:          DENIED - CEDF protected",
        "DB2 interface path:  INFERRED - DSNC present; use DB2 labs for validation",
        "",
        "[5] Forensic correlation",
        "------------------------",
        f"SDSF/SMF correlation: {corr}",
        "OPERLOG: review simulated CICS transaction security events",
        "zSecure: review CICS exposure findings",
        "",
        "Result: BLOCKED - safe Gibson forensic assessment only",
        "No real exploit, shell, JCL submission, or program install is implemented.",
    ]
    try:
        if hasattr(env.state, "security_events"):
            env.state.security_events.append({"source":"CICSPWN","target":res.display,"port":port,"correlation_id":corr,"severity":"MEDIUM","message":"CICSPWN safe assessment executed"})
    except Exception:
        pass
    return "\n".join(lines)
