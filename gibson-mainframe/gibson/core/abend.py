"""Authentic z/OS abend rendering (IEA995I SYMPTOM DUMP).

z/OS reports an abnormal end (ABEND) with a recognisable symptom dump: the
``IEA995I SYMPTOM DUMP OUTPUT`` eyecatcher, a ``SYSTEM COMPLETION CODE`` (and,
for system codes, a ``REASON CODE``), the PSW at the point of failure, and a
register dump. This module renders that text for the common completion-code
family so the simulator's abends read the way a systems programmer expects,
instead of a single ``ABENDED`` line.

It is a presentation helper only: it formats a documented diagnostic message
from a completion code and a little context. The codes and their meanings are
standard and public (IBM z/OS MVS System Codes). Nothing here changes control
flow or executes anything - callers pass the code they have already decided to
raise (e.g. a CICS ASRA / S0C4, an unfound module S806, a RACF denial S913).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AbendInfo:
    code: str                 # e.g. "0C7", "806", "913", "322", "0C4"
    kind: str                 # "SYSTEM" or "USER"
    reason: str               # reason code, hex, e.g. "00000004"
    desc: str                 # short human description
    psw: str = "078D1000 8A1C40C6"   # plausible PSW at time of error
    csect: str = "IGC0001C"   # failing CSECT (overridden per call)
    offset: str = "0000A1C4"  # offset into the CSECT


# code -> (kind, reason, description, default failing CSECT)
_CODES: Dict[str, tuple] = {
    "0C1": ("SYSTEM", "00000001", "OPERATION EXCEPTION", "IGC0001C"),
    "0C4": ("SYSTEM", "00000004", "PROTECTION EXCEPTION", "BNKUPD"),
    "0C7": ("SYSTEM", "00000007", "DATA EXCEPTION (INVALID DECIMAL DATA)", "PAYROL"),
    "806": ("SYSTEM", "00000004", "MODULE NOT FOUND (BLDL/LOAD FAILED)", "CONTENTS"),
    "813": ("SYSTEM", "00000004", "DATA SET OPEN - DSNAME/VOLSER MISMATCH", "OPEN"),
    "913": ("SYSTEM", "00000038", "RACF DATA SET ACCESS DENIED (READ/UPDATE)", "IFG0194E"),
    "322": ("SYSTEM", "00000000", "JOB OR STEP TIME LIMIT EXCEEDED", "IEAVTSDT"),
    "722": ("SYSTEM", "00000000", "OUTPUT (SYSOUT) LINE LIMIT EXCEEDED", "IEFRSTBL"),
    "B37": ("SYSTEM", "00000004", "DATA SET OUT OF SPACE - PRIMARY+SECONDARY FULL", "IGC0005E"),
    "D37": ("SYSTEM", "00000004", "DATA SET OUT OF SPACE - NO SECONDARY", "IGC0005E"),
    "E37": ("SYSTEM", "00000004", "DATA SET OUT OF SPACE - NO MORE VOLUMES", "IGC0005E"),
    "047": ("SYSTEM", "00000000", "UNAUTHORISED PROGRAM ISSUED RESTRICTED SVC", "IEAVEDS0"),
    "0CB": ("SYSTEM", "0000000B", "FIXED-POINT / DECIMAL DIVIDE EXCEPTION", "CALC"),
    # CICS surfaces ASRA as an S0C4-family program check
    "ASRA": ("SYSTEM", "00000004", "CICS PROGRAM CHECK (ASRA) - S0C4 PROTECTION", "DFHSRP"),
}

# A handful of realistic general-purpose register snapshots (R0-R15).
_DEFAULT_REGS = [
    "00000000 00006F30 008FD240 00006A18",
    "00006B40 008FCFF8 00000000 00FD6E88",
    "008FD0A0 00006C10 00000018 008FD1B8",
    "00006D88 8A1C4090 8A1C40C6 00006E70",
]


def lookup(code: str) -> AbendInfo:
    code = (code or "").strip().upper().lstrip("S").lstrip("U") or "0C7"
    kind, reason, desc, csect = _CODES.get(code, ("SYSTEM", "00000000", "ABNORMAL END", "IGC0001C"))
    return AbendInfo(code=code, kind=kind, reason=reason, desc=desc, csect=csect)


def symptom_dump(
    code: str,
    *,
    jobname: str = "IBMUSER",
    stepname: str = "STEP1",
    progname: Optional[str] = None,
    reason: Optional[str] = None,
    regs: Optional[List[str]] = None,
) -> str:
    """Render an IEA995I SYMPTOM DUMP for ``code`` (e.g. "S0C7", "806", "ASRA").

    Returns the multi-line dump text. ``progname`` overrides the failing CSECT;
    ``reason`` overrides the reason code; ``regs`` overrides the GPR snapshot.
    """
    info = lookup(code)
    csect = (progname or info.csect)[:8].upper()
    rsn = reason or info.reason
    reg_rows = regs or _DEFAULT_REGS
    cc_line = (
        f" SYSTEM COMPLETION CODE={info.code}  REASON CODE={rsn}"
        if info.kind == "SYSTEM"
        else f" USER COMPLETION CODE={info.code}"
    )
    # CICS surfaces a program check as ASRA over an underlying S0C4/S0C7;
    # show the system code the dump actually reports.
    if info.code == "ASRA":
        cc_line = " SYSTEM COMPLETION CODE=0C4  REASON CODE=00000004  (CICS ASRA - PROGRAM CHECK)"
    # Module line wording depends on the failure: a module-load/open failure
    # genuinely has no active module; an execution-time program check (S0C7,
    # S0C4, ...) abended *inside* a loaded module, so name it as active.
    if info.code in ("806", "813", "806-04"):
        module_line = f"   NO ACTIVE MODULE FOUND  NAME={csect}  OFFSET={info.offset}"
    else:
        module_line = f"   ACTIVE LOAD MODULE           ADDRESS=8A1C4000  NAME={csect}  OFFSET={info.offset}"
    lines = [
        "IEA995I SYMPTOM DUMP OUTPUT",
        cc_line,
        f"  {info.desc}",
        f" TIME=NOW  SEQ=00001  CPU=0000  ASID=002B",
        f" PSW AT TIME OF ERROR  {info.psw}  ILC 6  INTC 0007",
        module_line,
        f"   DATA AT PSW  {info.psw[:8]}. - 47F0F014 41100001 1B11",
        " GPR 0-3   " + reg_rows[0],
        " GPR 4-7   " + reg_rows[1 % len(reg_rows)],
        " GPR 8-11  " + reg_rows[2 % len(reg_rows)],
        " GPR 12-15 " + reg_rows[3 % len(reg_rows)],
        f" END OF SYMPTOM DUMP  JOB {jobname} STEP {stepname}",
    ]
    return "\n".join(lines)


def abend_block(
    code: str,
    *,
    jobname: str = "IBMUSER",
    stepname: str = "STEP1",
    progname: Optional[str] = None,
    reason: Optional[str] = None,
    with_jcl_messages: bool = True,
) -> str:
    """Full operator/JES view of an abend: the IEFxxx step-completion line, the
    symptom dump, and a SYSUDUMP-taken note - the way it appears in a job log."""
    info = lookup(code)
    head = []
    if with_jcl_messages:
        head = [
            f"IEF450I {jobname} {stepname} - ABEND=S{info.code} U0000 REASON={info.reason}",
            f"         TIME=NOW",
        ]
    dump = symptom_dump(code, jobname=jobname, stepname=stepname,
                        progname=progname, reason=reason)
    tail = ["IEA995I SYSUDUMP TAKEN TO SYS00001"]
    return "\n".join(head + [dump] + tail)
