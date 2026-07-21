"""Endevor SCM engine: element inventory, ESI authorization, element actions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

_ENDEVOR_VER = "18.1.00"          # CA/Broadcom Endevor SCM release shown in headers
_C1 = "C1"                         # the classic Endevor primary-options prefix

# Stage map: id -> (name, next stage).  D->T->Q->P with E (emergency) off to the side.
_STAGES = {
    "D": ("DEV", "Development"),
    "T": ("TEST", "Test"),
    "Q": ("QA", "Quality Assurance"),
    "P": ("PROD", "Production"),
    "E": ("EMER", "Emergency"),
}


@dataclass
class Element:
    env: str
    stage: str        # one of _STAGES
    system: str
    subsystem: str
    type: str         # COBOL, COPYBOOK, JCL, ...
    name: str
    source: list[str] = field(default_factory=list)
    owner: str = "IBMUSER"
    vvll: str = "01.00"
    signout: str = ""   # userid currently holding the element signed out, "" if available
    ccid: str = ""             # change control id of the last action
    comment: str = ""          # comment of the last action
    proc_group: str = ""       # processor group used by GENERATE
    last_action: str = "ADD"   # ADD / UPDATE / GENERATE / MOVE / SIGNOUT / ...
    last_act_user: str = "IBMUSER"
    last_act_date: str = ""    # yy/ddd hh:mm
    generated: bool = False    # has a successful GENERATE run at this level
    gen_rc: str = "----"       # highest RC of the last generate

    def key(self) -> tuple:
        return (self.env, self.stage, self.system, self.subsystem, self.type, self.name)


@dataclass
class EndevorStore:
    elements: dict[tuple, Element] = field(default_factory=dict)
    # ESI scope: "SYSTEM.SUBSYSTEM" -> set of userids authorized for that inventory area.
    scope: dict[str, set[str]] = field(default_factory=dict)

    def add(self, el: Element) -> None:
        self.elements[el.key()] = el

    def in_scope(self, userid: str, system: str, subsystem: str) -> bool:
        key = f"{system}.{subsystem}".upper()
        return userid.upper() in {u.upper() for u in self.scope.get(key, set())}


def get_endevor_store(state: Any) -> EndevorStore:
    st = getattr(state, "endevor_store", None)
    if st is not None:
        return st
    st = EndevorStore()

    # --- ESI scope (who may work in each System.Subsystem) ---------------------
    # TRAINING.GENERAL is the open training area; PAYROLL.SALARY is restricted to
    # the payroll team.  TRAINEE is deliberately NOT in PAYROLL scope.
    st.scope["TRAINING.GENERAL"] = {"TRAINEE", "FIBSUSR", "FIBSADM", "IBMUSER"}
    st.scope["PAYROLL.SALARY"] = {"PAYADMIN", "IBMUSER"}
    st.scope["BANKING.CORE"] = {"FIBSADM", "IBMUSER"}

    # --- seed inventory -------------------------------------------------------
    st.add(Element(
        env="DEV", stage="D", system="TRAINING", subsystem="GENERAL",
        type="COBOL", name="HELLO", owner="TRAINEE", vvll="01.03",
        source=[
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. HELLO.",
            "       PROCEDURE DIVISION.",
            "           DISPLAY 'HELLO FROM THE TRAINING SYSTEM'.",
            "           GOBACK.",
        ]))
    # The sensitive element a trainee should never be able to read.
    st.add(Element(
        env="PROD", stage="P", system="PAYROLL", subsystem="SALARY",
        type="COBOL", name="PAYCALC", owner="PAYADMIN", vvll="07.11",
        source=[
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. PAYCALC.",
            "      * CONFIDENTIAL - EXECUTIVE SALARY BANDS",
            "       01  WS-EXEC-BAND.",
            "           05  WS-CEO-BASE      PIC 9(7)V99 VALUE 1450000.00.",
            "           05  WS-CFO-BASE      PIC 9(7)V99 VALUE 0980000.00.",
            "           05  WS-BONUS-FACTOR  PIC 9V99    VALUE 1.85.",
            "       PROCEDURE DIVISION.",
            "           COMPUTE WS-PAYOUT = WS-CEO-BASE * WS-BONUS-FACTOR.",
            "           GOBACK.",
        ]))
    st.add(Element(
        env="PROD", stage="P", system="BANKING", subsystem="CORE",
        type="COBOL", name="ACCTPOST", owner="FIBSADM", vvll="12.40",
        source=[
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. ACCTPOST.",
            "       PROCEDURE DIVISION.",
            "           PERFORM POST-LEDGER-ENTRY.",
            "           GOBACK.",
        ]))

    setattr(state, "endevor_store", st)
    return st


# ---------------------------------------------------------------------------
# ESI authorization (RACROUTE REQUEST=AUTH model)
# ---------------------------------------------------------------------------
def _lab_vulnerable(state: Any) -> bool:
    return bool(getattr(getattr(state, "config", None), "endevor_lab_vulnerable_mode", True))


def esi_auth(state: Any, userid: str, action: str, el: Element) -> tuple[bool, str]:
    """Mirror Endevor's External Security Interface: issue a RACROUTE REQUEST=AUTH
    against the element's inventory scope.  Returns (allowed, racf_message)."""
    if get_endevor_store(state).in_scope(userid, el.system, el.subsystem):
        return True, ""
    group = "TRNGRP" if userid.upper() == "TRAINEE" else "SYS1"
    resource = f"{el.system}.{el.subsystem}.{el.type}.{el.name}"
    msg = (
        f"ICH408I USER({userid.upper():<8}) GROUP({group:<8}) NAME(########)\n"
        f"  {resource} CL(ENDEVOR )\n"
        f"  INSUFFICIENT ACCESS AUTHORITY\n"
        f"  ACCESS INTENT(READ   )  PERMITTED(NONE   )\n"
        f"C1G0000E  ESI SECURITY VIOLATION FOR ACTION {action.upper()} - REQUEST DENIED"
    )
    return False, msg


