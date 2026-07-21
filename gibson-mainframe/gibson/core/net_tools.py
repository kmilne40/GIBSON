"""True-to-life network tools for the OMVS / z/OS UNIX shell.

A single offline, deterministic resolver backs dig / nslookup / host / whois /
ping / traceroute so they all agree on addresses, and each command emits output
faithful to the real tool:

* dig        - ISC BIND dig transcript (HEADER/QUESTION/ANSWER, flags, +short, -x)
* nslookup   - resolver-style answer with Server/Address
* host       - one-line-per-record answer
* whois      - RIR/registrar style records for domains and IP ranges
* ping/oping - z/OS Communications Server "CS V2R5: Pinging host ..." transcript
* traceroute - z/OS CS hop-by-hop transcript with intermediate routers

Everything is deterministic (seeded by a hash of the target) so a given name
always produces the same addresses and timings. Documentation address ranges
(RFC 5737: 192.0.2/24, 198.51.100/24, 203.0.113/24) are used for synthesised
public hosts so nothing resolves to a real address.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

try:
    from gibson.core.network import DNS_FIXTURES
except Exception:  # pragma: no cover
    DNS_FIXTURES = {}

_LOCAL = {"mainframe", "localhost", "", "127.0.0.1", "::1"}
_IPRE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}$")
_NAMERE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62})\.)*[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62})$")


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


def _doc_ip(name: str) -> str:
    """Deterministic RFC-5737 documentation address for a synthesised host."""
    n = _h("A", name)
    blocks = ["192.0.2", "198.51.100", "203.0.113"]
    base = blocks[n % 3]
    host = (n >> 8) % 254 + 1
    return f"{base}.{host}"


def _ttl(name: str) -> int:
    return [300, 600, 1800, 3600, 86400][_h("ttl", name) % 5]


# --------------------------------------------------------------------------- #
#  Curated zone records (everything else is synthesised deterministically)
# --------------------------------------------------------------------------- #
_ZONE = {
    "example.com": {
        "A": ["93.184.216.34"], "AAAA": ["2606:2800:220:1:248:1893:25c8:1946"],
        "MX": ["10 mail.example.com."], "NS": ["a.iana-servers.net.", "b.iana-servers.net."],
        "TXT": ['"v=spf1 -all"'],
    },
    "iana.org": {"A": ["192.0.43.8"], "NS": ["a.icann-servers.net.", "b.icann-servers.net."]},
}
# Fold the classroom DNS fixtures (name -> single A) into the zone.
for _n, _ip in DNS_FIXTURES.items():
    _ZONE.setdefault(_n.lower(), {}).setdefault("A", [_ip])

# whois fixtures: domains and IP allocations.
_WHOIS_DOMAINS = {
    "example.com": {"Registrar": "RESERVED-Internet Assigned Numbers Authority",
                    "Created": "1995-08-14", "Updated": "2024-08-14", "Expiry": "2025-08-13",
                    "NS": ["A.IANA-SERVERS.NET", "B.IANA-SERVERS.NET"], "Status": "clientDeleteProhibited"},
}
_WHOIS_NETS = [
    ("93.184.216.0", "93.184.216.255", "93.184.216.0/24", "EDGECAST-NETBLK", "Edgecast Inc.", "US", "RIPE"),
    ("198.51.100.0", "198.51.100.255", "198.51.100.0/24", "TEST-NET-2", "IANA Documentation", "ZZ", "ARIN"),
    ("203.0.113.0", "203.0.113.255", "203.0.113.0/24", "TEST-NET-3", "IANA Documentation", "ZZ", "APNIC"),
    ("192.0.2.0", "192.0.2.255", "192.0.2.0/24", "TEST-NET-1", "IANA Documentation", "ZZ", "ARIN"),
    ("8.8.8.0", "8.8.8.255", "8.8.8.0/24", "GOGL", "Google LLC", "US", "ARIN"),
]


def _now_dig() -> str:
    return datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y")


def _classify(name: str):
    """Return ('local'|'ip'|'zone'|'synth'|'nxdomain', canonical_name, ip)."""
    raw = (name or "").strip().rstrip(".")
    low = raw.lower()
    if low in _LOCAL:
        return "local", raw or "mainframe", "127.0.0.1"
    if _IPRE.match(raw):
        return "ip", raw, raw
    if not low or low.endswith(".invalid") or not _NAMERE.match(raw):
        return "nxdomain", raw, ""
    if low in _ZONE and _ZONE[low].get("A"):
        return "zone", low, _ZONE[low]["A"][0]
    return "synth", low, _doc_ip(low)


# --------------------------------------------------------------------------- #
#  Record assembly
# --------------------------------------------------------------------------- #
def _records(name: str, qtype: str):
    """Return list of (name, ttl, type, value) for a query."""
    kind, canon, ip = _classify(name)
    if kind in ("nxdomain",):
        return []
    qt = qtype.upper()
    out = []
    ttl = _ttl(canon)
    base = _ZONE.get(canon, {})

    def add(t, vals):
        for v in vals:
            out.append((canon + ".", ttl, t, v))

    if kind == "ip":
        return out  # handled by reverse path
    wanted = ["A", "AAAA", "NS", "SOA", "MX", "TXT"] if qt == "ANY" else [qt]
    for t in wanted:
        if t == "A":
            add("A", base.get("A", [ip]))
        elif t == "AAAA":
            v = base.get("AAAA")
            if v:
                add("AAAA", v)
            elif qt == "AAAA":
                seg = format(_h("AAAA", canon) % 0xffff, "04x")
                add("AAAA", [f"2001:db8::{seg}"])
        elif t == "NS":
            add("NS", base.get("NS", [f"ns1.{canon}.", f"ns2.{canon}."]))
        elif t == "MX":
            add("MX", base.get("MX", [f"10 mail.{canon}."]))
        elif t == "TXT":
            if base.get("TXT"):
                add("TXT", base["TXT"])
        elif t == "SOA":
            serial = datetime.now().strftime("%Y%m%d") + "01"
            ns = base.get("NS", [f"ns1.{canon}."])[0]
            add("SOA", [f"{ns} hostmaster.{canon}. {serial} 7200 3600 1209600 3600"])
    return out


# --------------------------------------------------------------------------- #
#  dig
# --------------------------------------------------------------------------- #
def dig_command(env, cwd, argv) -> str:
    if argv and argv[0] in {"-h", "--help", "help"}:
        return ("dig [@server] name [type] [+short]\n"
                "  dig example.com         dig example.com MX        dig AAAA example.com\n"
                "  dig -x 93.184.216.34    dig example.com ANY       dig +short example.com")
    opts = [a for a in argv if a.startswith("+")]
    short = "+short" in opts
    toks = [a for a in argv if not a.startswith(("+", "@"))]
    reverse = False
    if "-x" in toks:
        reverse = True
        toks = [t for t in toks if t != "-x"]
    qtype = "A"
    name = ""
    if reverse and toks:
        name = toks[0]
        qtype = "PTR"
    elif len(toks) == 1:
        name = toks[0]
    elif len(toks) >= 2:
        if toks[0].upper() in {"A", "AAAA", "MX", "NS", "TXT", "SOA", "ANY", "PTR", "CNAME"}:
            qtype, name = toks[0].upper(), toks[1]
        else:
            name, qtype = toks[0], toks[1].upper()
    if not name:
        return "dig: missing name (try: dig example.com)"

    if reverse:
        ptr = _reverse_name(name)
        if short:
            return ptr or ";; NXDOMAIN"
        arpa = ".".join(reversed(name.split("."))) + ".in-addr.arpa."
        ans = [f"{arpa}\t{_ttl(name)}\tIN\tPTR\t{ptr}"] if ptr else []
        return _dig_render(arpa, "PTR", ans, server="198.51.100.1")

    kind, canon, _ip = _classify(name)
    recs = _records(name, qtype)
    if short:
        if not recs:
            return ""
        return "\n".join(r[3] for r in recs)
    if kind == "nxdomain" or not recs:
        return _dig_render(name + ".", qtype, [], status="NXDOMAIN")
    ans = [f"{rn}\t{ttl}\tIN\t{rt}\t{val}" for (rn, ttl, rt, val) in recs]
    return _dig_render(canon + ".", qtype, ans)


def _dig_render(qname, qtype, answers, *, status="NOERROR", server="198.51.100.1") -> str:
    qid = _h("id", qname, qtype) % 65535
    flags = "qr rd ra" if answers else "qr rd ra"
    n = len(answers)
    lines = [
        f"; <<>> DiG 9.18.30 <<>> {qtype} {qname.rstrip('.')}",
        ";; global options: +cmd",
        ";; Got answer:",
        f";; ->>HEADER<<- opcode: QUERY, status: {status}, id: {qid}",
        f";; flags: {flags}; QUERY: 1, ANSWER: {n}, AUTHORITY: 0, ADDITIONAL: 1",
        "",
        ";; QUESTION SECTION:",
        f";{qname}\t\t\tIN\t{qtype}",
        "",
    ]
    if answers:
        lines.append(";; ANSWER SECTION:")
        lines.extend(answers)
        lines.append("")
    lines += [
        f";; Query time: {_h('qt', qname) % 40 + 2} msec",
        f";; SERVER: {server}#53({server})",
        f";; WHEN: {_now_dig()}",
        f";; MSG SIZE  rcvd: {len(' '.join(answers)) + 45 if answers else 45}",
    ]
    return "\n".join(lines)


def _reverse_name(ip: str) -> str:
    if not _IPRE.match(ip):
        return ""
    for canon, data in _ZONE.items():
        if ip in data.get("A", []):
            return canon + "."
    # documentation hosts get a synthesised PTR
    return f"host-{ip.replace('.', '-')}.documentation.invalid." if ip.startswith(
        ("192.0.2.", "198.51.100.", "203.0.113.")) else f"{ip}.in-addr.arpa."


# --------------------------------------------------------------------------- #
#  nslookup / host
# --------------------------------------------------------------------------- #
def nslookup_command(env, cwd, argv) -> str:
    toks = [a for a in argv if not a.startswith("-")]
    if not toks or argv[:1] == ["-h"]:
        return "nslookup name [server]"
    name = toks[0]
    server = "198.51.100.1"
    if _IPRE.match(name):
        ptr = _reverse_name(name)
        body = [f"{name}\tname = {ptr}"] if ptr else [f"** server can't find {name}: NXDOMAIN"]
        return "\n".join([f"Server:\t\t{server}", f"Address:\t{server}#53", ""] + body)
    kind, canon, ip = _classify(name)
    head = [f"Server:\t\t{server}", f"Address:\t{server}#53", ""]
    if kind == "nxdomain":
        return "\n".join(head + [f"** server can't find {name}: NXDOMAIN"])
    aaaa = _records(canon, "AAAA")
    out = [f"Name:\t{canon}", f"Address: {ip}"]
    for r in aaaa:
        out.append(f"Name:\t{canon}")
        out.append(f"Address: {r[3]}")
    return "\n".join(head + out)


def host_command(env, cwd, argv) -> str:
    toks = [a for a in argv if not a.startswith("-")]
    if not toks or argv[:1] == ["-h"]:
        return "host name"
    name = toks[0]
    if _IPRE.match(name):
        ptr = _reverse_name(name)
        return (f"{'.'.join(reversed(name.split('.')))}.in-addr.arpa domain name pointer {ptr}"
                if ptr else f"Host {name} not found: 3(NXDOMAIN)")
    kind, canon, ip = _classify(name)
    if kind == "nxdomain":
        return f"Host {name} not found: 3(NXDOMAIN)"
    lines = [f"{canon} has address {ip}"]
    for r in _records(canon, "AAAA"):
        lines.append(f"{canon} has IPv6 address {r[3]}")
    for r in _records(canon, "MX"):
        lines.append(f"{canon} mail is handled by {r[3]}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  whois
# --------------------------------------------------------------------------- #
def whois_command(env, cwd, argv) -> str:
    toks = [a for a in argv if not a.startswith("-")]
    if not toks or argv[:1] in (["-h"], ["--help"]):
        return "whois <domain|ip-address>"
    q = toks[0].strip().rstrip(".")
    if _IPRE.match(q):
        return _whois_ip(q)
    return _whois_domain(q.lower())


def _whois_domain(dom: str) -> str:
    d = _WHOIS_DOMAINS.get(dom)
    if d is None:
        # synthesise a plausible record for any valid-looking domain
        if not _NAMERE.match(dom) or dom.endswith(".invalid"):
            return f"No whois server is known for this kind of object.\n%% {dom}: NOT FOUND"
        created = f"20{_h('c', dom) % 24:02d}-{_h('m', dom) % 12 + 1:02d}-{_h('d', dom) % 28 + 1:02d}"
        d = {"Registrar": "Gibson Classroom Registrar, LLC",
             "Created": created, "Updated": "2025-01-01", "Expiry": "2026-01-01",
             "NS": [f"NS1.{dom.upper()}", f"NS2.{dom.upper()}"], "Status": "ok"}
    lines = [
        f"Domain Name: {dom.upper()}",
        f"Registry Domain ID: {_h('id', dom) % 9_000_000 + 1_000_000}_DOMAIN-VRSN",
        f"Registrar: {d['Registrar']}",
        f"Updated Date: {d['Updated']}T00:00:00Z",
        f"Creation Date: {d['Created']}T00:00:00Z",
        f"Registry Expiry Date: {d['Expiry']}T00:00:00Z",
    ]
    for ns in d["NS"]:
        lines.append(f"Name Server: {ns}")
    lines += [f"Domain Status: {d['Status']} https://icann.org/epp#{d['Status']}",
              ">>> Last update of whois database: " + _now_dig() + " <<<"]
    return "\n".join(lines)


def _whois_ip(ip: str) -> str:
    octets = [int(x) for x in ip.split(".")]
    if octets[0] in (10,) or (octets[0] == 192 and octets[1] == 168) or (octets[0] == 172 and 16 <= octets[1] <= 31):
        return f"NetRange:       {ip}\nCIDR:           private\nNetName:        PRIVATE-USE\nOrgName:        RFC1918 Private Network\nCountry:        ZZ"
    for lo, hi, cidr, name, org, cc, rir in _WHOIS_NETS:
        if _ip_in(ip, lo, hi):
            return "\n".join([
                f"NetRange:       {lo} - {hi}", f"CIDR:           {cidr}",
                f"NetName:        {name}", f"OrgName:        {org}",
                f"Country:        {cc}", f"RegDate:        2010-01-01",
                f"Source:         {rir}",
            ])
    # synthesise
    return "\n".join([
        f"NetRange:       {ip} - {ip}", f"CIDR:           {ip}/32",
        f"NetName:        NET-{ip.replace('.', '-')}", "OrgName:        Gibson Classroom Allocation",
        "Country:        ZZ", "Source:         GIBSON",
    ])


def _ip_in(ip, lo, hi) -> bool:
    def packed(a):
        p = [int(x) for x in a.split(".")]
        return (p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]
    return packed(lo) <= packed(ip) <= packed(hi)


# --------------------------------------------------------------------------- #
#  ping / traceroute  (z/OS Communications Server format)
# --------------------------------------------------------------------------- #
def ping_command(host: str, count: int = 5) -> str:
    kind, canon, ip = _classify(host)
    if kind == "nxdomain":
        return "\n".join([f"CS V2R5: Pinging host {host}",
                          f"EZZ3210I Unknown host {host}",
                          "EZZ3218I Ping complete: 0 packets transmitted, 0 packets received"])
    count = max(1, min(count, 10))
    local = kind == "local" or ip == "127.0.0.1"
    target = canon if kind != "ip" else ip
    lines = [f"CS V2R5: Pinging host {target} ({ip})"]
    times = []
    for i in range(1, count + 1):
        base = 0.2 if local else (_h("rtt", canon, str(i)) % 380) / 10.0 + 4.0
        t = round(base / 1000.0, 3) if local else round(base / 1000.0, 3)
        times.append(base if not local else 0.2)
        lines.append(f"Ping #{i} response took {t:.3f} seconds.")
    lo, hi, avg = min(times), max(times), sum(times) / len(times)
    lines.append(f"EZZ3218I Ping complete: {count} packets transmitted, {count} packets received")
    lines.append(f"         round-trip min/avg/max = {lo:.1f}/{avg:.1f}/{hi:.1f} ms")
    return "\n".join(lines)


def traceroute_command(host: str, max_hops: int = 30) -> str:
    kind, canon, ip = _classify(host)
    if kind == "nxdomain":
        return f"CS V2R5: Traceroute to {host}\nEZZ3210I Unknown host {host}"
    target = canon if kind not in ("ip",) else ip
    lines = [f"CS V2R5: Traceroute to {target} ({ip}), {max_hops} hops max"]
    if kind == "local" or ip == "127.0.0.1":
        lines.append(f" 1  localhost (127.0.0.1)  0.210 ms  0.190 ms  0.180 ms")
        return "\n".join(lines)
    # build a believable path: gateway -> isp -> backbone -> dest
    hops = [
        ("10.0.0.1", "gateway.local"),
        ("172.16.0.1", "core1.classroom.net"),
        (f"198.51.100.{_h('h3', canon) % 200 + 1}", "edge.transit.net"),
        (f"203.0.113.{_h('h4', canon) % 200 + 1}", "peer.backbone.net"),
        (ip, target),
    ]
    for n, (hip, hname) in enumerate(hops, 1):
        base = (_h("hop", canon, str(n)) % 200) / 10.0 + n * 1.5
        t = [f"{base + j:.3f} ms" for j in (0.0, 0.4, 0.2)]
        lines.append(f"{n:2d}  {hname} ({hip})  " + "  ".join(t))
    return "\n".join(lines)
