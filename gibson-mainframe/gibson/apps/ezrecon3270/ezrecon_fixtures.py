"""Offline fixture output for EZRecon.

When the live Python modules (``dnspython`` / ``shodan``) are not installed on
the Gibson host, the recon toolkit would otherwise only print an install hint.
These fixtures return believable, deterministic reconnaissance output for the
training targets so the toolkit is fully usable offline.  Output is clearly
marked as simulated and uses the RFC 5737 documentation address ranges so it is
unambiguously non-routable lab data.
"""
from __future__ import annotations

import hashlib
from typing import List, Optional


def _h(name: str, n: int = 0) -> int:
    return int(hashlib.md5(f"{name}:{n}".encode()).hexdigest(), 16)


def _ip(name: str, n: int = 0) -> str:
    # 203.0.113.0/24 is TEST-NET-3 (documentation/lab use only).
    return f"203.0.113.{_h(name, n) % 250 + 2}"


def _sim(lines: List[str]) -> List[str]:
    return ["(simulated output - dnspython/shodan not installed on the Gibson host)",
            "(install with: pip install dnspython shodan  - then results go live)",
            ""] + lines


def dns_a(t: str, *_a) -> List[str]:
    return _sim([f"A records for {t}:", "",
                 f"  {_ip(t,1):<18} IN  A",
                 f"  {_ip(t,2):<18} IN  A"])


def mx(t: str, *_a) -> List[str]:
    return _sim([f"MX records for {t}:", "",
                 f"  10    mail1.{t}",
                 f"  20    mail2.{t}",
                 "", "SPF records:",
                 f'  v=spf1 include:_spf.{t} -all',
                 "", "DMARC records:",
                 f'  v=DMARC1; p=quarantine; rua=mailto:dmarc@{t}'])


def ns(t: str, *_a) -> List[str]:
    return _sim([f"NS records for {t}:", "",
                 f"  ns1.{t}", f"  ns2.{t}"])


def soa(t: str, *_a) -> List[str]:
    serial = 2026010100 + (_h(t) % 99)
    pairs = [("Primary Name Server", f"ns1.{t}"),
             ("Responsible Person", f"hostmaster.{t}"),
             ("Serial Number", serial), ("Refresh Interval", 7200),
             ("Retry Interval", 3600), ("Expire Limit", 1209600),
             ("Minimum TTL", 3600)]
    return _sim([f"SOA record for {t}:", ""] + [f"  {k:<20}: {v}" for k, v in pairs])


def reverse(t: str, *_a) -> List[str]:
    return _sim([f"PTR record for {t}:", "",
                 f"  {t} -> host-{t.replace('.', '-')}.in-addr.lab"])


def whois(t: str, *_a) -> List[str]:
    return _sim([f"WHOIS record for {t}:", "",
                 f"  Domain Name: {t.upper()}",
                 "  Registrar: Lab Registrar, Inc.",
                 "  Creation Date: 2014-03-12T00:00:00Z",
                 "  Registry Expiry Date: 2027-03-12T00:00:00Z",
                 f"  Name Server: NS1.{t.upper()}",
                 f"  Name Server: NS2.{t.upper()}",
                 "  DNSSEC: unsigned",
                 "  Registrant Organization: Sighber Cyber (training fixture)"])


def zone_transfer(t: str, *_a) -> List[str]:
    return _sim([f"AXFR attempt for {t}:", "",
                 "  Transfer refused by ns1 (REFUSED) - good hygiene.",
                 "  Transfer refused by ns2 (REFUSED).",
                 "", "  No zone data exposed."])


def email_scraper(t: str, *_a) -> List[str]:
    base = t.split("//")[-1].split("/")[0]
    return _sim([f"Email addresses harvested from {t}:", "",
                 f"  info@{base}", f"  security@{base}", f"  careers@{base}"])


def brute_force_subdomains(t: str, *_a) -> List[str]:
    subs = ["www", "mail", "vpn", "dev", "test", "api", "portal", "mq", "ftp"]
    found = [s for s in subs if _h(t, ord(s[0])) % 3]
    return _sim([f"Subdomains discovered for {t}:", ""] +
                [f"  {s}.{t:<24} {_ip(t, ord(s[0]))}" for s in found])


def shodan_search(t: str, *_a) -> List[str]:
    return _sim([f"Shodan results for {t}:", "",
                 f"  {_ip(t,3)}:23    IBM z/OS TN3270  (VTAM)",
                 f"  {_ip(t,3)}:21    IBM OS/390 ftpd V2R5",
                 f"  {_ip(t,3)}:50000 IBM Db2 DRDA",
                 "", "  (set a real SHODAN API key in the API Key field for live data)"])


_TABLE = {
    "dns_a": dns_a, "mx": mx, "ns": ns, "soa": soa, "reverse": reverse,
    "whois": whois, "zone_transfer": zone_transfer, "email_scraper": email_scraper,
    "brute_force_subdomains": brute_force_subdomains, "shodan_search": shodan_search,
}


def get(fn: str, target: str, arg: str = "", api_key: str = "") -> Optional[List[str]]:
    f = _TABLE.get(fn)
    return f(target, arg, api_key) if f else None


def looks_like_missing_dep(lines: List[str]) -> bool:
    """True if a live-lookup result is just a missing-module / install hint, or a
    Shodan no-key hint (so the toolkit still shows useful demo output offline)."""
    blob = " ".join(lines).lower()
    return ("not installed" in blob or "requires a python module" in blob
            or "no module named" in blob or "no shodan api key" in blob)
