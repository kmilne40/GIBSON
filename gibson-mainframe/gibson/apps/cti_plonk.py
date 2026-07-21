"""PLONK - a Splunk-style forensics console for the Gibson lab.

PLONK lets an analyst search across three correlated evidence sources, exactly the
way the Chapter-13 telemetry stack frames it:

* **Packets** - parsed from PCAP captures (seeded samples built from the book's
  Listing 13-5, plus any operator-supplied ``.pcap`` files dropped into the PCAP
  directory).  A minimal libpcap reader extracts the 5-tuple, timestamp and a
  payload preview - no external dependency required.
* **SMF** - the mainframe record stream (the same ``state.audit`` events the CTI
  Security page and the HMS IDS write).
* **SQL** - Db2 DDF / DRDA statements observed on the wire.

Search is Splunk-ish: bare words match anywhere, and ``key=value`` tokens filter
on fields (src, dst, port, proto, type, dsn, user...).
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PCAP_DIR_ENV = "GIBSON_PCAP_DIR"


# --------------------------------------------------------------------------- #
#  Packet model
# --------------------------------------------------------------------------- #
@dataclass
class Packet:
    ts: str
    src: str
    dst: str
    proto: str
    info: str
    length: int = 0
    payload: str = ""

    def as_row(self) -> List[str]:
        return [self.ts, self.src, self.dst, self.proto, str(self.length), self.info]

    def haystack(self) -> str:
        return " ".join([self.ts, self.src, self.dst, self.proto, self.info, self.payload]).lower()


@dataclass
class Capture:
    name: str
    source: str          # "seeded" | "<filename>"
    packets: List[Packet] = field(default_factory=list)
    note: str = ""


# --------------------------------------------------------------------------- #
#  Seeded captures (realistic, from the book + the HMS scenario)
# --------------------------------------------------------------------------- #
def _seed_captures() -> List[Capture]:
    tn = Capture("tn3270e_ftp_session.pcap", "seeded",
                 note="Listing 13-5: unusual client opens TN3270E then pulls a bulk FTP transfer")
    tn.packets = [
        Packet("02:14:09", "10.4.22.17:54011", "10.20.1.8:23", "TN3270E", "session_start LU=PAYT001", 96,
               "TN3270E SNA session bind; LU PAYT001"),
        Packet("02:14:42", "10.4.22.17:54011", "10.20.1.8:23", "TN3270E", 'screen_update "LOGON"', 1452,
               "LOGON ===> PAYT001"),
        Packet("02:15:10", "10.4.22.17:54011", "10.20.1.8:23", "TN3270E", 'screen_update "TSO/ISPF"', 1452,
               "ISPF PRIMARY OPTION MENU"),
        Packet("02:18:03", "10.20.1.8:21", "10.4.22.17:59231", "FTP", "file_xfer type=A size=38MB", 40360448,
               "RETR member; 226 Transfer complete"),
        Packet("02:18:04", "10.20.1.8:21", "10.4.22.17:59231", "FTP", "note code-page conversion", 64,
               "EBCDIC->ASCII conversion applied"),
        Packet("02:18:33", "10.4.22.17:54011", "10.20.1.8:23", "TN3270E", "session_end", 40,
               "TN3270E session terminated"),
    ]
    exfil = Capture("hms_ftp_exfil.pcap", "seeded",
                    note="HMS exfiltration: bulk RETR of payroll data off-platform")
    exfil.packets = [
        Packet("02:46:01", "10.4.22.17:59231", "10.20.1.8:21", "FTP", "USER hacker / PASS ******", 80,
               "230 user logged in"),
        Packet("02:46:08", "10.4.22.17:59231", "10.20.1.8:21", "FTP", "RETR PAYROLL.MASTER.DATA type=A", 92,
               "150 opening data connection"),
        Packet("02:48:55", "10.20.1.8:20", "10.4.22.17:59232", "FTP-DATA", "data type=A size=38MB", 39845888,
               "226 transfer complete; ~38MB"),
    ]
    db2 = Capture("db2_ddf_sql.pcap", "seeded",
                  note="Db2 DDF/DRDA session - SQL captured on the wire (collection stage)")
    db2.packets = [
        Packet("02:31:12", "10.4.22.17:51020", "10.20.1.8:446", "DRDA", "EXCSAT/ACCRDB DB=DSN1", 220,
               "DRDA connection to DDF DSN1"),
        Packet("02:31:13", "10.4.22.17:51020", "10.20.1.8:446", "DRDA",
               "SQL SELECT ACCT_NO,BALANCE FROM PROD.ACCOUNTS", 180,
               "SELECT ACCT_NO, BALANCE FROM PROD.ACCOUNTS WHERE BRANCH='0042'"),
        Packet("02:31:14", "10.4.22.17:51020", "10.20.1.8:446", "DRDA",
               "SQL SELECT CARD_NO,PIN FROM PROD.CARDS", 176,
               "SELECT CARD_NO, PIN FROM PROD.CARDS FETCH FIRST 5000 ROWS ONLY"),
        Packet("02:31:16", "10.4.22.17:51020", "10.20.1.8:446", "DRDA",
               "SQL INSERT INTO STAGING.EXFIL", 168,
               "INSERT INTO STAGING.EXFIL SELECT * FROM PROD.CUSTOMER"),
    ]
    return [tn, exfil, db2]


# --------------------------------------------------------------------------- #
#  Minimal libpcap parser (no external dependency)
# --------------------------------------------------------------------------- #
def _ip_str(b: bytes) -> str:
    return ".".join(str(x) for x in b)


def _preview(data: bytes) -> str:
    try:
        ascii_ = data.decode("ascii", "ignore")
        printable = "".join(c for c in ascii_ if 32 <= ord(c) < 127)
        if len(printable) >= max(4, len(data) // 4):
            return printable[:80]
        return data.decode("cp500", "ignore")[:80]   # try EBCDIC
    except Exception:
        return ""


def parse_pcap_bytes(data: bytes, name: str) -> Capture:
    cap = Capture(name, name)
    if len(data) < 24:
        cap.note = "truncated / not a pcap"
        return cap
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"):
        endian = "<" if magic == b"\xd4\xc3\xb2\xa1" else ">"
    else:
        cap.note = "unrecognised pcap magic (pcapng not supported)"
        return cap
    linktype = struct.unpack(endian + "I", data[20:24])[0]
    off = 24
    n = 0
    while off + 16 <= len(data) and n < 5000:
        ts_sec, ts_usec, incl, orig = struct.unpack(endian + "IIII", data[off:off + 16])
        off += 16
        pkt = data[off:off + incl]
        off += incl
        n += 1
        try:
            cap.packets.append(_decode_frame(pkt, linktype, ts_sec, ts_usec, orig))
        except Exception:
            continue
    cap.note = f"parsed {len(cap.packets)} packet(s), linktype {linktype}"
    return cap


def _decode_frame(pkt: bytes, linktype: int, ts_sec: int, ts_usec: int, orig: int) -> Packet:
    import datetime as _dt
    ts = _dt.datetime.utcfromtimestamp(ts_sec).strftime("%H:%M:%S") + f".{ts_usec // 1000:03d}"
    ipoff = 0
    if linktype == 1:           # Ethernet
        ipoff = 14
    elif linktype in (101, 12):  # raw IP
        ipoff = 0
    elif linktype == 113:        # Linux SLL
        ipoff = 16
    if len(pkt) < ipoff + 20:
        return Packet(ts, "?", "?", "RAW", "non-IP frame", orig, _preview(pkt))
    ver_ihl = pkt[ipoff]
    ihl = (ver_ihl & 0x0F) * 4
    proto_n = pkt[ipoff + 9]
    src = _ip_str(pkt[ipoff + 12:ipoff + 16])
    dst = _ip_str(pkt[ipoff + 16:ipoff + 20])
    l4 = ipoff + ihl
    proto = {6: "TCP", 17: "UDP", 1: "ICMP"}.get(proto_n, str(proto_n))
    sport = dport = 0
    payload = b""
    if proto in ("TCP", "UDP") and len(pkt) >= l4 + 4:
        sport, dport = struct.unpack(">HH", pkt[l4:l4 + 4])
        doff = ((pkt[l4 + 12] >> 4) * 4) if proto == "TCP" and len(pkt) > l4 + 12 else 8
        payload = pkt[l4 + doff:]
    info = f"{proto} {sport}->{dport}" if sport else proto
    return Packet(ts, f"{src}:{sport}" if sport else src, f"{dst}:{dport}" if dport else dst,
                  proto, info, orig, _preview(payload))


def _pcap_dir() -> Optional[str]:
    d = os.getenv(PCAP_DIR_ENV)
    candidates = [d] if d else []
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # gibson/
    candidates += [os.path.join(here, "data", "pcaps"), os.path.join(os.getcwd(), "pcaps")]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def _disk_captures() -> List[Capture]:
    out: List[Capture] = []
    d = _pcap_dir()
    if not d:
        return out
    try:
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith((".pcap", ".cap")):
                continue
            try:
                with open(os.path.join(d, fn), "rb") as fh:
                    out.append(parse_pcap_bytes(fh.read(), fn))
            except Exception:
                continue
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def list_captures(state: Any = None) -> List[Capture]:
    return _seed_captures() + _disk_captures()


def get_capture(state: Any, name: str) -> Optional[Capture]:
    for c in list_captures(state):
        if c.name == name:
            return c
    return None


def _match(hay: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    for tok in q.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            if v not in hay:
                return False
        elif tok not in hay:
            return False
    return True


def search_packets(query: str, state: Any = None) -> List[Packet]:
    out: List[Packet] = []
    for cap in list_captures(state):
        for p in cap.packets:
            if _match(p.haystack(), query):
                out.append(p)
    return out


def search_smf(state: Any, query: str) -> List[dict]:
    out: List[dict] = []
    audit = getattr(state, "audit", None)
    if audit is None:
        return out
    for ev in list(getattr(audit, "events", []))[-1000:]:
        ex = ev.extra or {}
        rec = {
            "ts": ev.ts.strftime("%H:%M:%S"),
            "type": ex.get("RECORD_TYPE", ""),
            "subtype": ex.get("SUBTYPE", ""),
            "event": ex.get("EVENT", "") or ev.command,
            "user": ev.userid,
            "result": ex.get("RESULT", "") or ev.result,
            "detail": ev.result,
        }
        hay = " ".join(str(v) for v in rec.values()).lower() + " smf" + str(rec["type"])
        if _match(hay, query):
            out.append(rec)
    return out[::-1]


def executed_sql(state: Any = None) -> List[dict]:
    """SQL statements observed on the wire (Db2 DDF/DRDA), correlated to the capture."""
    rows: List[dict] = []
    for cap in list_captures(state):
        for p in cap.packets:
            if p.proto == "DRDA" and ("SELECT" in p.payload.upper() or "INSERT" in p.payload.upper()
                                      or "UPDATE" in p.payload.upper() or "DELETE" in p.payload.upper()):
                verb = p.payload.split()[0].upper()
                rows.append({"ts": p.ts, "src": p.src, "db": "DSN1", "verb": verb,
                             "sql": p.payload, "capture": cap.name})
    return rows
