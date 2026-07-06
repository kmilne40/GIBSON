"""MVP - the MVS/CE software package manager, as a Gibson TSO command.

Invoked the way the real tool is, via the REXX exec runner::

    RX MVP UPDATE
    RX MVP LIST [--installed]
    RX MVP SEARCH ftp
    RX MVP SHOW FTPD            (alias INFO)
    RX MVP INSTALL FTPD         (resolves dependencies, submits jobs, checks CC 0000)

A bare ``MVP ...`` is also accepted.  INSTALL is gated on read access to the RAKF
``BRXMTTAUTH`` resource in the FACILITY class (the real MVP requires this); an
unauthorised user gets an authentic ICH408I and the install is refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set

from gibson.apps.mvp.catalog import CATALOG, Package

_FACILITY = "FACILITY"
_AUTH_RESOURCE = "BRXMTTAUTH"
_AUTH_GROUP_USERS = ("IBMUSER", "MVP", "ADMIN")   # permitted to install


@dataclass
class MvpState:
    installed: Set[str] = field(default_factory=set)
    cache_loaded: bool = False
    job_seq: int = 12000


def get_mvp_state(state: Any) -> MvpState:
    st = getattr(state, "mvp", None)
    if st is None:
        st = MvpState()
        try:
            state.mvp = st
        except Exception:
            pass
    _ensure_auth_profile(state)
    return st


def _ensure_auth_profile(state: Any) -> None:
    dr = getattr(state, "dynamic_racf", None)
    if dr is None:
        return
    try:
        if dr._find_profile(_FACILITY, _AUTH_RESOURCE) is None:
            dr.define(_FACILITY, _AUTH_RESOURCE, owner="MVP", uacc="NONE")
        prof = dr._find_profile(_FACILITY, _AUTH_RESOURCE)
        for u in _AUTH_GROUP_USERS:
            prof.permits.setdefault(u, "READ")
    except Exception:
        pass


def _install_authorised(state: Any, userid: str) -> tuple[bool, str]:
    dr = getattr(state, "dynamic_racf", None)
    if dr is None:
        return True, ""
    try:
        dec = dr.access_decision(_FACILITY, _AUTH_RESOURCE, userid, "READ", getattr(state, "racf", None))
    except Exception:
        return True, ""
    if dec.allowed:
        return True, ""
    msg = (f"ICH408I USER({userid.upper():<8}) GROUP(MVP     ) NAME(########)\n"
           f"  {_AUTH_RESOURCE} CL({_FACILITY:<8})\n"
           f"  INSUFFICIENT ACCESS AUTHORITY\n"
           f"  ACCESS INTENT(READ  )  PERMITTED(NONE   )")
    return False, msg


# --------------------------------------------------------------------------- #
#  Dependency resolution
# --------------------------------------------------------------------------- #
def _resolve(names: List[str]) -> tuple[List[str], List[str]]:
    """Return (ordered install list incl. deps, unknown names)."""
    order: List[str] = []
    unknown: List[str] = []
    seen: Set[str] = set()

    def visit(n: str, stack: Set[str]):
        key = n.upper()
        if key in seen:
            return
        pkg = CATALOG.get(key)
        if pkg is None:
            if key not in unknown:
                unknown.append(key)
            return
        for dep in pkg.depends:
            if dep.upper() not in stack:
                visit(dep, stack | {key})
        seen.add(key)
        order.append(key)

    for n in names:
        visit(n, set())
    return order, unknown


# --------------------------------------------------------------------------- #
#  Rendering
# --------------------------------------------------------------------------- #
_USAGE = "\n".join([
    "MVP - MVS/CE package manager",
    "Usage:  RX MVP <command> [options]",
    "  UPDATE                 refresh the package cache",
    "  LIST [--installed]     list available (or installed) packages",
    "  SEARCH <term>          search names and descriptions",
    "  SHOW | INFO <pkg>      show package detail (Depends, Maintainer, ...)",
    "  INSTALL <pkg> [<pkg>]  install package(s) and dependencies",
    "  -h | --help            this help",
])


def _list(mvp: MvpState, installed_only: bool) -> str:
    rows = ["Package          Type  Version   Status",
            "---------------- ----- --------- ----------"]
    for name in sorted(CATALOG):
        pkg = CATALOG[name]
        inst = name in mvp.installed
        if installed_only and not inst:
            continue
        status = "installed" if inst else "available"
        rows.append(f"{pkg.name:<16} {pkg.type:<5} {pkg.version:<9} {status}")
    total = len(mvp.installed) if installed_only else len(CATALOG)
    rows.append(f"-- {total} package(s) " + ("installed" if installed_only else "available") + " --")
    return "\n".join(rows)


def _search(term: str) -> str:
    t = term.lower()
    hits = [p for p in CATALOG.values() if t in p.name.lower() or t in p.description.lower()]
    if not hits:
        return f"MVP: no packages match '{term}'"
    rows = [f"{p.name:<16} {p.type:<5} {p.version:<9} {p.description}" for p in sorted(hits, key=lambda x: x.name)]
    return "\n".join(rows)


def _show(name: str, mvp: MvpState) -> str:
    pkg = CATALOG.get(name.upper())
    if pkg is None:
        return f"MVP: package {name.upper()} not found in cache (try: RX MVP SEARCH {name})"
    return "\n".join([
        f"Package:      {pkg.name}",
        f"Version:      {pkg.version}",
        f"Type:         {pkg.type}",
        f"Maintainer:   {pkg.maintainer}",
        f"Depends:      {', '.join(pkg.depends) if pkg.depends else '(none)'}",
        f"Homepage:     {pkg.homepage}",
        f"Status:       {'installed' if pkg.name in mvp.installed else 'not installed'}",
        f"Description:  {pkg.description}",
    ])


def _job(mvp: MvpState) -> str:
    mvp.job_seq += 1
    return f"JOB{mvp.job_seq:05d}"


def _install_jcl(pkg: Package, job: str) -> str:
    return (
        f"//{pkg.name[:8]:<8} JOB (ACCT),'MVP INSTALL',CLASS=A,MSGCLASS=A\n"
        f"//* MVP package {pkg.name} {pkg.version} ({pkg.type}) - {pkg.maintainer}\n"
        f"//* {pkg.description}\n"
        f"//RECV    EXEC PGM=IKJEFT01\n"
        f"//SYSTSPRT DD SYSOUT=*\n"
        f"//SYSTSIN  DD *\n"
        f"  RECEIVE INDSN('MVP.XMIT.{pkg.name[:8]}')\n"
        f"  DA('{pkg.name[:8]}.INSTALL')\n"
        f"/*\n")


def _install_one(state: Any, userid: str, mvp: MvpState, pkg: Package) -> List[str]:
    job = _job(mvp)
    is_rexx = bool(getattr(pkg, "rexx", ""))
    uid = (userid or "IBMUSER").upper()
    target_ds = f"{uid}.MVP.EXEC" if is_rexx else f"{uid}.MVP.CNTL"
    member = pkg.name[:8].upper()
    steps = ["RECV", "ALLOC", "APPLY"] if pkg.type == "XMI" else ["ALLOC", "RUN"]
    out = [
        f"MVP: submitting installation job for {pkg.name} {pkg.version} ({pkg.type}) ...",
        f"{job}  $HASP373 {pkg.name:<8} STARTED - INIT 1 - CLASS A",
    ]
    for st in steps:
        out.append(f"IEF142I {pkg.name[:8]:<8} {st:<5} - STEP WAS EXECUTED - COND CODE 0000")
    # materialise the package into a real dataset member the user can browse / run
    written = False
    try:
        body = pkg.rexx if is_rexx else _install_jcl(pkg, job)
        state.datasets.write(userid, f"{target_ds}({member})", body)
        written = True
    except Exception:
        written = False
    out.append(f"{job}  $HASP395 {pkg.name:<8} ENDED - MAXCC=0000")
    if written:
        out.append(f"MVP: {pkg.name} {pkg.version} installed into {target_ds}({member})")
        if is_rexx:
            out.append(f"MVP: run it with   EX '{target_ds}({member})'   or   %{member}")
    else:
        out.append(f"MVP: {pkg.name} {pkg.version} installed successfully (MAXCC=0000)")
    mvp.installed.add(pkg.name)
    return out


def _install(state: Any, userid: str, mvp: MvpState, names: List[str], debug: bool) -> str:
    ok, denial = _install_authorised(state, userid)
    if not ok:
        _audit(state, userid, "MVP INSTALL", f"PKG={','.join(names)}", "FAILURE")
        return "\n".join(["MVP: INSTALL requires READ access to FACILITY BRXMTTAUTH (RAKF).",
                          denial, "MVP: installation refused."])
    order, unknown = _resolve(names)
    lines: List[str] = []
    if unknown:
        lines.append("MVP: unknown package(s): " + ", ".join(unknown))
    to_do = [n for n in order if n not in mvp.installed]
    already = [n for n in order if n in mvp.installed]
    for n in already:
        lines.append(f"MVP: {n} is already installed (skipping)")
    if not to_do:
        if not unknown:
            lines.append("MVP: nothing to do.")
        return "\n".join(lines)
    deps = [n for n in to_do if n.upper() not in {x.upper() for x in names}]
    if deps:
        lines.append("MVP: the following dependencies will also be installed: " + ", ".join(deps))
    if debug:
        lines.append("MVP[debug]: install order = " + " -> ".join(to_do))
    for n in to_do:
        lines.extend(_install_one(state, userid, mvp, CATALOG[n]))
    _audit(state, userid, "MVP INSTALL", f"PKG={','.join(to_do)}", "SUCCESS")
    lines.append("MVP: " + str(len(to_do)) + " package(s) installed.")
    return "\n".join(lines)


def _audit(state: Any, userid: str, event: str, detail: str, result: str) -> None:
    try:
        state.record_security_event(userid, event, detail, result=result,
                                    service="MVP", terminal="TSO")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
#  Command entry
# --------------------------------------------------------------------------- #
def mvp_command(state: Any, userid: str, cmd: str) -> Optional[str]:
    raw = (cmd or "").strip()
    u = raw.upper()
    # accept "RX MVP ..." and bare "MVP ..."
    if u.startswith("RX "):
        rest = raw[3:].strip()
        if not rest.upper().startswith("MVP"):
            return None
        raw = rest
        u = raw.upper()
    if not (u == "MVP" or u.startswith("MVP ")):
        return None

    mvp = get_mvp_state(state)
    args = raw.split()[1:]            # drop the MVP verb
    if not args or args[0] in ("-h", "--help", "HELP", "?"):
        return _USAGE
    verb = args[0].upper()
    rest = args[1:]
    debug = any(a in ("-d", "--debug") for a in rest)
    rest = [a for a in rest if a not in ("-d", "--debug")]

    if verb == "UPDATE":
        mvp.cache_loaded = True
        return (f"MVP: refreshing package cache ...\n"
                f"MVP: cache updated - {len(CATALOG)} package(s) available.")
    if verb == "LIST":
        installed_only = any(a in ("--installed", "-i") for a in rest)
        return _list(mvp, installed_only)
    if verb == "SEARCH":
        if not rest:
            return "MVP: SEARCH requires a term"
        return _search(" ".join(rest))
    if verb in ("SHOW", "INFO"):
        if not rest:
            return "MVP: SHOW requires a package name"
        return _show(rest[0], mvp)
    if verb == "INSTALL":
        if not rest:
            return "MVP: INSTALL requires a package name"
        return _install(state, userid, mvp, rest, debug)
    if verb in ("INSTALL_MVP", "BOOTSTRAP"):
        return ("MVP: bootstrap complete - MVP user defined with a random password.\n"
                "MVP: run 'RX MVP UPDATE' then 'RX MVP LIST'.")
    return f"MVP: unknown command '{verb}'\n{_USAGE}"
