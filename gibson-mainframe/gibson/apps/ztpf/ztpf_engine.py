"""z/TPF engine: ECB transaction model, Z-message console, TPFDF records.

This is a *teaching* model of z/TPF - not a real TPF.  The cornerstone is the
Entry Control Block (ECB): every input message creates an ECB that is dispatched
through a program path (segments entered via ENTER/BACK), may do file I/O against
a small TPFDF-style record model, and produces a response.  Operator control is
via functional "Z-messages" (all prefixed Z, no online help facility - authentic
to TPF).  Two demo transactions are provided: airline availability and card
authorisation, each with a full ECB trace.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

_CPUID = "B"            # this z/Architecture CPU / I-stream identifier (TPF "CPU")
_SSU = "HPN"            # subsystem user


def _now() -> str:
    return datetime.now().strftime("%H%M%S")


def _stamp() -> str:
    # TPF time stamp form  *ddhhmm*  (julian-ish, fine for the sim)
    return datetime.now().strftime("*%j%H%M*")


@dataclass
class Ecb:
    """An Entry Control Block - one in-flight transaction."""
    ecb_id: str
    trancode: str
    data: str = ""
    istream: int = 1
    state: str = "CREATED"          # CREATED -> QUEUED -> DISPATCHED -> EXITED
    path: List[str] = field(default_factory=list)   # trace steps
    response: List[str] = field(default_factory=list)
    cpu: str = _CPUID

    def trace(self, step: str) -> None:
        self.path.append(step)


@dataclass
class FlightRecord:
    flight: str
    orig: str
    dest: str
    dep: str
    arr: str
    seats: int


@dataclass
class CardRecord:
    pan: str            # masked primary account number
    limit: int
    balance: int
    status: str = "OPEN"


@dataclass
class LineRecord:
    """A teleprocessing line (SNA/TCPIP circuit) into the z/TPF SSU."""
    line: str
    ltype: str           # SNA | TCPIP | X25
    state: str            # ACTIVE | INACTIVE | OOS
    remote: str
    msgs_in: int = 0
    msgs_out: int = 0


@dataclass
class NetNode:
    """A network node reachable over a line - host, gateway, or peer SSU."""
    node: str
    ntype: str            # SSU | HOST | GATEWAY
    state: str             # ACTIVE | INACTIVE
    line: str
    sessions: int = 0


@dataclass
class PerfStat:
    """Running per-trancode performance counters (feeds ZPERF)."""
    trancode: str
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return (self.total_ms / self.count) if self.count else 0.0


@dataclass
class TpfRecord:
    """A TPFDF record addressed by record TYPE + ORDINAL (no per-record ACL -
    knowing the type+ordinal is enough to read it: the core z/TPF exposure)."""
    rtype: str
    ordinal: int
    sensitive: bool
    data: Dict[str, str] = field(default_factory=dict)


@dataclass
class Terminal:
    """A terminal/session identity.  In z/TPF authority is carried by the
    terminal (LNIATA), not a RACF userid - reach an authorised LNIATA and you
    inherit its authority."""
    lniata: str
    authority: str = "BASIC"        # BASIC | PRIME (privileged / Prime CRAS)
    desc: str = ""
    locked: bool = False


# Functional messages that should require PRIME (privileged) authority.
_PRIME_VERBS = {"ZPTCH", "ZCYCL", "ZTPLD", "ZPUBK", "ZPVFS", "ZRECW", "ZSACT"}
# Record types that hold sensitive data.
_SENSITIVE_TYPES = {"CC01", "PR01"}


@dataclass
class ZtpfState:
    online: bool = True
    sys_state: str = "NORM"         # 1052 / NORM / CRAS
    istreams: int = 4
    cpu: str = _CPUID
    ecb_seq: int = 0x4000
    ecbs: List[Ecb] = field(default_factory=list)
    loadsets: Dict[str, str] = field(default_factory=dict)
    flights: List[FlightRecord] = field(default_factory=list)
    cards: Dict[str, CardRecord] = field(default_factory=dict)
    util: int = 7                   # CPU utilisation %
    # security model
    secure_mode: bool = False       # False = authentic default-weak TPF posture
    terminals: Dict[str, Terminal] = field(default_factory=dict)
    records: Dict[str, TpfRecord] = field(default_factory=dict)   # key "TYPE-ORD"
    lines: Dict[str, LineRecord] = field(default_factory=dict)     # key line id
    nodes: Dict[str, NetNode] = field(default_factory=dict)        # key node id
    perf: Dict[str, PerfStat] = field(default_factory=dict)        # key trancode
    memory: Dict[str, str] = field(default_factory=dict)          # patchable control bytes
    pubkeys: Dict[str, str] = field(default_factory=dict)
    audit: List[str] = field(default_factory=list)
    lab_flag_captured: bool = False
    lab_progress: set = field(default_factory=set)


def get_ztpf_state(state: Any) -> ZtpfState:
    st = getattr(state, "ztpf", None)
    if st is None:
        st = ZtpfState()
        _seed(st)
        try:
            state.ztpf = st
        except Exception:
            pass
    return st


def _seed(st: ZtpfState) -> None:
    st.loadsets = {
        "BASE": "ACTIVE  (base load - 3.1.0)",
        "AVL1": "ACTIVE  (availability application)",
        "CC01": "ACTIVE  (card authorisation application)",
    }
    st.flights = [
        FlightRecord("AA100", "DFW", "LAX", "0800", "0930", 42),
        FlightRecord("AA205", "DFW", "LAX", "1215", "1345", 7),
        FlightRecord("AA660", "DFW", "ORD", "0700", "0920", 118),
        FlightRecord("AA661", "ORD", "DFW", "1000", "1225", 0),
    ]
    st.cards = {
        "4111XXXXXXXX1111": CardRecord("4111XXXXXXXX1111", 5000_00, 1200_00),
        "5500XXXXXXXX0004": CardRecord("5500XXXXXXXX0004", 200000, 199500),
    }
    # Terminals (LNIATAs).  Note the *mis-configured* line: an ordinary remote
    # terminal that has been left with PRIME authority - the lab's foothold.
    st.terminals = {
        "010002": Terminal("010002", "PRIME", "Prime CRAS (operator console)"),
        "010040": Terminal("010040", "BASIC", "Reservations agent set"),
        "0700AA": Terminal("0700AA", "PRIME", "REMOTE AGENT - MISCONFIGURED (should be BASIC)"),
    }
    # TPFDF records addressed by TYPE+ORDINAL.  CC01 = card master (sensitive),
    # PR01 = PNR / reservation (sensitive), AA01 = flight schedule (public).
    def _rec(t, o, sens, **kw):
        st.records[f"{t}-{o}"] = TpfRecord(t, o, sens, kw)
    _rec("CC01", 1, True, PAN="4111111111111111", NAME="A WALKER", EXP="0628", LIMIT="5000.00", BAL="1200.00", CVV="217")
    _rec("CC01", 2, True, PAN="5500000000000004", NAME="R GIBSON", EXP="1127", LIMIT="2000.00", BAL="1995.00", CVV="884")
    _rec("CC01", 3, True, PAN="340000000000009", NAME="K MITNICK", EXP="0326", LIMIT="9000.00", BAL="150.00", CVV="3310")
    _rec("PR01", 1, True, PNR="GIBSON/R", FLT="AA100", DATE="14JUN", SEAT="3A", PHONE="214-555-0100")
    _rec("PR01", 2, True, PNR="WALKER/A", FLT="AA205", DATE="14JUN", SEAT="12C", PHONE="972-555-0114")
    _rec("AA01", 100, False, FLT="AA100", ORG="DFW", DST="LAX", SEATS="42")
    # Patchable control memory.  SECMODE byte gates the (weak) security checks;
    # AUTHCHK byte gates functional-message authority.
    st.memory = {
        "SECMODE": "00",    # 00 = checks OFF (vulnerable default), FF = ON
        "AUTHCHK": "00",    # 00 = functional-message authority NOT enforced
        "CRASKEY": "PRIME", # Prime CRAS master authority cell
    }
    st.pubkeys = {
        "CCAUTH01": "RSA-2048 ACTIVE  (card-auth signing key)",
        "TLSHOST1": "RSA-2048 ACTIVE  (host TLS key)",
    }
    # Teleprocessing lines (ZLINE) and the nodes reached over them (ZNETW).
    st.lines = {
        "L001": LineRecord("L001", "SNA", "ACTIVE", "ARINC-GATEWAY-1", msgs_in=1245, msgs_out=1198),
        "L002": LineRecord("L002", "TCPIP", "ACTIVE", "RES-AGENT-POOL", msgs_in=389, msgs_out=401),
        "L003": LineRecord("L003", "SNA", "OOS", "BACKUP-LINK-2"),
    }
    st.nodes = {
        "HPN": NetNode("HPN", "SSU", "ACTIVE", "LOCAL", sessions=4),
        "SABRE1": NetNode("SABRE1", "HOST", "ACTIVE", "L001", sessions=2),
        "ARINC1": NetNode("ARINC1", "GATEWAY", "ACTIVE", "L001", sessions=1),
        "BKUP2": NetNode("BKUP2", "GATEWAY", "INACTIVE", "L003", sessions=0),
    }
    # Baseline transaction volume/latency so ZPERF has real numbers before any
    # demo transaction is run in this session (the format matches the running
    # counters run_transaction() updates as AVL/AUTH traffic is entered).
    st.perf = {
        "AVL": PerfStat("AVL", count=142, total_ms=142 * 2.1, max_ms=4.8),
        "AUTH": PerfStat("AUTH", count=58, total_ms=58 * 3.4, max_ms=6.2),
    }


def authority_for(st: ZtpfState, lniata: str) -> str:
    """Resolve the authority of a terminal.  In secure mode an unknown terminal
    is BASIC; in the (authentic) vulnerable default, authority enforcement is off
    so callers treat everyone as PRIME-capable."""
    t = st.terminals.get((lniata or "").upper())
    return t.authority if t else "BASIC"


def _auth_enforced(st: ZtpfState) -> bool:
    # Authority is enforced only in secure mode AND when the AUTHCHK control byte
    # is on.  The lab can flip AUTHCHK via ZPTCH to disable enforcement.
    return st.secure_mode and st.memory.get("AUTHCHK", "00") != "00"


def _audit(st: ZtpfState, lniata: str, verb: str, detail: str = "") -> None:
    from datetime import datetime
    st.audit.append(f"{datetime.now().strftime('%H%M%S')} LNIATA={lniata or 'CRAS':<6} {verb:<7} {detail}".rstrip())
    st.audit = st.audit[-200:]


def _lab_event(state: Any, st: ZtpfState, stage: str, lniata: str, detail: str) -> None:
    """Record a vulnerability-lab milestone and raise a Gibson security event so
    TPF lab activity shows in Sentry / PLONK and can feed the HMS correlation."""
    st.lab_progress.add(stage)
    rec = getattr(state, "record_security_event", None)
    if callable(rec):
        try:
            rec("TPFLAB", f"TPF {stage.upper()}", detail, service="TPF",
                addr="", terminal=lniata or "CRAS",
                result="SUCCESS" if stage != "denied" else "FAILURE")
        except Exception:
            pass


# --------------------------------------------------------------------- ECB
def _new_ecb(st: ZtpfState, trancode: str, data: str) -> Ecb:
    st.ecb_seq += 1
    istream = (st.ecb_seq % max(1, st.istreams)) + 1
    ecb = Ecb(ecb_id=f"{st.ecb_seq:06X}", trancode=trancode.upper(), data=data, istream=istream)
    st.ecbs.append(ecb)
    st.ecbs = st.ecbs[-50:]
    return ecb


def _dispatch(st: ZtpfState, ecb: Ecb) -> None:
    """Walk the ECB through OPZERO -> queue -> dispatch, tracing each step."""
    ecb.trace(f"OPZERO   create ECB {ecb.ecb_id}  CPU-{ecb.cpu}  IS-{ecb.istream:02d}  (12KB)")
    ecb.state = "QUEUED"
    ecb.trace(f"CP/QUEUE enqueue input list  TRANCODE={ecb.trancode}")
    ecb.state = "DISPATCHED"
    ecb.trace(f"DISPATCH assign I-stream {ecb.istream}; ECB register R9 set")


def _exit(ecb: Ecb) -> None:
    ecb.trace("EXITC    return control to control program (ECB released)")
    ecb.state = "EXITED"


# ------------------------------------------------------------ transactions
_AVAIL_PREFIXES = ("AVL", "A", "AA")
_SELL_PREFIXES = ("SELL", "0", "SS")
_CARD_PREFIXES = ("AUTH", "CARD", "CC")


def _txn_availability(st: ZtpfState, ecb: Ecb) -> None:
    """Airline availability - the classic TPF/PARS entry."""
    ecb.trace("ENTRC    CCPLOGON -> availability segment AVL1")
    parts = ecb.data.upper().replace("-", " ").split()
    orig = dest = ""
    for tok in parts:
        if len(tok) == 6 and tok.isalpha():
            orig, dest = tok[:3], tok[3:]
        elif len(tok) == 3 and tok.isalpha() and not orig:
            orig = tok
        elif len(tok) == 3 and tok.isalpha() and orig and not dest:
            dest = tok
    ecb.trace(f"FINDC    TPFDF read flight schedule records  ORG={orig or '*'} DST={dest or '*'}")
    matches = [f for f in st.flights
               if (not orig or f.orig == orig) and (not dest or f.dest == dest)]
    if not orig or not dest:
        ecb.response.append("WALA0001 ENTER ORIGIN/DESTINATION e.g. AVL DFWLAX")
    elif not matches:
        ecb.response.append(f"NO FLIGHTS {orig}-{dest}")
    else:
        ecb.response.append(f"** AVAILABILITY {orig}-{dest} **")
        ecb.response.append("  FLT    DEP  ARR   SEATS")
        for i, f in enumerate(matches, 1):
            sa = "CLSD" if f.seats == 0 else f"{f.seats:>4}"
            ecb.response.append(f"{i:>2} {f.flight:<6} {f.dep} {f.arr}  {sa}")
    ecb.trace("ENTNC    format response (no return) -> output message")


def _txn_card_auth(st: ZtpfState, ecb: Ecb) -> None:
    """Card authorisation - the classic high-volume TPF financial entry."""
    ecb.trace("ENTRC    CCPLOGON -> card-auth segment CC01")
    toks = ecb.data.split()
    pan = toks[0] if toks else ""
    amt = 0
    for t in toks[1:]:
        d = t.replace("$", "").replace(".", "")
        if d.isdigit():
            amt = int(d); break
    # match by last 4 digits against masked PANs
    rec = None
    if pan:
        last4 = pan[-4:]
        for k, v in st.cards.items():
            if k.endswith(last4):
                rec = v; break
    ecb.trace(f"FINDC    TPFDF read card master  PAN=...{pan[-4:] if pan else '????'}")
    if rec is None:
        ecb.response.append("AUTH DECLINED  RC=14  CARD NOT ON FILE")
    elif rec.status != "OPEN":
        ecb.response.append(f"AUTH DECLINED  RC=04  ACCOUNT {rec.status}")
    elif amt <= 0:
        ecb.response.append("AUTH ERROR     RC=13  INVALID AMOUNT")
    elif rec.balance + amt > rec.limit:
        ecb.response.append(f"AUTH DECLINED  RC=51  OVER LIMIT (avail {(rec.limit-rec.balance)/100:.2f})")
    else:
        rec.balance += amt
        ecb.trace("FILEC    TPFDF update card balance (hold)")
        code = f"{st.ecb_seq % 1000000:06d}"
        ecb.response.append(f"AUTH APPROVED  RC=00  CODE={code}  AMT={amt/100:.2f}")
    ecb.trace("ENTNC    format ISO response -> output message")


def _record_perf(st: ZtpfState, code: str, base_ms: float) -> None:
    """Update running ZPERF counters and the line/node it rode in on - TPF
    transactions are wire-speed, so latency is simulated as small jitter around
    a per-trancode baseline rather than measured wall-clock time."""
    ms = max(0.1, base_ms + random.uniform(-0.6, 1.2))
    stat = st.perf.setdefault(code, PerfStat(code))
    stat.count += 1
    stat.total_ms += ms
    stat.max_ms = max(stat.max_ms, ms)
    if st.lines:
        line = list(st.lines.values())[st.ecb_seq % len(st.lines)]
        if line.state == "ACTIVE":
            line.msgs_in += 1
            line.msgs_out += 1


def run_transaction(state: Any, trancode: str, data: str) -> Ecb:
    """Create and dispatch an ECB for an input message; return the completed ECB."""
    st = get_ztpf_state(state)
    ecb = _new_ecb(st, trancode, data)
    _dispatch(st, ecb)
    code = trancode.upper()
    if code in _AVAIL_PREFIXES:
        _txn_availability(st, ecb)
        _record_perf(st, "AVL", 2.1)
    elif code in _CARD_PREFIXES:
        _txn_card_auth(st, ecb)
        _record_perf(st, "AUTH", 3.4)
    else:
        ecb.response.append(f"CPST0001 TRANSACTION {code} NOT DEFINED - INPUT REJECTED")
        ecb.trace(f"ENTNC    no application for {code} -> reject")
    _exit(ecb)
    return ecb


# -------------------------------------------------------------- Z-messages
def z_message(state: Any, raw: str, *, lniata: str = "CRAS", authority: Optional[str] = None) -> str:
    """Handle a TPF functional message (Z-message).  ``lniata``/``authority`` give
    the issuing terminal's identity; in secure mode privileged verbs require PRIME
    authority and are audited, while in the authentic default-weak posture they
    are not enforced.  Returns response text."""
    st = get_ztpf_state(state)
    parts = raw.strip().split()
    verb = parts[0].upper() if parts else ""
    arg = " ".join(parts[1:]).strip()
    pfx = f"CPU-{st.cpu} SS-BSS SSU-{_SSU}"
    if authority is None:
        authority = authority_for(st, lniata)

    # Functional-message authority check (only bites in secure mode with AUTHCHK on).
    if verb in _PRIME_VERBS and _auth_enforced(st) and authority != "PRIME":
        _audit(st, lniata, verb, f"DENIED (authority={authority})")
        return (f"{pfx}\nCSMP0105E FUNCTIONAL MESSAGE {verb} REJECTED - "
                f"TERMINAL {lniata} NOT AUTHORIZED (requires PRIME)\n{_stamp()}")
    if verb in _PRIME_VERBS:
        _audit(st, lniata, verb, arg[:40])

    if verb == "ZSTAT":
        return "\n".join([
            f"{pfx}",
            f"CSMP0097I {_now()} SYSTEM STATE: {st.sys_state}   ONLINE: {'YES' if st.online else 'NO'}",
            f"          I-STREAMS ACTIVE: {st.istreams}   CPU UTIL: {st.util:02d}%",
            f"          ECBS DISPATCHED: {len(st.ecbs)}   HIGH ECB: {st.ecb_seq:06X}",
            f"          LOADSETS: {', '.join(st.loadsets)}",
            _stamp(),
        ])
    if verb == "ZDORD":
        # Display a record by TYPE + ORDINAL - the core z/TPF data exposure: no
        # per-record ACL, so any terminal that knows type+ordinal can read it.
        a = arg.upper().split()
        if len(a) < 2 or not a[1].isdigit():
            return f"{pfx}\nCFRM0009E ZDORD - SPECIFY RECORD TYPE AND ORDINAL (e.g. ZDORD CC01 1)"
        rtype, ordn = a[0], int(a[1])
        rec = st.records.get(f"{rtype}-{ordn}")
        if rec is None:
            return f"{pfx}\nCFRM0011E RECORD {rtype} ORDINAL {ordn} NOT FOUND"
        if rec.sensitive and _auth_enforced(st) and authority != "PRIME":
            _audit(st, lniata, "ZDORD", f"DENIED {rtype}-{ordn} (sensitive)")
            return (f"{pfx}\nCFRM0012E RECORD {rtype} ORDINAL {ordn} IS PROTECTED - "
                    f"TERMINAL {lniata} NOT AUTHORIZED\n{_stamp()}")
        if rec.sensitive:
            _audit(st, lniata, "ZDORD", f"READ SENSITIVE {rtype}-{ordn}")
            _lab_event(state, st, "harvest", lniata, f"sensitive record {rtype}-{ordn} disclosed (PAN/PNR)")
        out = [f"{pfx}", f"CFRM0020I RECORD {rtype} ORDINAL {ordn}"
               + ("   *** SENSITIVE ***" if rec.sensitive else "")]
        for k, v in rec.data.items():
            out.append(f"   {k:<6}: {v}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZRECW":
        # write/alter a record field (privileged) - ZRECW TYPE ORD FIELD=VALUE
        a = arg.split()
        if len(a) < 3 or "=" not in a[2]:
            return f"{pfx}\nCFRM0029E ZRECW - SPECIFY TYPE ORDINAL FIELD=VALUE"
        rtype, ordn = a[0].upper(), a[1]
        rec = st.records.get(f"{rtype}-{ordn}")
        if rec is None:
            return f"{pfx}\nCFRM0011E RECORD {rtype} ORDINAL {ordn} NOT FOUND"
        fld, val = a[2].split("=", 1)
        rec.data[fld.upper()] = val
        _audit(st, lniata, "ZRECW", f"{rtype}-{ordn} {fld.upper()}={val}")
        return f"{pfx}\nCFRM0021I RECORD {rtype} ORDINAL {ordn} UPDATED ({fld.upper()})\n{_stamp()}"
    if verb == "ZPTCH":
        # Maintain memory patch decks - patch a live control cell.  No memory
        # protection: this is how a privileged terminal tampers with the system.
        a = arg.upper().split()
        if not a:
            out = [f"{pfx}", "CPSV0040I MEMORY PATCH CELLS"]
            for k, v in st.memory.items():
                out.append(f"   {k:<8} = {v}")
            out.append(_stamp())
            return "\n".join(out)
        if "=" in arg:
            cell, newval = arg.split("=", 1)
            cell, newval = cell.strip().upper(), newval.strip().upper()
        elif len(a) >= 2:
            cell, newval = a[0], a[1]
        else:
            return f"{pfx}\nCPSV0049E ZPTCH - SPECIFY CELL=VALUE (e.g. ZPTCH AUTHCHK=FF)"
        old = st.memory.get(cell, "(new)")
        st.memory[cell] = newval
        _audit(st, lniata, "ZPTCH", f"{cell}: {old} -> {newval}")
        if cell in ("SECMODE", "AUTHCHK", "CRASKEY"):
            _lab_event(state, st, "tamper", lniata, f"control cell {cell} patched {old}->{newval}")
        note = ""
        if cell == "SECMODE":
            st.secure_mode = newval not in ("00", "OFF")
            note = "  (security checks " + ("ENABLED" if st.secure_mode else "DISABLED") + ")"
        return f"{pfx}\nCPSV0041I PATCH APPLIED  {cell} = {newval}{note}\n{_stamp()}"
    if verb == "ZDPGM":
        name = (arg.split()[0].upper() if arg else "")
        rows = [("CCAU", "card-auth", "ACTIVE", "CC01"), ("AVLS", "availability", "ACTIVE", "AVL1"),
                ("CRAS", "operator", "ACTIVE", "BASE"), ("SIGN", "sign-on", "ACTIVE", "BASE")]
        out = [f"{pfx}", "CPRG0001I PROGRAM DISPLAY", "   NAME ALLOC    STATE   LOADSET"]
        for n, d, s, ls in rows:
            if not name or n == name:
                out.append(f"   {n:<4} {d:<8} {s:<7} {ls}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZDPAT":
        return "\n".join([f"{pfx}", "CPRG0010I PROGRAM ATTRIBUTE TABLE",
                          "   NAME KEY  STATE  RESTRICTED",
                          "   CCAU 1    ENAB   YES (card data)",
                          "   AVLS 1    ENAB   NO",
                          "   CRAS 0    ENAB   YES (operator)", _stamp()])
    if verb in ("ZDLOK", "ZDTRM"):
        _lab_event(state, st, "recon", lniata, "terminal/LNIATA table enumerated")
        out = [f"{pfx}", "CCSC0001I TERMINAL / LNIATA TABLE",
               "   LNIATA AUTHORITY STATE  DESCRIPTION"]
        for t in st.terminals.values():
            out.append(f"   {t.lniata:<6} {t.authority:<8} {'LOCK' if t.locked else 'OPEN':<5}  {t.desc}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZDRCT":
        return "\n".join([f"{pfx}", "CRCT0001I RESOURCE CONTROL TABLE (RCAT)",
                          "   RES     OWNER   STATE",
                          "   CC01    CCAUTH  IN-USE", "   AVL1    AVLS    IN-USE",
                          "   DASD01  SYSTEM  ONLINE", _stamp()])
    if verb in ("ZDMOD", "ZDASD"):
        return "\n".join([f"{pfx}", "CDMO0001I DASD / MODULE STATUS",
                          "   MOD SSID  STATE   RECORDS",
                          "   01  C001  ONLINE  CC01,PR01,AA01",
                          "   02  C002  ONLINE  PNR-OVERFLOW", _stamp()])
    if verb == "ZDNUM":
        return f"{pfx}\nCDMP0001I DUMP NUMBERS: 0001 0002 (SOFT)  NO HARD DUMPS\n{_stamp()}"
    if verb == "ZLINE":
        a = arg.upper().split()
        want = a[0] if a else ""
        lines = [l for l in st.lines.values() if not want or l.line == want]
        if want and not lines:
            return f"{pfx}\nCLNE0009E LINE {want} NOT FOUND"
        out = [f"{pfx}", "CLNE0001I TELEPROCESSING LINE STATUS",
               "   LINE  TYPE   STATE     REMOTE                MSGS-IN  MSGS-OUT"]
        for l in lines:
            out.append(f"   {l.line:<5} {l.ltype:<6} {l.state:<9} {l.remote:<20}  {l.msgs_in:>7}  {l.msgs_out:>8}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZNETW":
        a = arg.upper().split()
        want = a[0] if a else ""
        nodes = [n for n in st.nodes.values() if not want or n.node == want]
        if want and not nodes:
            return f"{pfx}\nCNET0009E NODE {want} NOT FOUND"
        out = [f"{pfx}", "CNET0001I NETWORK NODE STATUS",
               "   NODE    TYPE     STATE     LINE   SESSIONS"]
        for n in nodes:
            out.append(f"   {n.node:<7} {n.ntype:<8} {n.state:<9} {n.line:<6} {n.sessions:>8}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZPERF":
        a = arg.upper().split()
        want = a[0] if a else ""
        stats = [s for s in st.perf.values() if not want or s.trancode == want]
        if want and not stats:
            return f"{pfx}\nCPRF0009E NO PERFORMANCE DATA FOR TRANCODE {want}"
        out = [f"{pfx}", "CPRF0001I z/TPF PERFORMANCE MONITOR",
               "   TRANCODE  COUNT     AVG-MS   MAX-MS"]
        for s in stats:
            out.append(f"   {s.trancode:<8}  {s.count:>5}     {s.avg_ms:>6.2f}   {s.max_ms:>6.2f}")
        if not want:
            out.append(f"   ECBS DISPATCHED: {len(st.ecbs)}   I-STREAMS: {st.istreams}   CPU UTIL: {st.util:02d}%")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZPUBK":
        sub = (arg.split()[0].upper() if arg else "DISPLAY")
        if sub in ("DISPLAY", "DISP", ""):
            out = [f"{pfx}", "CPKI0001I PKI KEYSTORE - PUBLIC KEY PAIRS"]
            for k, v in st.pubkeys.items():
                out.append(f"   {k:<10} {v}")
            out.append(_stamp())
            return "\n".join(out)
        if sub == "EXTRACT":
            nm = arg.split()[1].upper() if len(arg.split()) > 1 else ""
            if nm in st.pubkeys:
                _audit(st, lniata, "ZPUBK", f"EXTRACT {nm}")
                return f"{pfx}\nCPKI0020I KEY {nm} EXTRACTED (public material released)\n{_stamp()}"
            return f"{pfx}\nCPKI0029E KEY {arg.split()[1] if len(arg.split())>1 else ''} NOT FOUND"
        return f"{pfx}\nCPKI0009I ZPUBK {sub} PROCESSED\n{_stamp()}"
    if verb == "ZPVFS":
        return f"{pfx}\nCVFS0001I z/TPF FILE SYSTEM (VFS) - {'LOGGED IN' if authority=='PRIME' else 'LOGIN REQUIRED'}\n{_stamp()}"
    if verb in ("ZAUDIT", "ZDAUD"):
        if not st.secure_mode and st.memory.get("SECMODE", "00") == "00":
            return f"{pfx}\nCAUD0009I AUDIT LOGGING IS NOT ACTIVE (no ESM in default posture)\n{_stamp()}"
        out = [f"{pfx}", "CAUD0001I FUNCTIONAL-MESSAGE AUDIT LOG"]
        out.extend("   " + e for e in st.audit[-12:]) or out.append("   (empty)")
        if not st.audit:
            out.append("   (empty)")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZDLOD":
        out = [f"{pfx}", "CLDR0001I LOADSET STATUS"]
        for name, desc in st.loadsets.items():
            out.append(f"          {name:<6} {desc}")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZTPLD":
        name = (arg.split()[0].upper() if arg else "")
        if not name:
            return f"{pfx}\nCLDR0101E ZTPLD - SPECIFY A LOADSET NAME"
        st.loadsets.setdefault(name, "LOADED  (operator load)")
        st.loadsets[name] = "ACTIVE  (operator load)"
        return f"{pfx}\nCLDR0050I LOADSET {name} ACCEPTED AND ACTIVATED\n{_stamp()}"
    if verb == "ZACES":
        out = [f"{pfx}", "CPSV0001I ACTIVE ENTRIES (RECENT ECBs)",
               "   ECB-ID  TRAN   IS  STATE"]
        for e in st.ecbs[-8:]:
            out.append(f"   {e.ecb_id} {e.trancode:<6} {e.istream:02d}  {e.state}")
        if not st.ecbs:
            out.append("   (no entries dispatched)")
        out.append(_stamp())
        return "\n".join(out)
    if verb == "ZDREC":
        # display a TPFDF record: ZDREC FLIGHT <flt>  or  ZDREC CARD <last4>
        a = arg.upper().split()
        if a and a[0] == "FLIGHT":
            flt = a[1] if len(a) > 1 else ""
            recs = [f for f in st.flights if not flt or f.flight == flt]
            out = [f"{pfx}", "CFRM0001I TPFDF FLIGHT RECORDS",
                   "   FLT    ORG-DST  DEP  ARR  SEATS"]
            for f in recs:
                out.append(f"   {f.flight:<6} {f.orig}-{f.dest}  {f.dep} {f.arr} {f.seats:>5}")
            out.append(_stamp())
            return "\n".join(out)
        if a and a[0] == "CARD":
            out = [f"{pfx}", "CFRM0002I TPFDF CARD MASTER RECORDS",
                   "   PAN               LIMIT     BAL      ST"]
            for k, v in st.cards.items():
                out.append(f"   {k} {v.limit/100:>8.2f} {v.balance/100:>8.2f}  {v.status}")
            out.append(_stamp())
            return "\n".join(out)
        return f"{pfx}\nCFRM0009E ZDREC - SPECIFY FLIGHT <flt> OR CARD"
    if verb == "ZCYCL":
        tgt = (arg.split()[0].upper() if arg else "")
        if tgt in ("1052", "NORM", "CRAS", "IDLE"):
            st.sys_state = tgt
            st.online = tgt in ("NORM", "1052")
            return f"{pfx}\nCSMP0098I SYSTEM CYCLED TO STATE {tgt}\n{_stamp()}"
        return f"{pfx}\nCSMP0099E ZCYCL - VALID STATES: 1052 NORM CRAS IDLE"
    if verb in ("ZTPTRACE", "ZECBTR", "ZTRACE"):
        if not st.ecbs:
            return f"{pfx}\nCPSV0009I NO ECB AVAILABLE TO TRACE"
        e = st.ecbs[-1]
        out = [f"{pfx}", f"CPSV0010I ECB TRACE  ID={e.ecb_id}  TRAN={e.trancode}  IS-{e.istream:02d}  STATE={e.state}"]
        for i, step in enumerate(e.path):
            out.append(f"   {i:02d}  {step}")
        out.append(_stamp())
        return "\n".join(out)
    if verb in ("ZLAB", "ZLABINFO"):
        return ztpf_lab_brief()
    if verb == "ZFLAG":
        need = {"recon", "harvest", "tamper"}
        done = st.lab_progress & need
        if need.issubset(st.lab_progress):
            st.lab_flag_captured = True
            _lab_event(state, st, "flag", lniata, "lab objective complete")
            return ("\n".join([
                f"{pfx}",
                "CTPF9999I *** z/TPF VULNERABILITY LAB - OBJECTIVE COMPLETE ***",
                "  You enumerated terminals (recon), read sensitive card/PNR records with",
                "  no per-record access control (harvest), and patched a live control cell",
                "  with no memory protection (tamper) - full compromise of a default-weak",
                "  z/TPF, with no ESM, no userid auth and no audit.",
                "  FLAG{ztpf_no_esm_terminal_authority_is_not_security}",
                "  Remediation: enforce functional-message authority (ZPTCH AUTHCHK=FF),",
                "  protect sensitive records, and enable ZAUDIT logging (ZPTCH SECMODE=FF).",
                _stamp()]))
        return (f"{pfx}\nCTPF9001I LAB INCOMPLETE - done {sorted(done) or '[]'}, "
                f"need {sorted(need - st.lab_progress)}.  Try ZLAB for the brief.\n{_stamp()}")
    if verb in ("ZHELP", "ZHLP", "HELP", "?"):
        return ("z/TPF has no online HELP facility (use the Operations Guide). "
                "Z-messages: ZSTAT ZDPGM ZDPAT ZDLOK ZDRCT ZDMOD ZDNUM ZACES ZDLOD ZTPLD "
                "ZDREC ZDORD ZRECW ZCYCL ZPTCH ZPUBK ZPVFS ZAUDIT ZTPTRACE ZLINE ZNETW ZPERF.")
    if verb.startswith("Z"):
        return f"{pfx}\nCSMP0101E FUNCTIONAL MESSAGE {verb} NOT DEFINED"
    return ""


def ztpf_lab_brief() -> str:
    """Briefing for the z/TPF vulnerability lab."""
    return (
        "z/TPF VULNERABILITY LAB - 'Heavy Metal Spider hits the TPF'\n"
        "-----------------------------------------------------------\n"
        "z/TPF has NO external security manager (no RACF/ACF2), authority is carried by\n"
        "the TERMINAL (LNIATA) not a userid, records have NO per-record access control,\n"
        "and memory is shared with no protection.  Demonstrate the default-weak posture:\n"
        "  1. RECON   : ZDLOK            - list terminals; spot the mis-configured PRIME LNIATA\n"
        "  2. HARVEST : ZDORD CC01 1     - read the card master (PAN/CVV) with no record ACL\n"
        "               ZDORD PR01 1     - read a PNR (passenger data)\n"
        "  3. TAMPER  : ZPTCH AUTHCHK=FF - patch a live control cell (no memory protection)\n"
        "  4. ZFLAG                       - capture the flag once 1-3 are done\n"
        "Then SECURE it and re-try:  ZPTCH SECMODE=FF ; ZPTCH AUTHCHK=FF\n"
        "  -> sensitive reads and privileged Z-messages from a BASIC terminal are now\n"
        "     DENIED and every privileged action is recorded - check with ZAUDIT.\n"
    )
