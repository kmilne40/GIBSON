"""Endevor package + separation-of-duties (SoD) bypass lab (roadmap Phase 3).

CA/Broadcom Endevor promotes element changes through stages (DEV -> TEST -> QA
-> PROD) inside a **package**: a unit of work that is CREATED, CAST (frozen),
APPROVED, then EXECUTED.  Change control demands *separation of duties* - the
engineer who creates and casts a package must NOT be the one who approves it.

The lab
-------
A developer ``DEVUSER`` has been mistakenly added to the package approver group
``#ENDVAPR`` (a real-world misconfiguration).  The lifecycle:

    ENDEVOR PACKAGE CREATE  PKGID system.subsystem.type.element [TO stage]
    ENDEVOR PACKAGE CAST    PKGID
    ENDEVOR PACKAGE APPROVE PKGID          <-- the SoD enforcement point
    ENDEVOR PACKAGE EXECUTE PKGID
    ENDEVOR PACKAGE LIST | DISPLAY PKGID

* **Vulnerable** (default): the SoD check is skipped, so the *creator* can
  approve their own package and execute it - code reaches PROD with no
  independent review (the classic change-control / SoD bypass).
* **Fixed**: self-approval is rejected (``C1G...E SEPARATION OF DUTIES``), an
  ICH408I/SMF audit event is cut, and EXECUTE requires an APPROVED package
  approved by a *different* member of the approver group.

Toggle: config ``endevor_sod_lab_vulnerable_mode`` /
env ``GIBSON_ENDEVOR_SOD_VULNERABLE`` (default vulnerable for training).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Package approver group.  DEVUSER is *mistakenly* a member - the seed of the
# bypass: a developer who can both author and approve a change.
PKG_APPROVER_GROUP = "#ENDVAPR"
PKG_APPROVERS = {"FIBSADM", "IBMUSER", "DEVUSER"}

_STAGE_NAME = {"D": "DEV", "T": "TEST", "Q": "QA", "P": "PROD"}


@dataclass
class Package:
    pkgid: str
    creator: str
    action: str = ""          # e.g. "MOVE BANKING.CORE.COBOL.ACCTPOST -> PROD"
    status: str = "IN-EDIT"   # IN-EDIT -> CAST -> APPROVED -> EXECUTED | DENIED
    approvals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    self_approved: bool = False


def _vulnerable(state: Any) -> bool:
    return bool(getattr(getattr(state, "config", None),
                        "endevor_sod_lab_vulnerable_mode", True))


def get_packages(state: Any) -> Dict[str, Package]:
    store = getattr(state, "endevor_packages", None)
    if store is None:
        store = {}
        try:
            state.endevor_packages = store
        except Exception:
            pass
    return store


def _audit(state: Any, userid: str, event: str, detail: str, *, result: str) -> None:
    try:
        state.record_security_event(
            userid, event, detail, result=result, service="ENDEVOR", terminal="3270")
    except Exception:
        pass


def _ready(line: str) -> str:
    return line


# --------------------------------------------------------------------------- #
#  Lifecycle verbs
# --------------------------------------------------------------------------- #
def pkg_create(state: Any, userid: str, pkgid: str, spec: str, to_stage: str) -> str:
    pkgs = get_packages(state)
    pkgid = pkgid.upper()
    if pkgid in pkgs:
        return f" C1X0001E  PACKAGE {pkgid} ALREADY EXISTS"
    tgt = _STAGE_NAME.get((to_stage or "P").upper()[:1], "PROD")
    action = f"MOVE {spec.upper()} -> {tgt}" if spec else f"PROMOTE -> {tgt}"
    pkgs[pkgid] = Package(pkgid=pkgid, creator=userid.upper(), action=action)
    _audit(state, userid, "ENDEVOR PACKAGE CREATE", f"{pkgid} {action}", result="SUCCESS")
    return (f" C1X0000I  PACKAGE {pkgid} CREATED IN-EDIT BY {userid.upper()}\n"
            f"           ACTION: {action}\n"
            f"           Next: ENDEVOR PACKAGE CAST {pkgid}")


def pkg_cast(state: Any, userid: str, pkgid: str) -> str:
    pkgs = get_packages(state)
    p = pkgs.get(pkgid.upper())
    if p is None:
        return f" C1X0002E  PACKAGE {pkgid.upper()} NOT FOUND"
    if p.status != "IN-EDIT":
        return f" C1X0003E  PACKAGE {p.pkgid} IS {p.status}; CANNOT CAST"
    p.status = "CAST"
    _audit(state, userid, "ENDEVOR PACKAGE CAST", p.pkgid, result="SUCCESS")
    return (f" C1X0004I  PACKAGE {p.pkgid} CAST AND READY FOR APPROVAL\n"
            f"           Approver group {PKG_APPROVER_GROUP} must APPROVE before EXECUTE.")


def pkg_approve(state: Any, userid: str, pkgid: str) -> str:
    """The separation-of-duties enforcement point."""
    pkgs = get_packages(state)
    p = pkgs.get(pkgid.upper())
    uid = userid.upper()
    if p is None:
        return f" C1X0002E  PACKAGE {pkgid.upper()} NOT FOUND"
    if p.status not in ("CAST", "APPROVED"):
        return f" C1X0005E  PACKAGE {p.pkgid} IS {p.status}; NOT IN APPROVAL"
    if uid not in PKG_APPROVERS:
        _audit(state, userid, "ENDEVOR PACKAGE APPROVE",
               f"{p.pkgid} NOT IN APPROVER GROUP {PKG_APPROVER_GROUP}", result="FAILURE")
        return (f" ICH408I USER({uid:<8}) GROUP(SYS1    ) NAME(########)\n"
                f"   PACKAGE {p.pkgid} CL(ENDEVOR )\n"
                f"   INSUFFICIENT ACCESS AUTHORITY\n"
                f" C1X0006E  {uid} IS NOT IN APPROVER GROUP {PKG_APPROVER_GROUP}")

    # --- Separation of duties: the creator must not approve their own package ---
    if uid == p.creator:
        if not _vulnerable(state):
            _audit(state, userid, "ENDEVOR SOD VIOLATION",
                   f"{p.pkgid} SELF-APPROVAL BY CREATOR {uid} DENIED", result="FAILURE")
            return (f" ICH408I USER({uid:<8}) GROUP({PKG_APPROVER_GROUP:<8}) NAME(########)\n"
                    f"   PACKAGE {p.pkgid} CL(ENDEVOR )\n"
                    f"   SEPARATION OF DUTIES - CREATOR MAY NOT APPROVE OWN PACKAGE\n"
                    f" C1X0007E  APPROVAL DENIED; A DIFFERENT APPROVER IS REQUIRED")
        # vulnerable: self-approval allowed (the bypass)
        p.self_approved = True
        _audit(state, userid, "ENDEVOR SOD BYPASS",
               f"{p.pkgid} SELF-APPROVED BY CREATOR {uid}", result="SUCCESS")

    if uid not in p.approvals:
        p.approvals.append(uid)
    p.status = "APPROVED"
    banner = ""
    if p.self_approved:
        banner = ("\n *** SEPARATION-OF-DUTIES BYPASS: package was created AND approved\n"
                  f" *** by the same engineer ({uid}); no independent review occurred.")
    _audit(state, userid, "ENDEVOR PACKAGE APPROVE", p.pkgid, result="SUCCESS")
    return (f" C1X0008I  PACKAGE {p.pkgid} APPROVED BY {uid}\n"
            f"           Approvals: {', '.join(p.approvals)}\n"
            f"           Next: ENDEVOR PACKAGE EXECUTE {p.pkgid}{banner}")


def pkg_execute(state: Any, userid: str, pkgid: str) -> str:
    pkgs = get_packages(state)
    p = pkgs.get(pkgid.upper())
    if p is None:
        return f" C1X0002E  PACKAGE {pkgid.upper()} NOT FOUND"
    if p.status != "APPROVED":
        return (f" C1X0009E  PACKAGE {p.pkgid} IS {p.status}; "
                f"AN APPROVED PACKAGE IS REQUIRED TO EXECUTE")
    p.status = "EXECUTED"
    result = (f" C1X0010I  PACKAGE {p.pkgid} EXECUTED\n"
              f"           {p.action}\n"
              f"           Approved by: {', '.join(p.approvals)}")
    if p.self_approved:
        _audit(state, userid, "ENDEVOR SOD BYPASS EXECUTE",
               f"{p.pkgid} PROMOTED TO PROD WITHOUT INDEPENDENT REVIEW", result="SUCCESS")
        result += ("\n *** Change reached PROD on a self-approved package -\n"
                   " *** the separation-of-duties control was bypassed.")
    else:
        _audit(state, userid, "ENDEVOR PACKAGE EXECUTE", p.pkgid, result="SUCCESS")
    return result


def pkg_list(state: Any) -> str:
    pkgs = get_packages(state)
    out = [" C1 PACKAGE LIST",
           " " + "-" * 64,
           " PACKAGE    CREATOR   STATUS     APPROVALS         SoD"]
    if not pkgs:
        out.append(" (no packages)")
    for p in sorted(pkgs.values(), key=lambda x: x.pkgid):
        sod = "SELF-APPROVED" if p.self_approved else ("OK" if p.approvals else "-")
        out.append(f" {p.pkgid:<10} {p.creator:<9} {p.status:<10} "
                   f"{(','.join(p.approvals) or '-'):<17} {sod}")
    return "\n".join(out)


def pkg_display(state: Any, pkgid: str) -> str:
    p = get_packages(state).get(pkgid.upper())
    if p is None:
        return f" C1X0002E  PACKAGE {pkgid.upper()} NOT FOUND"
    lines = [f" C1 PACKAGE {p.pkgid}",
             " " + "-" * 64,
             f"   CREATOR   : {p.creator}",
             f"   STATUS    : {p.status}",
             f"   ACTION    : {p.action}",
             f"   APPROVERS : {PKG_APPROVER_GROUP} = {', '.join(sorted(PKG_APPROVERS))}",
             f"   APPROVALS : {', '.join(p.approvals) or '(none)'}",
             f"   SoD       : {'SELF-APPROVED (bypass)' if p.self_approved else 'separate approver' if p.approvals else 'pending'}"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Command router: handle "PACKAGE ..." subverbs for endevor_command.
# --------------------------------------------------------------------------- #
def handle_package(state: Any, userid: str, rest: str) -> Optional[str]:
    """``rest`` is everything after the PACKAGE keyword.  Returns text or None."""
    toks = (rest or "").split()
    if not toks:
        return pkg_list(state)
    sub = toks[0].upper()
    if sub in ("LIST", "L"):
        return pkg_list(state)
    if sub in ("DISPLAY", "DIS", "D") and len(toks) >= 2:
        return pkg_display(state, toks[1])
    if sub in ("CREATE", "CRE") and len(toks) >= 3:
        # CREATE pkgid system.subsystem.type.element [TO stage]
        to_stage = "P"
        if "TO" in [t.upper() for t in toks]:
            i = [t.upper() for t in toks].index("TO")
            to_stage = toks[i + 1] if i + 1 < len(toks) else "P"
            spec = toks[2] if len(toks) > 2 else ""
        else:
            spec = toks[2]
        return pkg_create(state, userid, toks[1], spec, to_stage)
    if sub in ("CAST",) and len(toks) >= 2:
        return pkg_cast(state, userid, toks[1])
    if sub in ("APPROVE", "APP") and len(toks) >= 2:
        return pkg_approve(state, userid, toks[1])
    if sub in ("EXECUTE", "EXEC", "EX") and len(toks) >= 2:
        return pkg_execute(state, userid, toks[1])
    return (" C1 PACKAGE actions: CREATE pkgid elem [TO stage] | CAST pkgid |\n"
            "    APPROVE pkgid | EXECUTE pkgid | LIST | DISPLAY pkgid")