def _audit_violation(state: Any, userid: str, action: str, el: Element) -> None:
    try:
        state.record_security_event(
            userid, f"ENDEVOR {action.upper()}",
            f"{el.system}.{el.subsystem}.{el.type}.{el.name} STAGE={el.stage} OWNER={el.owner}",
            result="FAILURE", service="ENDEVOR", terminal="3270",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def _primary_menu() -> str:
    now = datetime.now().strftime("%d%b%y %H:%M").upper()
    return "\n".join([
        f" {_C1} ------------------------  ENDEVOR PRIMARY OPTIONS MENU  ----------------------",
        f" OPTION  ===>                                                      {now}",
        "",
        "     0  DEFAULTS    - Specify Endevor session defaults",
        "     1  DISPLAY     - Display environment information",
        "     2  FOREGROUND  - Perform element actions in foreground",
        "     3  BATCH       - Create batch SCL action requests",
        "     4  PACKAGE     - Perform package actions",
        "     5  BATCH PACKAGE - Create batch package requests",
        "     6  ENVIRONMENT - Display/route to another environment",
        "",
        f"     Element actions: DISPLAY / BROWSE / RETRIEVE / ADD  (CA Endevor SCM {_ENDEVOR_VER})",
        "     Inventory: ENVIRONMENT . SYSTEM . SUBSYSTEM . TYPE . ELEMENT  (STAGE D/T/Q/P/E)",
    ])


def _fmt_element_row(el: Element) -> str:
    stage = _STAGES.get(el.stage, (el.stage, ""))[0]
    so = el.signout or "*NONE*"
    return (f"  {el.system:<8} {el.subsystem:<8} {el.type:<8} {el.name:<8} "
            f"{el.vvll:<6} {stage:<5} {el.owner:<8} SO:{so}")


def _resolve(state: Any, spec: str) -> Optional[Element]:
    """Resolve SYSTEM.SUBSYSTEM.TYPE.ELEMENT (any stage) to a stored element."""
    parts = [p for p in spec.replace("/", ".").split(".") if p]
    if len(parts) < 4:
        return None
    system, subsystem, etype, name = (p.upper() for p in parts[:4])
    for el in get_endevor_store(state).elements.values():
        if (el.system.upper(), el.subsystem.upper(), el.type.upper(), el.name.upper()) == \
           (system, subsystem, etype, name):
            return el
    return None


def _render_element(el: Element, *, leaked: bool = False) -> str:
    stage = _STAGES.get(el.stage, (el.stage, el.stage))[1]
    head = [
        f" {_C1} BROWSE ELEMENT  {el.system}.{el.subsystem}.{el.type}.{el.name}",
        f"     ENVIRONMENT {el.env}  STAGE {el.stage} ({stage})  VVLL {el.vvll}  OWNER {el.owner}",
        f"     LAST ACTION {el.last_action} BY {el.last_act_user} {el.last_act_date}"
        f"   SIGNOUT {el.signout or '*NONE*'}",
        f"     CCID {el.ccid or '*NONE*'}   PROC GROUP {el.proc_group or '*NONE*'}"
        f"   GENERATED {'YES RC=' + el.gen_rc if el.generated else 'NO'}",
        " " + "-" * 74,
    ]
    if leaked:
        head.append(" *** ESI SCOPE CHECK BYPASSED - element returned without authorization ***")
        head.append(" " + "-" * 74)
    body = [f" {i+1:>5} {line}" for i, line in enumerate(el.source)]
    return "\n".join(head + body + [" " + "-" * 74, f" C1F0000I  {len(el.source)} LINE(S) DISPLAYED"])


def _now_stamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%y/%j %H:%M")


def _stamp(el: Element, action: str, userid: str, *, ccid: str = "", comment: str = "") -> None:
    el.last_action = action.upper()
    el.last_act_user = userid.upper()
    el.last_act_date = _now_stamp()
    if ccid:
        el.ccid = ccid.upper()
    if comment:
        el.comment = comment


def _bump_vvll(el: Element) -> None:
    try:
        vv, ll = el.vvll.split(".")
        ll = int(ll) + 1
        if ll > 99:
            vv = f"{int(vv) + 1:02d}"
            ll = 0
        el.vvll = f"{vv}.{ll:02d}"
    except Exception:
        el.vvll = "01.01"


def _signout_blocked(el: Element, userid: str) -> bool:
    """True if the element is signed out to *someone else* (blocks update/move/delete)."""
    return bool(el.signout) and el.signout.upper() != userid.upper()


_STAGE_ORDER = ["D", "T", "Q", "P"]


def _next_stage(stage: str) -> Optional[str]:
    s = stage.upper()
    if s in _STAGE_ORDER and _STAGE_ORDER.index(s) < len(_STAGE_ORDER) - 1:
        return _STAGE_ORDER[_STAGE_ORDER.index(s) + 1]
    return None


def _parse_options(rest: str):
    """Pull CCID and COMMENT options off the tail of a command, returning
    (spec_without_options, ccid, comment)."""
    ccid = ""
    comment = ""
    u = rest
    import re as _re
    m = _re.search(r"\bCCID\s+(\S+)", u, _re.I)
    if m:
        ccid = m.group(1)
        u = u[:m.start()] + u[m.end():]
    m = _re.search(r"\bCOMMENT\s+['\"]?([^'\"]+)['\"]?\s*$", u, _re.I)
    if m:
        comment = m.group(1).strip()
        u = u[:m.start()] + u[m.end():]
    return u.strip(), ccid, comment


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
def endevor_command(state: Any, userid: str, cmd: str) -> Optional[str]:
    """Drive the Endevor subsystem.  Recognised verbs:
       ENDEVOR | MENU | HELP
       ENDEVOR DISPLAY [system.subsystem]
       ENDEVOR BROWSE  system.subsystem.type.element   (the access-control lab)
       ENDEVOR RETRIEVE system.subsystem.type.element
       ENDEVOR ADD system.subsystem.type.element
    """
    raw = (cmd or "").strip()
    u = raw.upper()
    if not (u == "ENDEVOR" or u == "NDVR" or u.startswith("ENDEVOR ") or u.startswith("NDVR ")):
        return None
    if u in {"ENDEVOR", "ENDEVOR MENU", "NDVR"}:
        return _primary_menu()
    # strip a leading ENDEVOR/NDVR verb
    body = raw
    for pfx in ("ENDEVOR ", "NDVR "):
        if u.startswith(pfx):
            body = raw[len(pfx):].strip()
            break
    verb, _, rest = body.partition(" ")
    verb = verb.upper().strip()
    rest = rest.strip()

    if verb in {"HELP", "MENU", "?"}:
        return _primary_menu()

    if verb in {"PACKAGE", "PKG", "PACK"}:
        from gibson.apps.endevor.package_lab import handle_package
        return handle_package(state, userid, rest)

    store = get_endevor_store(state)

    if verb in {"DISPLAY", "LIST", "DIS"}:
        # Filter by system.subsystem if given.  Scope is enforced for the listing
        # only when the lab is OFF; in vulnerable mode the listing is unfiltered.
        filt = [p for p in rest.replace("/", ".").split(".") if p]
        rows: list[Element] = []
        for el in sorted(store.elements.values(), key=lambda e: e.key()):
            if filt and el.system.upper() != filt[0].upper():
                continue
            if len(filt) > 1 and el.subsystem.upper() != filt[1].upper():
                continue
            if not _lab_vulnerable(state) and not store.in_scope(userid, el.system, el.subsystem):
                continue
            rows.append(el)
        header = (f" {_C1} ELEMENT DISPLAY   (for {userid.upper()})\n"
                  "  SYSTEM   SUBSYS   TYPE     ELEMENT  VVLL   STAGE OWNER    SIGNOUT")
        if not rows:
            return header + "\n  C1F0001I  NO ELEMENTS MATCH / NONE IN SCOPE"
        return header + "\n" + "\n".join(_fmt_element_row(e) for e in rows)

    if verb in {"BROWSE", "RETRIEVE", "VIEW", "RET"}:
        el = _resolve(state, rest)
        if el is None:
            return f" {_C1} {verb}\n  C1F0002E  ELEMENT NOT FOUND: {rest.upper()}"
        # *** The access-control lab lives here ***
        if _lab_vulnerable(state):
            # VULNERABLE: existence is verified, but the ESI scope check is skipped.
            leaked = not store.in_scope(userid, el.system, el.subsystem)
            return _render_element(el, leaked=leaked)
        # FIXED: enforce the ESI RACROUTE REQUEST=AUTH scope check.
        ok, racf_msg = esi_auth(state, userid, verb, el)
        if not ok:
            _audit_violation(state, userid, verb, el)
            return f" {_C1} {verb}  {el.system}.{el.subsystem}.{el.type}.{el.name}\n" + racf_msg
        return _render_element(el, leaked=False)

    if verb in {"ADD", "UPDATE"}:
        spec, ccid, comment = _parse_options(rest)
        parts = [p for p in spec.replace("/", ".").split(".") if p]
        if len(parts) < 4:
            return f" {_C1} {verb}\n  C1F0003E  SYNTAX: {verb} SYSTEM.SUBSYSTEM.TYPE.ELEMENT [CCID id] [COMMENT 'text']"
        system, subsystem, etype, name = (p.upper() for p in parts[:4])
        if not _lab_vulnerable(state) and not store.in_scope(userid, system, subsystem):
            tmp = Element(env="DEV", stage="D", system=system, subsystem=subsystem, type=etype, name=name)
            ok, racf_msg = esi_auth(state, userid, verb, tmp)
            if not ok:
                _audit_violation(state, userid, verb, tmp)
                return f" {_C1} {verb}  {system}.{subsystem}.{etype}.{name}\n" + racf_msg
        existing = _resolve(state, f"{system}.{subsystem}.{etype}.{name}")
        if verb == "UPDATE" and existing is not None:
            if _signout_blocked(existing, userid):
                return (f" {_C1} UPDATE  {system}.{subsystem}.{etype}.{name}\n"
                        f"  C1F0008E  ELEMENT IS SIGNED OUT TO {existing.signout} - UPDATE DENIED")
            _bump_vvll(existing)
            existing.generated = False
            existing.gen_rc = "----"
            existing.signout = userid.upper()
            _stamp(existing, "UPDATE", userid, ccid=ccid, comment=comment)
            return (f" {_C1} UPDATE\n  C1G0000I  ELEMENT {system}.{subsystem}.{etype}.{name} "
                    f"UPDATED TO VV.LL {existing.vvll}  CCID {existing.ccid or '*NONE*'}")
        el = Element(env="DEV", stage="D", system=system, subsystem=subsystem,
                     type=etype, name=name, owner=userid.upper(), vvll="01.00",
                     signout=userid.upper(),
                     source=[f"      * {name} ADDED BY {userid.upper()}"])
        _stamp(el, "ADD", userid, ccid=ccid, comment=comment)
        store.add(el)
        return (f" {_C1} {verb}\n  C1G0000I  ELEMENT {system}.{subsystem}.{etype}.{name} "
                f"ADDED TO STAGE D  VV.LL 01.00  SIGNOUT {userid.upper()}")

    if verb in {"GENERATE", "GEN"}:
        spec, ccid, _c = _parse_options(rest)
        el = _resolve(state, spec)
        if el is None:
            return f" {_C1} GENERATE\n  C1F0002E  ELEMENT NOT FOUND: {spec.upper()}"
        if not _lab_vulnerable(state) and not store.in_scope(userid, el.system, el.subsystem):
            ok, racf_msg = esi_auth(state, userid, "GENERATE", el)
            if not ok:
                _audit_violation(state, userid, "GENERATE", el)
                return f" {_C1} GENERATE  {el.system}.{el.subsystem}.{el.type}.{el.name}\n" + racf_msg
        return _generate(el, userid, ccid)

    if verb in {"MOVE"}:
        return _move(state, store, userid, rest)

    if verb in {"DELETE", "DEL"}:
        el = _resolve(state, _parse_options(rest)[0])
        if el is None:
            return f" {_C1} DELETE\n  C1F0002E  ELEMENT NOT FOUND"
        if _signout_blocked(el, userid):
            return (f" {_C1} DELETE  {el.system}.{el.subsystem}.{el.type}.{el.name}\n"
                    f"  C1F0008E  ELEMENT IS SIGNED OUT TO {el.signout} - DELETE DENIED")
        if not _lab_vulnerable(state) and not store.in_scope(userid, el.system, el.subsystem):
            ok, racf_msg = esi_auth(state, userid, "DELETE", el)
            if not ok:
                _audit_violation(state, userid, "DELETE", el)
                return f" {_C1} DELETE  {el.system}.{el.subsystem}.{el.type}.{el.name}\n" + racf_msg
        store.elements.pop(el.key(), None)
        return (f" {_C1} DELETE\n  C1G0000I  ELEMENT {el.system}.{el.subsystem}.{el.type}.{el.name} "
                f"DELETED FROM STAGE {el.stage}")

    if verb in {"SIGNOUT", "SO"}:
        el = _resolve(state, _parse_options(rest)[0])
        if el is None:
            return f" {_C1} SIGNOUT\n  C1F0002E  ELEMENT NOT FOUND"
        if _signout_blocked(el, userid):
            return (f" {_C1} SIGNOUT\n  C1F0008E  ELEMENT ALREADY SIGNED OUT TO {el.signout}")
        el.signout = userid.upper()
        _stamp(el, "SIGNOUT", userid)
        return f" {_C1} SIGNOUT\n  C1G0000I  ELEMENT SIGNED OUT TO {userid.upper()}"

    if verb in {"SIGNIN", "SI"}:
        el = _resolve(state, _parse_options(rest)[0])
        if el is None:
            return f" {_C1} SIGNIN\n  C1F0002E  ELEMENT NOT FOUND"
        if _signout_blocked(el, userid):
            return (f" {_C1} SIGNIN\n  C1F0008E  ELEMENT IS SIGNED OUT TO {el.signout} "
                    f"- USE SIGNOVER TO OVERRIDE")
        el.signout = ""
        _stamp(el, "SIGNIN", userid)
        return f" {_C1} SIGNIN\n  C1G0000I  ELEMENT SIGNED IN"

    if verb in {"SIGNOVER", "OVERRIDE"}:
        el = _resolve(state, _parse_options(rest)[0])
        if el is None:
            return f" {_C1} SIGNOVER\n  C1F0002E  ELEMENT NOT FOUND"
        held = el.signout or "*NONE*"
        el.signout = ""
        _stamp(el, "SIGNOVER", userid)
        return f" {_C1} SIGNOVER\n  C1G0000I  SIGNOUT OVERRIDE - ELEMENT WAS HELD BY {held}"

    if verb in {"SCL", "BATCH"}:
        return _run_scl(state, userid, rest)

    return (f" {_C1}\n  C1F0009E  UNKNOWN ACTION '{verb}' - try DISPLAY / BROWSE / RETRIEVE / ADD / "
            f"UPDATE / GENERATE / MOVE / DELETE / SIGNOUT / SIGNIN / SCL")


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------
def _generate(el: Element, userid: str, ccid: str = "") -> str:
    """Run the processor for the element's type and stamp a successful build."""
    proc = {"COBOL": "CExxxxxx", "ASM": "AExxxxxx", "PLI": "PLIEXEC",
            "JCL": "JCLPROC", "COPYBOOK": "COPYGEN"}.get(el.type.upper(), "GENERIC")
    el.proc_group = proc
    steps = []
    if el.type.upper() in ("COBOL", "PLI", "ASM"):
        steps = [("CONLIST", "0000"), (el.type.upper()[:8], "0000"), ("LKED", "0000")]
    elif el.type.upper() == "COPYBOOK":
        steps = [("CONLIST", "0000")]
    else:
        steps = [("COPYSTEP", "0000")]
    highest = max(int(rc) for _s, rc in steps)
    _bump_vvll(el)
    el.generated = True
    el.gen_rc = f"{highest:04d}"
    _stamp(el, "GENERATE", userid, ccid=ccid)
    lines = [f" {_C1} GENERATE  {el.system}.{el.subsystem}.{el.type}.{el.name}",
             f"     PROCESSOR GROUP {proc}   ENVIRONMENT {el.env}  STAGE {el.stage}"]
    for s, rc in steps:
        lines.append(f"  C1G0000I  STEP {s:<8} EXECUTED   RC={rc}")
    lines.append(f"  C1GE0000I  GENERATE COMPLETED - HIGHEST RC={highest:04d}  VV.LL {el.vvll}")
    return "\n".join(lines)


def _move(state: Any, store: "EndevorStore", userid: str, rest: str) -> str:
    import re as _re
    spec = rest
    target_env = ""
    m = _re.search(r"\bTO\s+(?:ENVIRONMENT\s+)?(\S+)", rest, _re.I)
    if m:
        target_env = m.group(1).upper()
        spec = rest[:m.start()].strip()
    spec, _ccid, _c = _parse_options(spec)
    el = _resolve(state, spec)
    if el is None:
        return f" {_C1} MOVE\n  C1F0002E  ELEMENT NOT FOUND: {spec.upper()}"
    if not _lab_vulnerable(state) and not store.in_scope(userid, el.system, el.subsystem):
        ok, racf_msg = esi_auth(state, userid, "MOVE", el)
        if not ok:
            _audit_violation(state, userid, "MOVE", el)
            return f" {_C1} MOVE  {el.system}.{el.subsystem}.{el.type}.{el.name}\n" + racf_msg
    if _signout_blocked(el, userid):
        return (f" {_C1} MOVE\n  C1F0008E  ELEMENT IS SIGNED OUT TO {el.signout} - MOVE DENIED")
    if not el.generated:
        return (f" {_C1} MOVE\n  C1F0010E  ELEMENT NOT GENERATED AT STAGE {el.stage} "
                f"- GENERATE BEFORE MOVE")
    nxt = _next_stage(el.stage)
    if nxt is None:
        return f" {_C1} MOVE\n  C1F0011E  ELEMENT ALREADY AT FINAL STAGE {el.stage} (PROD)"
    from_stage, el.stage = el.stage, nxt
    el.env = _STAGES.get(nxt, (el.env, ""))[0]
    el.signout = ""  # moving signs the element in at the new stage
    _stamp(el, "MOVE", userid)
    return (f" {_C1} MOVE  {el.system}.{el.subsystem}.{el.type}.{el.name}\n"
            f"  C1G0000I  ELEMENT MOVED FROM STAGE {from_stage} TO STAGE {nxt} "
            f"({_STAGES.get(nxt, ('', ''))[0]})  VV.LL {el.vvll}")


def _run_scl(state: Any, userid: str, deck: str) -> str:
    """Parse and execute an inline SCL deck (statements separated by ';').

    Supported: SET (SYSTEM/SUBSYS/TYPE/STAGE/ENV/CCID context) and the action
    statements ADD/UPDATE/GENERATE/MOVE/DELETE [ELEMENT] name.  Produces a
    C1BM3000-style batch report with a per-action return code and a final MAXCC.
    """
    ctx = {"SYSTEM": "", "SUBSYSTEM": "", "TYPE": "", "STAGE": "D", "CCID": ""}
    out = [f" {_C1} SCL BATCH EXECUTION  (C1BM3000)  USER {userid.upper()}",
           " " + "-" * 74]
    maxcc = 0
    stmts = [s.strip() for s in deck.replace("\n", ";").split(";") if s.strip()]
    if not stmts:
        return (f" {_C1} SCL\n  C1F0012E  EMPTY SCL DECK - e.g. "
                "SCL SET SYSTEM TRAINING SUBSYS GENERAL TYPE COBOL; GENERATE ELEMENT HELLO")
    for stmt in stmts:
        toks = stmt.split()
        verb = toks[0].upper()
        if verb == "SET":
            i = 1
            while i + 1 < len(toks) + 0 and i < len(toks):
                k = toks[i].upper()
                key = {"SYSTEM": "SYSTEM", "SYS": "SYSTEM", "SUBSYSTEM": "SUBSYSTEM",
                       "SUBSYS": "SUBSYSTEM", "TYPE": "TYPE", "STAGE": "STAGE",
                       "ENVIRONMENT": "ENV", "ENV": "ENV", "CCID": "CCID"}.get(k)
                if key and i + 1 < len(toks):
                    ctx[key if key != "ENV" else "ENV"] = toks[i + 1].upper()
                    i += 2
                else:
                    i += 1
            out.append(f"  SET   {stmt[4:].strip()}   RC=0000")
            continue
        # action statement: VERB [ELEMENT] name
        rest = toks[1:]
        if rest and rest[0].upper() == "ELEMENT":
            rest = rest[1:]
        elname = rest[0].upper() if rest else ""
        if not (ctx["SYSTEM"] and ctx["SUBSYSTEM"] and ctx["TYPE"] and elname):
            out.append(f"  {verb:<6} {elname:<8}   RC=0012  (SET SYSTEM/SUBSYS/TYPE first)")
            maxcc = max(maxcc, 12)
            continue
        spec = f"{ctx['SYSTEM']}.{ctx['SUBSYSTEM']}.{ctx['TYPE']}.{elname}"
        opt = f" CCID {ctx['CCID']}" if ctx["CCID"] else ""
        if verb in ("ADD", "UPDATE", "GENERATE", "GEN", "MOVE", "DELETE", "DEL"):
            sub = endevor_command(state, userid, f"ENDEVOR {verb} {spec}{opt}") or ""
            rc = "0000"
            if "C1F" in sub:   # any C1FxxxxE error
                rc = "0012"
                maxcc = max(maxcc, 12)
            out.append(f"  {verb:<6} {elname:<8}   RC={rc}")
        else:
            out.append(f"  {verb:<6} {elname:<8}   RC=0012  (UNKNOWN SCL ACTION)")
            maxcc = max(maxcc, 12)
    out.append(" " + "-" * 74)
    out.append(f"  C1BM3000I  SCL EXECUTION COMPLETE - {len(stmts)} STATEMENT(S)  MAXCC={maxcc:04d}")
    return "\n".join(out)
