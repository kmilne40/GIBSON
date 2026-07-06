"""Simulated CICS post-exploitation shell (training artifact).

When the real cicspwn tool drives the SPOOLOPEN/SPOOLWRITE/SPOOLCLOSE
JCL-submission path against Gibson's CICS region, the engine registers a
"shell" record in ``state.cics_pwn_shells``.  This module surfaces that record
as a *simulated* interactive shell for the security class.

It is explicitly a canned teaching artifact: nothing here executes host code,
opens a network connection, or touches a real system.  It illustrates what a
post-exploitation session would look like so students can study and detect it.
"""
from __future__ import annotations

from typing import Any, Iterable

_BANNER = "GIBSON LAB - SIMULATED CICS POST-EXPLOITATION SHELL (training only; no host code runs)"


def _active(state) -> list:
    return [s for s in getattr(state, "cics_pwn_shells", []) or [] if s.get("active")]


def _canned(cmd: str, sess: dict) -> str:
    c = (cmd or "").strip()
    low = c.lower()
    region_user = sess.get("userid", "CICSUSER")
    if low in ("", "help", "?"):
        return ("commands: id  whoami  env  pwd  ls [hlq]  cat <dsn>  listuser <id>  "
                "racf  history  exit\n(all output is simulated for the lab)")
    if low in ("id", "whoami"):
        return (f"{region_user}  uid=0(region)  groups=CICS,SYS1\n"
                "running with the CICS region's authority - the region can act as any "
                "user because RACF surrogate/region access was abused (simulated)")
    if low == "env":
        return ("_BPX_SHAREAS=YES\nSTEPLIB=GIBSON.CICS.SDFHLOAD\n"
                "APPLID=CICS\nSYSID=GIB1\nUSER=" + region_user)
    if low == "pwd":
        return "/u/" + region_user.lower()
    if low.startswith("ls"):
        return ("SYS1.PARMLIB\nSYS1.PROCLIB\nGIBSON.CICS.SDFHLOAD\n"
                "GIBSON.BANK.ACCOUNTS\nSYS1.RACFDS  (RACF database - simulated)")
    if low.startswith("cat"):
        target = c[3:].strip() or "SYS1.PARMLIB(IEASYS00)"
        if "RACF" in target.upper() or "GACF" in target.upper():
            return ("IBMUSER  SPECIAL OPERATIONS OMVS(UID=0) PASSWORD=********\n"
                    "GUEST    NONE OMVS(UID=99) PASSWORD=********\n"
                    "(simulated RACF DB extract - illustrates impact, not real hashes)")
        return f"* simulated contents of {target}\nSYS=(GIBSON),CLOCK=00\n"
    if low.startswith("listuser") or low == "racf":
        return ("USER=IBMUSER  SPECIAL OPERATIONS  OWNER=SYS1\n"
                " ATTRIBUTES=SPECIAL OPERATIONS\n"
                " (region authority can read/alter RACF profiles - simulated)")
    if low == "history":
        return "\n".join(s.get("corrid", "") for s in [sess])
    return f"{c}: simulated - command acknowledged, no host code executed"


def run_cics_shell(state: Any, argv: Iterable[str], env: Any, cwd: str) -> str:
    args = list(argv)
    sessions = _active(state)
    if args and args[0] in ("-l", "--list", "list", "sessions"):
        alls = getattr(state, "cics_pwn_shells", []) or []
        if not alls:
            return "cicsshell: no CICS shell sessions recorded. Run a cicspwn code-exec / SPOOLCLOSE first."
        out = ["Recorded simulated CICS shell sessions:"]
        for s in alls:
            out.append(f"  {s.get('time','')}  {s.get('jobname','')}/{s.get('jobid','')}  "
                       f"user={s.get('userid','')}  payload={s.get('payload','')}  "
                       f"{'ACTIVE' if s.get('active') else 'closed'}  corrid={s.get('corrid','')}")
        return "\n".join(out)
    if not sessions:
        return ("cicsshell: no active simulated CICS shell.\n"
                "Trigger one by running cicspwn code-execution against L CICS "
                "(SPOOLOPEN/SPOOLWRITE/SPOOLCLOSE with a REXX/JCL payload), then re-run cicsshell.\n"
                "Use 'cicsshell --list' to see recorded sessions.")
    sess = sessions[-1]
    header = [
        _BANNER,
        f"Region: {sess.get('region','CICSGIB1')}   Applid: {sess.get('applid','CICS')}   "
        f"Running as: {sess.get('userid','CICSUSER')} (CICS region authority)",
        f"Origin: {sess.get('jobname','GIBPWN')}/{sess.get('jobid','')} via INTRDR  corrid={sess.get('corrid','')}",
        "-" * 78,
    ]
    cmd = " ".join(args)
    if cmd.strip().lower() in ("exit", "quit", "logoff"):
        sess["active"] = False
        return "\n".join(header + ["$ exit", "simulated shell closed."])
    body = _canned(cmd, sess)
    prompt = f"$ {cmd}" if cmd else "$"
    return "\n".join(header + [prompt, body])
