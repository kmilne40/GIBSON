"""IMS Connect / OTMA security lab.

Models the IMS Connect TCP/IP gateway and the OTMA (Open Transaction Manager
Access) message pipe in front of an IMS TM system.  The teaching point is the
classic exposure: IMS Connect flows a *client-supplied* userid to IMS, and when
OTMA security is ``NONE`` (or no RACF resource profiles exist) anyone who can
reach the gateway can inject transactions and operator commands under a chosen
identity.

Security model (``/SECURE OTMA`` levels):

* ``NONE``  - OTMA makes no RACF calls; the client userid is trusted as-is.
              Transactions and commands run with no authorization.  (THE LEAK.)
* ``CHECK`` - RACF authorizes transactions against class ``TIMS``; operator
              commands are still accepted.
* ``FULL``  - RACF authorizes transactions (``TIMS``), operator commands
              (``CIMS``) and resume-TPIPE / async output (``RIMS``).

The lab's before/after toggle (``ims_otma_lab_vulnerable_mode``):

* vulnerable (default) -> ``/SECURE OTMA NONE``, no TIMS/CIMS/RIMS profiles.
* fixed                -> ``/SECURE OTMA FULL`` with the profiles defined and
                          permitted to the legitimate IMS users only.

Authorization uses the real Gibson dynamic-RACF general-resource store, so a
denial produces an authentic ``ICH408I`` and an SMF type-80 record, exactly like
the dataset and Endevor paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

_HWS = "HWS1"            # IMS Connect (Host Web Services) datastore/member name
_IMSID = "IMS1"          # IMS TM subsystem id
_CONNECT_PORT = 9999     # IMS Connect listening port
_OTMA_LEVELS = ("NONE", "CHECK", "FULL")
# Legitimate identities permitted in fixed mode.
_PERMITTED = ("IMSUSER", "IBMUSER")
_OPERATORS = ("IMSOPER", "IBMUSER")


@dataclass
class ImsTransaction:
    code: str
    program: str
    psb: str
    cls: str = "1"
    status: str = "STARTED"      # STARTED / STOPPED
    privileged: bool = False     # update transactions (vs read-only inquiry)
    reply: str = ""              # canned application reply


@dataclass
class ImsState:
    otma_security: str = "NONE"
    datastore: str = _HWS
    imsid: str = _IMSID
    port: int = _CONNECT_PORT
    transactions: dict = field(default_factory=dict)
    databases: dict = field(default_factory=dict)   # dbd -> status
    tpipes: dict = field(default_factory=dict)       # tpipe -> queued async msgs
    profiles_defined: bool = False


def _now() -> str:
    return datetime.now().strftime("%y.%j %H:%M:%S")


# --------------------------------------------------------------------------- #
#  State / seeding
# --------------------------------------------------------------------------- #
def get_ims_state(state: Any) -> ImsState:
    st = getattr(state, "ims", None)
    if st is not None:
        return st
    st = ImsState()
    st.transactions = {
        "PART":   ImsTransaction("PART", "DFSSAM02", "DFSSAM02", "1",
                                 reply="PART NUMBER 02BBBBBBBBB02   STOCK 0083  AREA SAN JOSE"),
        "DSPINV": ImsTransaction("DSPINV", "DFSSAM03", "DFSSAM03", "1",
                                 reply="INVENTORY DISPLAY - 0083 ON HAND, 0012 ON ORDER"),
        "ADDINV": ImsTransaction("ADDINV", "DFSSAM04", "DFSSAM04", "2", privileged=True,
                                 reply="ADDINV COMPLETE - INVENTORY UPDATED"),
        "ADDPART": ImsTransaction("ADDPART", "DFSSAM05", "DFSSAM05", "2", privileged=True,
                                  reply="ADDPART COMPLETE - PART MASTER UPDATED"),
        "DLETINV": ImsTransaction("DLETINV", "DFSSAM06", "DFSSAM06", "2", privileged=True,
                                  reply="DLETINV COMPLETE - INVENTORY RECORD DELETED"),
        "IVTNO":  ImsTransaction("IVTNO", "DFSIVP31", "DFSIVP37", "4",
                                 reply="IVTNO     ENTRY WAS DISPLAYED  LAST=A1234567"),
    }
    st.databases = {"DI21PART": "OPEN", "DI21INV": "OPEN", "IVPDB1": "OPEN"}
    # initial OTMA security follows the lab toggle
    vuln = bool(getattr(getattr(state, "config", None), "ims_otma_lab_vulnerable_mode", True))
    _apply_security(state, st, "NONE" if vuln else "FULL")
    try:
        state.ims = st
    except Exception:
        pass
    return st


def _profiles(ims: ImsState):
    """RACF general-resource profiles the fixed configuration defines."""
    tims = [(t, list(_PERMITTED)) for t in ims.transactions]
    cims = [(c, list(_OPERATORS)) for c in ("DIS", "STA", "STO", "DBR", "START", "STOP", "BRO")]
    rims = [(f"{ims.datastore}.RESUME", list(_PERMITTED))]
    return tims, cims, rims


def _apply_security(state: Any, ims: ImsState, level: str) -> None:
    """Set the OTMA security level and (de)define the RACF resource profiles."""
    level = level.upper()
    if level not in _OTMA_LEVELS:
        return
    ims.otma_security = level
    dr = getattr(state, "dynamic_racf", None)
    if dr is None:
        return
    tims, cims, rims = _profiles(ims)
    if level == "NONE":
        # The vulnerable posture: tear the profiles down so even a stray check
        # would find UACC(NONE)-less, undefined resources.
        for cls, items in (("TIMS", tims), ("CIMS", cims), ("RIMS", rims)):
            for name, _u in items:
                try:
                    dr.profiles.get(cls, {}).pop(name.upper(), None)
                except Exception:
                    pass
        ims.profiles_defined = False
        return
    # CHECK / FULL: define the profiles UACC(NONE) and permit the right users.
    for cls, items in (("TIMS", tims), ("CIMS", cims), ("RIMS", rims)):
        for name, users in items:
            try:
                if dr._find_profile(cls, name) is None:
                    dr.define(cls, name, owner="IMSADMIN", uacc="NONE")
                prof = dr._find_profile(cls, name)
                for u in users:
                    prof.permits[u.upper()] = "READ"
            except Exception:
                pass
    ims.profiles_defined = True


# --------------------------------------------------------------------------- #
#  Authorization (RACROUTE REQUEST=AUTH against TIMS / CIMS / RIMS)
# --------------------------------------------------------------------------- #
def _ich408i(userid: str, cls: str, resource: str, intent: str = "READ") -> str:
    return (f"ICH408I USER({userid.upper():<8}) GROUP(IMSGRP  ) NAME(########)\n"
            f"  {resource} CL({cls:<8})\n"
            f"  INSUFFICIENT ACCESS AUTHORITY\n"
            f"  ACCESS INTENT({intent:<6})  PERMITTED(NONE   )")


def _authorize(state: Any, ims: ImsState, userid: str, cls: str, resource: str) -> tuple[bool, str]:
    """Return (allowed, racf_message).  NONE bypasses RACF entirely."""
    if ims.otma_security == "NONE":
        return True, ""
    dr = getattr(state, "dynamic_racf", None)
    if dr is None:
        return True, ""
    try:
        dec = dr.access_decision(cls, resource, userid, "READ", getattr(state, "racf", None))
    except Exception:
        return True, ""
    if dec.allowed:
        return True, ""
    return False, _ich408i(userid, cls, resource)


def _audit(state: Any, userid: str, event: str, detail: str, result: str) -> None:
    try:
        state.record_security_event(userid, event, detail, result=result,
                                    service="IMS-CONNECT", terminal="OTMA")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
#  Rendering
# --------------------------------------------------------------------------- #
def _primary_panel(ims: ImsState) -> str:
    return "\n".join([
        " IMS CONNECT / OTMA  -  PRIMARY OPTIONS                          " + _now(),
        " -------------------------------------------------------------------------------",
        f"   Datastore . : {ims.datastore}        IMSID . . : {ims.imsid}        Port : {ims.port}",
        f"   OTMA security : /SECURE OTMA {ims.otma_security}",
        "",
        "   Submit work through the gateway:",
        "     IMS STATUS                         Connect / OTMA status + RACF classes",
        "     IMS SUBMIT trancode [data] [AS userid]   Send a transaction via OTMA",
        "     IMS CMD /DIS A | /STA | /STO | /DBR ...  Send an IMS command via OTMA",
        "     IMS RESUME tpipe                   Retrieve async output (resume-TPIPE)",
        "     IMS SECURE OTMA NONE|CHECK|FULL    Set the OTMA security level",
        "     IMS AUDIT                          OTMA security posture audit",
        "     IMS DB                             IMS DB / DL/I hierarchical database lab",
        "",
        "   'AS userid' supplies the OTMA client userid - the trust boundary the lab",
        "   demonstrates.  With /SECURE OTMA NONE it is accepted with no RACF call.",
    ])


def _status(ims: ImsState) -> str:
    lines = [
        f"HWSC0000I  IMS CONNECT {ims.datastore} ACTIVE   PORT={ims.port}  IMSID={ims.imsid}",
        f"           OTMA MEMBER {ims.datastore} - CONNECTED  TPIPE STATUS ACTIVE",
        f"           /SECURE OTMA {ims.otma_security}",
        f"           RACF CLASSES TIMS/CIMS/RIMS: {'ACTIVE' if ims.profiles_defined else 'NOT DEFINED'}",
        " -------------------------------------------------------------------------------",
        " TRANCODE  PROGRAM   PSB       CL  STATUS    AUTH(TIMS)",
    ]
    for t in ims.transactions.values():
        auth = "n/a" if ims.otma_security == "NONE" else ("PROFILE" if ims.profiles_defined else "UNDEFINED")
        lines.append(f"   {t.code:<8}{t.program:<10}{t.psb:<10}{t.cls:<4}{t.status:<10}{auth}")
    lines.append(" DATABASES: " + "  ".join(f"{d}({s})" for d, s in ims.databases.items()))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Actions
# --------------------------------------------------------------------------- #
def _submit_transaction(state: Any, ims: ImsState, caller: str, trancode: str,
                        as_user: str, data: str) -> str:
    code = trancode.upper()
    tran = ims.transactions.get(code)
    eff_user = (as_user or caller).upper()
    if tran is None:
        _audit(state, eff_user, "IMS OTMA TX", f"TRAN={code} UNKNOWN", "FAILURE")
        return f"DFS064I  TRANCODE {code} NOT DEFINED OR NOT STARTED - INPUT REJECTED"
    if tran.status == "STOPPED":
        return f"DFS065I  TRANCODE {code} IS STOPPED - INPUT REJECTED"
    allowed, racf = _authorize(state, ims, eff_user, "TIMS", code)
    spoofed = bool(as_user) and as_user.upper() != caller.upper()
    if not allowed:
        _audit(state, eff_user, "IMS OTMA TX", f"TRAN={code} CL=TIMS", "FAILURE")
        return ("\n".join([
            f"DFS3662W  OTMA SECURITY VIOLATION - TRANSACTION {code} REJECTED",
            racf,
        ]))
    # authorized (or NONE): the transaction is scheduled and replies
    note = ""
    if ims.otma_security == "NONE":
        note = (f"\n *** OTMA SECURITY NONE: client userid {eff_user} accepted with no RACF call"
                + (f" (spoofed by {caller.upper()})" if spoofed else "") + " ***")
        if tran.privileged:
            note += f"\n *** UPDATE transaction {code} executed by unauthenticated client ***"
    _audit(state, eff_user, "IMS OTMA TX", f"TRAN={code} PGM={tran.program}", "SUCCESS")
    return "\n".join([
        f"HWSC0001I  MESSAGE ACCEPTED - TPIPE={ims.datastore} USERID={eff_user}",
        f"DFS058I  {_now()}  TRANSACTION {code} SCHEDULED PSB {tran.psb} REGION 0001",
        f"   {tran.reply}",
        f"DFS058I  TRANSACTION {code} COMPLETED",
    ]) + note


_CMD_RESOURCE = {"/DIS": "DIS", "/DISPLAY": "DIS", "/STA": "STA", "/START": "START",
                 "/STO": "STO", "/STOP": "STOP", "/DBR": "DBR", "/DBRECOVERY": "DBR",
                 "/BRO": "BRO", "/BROADCAST": "BRO"}


def _submit_command(state: Any, ims: ImsState, caller: str, cmd: str, as_user: str) -> str:
    eff_user = (as_user or caller).upper()
    parts = cmd.split()
    verb = parts[0].upper() if parts else ""
    res = _CMD_RESOURCE.get(verb)
    if res is None:
        return f"DFS1292E  COMMAND {verb} NOT RECOGNISED BY OTMA"
    # CIMS command authorization only at FULL
    if ims.otma_security == "FULL":
        allowed, racf = _authorize(state, ims, eff_user, "CIMS", res)
        if not allowed:
            _audit(state, eff_user, "IMS OTMA CMD", f"CMD={verb} CL=CIMS", "FAILURE")
            return "\n".join([
                f"DFS3662W  OTMA SECURITY VIOLATION - COMMAND {verb} REJECTED",
                racf,
            ])
    spoof = bool(as_user) and as_user.upper() != caller.upper()
    note = ""
    if ims.otma_security in ("NONE", "CHECK"):
        why = "NONE: no RACF call" if ims.otma_security == "NONE" else "CHECK: commands not authorized at this level"
        note = f"\n *** OTMA SECURITY {why}; command run as {eff_user}" + \
               (f" (spoofed by {caller.upper()})" if spoof else "") + " ***"
    out = _run_command(ims, parts)
    _audit(state, eff_user, "IMS OTMA CMD", f"CMD={cmd.strip()}", "SUCCESS")
    return out + note


def _run_command(ims: ImsState, parts: list) -> str:
    verb = parts[0].upper()
    arg = " ".join(parts[1:]).upper()
    if verb in ("/DIS", "/DISPLAY"):
        if arg.startswith("A") or arg in ("ACTIVE", ""):
            return "\n".join([
                "DFS000I  REGID  JOBNAME  TYPE   TRAN/STEP   STATUS",
                "DFS000I  0001   IMS1DEP  TP     PART        WAIT-INPUT",
                "DFS000I  0002   IMS1BMP  BMP    IVTNO       ACTIVE",
                "*89001/140233*",
            ])
        if arg.startswith("TRAN"):
            tn = arg.split()[-1]
            t = ims.transactions.get(tn)
            if t:
                return f"DFS000I  TRAN {t.code}  CLS {t.cls}  PGM {t.program}  {t.status}\n*89001/140233*"
            return f"DFS000I  TRAN {tn} NOT FOUND\n*89001/140233*"
        if arg.startswith("DB"):
            return "DFS000I  " + "  ".join(f"{d} {s}" for d, s in ims.databases.items()) + "\n*89001/140233*"
        return "DFS000I  DISPLAY COMPLETE\n*89001/140233*"
    if verb in ("/STO", "/STOP") and arg.startswith("TRAN"):
        tn = arg.split()[-1]
        if tn in ims.transactions:
            ims.transactions[tn].status = "STOPPED"
            return f"DFS058I  {_now()}  STOP COMMAND COMPLETED - TRAN {tn} STOPPED"
        return f"DFS000I  TRAN {tn} NOT FOUND"
    if verb in ("/STA", "/START") and arg.startswith("TRAN"):
        tn = arg.split()[-1]
        if tn in ims.transactions:
            ims.transactions[tn].status = "STARTED"
            return f"DFS058I  {_now()}  START COMMAND COMPLETED - TRAN {tn} STARTED"
        return f"DFS000I  TRAN {tn} NOT FOUND"
    if verb in ("/DBR", "/DBRECOVERY") and arg.startswith("DB"):
        db = arg.split()[-1]
        if db in ims.databases:
            ims.databases[db] = "STOPPED"
            return f"DFS058I  {_now()}  DBRECOVERY COMMAND COMPLETED - {db} STOPPED"
        return f"DFS000I  DATABASE {db} NOT FOUND"
    return f"DFS058I  {_now()}  {verb} COMMAND COMPLETED"


def _resume_tpipe(state: Any, ims: ImsState, caller: str, tpipe: str) -> str:
    allowed, racf = _authorize(state, ims, caller, "RIMS", f"{ims.datastore}.RESUME") \
        if ims.otma_security == "FULL" else (True, "")
    if not allowed:
        _audit(state, caller, "IMS OTMA RESUME", f"TPIPE={tpipe} CL=RIMS", "FAILURE")
        return "\n".join([f"DFS3662W  OTMA SECURITY VIOLATION - RESUME TPIPE {tpipe} REJECTED", racf])
    _audit(state, caller, "IMS OTMA RESUME", f"TPIPE={tpipe}", "SUCCESS")
    return (f"HWSC0010I  RESUME TPIPE {tpipe} ACCEPTED\n"
            f"           NO ASYNC OUTPUT QUEUED FOR {tpipe}")


def _audit_report(ims: ImsState) -> str:
    leaky = ims.otma_security == "NONE"
    lines = [
        " OTMA SECURITY POSTURE AUDIT",
        " ------------------------------------------------------------",
        f"   /SECURE OTMA setting . . : {ims.otma_security}",
        f"   RACF TIMS/CIMS/RIMS  . . : {'DEFINED' if ims.profiles_defined else 'NOT DEFINED'}",
        f"   Client userid trust  . . : {'TRUSTED AS-IS (no RACF call)' if leaky else 'RACF VERIFIED'}",
        f"   Transaction injection  . : {'POSSIBLE' if leaky else 'DENIED (TIMS)'}",
        f"   Command injection  . . . : {'POSSIBLE' if ims.otma_security != 'FULL' else 'DENIED (CIMS)'}",
        " ------------------------------------------------------------",
    ]
    if leaky:
        lines += [
            "   RISK: IMS Connect on the network with /SECURE OTMA NONE lets any",
            "   client inject transactions and /commands under a chosen userid.",
            "   FIX: /SECURE OTMA FULL and define TIMS/CIMS/RIMS profiles,",
            "        permitting only the legitimate IMS users.",
        ]
    else:
        lines += [
            "   POSTURE: OTMA calls RACF for every message; the client userid is",
            "   authenticated and authorized against TIMS/CIMS/RIMS.",
        ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Command dispatch
# --------------------------------------------------------------------------- #
def ims_command(state: Any, userid: str, cmd: str) -> Optional[str]:
    """Drive the IMS Connect / OTMA lab.  Returns None if not an IMS command."""
    raw = (cmd or "").strip()
    u = raw.upper()
    if not (u == "IMS" or u.startswith("IMS ") or u.startswith("IMSCONN")):
        return None
    ims = get_ims_state(state)

    if u in ("IMS", "IMS MENU", "IMS HELP", "IMSCONN"):
        return _primary_panel(ims)

    body = raw[4:].strip() if len(raw) > 3 else ""
    ub = body.upper()

    if ub in ("STATUS", "STA", "QUERY", "Q"):
        return _status(ims)
    if ub == "AUDIT":
        return _audit_report(ims)

    # IMS DB learning module (DBD / PSB / DL/I calls)
    if ub in ("DB", "DLI", "DL/I") or ub.startswith(("DB ", "DBD", "PSB", "DLI ", "DL/I ")):
        from gibson.apps.ims.ims_db import dli_command
        return dli_command(state, userid, body)

    # IMS SECURE OTMA NONE|CHECK|FULL   (also accepts /SECURE OTMA ...)
    if ub.startswith("SECURE") or ub.startswith("/SECURE"):
        toks = ub.replace("/SECURE", "SECURE").split()
        level = toks[-1] if toks else ""
        if level in _OTMA_LEVELS:
            _apply_security(state, ims, level)
            return (f"DFS058I  {_now()}  /SECURE OTMA {level} COMMAND COMPLETED\n"
                    f"   OTMA security set to {level}; "
                    f"RACF TIMS/CIMS/RIMS {'defined' if ims.profiles_defined else 'not defined'}.")
        return "DFS1292E  /SECURE OTMA OPERAND INVALID - SPECIFY NONE | CHECK | FULL"

    # parse a trailing "AS userid"
    as_user = ""
    if " AS " in f" {ub} ":
        head, _, tail = body.rpartition(" AS ")
        # only treat as 'AS userid' when tail is a single token
        if tail and len(tail.split()) == 1:
            as_user = tail.strip()
            body = head.strip()
            ub = body.upper()

    if ub.startswith("SUBMIT") or ub.startswith("TX"):
        rest = body.split(None, 1)[1].strip() if len(body.split(None, 1)) > 1 else ""
        if not rest:
            return "DFS1292E  SUBMIT REQUIRES A TRANCODE - IMS SUBMIT trancode [data] [AS userid]"
        trancode, _, data = rest.partition(" ")
        return _submit_transaction(state, ims, userid, trancode, as_user, data.strip())

    if ub.startswith("CMD") or body.lstrip().startswith("/"):
        c = body[3:].strip() if ub.startswith("CMD") else body.strip()
        if not c.startswith("/"):
            c = "/" + c
        return _submit_command(state, ims, userid, c, as_user)

    if ub.startswith("RESUME"):
        tp = body.split(None, 1)[1].strip() if len(body.split(None, 1)) > 1 else ims.datastore
        return _resume_tpipe(state, ims, userid, tp)

    return ("DFS1292E  UNRECOGNISED IMS REQUEST - try: IMS, IMS STATUS, IMS SUBMIT, "
            "IMS CMD /DIS A, IMS SECURE OTMA, IMS AUDIT")
