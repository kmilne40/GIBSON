"""Live reconnaissance backend for the EZRecon ISPF panel.

A faithful port of the kmilne40/EZRecon ("Reccy Toolkit") lookup functions. Each
function performs the *real* lookup exactly as the original curses tool does -
DNS via dnspython, WHOIS via the system ``whois`` binary, email harvesting via
requests+BeautifulSoup, subdomain brute force via DNS resolution, and Shodan via
the ``shodan`` API - and returns a list of text lines for the panel to render.

The port-scan and "get all" actions from the original are intentionally absent.

Each function degrades gracefully: a missing Python dependency or the missing
``whois`` binary yields a clear message instead of raising, matching the spirit
of the original tool's error handling. Network calls are bounded by timeouts so a
3270 session is never hung indefinitely.

The DNS/WHOIS/HTTP/Shodan calls are routed through small seam helpers
(``_dns_records``, ``_whois_raw``, ``_http_get``, ``_shodan_search_raw``,
``_shodan_host_raw``, ``_axfr``) so they can be monkeypatched in tests where there
is no network.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
from typing import List, Optional

DNS_TIMEOUT = 5.0
WHOIS_TIMEOUT = 15.0
HTTP_TIMEOUT = 10.0
SHODAN_TIMEOUT = 15.0
SUBDOMAIN_BUDGET = 60.0          # seconds; keeps the panel responsive
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_DOMAIN_RE = re.compile(r"^(?!-)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")


# --------------------------------------------------------------- validation
def is_valid_domain(domain: str) -> bool:
    return bool(_DOMAIN_RE.match(domain or ""))


def is_valid_ip(ip_address: str) -> bool:
    try:
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------- seams
def _resolver():
    import dns.resolver  # noqa: F401  (raises ImportError if dnspython absent)
    import dns.reversename  # noqa: F401
    import dns.resolver as resolver
    return resolver


def _dns_records(domain: str, rtype: str) -> List[str]:
    """Resolve a record type, returning a list of to_text() strings. May raise."""
    resolver = _resolver()
    resolver.default_resolver = resolver.get_default_resolver()
    answers = resolver.resolve(domain, rtype, lifetime=DNS_TIMEOUT)
    return [rdata.to_text() for rdata in answers]


def _dns_answer(domain: str, rtype: str):
    """Return the raw answer object for richer record types (SOA/MX). May raise."""
    resolver = _resolver()
    return resolver.resolve(domain, rtype, lifetime=DNS_TIMEOUT)


def _reverse_ptr(ip: str) -> List[str]:
    import dns.reversename
    resolver = _resolver()
    rev = dns.reversename.from_address(ip)
    answers = resolver.resolve(rev, "PTR", lifetime=DNS_TIMEOUT)
    return [str(r.target).rstrip(".") for r in answers]


def _axfr(ns: str, domain: str) -> Optional[str]:
    """Attempt a zone transfer from one nameserver; return zone text or None."""
    import dns.query
    import dns.zone
    try:
        zone = dns.zone.from_xfr(dns.query.xfr(ns, domain, timeout=DNS_TIMEOUT))
    except Exception:
        return None
    return zone.to_text() if zone else None


def _whois_raw(domain: str) -> str:
    return subprocess.check_output(
        ["whois", domain], stderr=subprocess.STDOUT, text=True, timeout=WHOIS_TIMEOUT)


def _http_get(url: str) -> str:
    import requests
    resp = requests.get(url, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _shodan_api(api_key: str):
    import shodan
    return shodan.Shodan(api_key)


def _shodan_search_raw(api_key: str, query: str):
    return _shodan_api(api_key).search(query)


def _shodan_host_raw(api_key: str, ip: str):
    return _shodan_api(api_key).host(ip)


def _dep_msg(exc: Exception, what: str) -> List[str]:
    if isinstance(exc, ImportError):
        return [f"{what} requires a Python module that is not installed: {exc}.",
                "Install it on the host running Gibson (e.g. pip install dnspython shodan)."]
    if isinstance(exc, FileNotFoundError):
        return [f"{what}: the 'whois' command is not installed on this host."]
    if isinstance(exc, subprocess.TimeoutExpired):
        return [f"{what}: command timed out."]
    return [f"{what} error: {exc}"]


# --------------------------------------------------------------- 1. DNS A
def dns_a(domain: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    try:
        recs = _dns_records(domain, "A")
    except Exception as exc:
        return _dep_msg(exc, "DNS lookup") if isinstance(exc, (ImportError,)) else \
            [f"No A records found for {domain} or domain is invalid.", f"({exc})"]
    if not recs:
        return [f"No A records found for {domain}."]
    return [f"A records for {domain}:", ""] + [f"  {ip:<18} IN  A" for ip in recs]


# --------------------------------------------------------------- 2. MX (+SPF/DMARC)
def mx(domain: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    out: List[str] = []
    try:
        ans = _dns_answer(domain, "MX")
        mxr = sorted((int(r.preference), r.exchange.to_text()) for r in ans)
        out += [f"MX records for {domain}:", ""]
        out += [f"  {pref:<5} {host}" for pref, host in mxr]
    except Exception as exc:
        if isinstance(exc, ImportError):
            return _dep_msg(exc, "MX lookup")
        return [f"No MX records found for {domain} or domain is invalid."]
    # SPF (TXT containing v=spf1)
    out += ["", "SPF records:"]
    try:
        txt = _dns_records(domain, "TXT")
        spf = [t.strip('"') for t in txt if "v=spf1" in t]
        out += [f"  {s}" for s in spf] if spf else ["  (none found)"]
    except Exception:
        out += ["  (none found)"]
    # DMARC (_dmarc.<domain> TXT)
    out += ["", "DMARC records:"]
    try:
        dmarc = _dns_records("_dmarc." + domain, "TXT")
        out += [f"  {d.strip(chr(34))}" for d in dmarc] if dmarc else ["  (none found)"]
    except Exception:
        out += ["  (none found)"]
    return out


# --------------------------------------------------------------- 3. NS
def ns(domain: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    try:
        ans = _dns_answer(domain, "NS")
        recs = [r.target.to_text() for r in ans]
    except Exception as exc:
        if isinstance(exc, ImportError):
            return _dep_msg(exc, "NS lookup")
        return [f"No NS records found for {domain} or domain is invalid."]
    if not recs:
        return [f"No NS records found for {domain}."]
    return [f"NS records for {domain}:", ""] + [f"  {n}" for n in recs]


# --------------------------------------------------------------- 4. SOA
def soa(domain: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    try:
        ans = _dns_answer(domain, "SOA")
        r = list(ans)[0]
        pairs = [("Primary Name Server", r.mname.to_text()),
                 ("Responsible Person", r.rname.to_text()),
                 ("Serial Number", r.serial), ("Refresh Interval", r.refresh),
                 ("Retry Interval", r.retry), ("Expire Limit", r.expire),
                 ("Minimum TTL", r.minimum)]
    except Exception as exc:
        if isinstance(exc, ImportError):
            return _dep_msg(exc, "SOA lookup")
        return [f"No SOA record found for {domain}."]
    return [f"SOA record for {domain}:", ""] + [f"  {k:<20}: {v}" for k, v in pairs]


# --------------------------------------------------------------- 5. reverse DNS
def reverse(ip_address: str) -> List[str]:
    if not is_valid_ip(ip_address):
        return [f"Invalid IP address: {ip_address}"]
    try:
        recs = _reverse_ptr(ip_address)
    except Exception as exc:
        if isinstance(exc, ImportError):
            return _dep_msg(exc, "Reverse DNS lookup")
        return [f"No PTR record found for {ip_address}."]
    if not recs:
        return [f"No PTR record found for {ip_address}."]
    return [f"PTR record for {ip_address}:", ""] + [f"  {ip_address} -> {n}" for n in recs]


# --------------------------------------------------------------- 6. WHOIS
def whois(domain: str) -> List[str]:
    if not domain:
        return ["No domain entered."]
    try:
        raw = _whois_raw(domain)
    except subprocess.CalledProcessError as exc:
        return [f"WHOIS command failed:", *(exc.output or "").splitlines()]
    except Exception as exc:
        return _dep_msg(exc, "WHOIS lookup")
    lines = [f"WHOIS information for {domain}:", ""]
    lines += [ln.rstrip() for ln in raw.splitlines()]
    return lines


# --------------------------------------------------------------- 7. zone transfer
def zone_transfer(domain: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    try:
        ans = _dns_answer(domain, "NS")
        servers = [r.target.to_text().rstrip(".") for r in ans]
    except Exception as exc:
        if isinstance(exc, ImportError):
            return _dep_msg(exc, "Zone transfer")
        return [f"No NS records found for {domain}; cannot attempt AXFR."]
    out = [f"Attempting zone transfer (AXFR) for {domain}:", ""]
    for nsrv in servers:
        zt = _axfr(nsrv, domain)
        if zt:
            out.append(f"  {nsrv:<30} XFR ALLOWED")
            out += ["", f"Zone transfer succeeded against {nsrv}:", ""]
            out += ["  " + ln for ln in zt.splitlines()]
            out += ["", "FINDING: zone transfer allowed - information disclosure (CWE-200)."]
            return out
        out.append(f"  {nsrv:<30} REFUSED")
    out += ["", "Zone transfer did not succeed with any name server."]
    return out


# --------------------------------------------------------------- 8. email scraper
def email_scraper(base_url: str, depth: int = 2) -> List[str]:
    if not base_url:
        return ["No URL entered."]
    if not base_url.startswith(("http://", "https://")):
        base_url = "http://" + base_url
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except Exception as exc:
        return _dep_msg(exc, "Email scraper")
    visited, emails = set(), set()
    queue = [(base_url, 0)]
    visited.add(base_url)
    pages = 0
    while queue and pages < 60:
        url, d = queue.pop(0)
        if d > depth:
            continue
        try:
            html = _http_get(url)
        except Exception:
            continue
        pages += 1
        for e in EMAIL_RE.findall(html):
            emails.add(e)
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a.get("href"))
                if link.startswith(base_url) and link not in visited:
                    visited.add(link)
                    queue.append((link, d + 1))
        except Exception:
            pass
    out = [f"Email harvest for {base_url} (depth {depth}, {pages} pages):", ""]
    if emails:
        out += [f"  {e}" for e in sorted(emails)]
        out += ["", f"{len(emails)} addresses found."]
    else:
        out += ["  No emails found."]
    return out


# --------------------------------------------------------------- 9. subdomains
def brute_force_subdomains(domain: str, wordlist_path: str) -> List[str]:
    if not is_valid_domain(domain):
        return [f"Invalid domain format: {domain}"]
    if not wordlist_path:
        return ["No wordlist path supplied (set WORDLIST ===> /path/to/subs.txt)."]
    try:
        with open(wordlist_path, "r", encoding="utf-8", errors="ignore") as fh:
            words = [w.strip() for w in fh if w.strip()]
    except FileNotFoundError:
        return [f"Wordlist file not found: {wordlist_path}"]
    except Exception as exc:
        return [f"Error reading wordlist '{wordlist_path}': {exc}"]
    try:
        self_resolver = _resolver()
    except Exception as exc:
        return _dep_msg(exc, "Subdomain brute force")
    import time
    found, start, tried = [], time.time(), 0
    for sub in words:
        if time.time() - start > SUBDOMAIN_BUDGET:
            break
        tried += 1
        fqdn = f"{sub}.{domain}"
        try:
            ips = self_resolver.resolve(fqdn, "A", lifetime=DNS_TIMEOUT)
            found.append((fqdn, ", ".join(r.address for r in ips)))
        except Exception:
            continue
    out = [f"Subdomain brute force for {domain} ({tried} tried):", ""]
    if found:
        out += [f"  {h:<36} {ips}" for h, ips in found]
        out += ["", f"{len(found)} subdomains discovered."]
    else:
        out += ["  No subdomains were discovered."]
    return out


# --------------------------------------------------------------- 10. shodan
def shodan_search(query: str, api_key: str) -> List[str]:
    if not api_key:
        return ["No Shodan API key set (enter it in the APIKEY field or set SHODAN_API_KEY)."]
    if not query:
        return ["No Shodan search query entered."]
    try:
        results = _shodan_search_raw(api_key, query)
    except Exception as exc:
        return _dep_msg(exc, "Shodan search") if isinstance(exc, ImportError) else \
            [f"Shodan API error: {exc}"]
    matches = results.get("matches", []) if isinstance(results, dict) else []
    out = [f"Shodan search results for '{query}':", "",
           f"  {'#':<4}{'IP':<16}{'PORT':<6}DATA"]
    for i, m in enumerate(matches[:100], 1):
        ip = m.get("ip_str", "N/A")
        port = m.get("port", "N/A")
        data = (m.get("data", "") or "").replace("\n", " ").strip()[:48]
        out.append(f"  {i:<4}{ip:<16}{str(port):<6}{data}")
    out += ["", f"{min(len(matches),100)} of {results.get('total', len(matches))} matches shown."]
    return out


def shodan_host(ip: str, api_key: str) -> List[str]:
    if not api_key:
        return ["No Shodan API key set (enter it in the APIKEY field or set SHODAN_API_KEY)."]
    if not is_valid_ip(ip):
        return [f"Invalid IP address: {ip}"]
    try:
        host = _shodan_host_raw(api_key, ip)
    except Exception as exc:
        return _dep_msg(exc, "Shodan host") if isinstance(exc, ImportError) else \
            [f"Shodan API error: {exc}"]
    out = [f"Shodan host information for {ip}:", "",
           f"  IP:           {host.get('ip_str', 'N/A')}",
           f"  Organization: {host.get('org', 'N/A')}",
           f"  Operating Sys:{host.get('os', 'N/A')}", "",
           "  Open ports and services:"]
    for svc in host.get("data", []):
        port = svc.get("port", "N/A")
        prod = svc.get("product", "") or ""
        banner = (svc.get("data", "") or "").replace("\n", " ").strip()[:46]
        out.append(f"    {str(port):<6}{prod:<14}{banner}")
    vulns = host.get("vulns", [])
    if vulns:
        out += ["", "  Vulnerabilities:"] + [f"    {v}" for v in vulns]
    return out


# selection helpers used by the panel: ((code, label, kind)) where kind drives
# which entry field is used (domain / ip / url / query).
ACTIONS = [
    ("1",  "DNS Lookup (A)",        "domain", "dns_a"),
    ("2",  "MX Lookup",             "domain", "mx"),
    ("3",  "NS Lookup",             "domain", "ns"),
    ("4",  "SOA Lookup",            "domain", "soa"),
    ("5",  "Reverse DNS Lookup",    "ip",     "reverse"),
    ("6",  "WHOIS Lookup",          "domain", "whois"),
    ("7",  "Zone Transfer",         "domain", "zone_transfer"),
    ("8",  "Email Scraper",         "url",    "email_scraper"),
    ("9",  "Brute Force Subdomains","domain", "brute_force_subdomains"),
    ("10", "Shodan Lookup",         "shodan", "shodan_search"),
]
