"""Heavy Metal Spider (HMS) IDS engine.

Models the Chapter-13 ransomware crew "Heavy Metal Spider" as a detectable kill
chain.  Each IDS trigger fires the field-correct SMF record(s) for that stage into
``state.audit`` (the same stream the CTI Security page and PLONK read), records a
sighting, and - once 3+ distinct TTP/tool signatures are seen - raises a single
correlation alarm.

Nothing here performs real scanning, cracking or exfiltration: the engine reacts to
sim signals and to an explicit lab runner, and the destructive Impact stage stays a
tabletop entry, exactly as the book insists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

ALARM_THRESHOLD = 3
ACTOR = "HEAVY METAL SPIDER"


# --------------------------------------------------------------------------- #
#  TTP catalogue
# --------------------------------------------------------------------------- #
@dataclass
class Ttp:
    id: str
    order: int
    attack: str
    name: str
    procedure: str
    smf: str            # human summary of the SMF evidence
    control: str
    tool: str = ""


# IDS detection chain, in the order requested.
HMS_TTPS: List[Ttp] = [
    Ttp("nmap", 1, "T1046", "Port scan (nmap)",
        "Rapid TCP connects across Gibson's listener ports",
        "SMF 119.2 TCP connection termination (xN, short-lived, many ports)",
        "Reduce exposed surface; alert on connection fan-out", "nmap"),
    Ttp("vtam_enum", 2, "T1590", "VTAM enumeration",
        "TN3270E / VTAM application sweep",
        "SMF 119.20/119.21 TN3270E session init/term; SMF 80(1) JOBINIT APPL probes",
        "Restrict APPL; alert on APPL sweeps", "vtam-enum"),
    Ttp("tso_enum", 3, "T1087", "TSO userid enumeration",
        "TSO userid discovery via logon attempts",
        "SMF 80(1) JOBINIT, qualifier!=0 (logon failure) xN",
        "Userid lockout; alert on enumeration", "tso-enum"),
    Ttp("ftp_brute", 4, "T1110", "FTP brute force",
        "Repeated FTP password guesses",
        "SMF 119.72 FTP server logon failure xN; SMF 80(1)",
        "FTP lockout; alert on burst", "hydra"),
    Ttp("jcl_rexx", 5, "T1105", "JCL/REXX upload",
        "Upload JCL with embedded REXX to the internal reader",
        "SMF 119.70 FTP STOR completion; SMF 30.1 / SMF 26 JES job",
        "Restrict submitters; alert on new submitter", ""),
    Ttp("backdoor", 6, "T1571", "Backdoor listener",
        "Rogue LISTEN on a high port (4000+) / new address space",
        "SMF 119.1 TCP connection init (LISTEN >4000); SMF 30.1 new address space",
        "Egress/port policy; alert on new listener", ""),
    Ttp("elv_apf", 7, "T1068", "APF privilege escalation",
        "Write to a writable APF library, AC(1)/key-zero/ACEE -> SPECIAL",
        "SMF 80 ALTUSER (SPECIAL, violation bit); SMF 42.6 dataset writes; SMF 90 APF change",
        "Remove APF write; alert on APF change & ALTUSER SPECIAL", ""),
    Ttp("racfds_john", 8, "T1110.002", "RACF DB offline crack (John)",
        "Offline crack of a SYS1.RACFDS copy on OMVS",
        "SMF 92 USS file open/read; SMF 80(2) ACCESS SYS1.RACF; SMF 14 dataset read",
        "Restrict SYS1.RACF/STGADMIN; alert on dump/copy", "john"),
    Ttp("nje_node_brute", 10, "T1590", "NJE node-name enumeration",
        "OPEN/NAK reason-code side-channel (0x01/0x04) on port 175/2252",
        "SMF 80 NJE OPEN xN (REJECTED, varying OHOST/RHOST)",
        "Restrict NJE source IPs; alert on OPEN fan-out", "nje-node-brute"),
    Ttp("nje_pass_brute", 11, "T1110", "NJE node-password brute force",
        "I-record (NCCILPAS) sign-on password guessing after a valid OPEN",
        "SMF 80 NJE SIGNON xN (FAILURE)",
        "TLS+mutual auth on 2252; strong node passwords; alert on signon failures", "nje-pass-brute"),
    Ttp("nje_nmr", 12, "T1059", "NJE NMR operator-command injection",
        "Injected $T NJEDEF / $T NODE / $ADD SOCKET via NMR on a trusted link",
        "SMF 80 NJE NMR (OPCMD=$T NODE.../AUTH=(NET,SYSTEM))",
        "AUTH=(JOB) not NET; alert on NJEDEF/NODE changes from a peer", "iNJEctor"),
    Ttp("nje_exec", 13, "T1021", "NJE cross-node execution",
        "/*XEQ to a trusted node under a forged NJHTOUSR identity",
        "$HASP122 RECEIVED; IEF403I/IEF404I; SMF 80 ALTUSER SPECIAL under forged user",
        "Distinct identities across nodes; alert on $HASP122 + RACF change", "jcl.py"),
    Ttp("ftp_exfil", 9, "T1567", "FTP exfiltration",
        "Bulk data leaves over FTP",
        "SMF 119.70/119.3 FTP completion (RETR, large bytes); SMF 14 dataset read",
        "Egress restriction; alert on after-hours bulk transfer", ""),
]

# Correlation tool signatures - profiled once the alarm raises.
HMS_TOOLS: List[Ttp] = [
    Ttp("hydra", 90, "T1110", "Hydra brute-forcer",
        "Network credential brute force against FTP/TN3270",
        "SMF 119.72 / SMF 80(1) bursts", "Account lockout; rate limiting", "hydra"),
    Ttp("nikto", 91, "T1595", "Nikto web scanner",
        "Web vulnerability scan against the HTTP/CTI listeners",
        "HTTP access bursts; SMF 119.2", "WAF; alert on scanner UA", "nikto"),
    Ttp("surrogat", 92, "T1550", "Surrogat / PassTicket abuse",
        "Surrogate / PassTicket impersonation toward SPECIAL",
        "SMF 80 PassTicket eval (event 81); SMF 80 ALTUSER", "PassTicket controls", "surrogat"),
]

_TTP_BY_ID = {t.id: t for t in (HMS_TTPS + HMS_TOOLS)}

# Full HMS kill chain as framed in Chapter 13 (for the actor-profile page).
HMS_KILLCHAIN = [
    ("T1592", "Reconnaissance", "OSINT on job posts, public pages, code repos",
     "External only (no host record yet)", "Reduce public footprint"),
    ("T1566.002", "Initial access", "Spear-phishing link to a SighberBank mainframe techie",
     "Mail/proxy logs, endpoint", "Link filtering; user awareness"),
    ("T1557", "Credential access", "Adversary-in-the-middle on TN3270 / FTP",
     "PCAP, SMF 119, zERT metadata", "Enforce AT-TLS; alert on cleartext"),
    ("T1106", "Execution", "CICS CECI SPOOLOPEN/SPOOLWRITE to the JES internal reader",
     "SMF 110 (CICS), JES job records", "Tighten region security; alert on new submitter"),
    ("T1068", "Privilege escalation", "Writable APF lib, AC(1)/key-zero/ACEE -> SPECIAL",
     "SMF 80 (ALTUSER), SMF 42 writes, APF list change", "Remove APF write"),
    ("T1005", "Collection", "Acquire RACF artifacts / extract from Db2",
     "SMF 80, SMF 101/102 (Db2 audit), dataset access", "Restrict SYS1.RACF & STGADMIN"),
    ("T1567", "Exfiltration", "Data leaves over FTP / SFTP",
     "SMF 119 + network flow", "Egress restriction; after-hours bulk alert"),
    ("T1070", "Defense evasion", "Purge JES SYSOUT and transient queues",
     "The gap itself - missing SMF/SYSLOG", "Protect & forward logs off-platform"),
    ("T1486", "Impact (tabletop)", "Would encrypt PDSE/VSAM - described, never run",
     "Assessed in the report only", "Backups & immutability"),
]


# --------------------------------------------------------------------------- #
#  State
# --------------------------------------------------------------------------- #
@dataclass
class HmsSighting:
    ts: str
    ttp_id: str
    attack: str
    name: str
    src_ip: str
    userid: str
    detail: str
    smf: List[str] = field(default_factory=list)   # summaries of records emitted


@dataclass
class HmsState:
    sightings: List[HmsSighting] = field(default_factory=list)
    alarm: Optional[dict] = None
    job_seq: int = 4700
    asid_seq: int = 0x0A20
    auto_fired: set = field(default_factory=set)   # TTPs already auto-detected (fire once)
    ftp_fail: int = 0
    tso_fail: int = 0


def get_hms_state(state: Any) -> HmsState:
    st = getattr(state, "hms", None)
    if st is None:
        st = HmsState()
        try:
            state.hms = st
        except Exception:
            pass
    return st


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
#  SMF record emission (field-correct, into the shared audit stream)
# --------------------------------------------------------------------------- #
def _smf(state: Any, smf_type: int, subtype: Optional[int], event: str, userid: str,
         fields: Dict[str, str], result: str = "SUCCESS") -> str:
    """Write one realistic SMF record into state.audit and return a one-line summary."""
    audit = getattr(state, "audit", None)
    sub = f".{subtype}" if subtype is not None else ""
    command = f"SMF TYPE {smf_type}{(' SUBTYPE ' + str(subtype)) if subtype is not None else ''} {event}".strip()
    extra = {"RECORD_TYPE": str(smf_type), "SUBTYPE": ("" if subtype is None else str(subtype)),
             "EVENT": event.upper(), "RESULT": result.upper(), "ACTOR": ACTOR,
             "TIME": datetime.now().strftime("%H:%M:%S"), "DATE": datetime.now().strftime("%Y-%m-%d")}
    extra.update({str(k).upper(): str(v) for k, v in fields.items()})
    detail = " ".join(f"{k}={v}" for k, v in fields.items())
    if audit is not None:
        try:
            audit.record(userid.upper(), command, f"{result.upper()} {detail}".strip(),
                         f"SMF{smf_type}", extra=extra)
        except Exception:
            pass
    return f"SMF {smf_type}{sub} {event} {detail}".strip()


def _next_job(hms: HmsState) -> str:
    hms.job_seq += 1
    return f"JOB{hms.job_seq:05d}"


# --------------------------------------------------------------------------- #
#  Per-TTP evidence generators
# --------------------------------------------------------------------------- #
def _gen(state: Any, hms: HmsState, ttp: Ttp, src_ip: str, userid: str, detail: str) -> List[str]:
    ip = src_ip or "10.4.22.17"
    u = (userid or "HACKER").upper()
    out: List[str] = []
    if ttp.id == "nmap":
        for port in (21, 23, 992, 3270, 2380, 8080):
            out.append(_smf(state, 119, 2, "TCP CONNECTION TERMINATION", u, {
                "SRCIP": ip, "SRCPORT": "54011", "DESTIP": "10.20.1.8", "DESTPORT": str(port),
                "PROTOCOL": "TCP", "FLAGS": "SYN", "BYTESIN": "0", "BYTESOUT": "0", "DURATION": "0.01"},
                result="SUCCESS"))
    elif ttp.id == "vtam_enum":
        out.append(_smf(state, 119, 20, "TN3270E SNA SESSION INITIATION", u, {
            "SRCIP": ip, "LU": "PAYT001", "APPL": "TSO", "DESTPORT": "3270"}))
        out.append(_smf(state, 119, 21, "TN3270E SNA SESSION TERMINATION", u, {
            "SRCIP": ip, "LU": "PAYT001", "APPL": "CICSPROD", "REASON": "APPL-PROBE"}))
        out.append(_smf(state, 80, 1, "JOBINIT", u, {
            "APPL": "VTAM", "TERMINAL": "PAYT001", "RESOURCE": "APPL", "QUALIFIER": "1"}, result="VIOLATION"))
    elif ttp.id == "tso_enum":
        for guess in ("OMVSADM", "PAYADMIN", "DB2ADM", "STC"):
            out.append(_smf(state, 80, 1, "JOBINIT", guess, {
                "APPL": "TSO", "TERMINAL": "TN3270", "SRCIP": ip, "QUALIFIER": "4",
                "REASON": "USER-NOT-DEFINED-OR-REVOKED"}, result="VIOLATION"))
    elif ttp.id == "ftp_brute":
        for _ in range(4):
            out.append(_smf(state, 119, 72, "FTP SERVER LOGON FAILURE", u, {
                "SRCIP": ip, "SRCPORT": "59231", "DESTPORT": "21", "FTPUSER": u, "REPLY": "530"},
                result="VIOLATION"))
        out.append(_smf(state, 80, 1, "JOBINIT", u, {
            "APPL": "FTPD", "SRCIP": ip, "QUALIFIER": "3", "REASON": "PASSWORD-INVALID"}, result="VIOLATION"))
    elif ttp.id == "jcl_rexx":
        job = _next_job(hms)
        out.append(_smf(state, 119, 70, "FTP SERVER TRANSFER COMPLETION", u, {
            "SRCIP": ip, "DIRECTION": "STOR", "DSN": f"{u}.HMS.JCL", "TYPE": "A", "BYTES": "2048"}))
        out.append(_smf(state, 30, 1, "ADDRESS SPACE / JOB START", u, {
            "JOBNAME": "HMSDROP", "JOBID": job, "SUBMITTER": u, "PGM": "IKJEFT01",
            "DETAIL": "JCL WITH EMBEDDED REXX SUBMITTED TO INTERNAL READER"}))
    elif ttp.id == "backdoor":
        out.append(_smf(state, 119, 1, "TCP CONNECTION INITIATION", u, {
            "SRCIP": ip, "LOCALPORT": "4444", "STATE": "LISTEN", "PROTOCOL": "TCP",
            "DETAIL": "ROGUE LISTENER ON HIGH PORT"}))
        hms.asid_seq += 1
        out.append(_smf(state, 30, 1, "ADDRESS SPACE / JOB START", u, {
            "JOBNAME": "BKDOOR", "ASID": f"{hms.asid_seq:04X}", "PGM": "BPXBATCH",
            "DETAIL": "NEW ADDRESS SPACE OPENING LISTENER 4444"}))
    elif ttp.id == "elv_apf":
        out.append(_smf(state, 42, 6, "DATASET I/O", u, {
            "DSN": "SYS2.ELV.APF", "ACCESS": "WRITE", "VOLSER": "WORK01",
            "DETAIL": "WRITE TO WRITABLE APF LIBRARY"}))
        out.append(_smf(state, 90, None, "SET PROG APF CHANGE", u, {
            "APF": "ADD", "DSN": "SYS2.ELV.APF", "VOLSER": "WORK01"}))
        out.append(_smf(state, 80, None, "ALTUSER", u, {
            "COMMAND": "ALTUSER", "TARGET": u, "ATTRIBUTE": "SPECIAL", "SPECIAL": "YES",
            "QUALIFIER": "1", "DETAIL": "AC(1)/KEY-ZERO/ACEE PERSISTS SPECIAL"}, result="VIOLATION"))
    elif ttp.id == "racfds_john":
        out.append(_smf(state, 92, 11, "USS FILE OPEN", u, {
            "PATH": "/u/hacker/racfds.unload", "ACCESS": "READ", "DETAIL": "JOHN READING RACF DB COPY"}))
        out.append(_smf(state, 80, 2, "RESOURCE ACCESS", u, {
            "RESOURCE": "SYS1.RACF", "CLASS": "DATASET", "ACCESS": "READ", "QUALIFIER": "0",
            "DETAIL": "RACF DATABASE READ FOR OFFLINE CRACK"}))
        out.append(_smf(state, 14, None, "DATASET READ", u, {
            "DSN": "SYS1.RACFDS", "ACCESS": "INPUT", "VOLSER": "RACFVL"}))
    elif ttp.id == "ftp_exfil":
        out.append(_smf(state, 119, 70, "FTP SERVER TRANSFER COMPLETION", u, {
            "SRCIP": "10.20.1.8", "DESTIP": ip, "DIRECTION": "RETR", "DSN": "PAYROLL.MASTER.DATA",
            "TYPE": "A", "BYTES": "39845888", "DETAIL": "BULK TRANSFER (~38MB) OFF-PLATFORM"}))
        out.append(_smf(state, 14, None, "DATASET READ", u, {
            "DSN": "PAYROLL.MASTER.DATA", "ACCESS": "INPUT", "VOLSER": "PAYVOL"}))
    elif ttp.id in ("hydra", "nikto", "surrogat"):
        out.append(_smf(state, 119, 2, f"{ttp.tool.upper()} ACTIVITY", u, {
            "SRCIP": ip, "TOOL": ttp.tool, "DETAIL": ttp.procedure}))
    return out


# --------------------------------------------------------------------------- #
#  Trigger + correlation
# --------------------------------------------------------------------------- #
def trigger_ttp(state: Any, ttp_id: str, *, src_ip: str = "", userid: str = "",
                detail: str = "") -> Optional[HmsSighting]:
    ttp = _TTP_BY_ID.get(ttp_id)
    if ttp is None:
        return None
    hms = get_hms_state(state)
    smf = _gen(state, hms, ttp, src_ip, userid, detail)
    sight = HmsSighting(_now(), ttp.id, ttp.attack, ttp.name, src_ip or "10.4.22.17",
                        (userid or "HACKER").upper(), detail or ttp.procedure, smf)
    hms.sightings.append(sight)
    _evaluate_correlation(state, hms)
    return sight


def seen_ttp_ids(hms: HmsState) -> List[str]:
    out: List[str] = []
    for s in hms.sightings:
        if s.ttp_id not in out:
            out.append(s.ttp_id)
    return out


def _evaluate_correlation(state: Any, hms: HmsState) -> None:
    distinct = [t for t in seen_ttp_ids(hms)]
    if len(distinct) >= ALARM_THRESHOLD and hms.alarm is None:
        # include the HYDRA / NIKTO / SURROGAT signatures in the profile on alarm
        associated = [t.id for t in HMS_TOOLS]
        hms.alarm = {
            "ts": _now(),
            "actor": ACTOR,
            "message": "Potential Heavy Metal Spider detected",
            "ttps_seen": distinct,
            "associated_tools": associated,
            "count": len(distinct),
            "delivered": False,           # Phase 3 wires console/dashboard/SEND MESSAGE
            "notified": ["KEVIN", "IBMUSER"],
        }
        # leave an SMF/audit marker for the alarm itself
        _smf(state, 80, None, "HMS CORRELATION ALARM", "GIBSON", {
            "ACTOR": ACTOR, "TTPS": ",".join(distinct), "THRESHOLD": str(ALARM_THRESHOLD),
            "DETAIL": "Potential Heavy Metal Spider detected"}, result="VIOLATION")
        _deliver_alarm(state, hms.alarm)


def _deliver_alarm(state: Any, alarm: dict) -> None:
    """Raise the alarm in the Master Console, the web dashboard, and SEND MESSAGE
    to KEVIN and IBMUSER (live if connected, otherwise queued for next logon)."""
    msg = alarm["message"]
    detail = f"{msg} - {alarm['count']} TTPs: {', '.join(alarm['ttps_seen'])}"
    # Master Console (z/OS-style action message)
    try:
        state.notify_console(f"*HMS001A {detail}", severity="ALERT")
    except Exception:
        pass
    # Web dashboard alert badge
    try:
        state.raise_dashboard_alert(detail, severity="ALERT", event_type="HMS")
    except Exception:
        pass
    # SEND MESSAGE to KEVIN and IBMUSER
    delivered_to = []
    for who in ("KEVIN", "IBMUSER"):
        live = False
        try:
            sessions = getattr(state, "sessions", None)
            if sessions is not None:
                live = bool(sessions.notify(who, f"HMS ALERT FROM GIBSON-SENTRY: {msg}"))
        except Exception:
            live = False
        if not live:
            try:
                state.pending_messages.setdefault(who.upper(), []).append(
                    ("GSENTRY", f"HMS ALERT: {msg}"))
            except Exception:
                pass
        delivered_to.append(f"{who}{'(live)' if live else '(queued)'}")
    alarm["delivered"] = True
    alarm["delivery"] = delivered_to


def reset(state: Any) -> None:
    hms = get_hms_state(state)
    hms.sightings.clear()
    hms.alarm = None


def run_scenario(state: Any, *, src_ip: str = "10.4.22.17", userid: str = "HACKER") -> List[HmsSighting]:
    """Fire the full 9-stage HMS kill chain in order (lab runner)."""
    out = []
    for ttp in HMS_TTPS:
        s = trigger_ttp(state, ttp.id, src_ip=src_ip, userid=userid)
        if s:
            out.append(s)
    return out


# --------------------------------------------------------------------------- #
#  Watched logon alerts (LVM/MAINT and GUEST/IBMUSER to TSO)
# --------------------------------------------------------------------------- #
_WATCHED_TSO = {"GUEST", "IBMUSER"}


_FTP_BRUTE_THRESHOLD = 3
_TSO_ENUM_THRESHOLD = 3


def observe_security_event(state: Any, userid: str, event: str, service: str,
                           result: str, detail: str = "", addr: str = "") -> Optional[str]:
    """Auto-detection: map an organic sim security event to an HMS TTP and FIRE it
    for real (in addition to the manual demo controls).  Signatures are kept
    specific so ordinary administration does not trip the IDS.  Each auto-detected
    TTP fires once; the normal correlation then raises the alarm at 3+ distinct."""
    try:
        hms = get_hms_state(state)
    except Exception:
        return None
    evt = (event or "").upper()
    svc = (service or "").upper()
    res = ((result or "SUCCESS").upper().split() or ["SUCCESS"])[0]
    d = (detail or "").upper()
    fail = res in ("FAILURE", "DENIED", "FAIL")
    fired: Optional[str] = None
    if "LOGON" in evt and fail and "FTP" in svc:
        hms.ftp_fail += 1
        if hms.ftp_fail >= _FTP_BRUTE_THRESHOLD:
            fired = "ftp_brute"
    elif "LOGON" in evt and fail and any(s in svc for s in ("TSO", "VTAM", "TN3270")):
        hms.tso_fail += 1
        if hms.tso_fail >= _TSO_ENUM_THRESHOLD:
            fired = "tso_enum"
    elif ("ALTUSER" in evt and "SPECIAL" in d) or "ELV.APF" in d:
        fired = "elv_apf"
    elif "SYS1.RACFDS" in d or "RACFDS" in d:
        fired = "racfds_john"
    elif "FTP" in svc and not fail and ("RETR" in d or "EXFIL" in d):
        fired = "ftp_exfil"
    if fired and fired not in hms.auto_fired:
        hms.auto_fired.add(fired)
        trigger_ttp(state, fired, src_ip=addr or "10.4.22.17",
                    userid=userid or "HACKER", detail="auto-detected: " + (detail or evt)[:60])
        return fired
    return None


def observe_port_scan(state: Any, addr: str, distinct_ports: int) -> Optional[str]:
    """Auto-detection of an nmap-style port scan: many distinct ports from one
    source within the touch window fires the nmap TTP once."""
    if distinct_ports < 6:
        return None
    try:
        hms = get_hms_state(state)
    except Exception:
        return None
    if "nmap" in hms.auto_fired:
        return None
    hms.auto_fired.add("nmap")
    trigger_ttp(state, "nmap", src_ip=addr or "10.4.22.17", userid="SCANNER",
                detail=f"auto-detected: {distinct_ports} distinct ports scanned")
    return "nmap"


def note_logon_alert(state: Any, userid: str, service: str, addr: str = "") -> Optional[str]:
    """Raise a logon alert (dashboard + master console) for the watched cases:
    MAINT signing on to LVM (z/VM), and GUEST/IBMUSER signing on to TSO."""
    u = (userid or "").upper()
    svc = (service or "").upper()
    msg = None
    if u == "MAINT" and "ZVM" in svc:
        msg = f"z/VM LOGON ALERT: MAINT signed on to LVM from {addr or 'unknown'}"
    elif u in _WATCHED_TSO and "ZVM" not in svc and any(s in svc for s in ("TSO", "VTAM", "TN3270")):
        msg = f"TSO LOGON ALERT: {u} signed on to TSO from {addr or 'unknown'}"
    if not msg:
        return None
    try:
        state.raise_dashboard_alert(msg, severity="ALERT", addr=addr, event_type="LOGON")
    except Exception:
        pass
    try:
        state.notify_console("*" + msg, severity="ALERT")
    except Exception:
        pass
    return msg
