from __future__ import annotations

import csv
import io
import json
import os
import base64
from datetime import datetime
from html import escape
from urllib.parse import parse_qs, urlparse, unquote_plus

from .content import PAGES
from . import sentry_pages

NAV = ["/welcome", "/gibson", "/manual", "/apps", "/ports", "/getting-started", "/safety", "/labs/identity", "/cti", "/links"]
CTI_CANONICAL = {
    "/cti", "/cti/dashboard", "/cti/feed", "/cti/ioc-search", "/cti/threat-actors",
    "/cti/c2-tracker", "/cti/investigations", "/cti/reports", "/cti/settings", "/cti/documentation",
    "/cti/events", "/cti/security", "/cti/hms", "/cti/plonk", "/cti/plonk/sql", "/cti/plonk/pcap", "/cti/iocs", "/cti/providers", "/cti/api-keys", "/cti/enrichment",
    "/cti/api/events", "/cti/reports/security.csv",
    "/cti/mitre", "/cti/m4m", "/cti/m4m/navigator", "/cti/m4m/layer.json", "/cti/honeypot", "/cti/rss", "/cti/rss/status", "/cti/actors", "/cti/vulnerabilities", "/cti/ttps",
}
CTI_ALIASES = {
    "/cti/map": "/cti/dashboard",
        "/cti/research": "/cti/ioc-search",
    "/cti/stats": "/cti/dashboard",
    "/cti/feeds": "/cti/settings",
    "/cti/export": "/cti/reports",
    "/cti/help": "/cti/documentation",
}
CTI_ROUTES = CTI_CANONICAL | set(CTI_ALIASES)

# Gibson-native fixture equivalents of the Sentinel/Base44 entities.  These are
# not imported from the React app; they are the offline-first training data model.
THREAT_ACTORS = [
    {"name":"APT28 (Fancy Bear)", "aliases":"Sofacy, STRONTIUM", "motivation":"Espionage", "regions":"Eastern Europe", "confidence":"High", "severity":"critical", "status":"Active", "tags":"phishing,c2,credential-access"},
    {"name":"FIN7-style Retail Cluster", "aliases":"Carbanak-inspired", "motivation":"Financial", "regions":"Global", "confidence":"Medium", "severity":"high", "status":"Tracking", "tags":"malware,pos,c2"},
    {"name":"Mainframe Scanner Botnet", "aliases":"Gibson fixture", "motivation":"Reconnaissance", "regions":"Mixed", "confidence":"Fixture", "severity":"medium", "status":"Lab", "tags":"scanner,tn3270,botnet"},
]
INVESTIGATIONS = [
    {"title":"Suspected TN3270 Reconnaissance", "status":"Open", "severity":"high", "owner":"SOC1", "summary":"Multiple login and port-touch events linked to a red CTI source."},
    {"title":"Tomcat Manager Default Credential Exposure", "status":"In Progress", "severity":"critical", "owner":"SOC2", "summary":"Correlates Manager login, WAR metadata deployment and 31337 session telemetry."},
]
REPORTS = [
    {"title":"Daily Gibson Honeypot Intelligence Summary", "severity":"medium", "format":"SMF/JSON/CSV", "summary":"Summary of geolocation, IOC matches, high-risk connections and training evidence."},
]


CTI_PROVIDERS = [
    {"name":"AbuseIPDB","category":"IP reputation","key":"required","free":"Free tier available","data":"abuse score, country, ISP, reports","ttl":"24h"},
    {"name":"VirusTotal","category":"IP/domain/url/hash reputation","key":"required","free":"Community API tier","data":"detections, relationships, submissions","ttl":"24h"},
    {"name":"Shodan","category":"Internet exposure","key":"required","free":"Limited/free account queries","data":"open ports, banners, org, tags","ttl":"7d"},
    {"name":"Censys","category":"Internet exposure","key":"required","free":"Free tier","data":"hosts, certificates, services","ttl":"7d"},
    {"name":"GreyNoise","category":"Scanner/noise classification","key":"optional","free":"Community/API options","data":"noise, benign, malicious, RIOT","ttl":"24h"},
    {"name":"URLHaus","category":"Malicious URLs","key":"not required","free":"Open API","data":"malware URLs, payloads, status","ttl":"12h"},
    {"name":"ThreatFox","category":"IOCs and malware families","key":"not required","free":"Open API","data":"IOC, malware, confidence, tags","ttl":"12h"},
    {"name":"MalwareBazaar","category":"Malware hashes","key":"not required","free":"Open API","data":"hashes, signatures, tags","ttl":"24h"},
    {"name":"AlienVault OTX","category":"Pulses/threat intel","key":"required","free":"Free community tier","data":"pulses, indicators, tags","ttl":"24h"},
    {"name":"CISA KEV","category":"Known exploited CVEs","key":"not required","free":"Public catalog","data":"CVE, vendor, product, due date","ttl":"24h"},
    {"name":"NVD","category":"CVE metadata","key":"optional","free":"Public API with limits","data":"CVSS, descriptions, references","ttl":"24h"},
    {"name":"FIRST EPSS","category":"Exploit prediction","key":"not required","free":"Public API","data":"EPSS probability and percentile","ttl":"24h"},
    {"name":"RDAP/WHOIS","category":"Registration context","key":"not required","free":"Public RDAP","data":"registrar, network, ASN hints","ttl":"7d"},
    {"name":"IPinfo/Free Geo","category":"Geo/ASN","key":"optional","free":"Free tiers vary","data":"geo, ASN, org, privacy flags","ttl":"7d"},
    {"name":"Spamhaus DROP/EDROP","category":"Drop lists","key":"not required","free":"Public lists","data":"known malicious ranges","ttl":"24h"},
    {"name":"Feodo Tracker","category":"Botnet C2","key":"not required","free":"Public feed","data":"C2 IPs, ports, malware family","ttl":"6h"},
]

M4M_TTPS = [
    ("MF-TTP01", "OSINT and mainframe footprinting", "Reconnaissance", "T1592"),
    ("MF-TTP02", "Phishing path to users with mainframe reach", "Initial Access", "T1566.002"),
    ("MF-TTP03", "Adversary-in-the-middle against TN3270/FTP paths", "Credential Access", "T1557.003"),
    ("MF-TTP04", "CICS to JES internal reader abuse", "Execution", "T1106"),
    ("MF-TTP05", "Writable APF-authorized library escalation", "Privilege Escalation", "T1068"),
    ("MF-TTP06", "RACF/Db2/dataset collection", "Collection", "T1005"),
    ("MF-TTP07", "Exfiltration of PII/card data", "Exfiltration", "T1567"),
    ("MF-TTP08", "Offline RACF hash cracking", "Credential Access", "T1110.002"),
    ("MF-TTP09", "JES/SDSF/SYSOUT footprint reduction", "Defense Evasion", "T1070"),
    ("MF-TTP10", "Dataset encryption impact scenario", "Impact", "T1486"),
]

HONEYPOT_FIXTURE = [
    {"session":"EZIDS-0001","ip":"185.220.101.34","country":"DE","service":"TN3270","user":"IBMUSER","classification":"mainframe-aware probe","risk":"critical","commands":"L TSO, LU IBMUSER, LISTCAT","cti":"Tor/abuse fixture"},
    {"session":"EZFTP-0007","ip":"45.146.164.110","country":"NL","service":"FTP/JES","user":"anonymous","classification":"credential spray","risk":"high","commands":"USER anonymous, SITE FILETYPE=JES","cti":"Feodo/Spamhaus fixture"},
    {"session":"EZPROXY-0012","ip":"198.51.100.66","country":"US","service":"Tomcat","user":"tomcat","classification":"default credential bot","risk":"critical","commands":"manager/html, WAR deploy","cti":"Gibson C2 fixture"},
]


def is_welcome_route(path: str) -> bool:
    base = urlparse(path or "/").path
    return base in PAGES or base == "/health" or base.startswith("/manual") or base in CTI_ROUTES


def _sysname(state=None) -> str:
    return escape(getattr(getattr(state, "network", None), "hostname", "GIBSON") if state is not None else "GIBSON")


def _base_style() -> str:
    return """
<style>
:root{--bg:#07111c;--panel:#0c1726;--panel2:#102239;--line:#1d3a5c;--text:#ecf4ff;--muted:#8ea6c4;--blue:#20a7e2;--green:#20c997;--purple:#a85ed6;--orange:#f59e0b;--red:#ef4444;--cyan:#22d3ee}
*{box-sizing:border-box}body{font-family:Inter,system-ui,Arial,sans-serif;margin:0;background:var(--bg);color:var(--text)}a{color:#40bfff;text-decoration:none}.shell{display:flex;min-height:100vh}.sidebar{width:250px;background:#081321;border-right:1px solid #182b45;position:sticky;top:0;height:100vh;padding:0}.brand{height:72px;border-bottom:1px solid #182b45;display:flex;align-items:center;gap:12px;padding:0 18px}.shield{width:36px;height:36px;border-radius:10px;background:#0c3150;display:grid;place-items:center;color:#20a7e2;font-weight:900}.brand h1{font-size:14px;margin:0;letter-spacing:.06em}.brand p{font-size:10px;color:var(--muted);margin:0;letter-spacing:.18em}.nav{padding:16px 10px}.nav a{display:flex;align-items:center;gap:10px;padding:12px 14px;border-radius:10px;color:#91a7c5;margin-bottom:6px;font-weight:600}.nav a.active,.nav a:hover{background:#0b243d;color:#16b7ff}.main{flex:1}.top{height:72px;border-bottom:1px solid #182b45;background:#070e19;display:flex;align-items:center;justify-content:space-between;padding:0 28px}.top h2{margin:0;font-size:26px}.sub{color:var(--muted);font-size:14px}.live{border:1px solid #095f54;border-radius:999px;color:#28e0ac;background:#072d29;padding:8px 14px;font-family:ui-monospace,monospace}.content{padding:28px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}.card{background:var(--panel);border:1px solid #1b304d;border-radius:14px;padding:20px;margin-bottom:18px}.card h3,.card h2{margin-top:0}.stat .label{color:#91a7c5;text-transform:uppercase;letter-spacing:.08em;font-size:13px}.stat .value{font-size:34px;font-weight:800;margin-top:10px}.badge{display:inline-block;border-radius:8px;padding:4px 9px;font-size:12px;font-family:ui-monospace,monospace;border:1px solid #253d60;background:#101f33;margin:2px}.critical,.red{color:#ff6b6b;border-color:#7f1d1d;background:#331218}.high,.orange{color:#ffb04d;border-color:#7c4b13;background:#2f2111}.medium{color:#d8b4fe;border-color:#4c1d95;background:#1d1430}.low,.green{color:#36e0b3;border-color:#065f46;background:#0b2a23}.yellow{color:#fff176;border-color:#7c6f00;background:#2a2600}.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #1b304d;padding:10px;text-align:left;vertical-align:top}th{color:#9ab2d1;font-size:12px;text-transform:uppercase;letter-spacing:.08em}.bars{height:190px;display:flex;align-items:end;gap:24px;padding:18px}.bar{width:52px;border-radius:6px 6px 0 0;background:var(--blue);min-height:8px}.donut{width:170px;height:170px;border-radius:50%;background:conic-gradient(var(--blue) 0 25%,var(--green) 25% 50%,var(--purple) 50% 72%,var(--orange) 72% 100%);margin:auto;position:relative}.donut:after{content:"";position:absolute;inset:45px;border-radius:50%;background:var(--panel)}.mapbox{min-height:260px;background:#050b14;border:1px solid #19314f;border-radius:14px;padding:14px}.marker{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px}.m-red{background:var(--red)}.m-orange{background:var(--orange)}.m-yellow{background:#e6d84b}.m-neutral{background:#5aa1ff}.form input,.form select{background:#07111c;color:var(--text);border:1px solid #244363;border-radius:8px;padding:9px;margin-right:8px}.form button{background:#0ea5e9;color:white;border:0;border-radius:8px;padding:10px 14px;font-weight:700}.footer{padding:20px 28px;color:#8297b3;border-top:1px solid #182b45}.plain{max-width:1200px;margin:auto;padding:2rem}.plain header,.plain footer{background:#06111f;padding:1rem 2rem}.plain .card{margin:1rem 0}.plain nav a{margin-right:1rem}

.docs-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px;align-items:start}.docs-sidebar{position:sticky;top:10px;max-height:calc(100vh - 40px);overflow:auto;border:1px solid var(--line);border-radius:14px;background:#06111f;padding:14px}.docs-sidebar a{display:block;padding:8px 10px;border-radius:8px;color:#b9d1ee}.docs-sidebar a:hover{background:#0b243d;color:#fff}.manual-article{max-width:none;min-width:0}.manual-article h1{font-size:34px}.manual-article h2{border-top:1px solid var(--line);padding-top:20px}.manual-article p{line-height:1.65}.manual-table-wrap{overflow-x:auto;margin:16px 0;border:1px solid #1b304d;border-radius:12px}.manual-table-wrap table{min-width:760px;width:max-content;max-width:none}.manual-article table{display:table;width:100%;border-collapse:collapse}.manual-article th,.manual-article td{white-space:normal;min-width:140px;line-height:1.45}.manual-article pre{overflow:auto;background:#020912;border:1px solid #18314f;border-radius:12px;padding:14px;color:#b7f7d3}.manual-article code{font-family:ui-monospace,monospace;color:#b7f7d3}.callout{border-left:4px solid var(--orange);background:#23190a;padding:12px 14px;border-radius:10px;margin:14px 0}@media(max-width:900px){.docs-layout{grid-template-columns:1fr}.docs-sidebar{position:relative;max-height:none}}
.rss-item{border-left:3px solid var(--cyan);padding:10px 12px;margin:8px 0;background:#081525;border-radius:10px}.matrix{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.tactic{background:#07111c;border:1px solid #1b304d;border-radius:12px;padding:10px}.tech{display:block;margin:7px 0;padding:8px;border-radius:8px;background:#102239;border:1px solid #25496e}.tech.score3{background:#233814;border-color:#4b7c24}.tech.score2{background:#2a2600;border-color:#7c6f00}.event-detail pre{white-space:pre-wrap;background:#020912;border:1px solid #18314f;border-radius:12px;padding:12px;color:#b7f7d3}</style>
"""


def _cti_nav(active: str) -> str:
    items=[("/cti/dashboard","Dashboard"),("/cti/events","Events"),("/cti/security","Security"),("/cti/hms","HMS TA"),("/cti/plonk","PLONK"),("/cti/iocs","IOCs"),("/cti/providers","Providers"),("/cti/api-keys","API Keys"),("/cti/enrichment","Enrichment"),("/cti/mitre","MITRE"),("/cti/m4m/navigator","M4M Navigator"),("/cti/rss","RSS Feed"),("/cti/actors","Actors"),("/cti/vulnerabilities","Vulnerabilities"),("/cti/ttps","TTPs"),("/cti/honeypot","Honeypot"),("/cti/investigations","Investigations"),("/cti/feed","Threat Feed"),("/cti/reports","Reports"),("/cti/settings","Settings")]
    return "".join(f'<a class="{ "active" if p==active else "" }" href="{p}"><span>▣</span>{escape(label)}</a>' for p,label in items)


def _cti_layout(title: str, subtitle: str, body: str, *, state=None, active="/cti/dashboard") -> str:
    sysname=_sysname(state)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)} - Gibson Sentry</title>{_base_style()}</head>
<body><div class="shell"><aside class="sidebar"><div class="brand"><div class="shield">◇</div><div><h1>GIBSON SENTRY</h1><p>THREAT INTEL</p></div></div><nav class="nav">{_cti_nav(active)}</nav></aside><section class="main"><div class="top"><div><h2>{escape(title)}</h2><div class="sub">{escape(subtitle)} · System {sysname}</div></div><div class="live">● LIVE</div></div><div class="content">{body}</div><div class="footer">CTI/geolocation is approximate, offline-first and privacy-safe by default. No usernames or API keys are sent to external providers.</div></section></div></body></html>"""


def _layout(title: str, body_html: str, *, state=None) -> str:
    nav = "".join(f'<a href="{escape(n)}">{escape(n.strip("/") or "home")}</a>' for n in NAV)
    sysname = _sysname(state)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)} - Gibson</title>{_base_style()}</head>
<body><div class="plain"><header><h1>Gibson Mainframe Simulator</h1><div class="muted">System: {sysname}</div><nav>{nav}</nav></header><main>{body_html}</main><footer>Gibson educational simulator. CTI/geolocation is approximate, privacy-safe and offline-first by default.</footer></div></body></html>"""



def _manual_manifest() -> list[dict]:
    try:
        from pathlib import Path
        import json
        path = Path(__file__).resolve().parents[3] / "docs" / "manual" / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

def _inline_md(text: str) -> str:
    """Small, safe inline Markdown renderer for Gibson manual pages."""
    import re
    t = escape(text)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', t)
    return t


def _markdown_to_html(md: str) -> str:
    """Render the extracted manual as readable HTML.

    The previous converter rendered every Markdown table row as a separate
    preformatted block.  That squeezed command matrices into a single narrow
    text column on /manual pages.  This converter recognises pipe tables,
    repairs simple separator rows and wraps wide tables in a horizontal-scroll
    container.
    """
    out=[]; in_ul=False; in_pre=False; table=[]
    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append('</ul>'); in_ul=False
    def flush_table():
        nonlocal table
        if not table:
            return
        rows=[]
        for raw in table:
            cells=[c.strip() for c in raw.strip().strip('|').split('|')]
            if cells and all(set(c.replace(':','').replace('-','').strip()) <= {'-'} for c in cells):
                continue
            rows.append(cells)
        if rows:
            header=rows[0]; body=rows[1:]
            out.append('<div class="manual-table-wrap"><table>')
            out.append('<thead><tr>' + ''.join('<th>'+_inline_md(c)+'</th>' for c in header) + '</tr></thead>')
            out.append('<tbody>')
            for row in body:
                if len(row) < len(header): row += ['']*(len(header)-len(row))
                out.append('<tr>' + ''.join('<td>'+_inline_md(c)+'</td>' for c in row[:len(header)]) + '</tr>')
            out.append('</tbody></table></div>')
        table=[]
    for raw in (md or '').splitlines():
        line=raw.rstrip()
        if line.startswith('```'):
            flush_table(); close_ul()
            out.append('</pre>' if in_pre else '<pre>'); in_pre=not in_pre; continue
        if in_pre:
            out.append(escape(line)); continue
        if line.startswith('|') and line.count('|') >= 2:
            close_ul(); table.append(line); continue
        else:
            flush_table()
        if not line.strip():
            close_ul(); continue
        if line.startswith('# '):
            close_ul(); out.append('<h1>'+_inline_md(line[2:].strip())+'</h1>'); continue
        if line.startswith('## '):
            close_ul(); out.append('<h2>'+_inline_md(line[3:].strip())+'</h2>'); continue
        if line.startswith('### '):
            close_ul(); out.append('<h3>'+_inline_md(line[4:].strip())+'</h3>'); continue
        if line.startswith('#### '):
            close_ul(); out.append('<h4>'+_inline_md(line[5:].strip())+'</h4>'); continue
        upper=line.strip().upper()
        if upper.startswith(('NOTE', 'WARNING', 'IMPORTANT', 'TROUBLESHOOTING')):
            close_ul(); out.append('<div class="callout">'+_inline_md(line.strip())+'</div>'); continue
        if line.startswith('- ') or line.startswith(' '):
            if not in_ul: out.append('<ul>'); in_ul=True
            out.append('<li>'+_inline_md(line[2:].strip())+'</li>'); continue
        close_ul(); out.append('<p>'+_inline_md(line)+'</p>')
    flush_table(); close_ul()
    if in_pre: out.append('</pre>')
    return '\n'.join(out)

def _manual_page(path: str, state=None) -> str:
    from pathlib import Path
    base = urlparse(path or '/manual').path
    docs = Path(__file__).resolve().parents[3] / 'docs' / 'manual'
    manifest = _manual_manifest()
    if base in {'/manual','/manual/'}:
        cards = []
        for c in manifest:
            slug = escape(str(c.get('slug','')))
            title = escape(str(c.get('title','')))
            snippet = escape(str(c.get('snippet','')))
            cards.append(f'<div class="card"><h3><a href="/manual/{slug}">{title}</a></h3><p>{snippet}</p></div>')
        body = '<section class="card"><h2>Gibson Technical Manual</h2><p>This web manual is imported from the supplied technical manual PDF and styled for Gibson\'s port 80 learning site. It is a training reference for installation, ports, TSO, ISPF, RACF, ACF2, CICS, Db2, OMVS, JES, security labs and operational evidence.</p><p><a href="/manual/full">Open full extracted manual</a></p></section><section class="grid3">' + ''.join(cards) + '</section>'
        return _layout('Technical Manual', body, state=state)
    slug = base.rsplit('/',1)[-1]
    md_path = docs / ('index.md' if slug == 'full' else f'{slug}.md')
    if not md_path.exists():
        return _layout('Manual page not found', '<section class="card"><h2>Manual page not found</h2><p><a href="/manual">Back to manual index</a></p></section>', state=state)
    side = '<aside class="docs-sidebar"><h3>Manual</h3>' + ''.join(f'<a href="/manual/{escape(str(c.get("slug","")))}">{escape(str(c.get("title","")))}</a>' for c in manifest) + '</aside>'
    html_body = '<div class="docs-layout">' + side + '<section class="card manual-article"><p class="muted"><a href="/manual">← Manual index</a> / ' + escape(slug) + '</p>' + _markdown_to_html(md_path.read_text(encoding='utf-8')[:220000]) + '<p class="muted"><a href="/manual">Back to manual index</a></p></section></div>'
    return _layout('Gibson Manual', html_body, state=state)


def _cti_events(state) -> list[dict]:
    return list(getattr(state, "geo_events", []))[-300:] if state is not None else []


def _cti_security_events(state, limit: int = 400) -> list[dict]:
    """Live security telemetry from the mainframe SMF type-80 stream: RACF, IMS,
    Endevor, MVP, z/VM and LENNOX events the labs emit via record_security_event."""
    out: list[dict] = []
    audit = getattr(state, "audit", None)
    if audit is None:
        return out
    for ev in list(getattr(audit, "events", [])):
        if (getattr(ev, "component", "") or "").upper() != "SMF80":
            continue
        ex = ev.extra or {}
        evt = (ex.get("EVENT") or "").upper()
        # drop the routine SPECIAL-bypass dataset probes fired at every logon
        if evt == "DATASET ACCESS" and "BYPASS" in (ev.result or "").upper():
            continue
        result = (ex.get("RESULT") or ev.result or "").upper().split()[0] if (ex.get("RESULT") or ev.result) else "SUCCESS"
        fail = result in {"FAILURE", "DENIED", "FAIL"} or ex.get("MESSAGE_ID") == "ICH408I"
        out.append({
            "ts": ev.ts.strftime("%Y-%m-%d %H:%M:%S"),
            "userid": ev.userid,
            "event": evt or (ev.command or "").replace("SMF TYPE 80 ", ""),
            "service": ex.get("SERVICE") or ex.get("RESOURCE") or "",
            "result": result or "SUCCESS",
            "risk": "high" if fail else "low",
            "terminal": ex.get("TERMINAL") or "",
            "addr": ex.get("ADDR") or "",
            "msgid": ex.get("MESSAGE_ID") or "",
            "detail": (ex.get("DETAIL") or ev.result or "")[:160],
        })
    return out[-limit:][::-1]


def _security_events_page(state=None) -> str:
    evs = _cti_security_events(state)
    viol = [e for e in evs if e["risk"] == "high"]
    users = {e["userid"] for e in evs}
    svcs = {e["service"] for e in evs if e["service"]}
    rows = []
    for e in evs[:250]:
        badge = _severity_badge("high" if e["risk"] == "high" else "low")
        res = f'{badge} {escape(e["result"])}'
        rows.append([e["ts"], escape(e["userid"]), escape(e["event"]), escape(e["service"]),
                     res, escape(e["terminal"] or e["addr"]), escape(e["detail"])])
    stat = (f'<div class="grid"><div class="card stat"><div class="label">Security Events (SMF 80)</div>'
            f'<div class="value">{len(evs)}</div></div>'
            f'<div class="card stat"><div class="label">RACF Violations</div>'
            f'<div class="value red">{len(viol)}</div></div>'
            f'<div class="card stat"><div class="label">Users Seen</div><div class="value">{len(users)}</div></div>'
            f'<div class="card stat"><div class="label">Services</div><div class="value">{len(svcs)}</div></div></div>')
    exp = ('<div class="card"><p class="muted">Live feed from the mainframe SMF type-80 security '
           'stream (RACF, IMS, Endevor, MVP, z/VM, LENNOX). Export: '
           '<a href="/cti/api/events">JSON API</a> &middot; '
           '<a href="/cti/reports/security.csv">CSV report</a></p></div>')
    body = stat + exp + '<div class="card"><h3>SMF Type 80 Security Events</h3>' + _table(
        ["Time", "User", "Event", "Service", "Result", "Terminal/Addr", "Detail"], rows) + '</div>'
    return _cti_layout('Security Events', 'Live RACF / SMF80 security telemetry from the labs',
                       body, state=state, active='/cti/security')


def _cti_api_events(state) -> str:
    sec = _cti_security_events(state)
    geo = _cti_events(state)
    payload = {
        "generated": _dt_now_iso(),
        "counts": {
            "security_events": len(sec),
            "racf_violations": sum(1 for e in sec if e["risk"] == "high"),
            "geo_events": len(geo),
        },
        "security_events": sec,
        "geo_events": [{k: e.get(k) for k in ("timestamp", "source_ip", "service", "port", "risk", "user", "result")}
                       for e in geo[-100:]],
    }
    return json.dumps(payload, indent=2, default=str)


def _cti_security_csv(state) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "userid", "event", "service", "result", "risk", "terminal", "addr", "msgid", "detail"])
    for e in _cti_security_events(state):
        w.writerow([e["ts"], e["userid"], e["event"], e["service"], e["result"], e["risk"],
                    e["terminal"], e["addr"], e["msgid"], e["detail"]])
    return buf.getvalue()


def _dt_now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _plonk_page(path: str, state=None) -> str:
    from gibson.apps import cti_plonk as P
    qs = parse_qs(urlparse(path or '').query)
    q = (qs.get('q') or [''])[0].strip()
    src = (qs.get('src') or ['packets'])[0]
    caps = P.list_captures(state)
    cap_rows = [[f'<a href="/cti/plonk/pcap?cap={escape(c.name)}">{escape(c.name)}</a>',
                 c.source, str(len(c.packets)), escape(c.note)] for c in caps]
    form = (f'<div class="card"><h3>PLONK search</h3>'
            f'<form class="form" method="get" action="/cti/plonk">'
            f'<input name="q" placeholder="e.g. proto=ftp size=38mb  |  smf119 ftp  |  src=10.4.22.17" value="{escape(q)}" style="min-width:60%">'
            f'<select name="src"><option value="packets"{" selected" if src=="packets" else ""}>Packets</option>'
            f'<option value="smf"{" selected" if src=="smf" else ""}>SMF</option></select>'
            f'<button>Search</button></form>'
            f'<p class="muted">Splunk-style: bare words match anywhere; <code>key=value</code> filters '
            f'(src, dst, port, proto, type, dsn, user). '
            f'Views: <a href="/cti/plonk/sql">Executed SQL</a> &middot; '
            f'<a href="/cti/plonk?src=smf&q=smf80">SMF type 80</a> &middot; '
            f'<a href="/cti/plonk?src=packets&q=proto=ftp">FTP packets</a></p></div>')
    results = ''
    if q:
        if src == 'smf':
            rows = [[r['ts'], f"SMF {r['type']}{('.'+r['subtype']) if r['subtype'] else ''}",
                     escape(r['event']), escape(r['user']), escape(r['result']), escape(str(r['detail'])[:70])]
                    for r in P.search_smf(state, q)[:200]]
            results = ('<div class="card"><h3>SMF results (' + str(len(rows)) + ')</h3>'
                       + _table(["Time", "Record", "Event", "User", "Result", "Detail"], rows) + '</div>')
        else:
            pk = P.search_packets(q, state)[:300]
            rows = [[p.ts, escape(p.src), escape(p.dst), p.proto, str(p.length),
                     escape(p.info + (('  |  ' + p.payload) if p.payload else ''))] for p in pk]
            results = ('<div class="card"><h3>Packet results (' + str(len(rows)) + ')</h3>'
                       + _table(["Time", "Source", "Destination", "Proto", "Bytes", "Info / payload"], rows) + '</div>')
    captures = ('<div class="card"><h3>Captures</h3>'
                + _table(["Capture", "Source", "Packets", "Note"], cap_rows)
                + '<p class="muted">Drop additional <code>.pcap</code> files in the PCAP directory '
                '(<code>$GIBSON_PCAP_DIR</code> or <code>gibson/data/pcaps</code>) and they appear here.</p></div>')
    body = form + results + captures
    return _cti_layout('PLONK &mdash; Forensics', 'Packet / SMF / SQL search over captures and the mainframe audit stream',
                       body, state=state, active='/cti/plonk')


def _plonk_pcap_page(path: str, state=None) -> str:
    from gibson.apps import cti_plonk as P
    qs = parse_qs(urlparse(path or '').query)
    name = (qs.get('cap') or [''])[0]
    cap = P.get_capture(state, name)
    if cap is None:
        return _cti_layout('PLONK &mdash; PCAP', 'Capture not found',
                           '<div class="card"><p>No such capture. <a href="/cti/plonk">Back to PLONK</a></p></div>',
                           state=state, active='/cti/plonk')
    rows = [[p.ts, escape(p.src), escape(p.dst), p.proto, str(p.length),
             escape(p.info), escape(p.payload[:80])] for p in cap.packets]
    body = (f'<div class="card"><h3>{escape(cap.name)}</h3><p class="muted">{escape(cap.note)} '
            f'&middot; <a href="/cti/plonk">back to PLONK</a></p>'
            + _table(["Time", "Source", "Destination", "Proto", "Bytes", "Info", "Payload preview"], rows) + '</div>')
    return _cti_layout('PLONK &mdash; PCAP analysis', escape(cap.name), body, state=state, active='/cti/plonk')


def _plonk_sql_page(path: str, state=None) -> str:
    from gibson.apps import cti_plonk as P
    rows = [[r['ts'], escape(r['src']), escape(r['db']), r['verb'],
             f'<code>{escape(r["sql"])}</code>', escape(r['capture'])] for r in P.executed_sql(state)]
    body = ('<div class="card"><h3>Executed SQL (Db2 DDF / DRDA)</h3>'
            '<p class="muted">SQL statements observed on the wire, correlated to their capture. '
            '<a href="/cti/plonk">back to PLONK</a></p>'
            + (_table(["Time", "Source", "DB", "Verb", "SQL", "Capture"], rows) if rows
               else '<p class="muted">No SQL observed in the current captures.</p>') + '</div>')
    return _cti_layout('PLONK &mdash; Executed SQL', 'Db2 DDF / DRDA statements seen on the wire',
                       body, state=state, active='/cti/plonk')


def _hms_page(path: str, state=None) -> str:
    from gibson.apps import cti_hms as H
    qs = parse_qs(urlparse(path or '').query)
    # lab controls (GET): run the full scenario, fire one stage, or reset
    if 'run' in qs and state is not None:
        H.run_scenario(state)
    if 'fire' in qs and state is not None:
        H.trigger_ttp(state, qs['fire'][0], src_ip=(qs.get('ip') or ['10.4.22.17'])[0],
                      userid=(qs.get('user') or ['HACKER'])[0])
    if 'reset' in qs and state is not None:
        H.reset(state)
    hms = H.get_hms_state(state) if state is not None else H.HmsState()
    seen = set(H.seen_ttp_ids(hms))

    # alarm banner
    alarm_html = ''
    if hms.alarm:
        a = hms.alarm
        alarm_html = (f'<div class="card" style="border:2px solid #c00;background:#2a0d0d">'
                      f'<h3 style="color:#ff5252">&#9888; ALARM &mdash; {escape(a["message"])}</h3>'
                      f'<p>Correlation threshold reached ({a["count"]} distinct TTPs). '
                      f'Associated tooling profiled: {escape(", ".join(t.upper() for t in a["associated_tools"]))}. '
                      f'Notified: {escape(", ".join(a["notified"]))}.</p>'
                      f'<p class="muted">Raised {escape(a["ts"])}</p></div>')

    profile = (
        '<div class="card"><h3>Threat Actor Profile</h3>'
        '<table class="t"><tr><th>Actor</th><td>Heavy Metal Spider (HMS)</td></tr>'
        '<tr><th>Type</th><td>Ransomware crew &mdash; elite mainframe offensive researchers</td></tr>'
        '<tr><th>Target</th><td>SighberBank z/OS estate (TSO, CICS, Db2, FTP, TN3270)</td></tr>'
        '<tr><th>Objective</th><td>Credential theft &rarr; SPECIAL &rarr; collection &rarr; exfiltration &rarr; impact</td></tr>'
        '<tr><th>Signature tooling</th><td>nmap, hydra, john, nikto, surrogat, custom JCL/REXX droppers</td></tr></table></div>')

    # kill chain
    kc_rows = [[a, stage, proc, ev, ctl] for (a, stage, proc, ev, ctl) in H.HMS_KILLCHAIN]
    killchain = ('<div class="card"><h3>ATT&amp;CK Kill Chain (Chapter 13)</h3>'
                 + _table(["ATT&CK", "Stage", "Mainframe procedure", "Evidence", "Control"], kc_rows) + '</div>')

    # IDS detection chain
    ids_rows = []
    for t in H.HMS_TTPS:
        status = (_severity_badge('high') + ' DETECTED') if t.id in seen else '<span class="badge low">&mdash;</span>'
        fire = f'<a href="/cti/hms?fire={t.id}">fire</a>'
        ids_rows.append([str(t.order), t.attack, escape(t.name), escape(t.procedure),
                         escape(t.smf), status, fire])
    ids_tbl = ('<div class="card"><h3>IDS Detection Chain</h3>'
               '<p class="muted">Each stage fires the field-correct SMF record(s) into the '
               'mainframe audit stream. <a href="/cti/hms?run=scenario">Run full scenario</a> '
               '&middot; <a href="/cti/hms?reset=1">reset</a></p>'
               + _table(["#", "ATT&CK", "Technique", "Procedure", "SMF evidence", "Status", "Lab"], ids_rows)
               + '</div>')

    # live detections + SMF evidence
    det_rows = []
    for s in reversed(hms.sightings[-60:]):
        det_rows.append([s.ts, s.attack, escape(s.name), escape(s.userid), escape(s.src_ip),
                         escape("; ".join(s.smf)[:120])])
    detections = ('<div class="card"><h3>Live Detections &amp; SMF Evidence</h3>'
                  + (_table(["Time", "ATT&CK", "Technique", "User", "Source IP", "SMF record(s)"], det_rows)
                     if det_rows else '<p class="muted">No detections yet. Run the scenario or fire a stage above.</p>')
                  + '<p class="muted">Full SMF records appear on <a href="/cti/security">Security Events</a>, '
                  'and packets/SMF/SQL are searchable in <a href="/cti/plonk">PLONK</a>.</p></div>')

    body = alarm_html + profile + killchain + ids_tbl + detections
    return _cti_layout('HMS TA &mdash; Heavy Metal Spider',
                       'Threat-actor profile, kill chain and live IDS detection', body,
                       state=state, active='/cti/hms')


def _ioc_rows(state=None) -> list[dict]:
    store = getattr(getattr(state, "cti_matcher", None), "store", None) if state is not None else None
    rows=[ioc.to_dict() for ioc in getattr(store,"iocs",[]) if store]
    if not rows:
        rows=[
            {"value":"198.51.100.66","type":"ip","severity":"critical","tags":["C2","BOTNET"],"confidence":95,"source":"Gibson fixture","description":"Fixture C2/botnet host"},
            {"value":"5.188.10.0/24","type":"cidr","severity":"high","tags":["SCANNER","ABUSE"],"confidence":80,"source":"Gibson fixture","description":"Fixture scanner network"},
            {"value":"evil-update.com","type":"domain","severity":"high","tags":["MALWARE","C2"],"confidence":75,"source":"Gibson fixture","description":"Training malware domain"},
            {"value":"44d88612fea8a8f36de82e1278abb02f","type":"md5","severity":"critical","tags":["MALWARE"],"confidence":88,"source":"Gibson fixture","description":"EICAR-like training hash"},
            {"value":"CVE-2024-3400","type":"cve","severity":"critical","tags":["EXPLOIT"],"confidence":90,"source":"Gibson fixture","description":"Example KEV-style CVE reference"},
        ]
    return rows


def _table(headers, rows) -> str:
    h="".join(f"<th>{escape(str(x))}</th>" for x in headers)
    r="".join("<tr>"+"".join(f"<td>{c}</td>" if str(c).startswith('<') else f"<td>{escape(str(c))}</td>" for c in row)+"</tr>" for row in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{r or '<tr><td colspan=12>No data yet.</td></tr>'}</tbody></table>"


def _severity_badge(sev: str) -> str:
    s=(sev or 'low').lower()
    cls='critical' if s in {'red','critical'} else ('high' if s=='high' else ('medium' if s=='medium' else 'low'))
    return f'<span class="badge {cls}">{escape(s.upper())}</span>'


def _cti_dashboard(state=None) -> str:
    events=_cti_events(state); iocs=_ioc_rows(state)
    sec=_cti_security_events(state); sec_viol=[e for e in sec if e['risk']=='high']
    sec_rows=[[e['ts'], e['userid'], e['event'], e['service'], _severity_badge('high' if e['risk']=='high' else 'low')+' '+escape(e['result'])] for e in sec[:8]]
    hms_banner=''
    try:
        from gibson.apps import cti_hms as _H
        _a=_H.get_hms_state(state).alarm if state is not None else None
        if _a:
            hms_banner=(f'<div class="card" style="border:2px solid #c00;background:#2a0d0d">'
                        f'<h3 style="color:#ff5252">&#9888; {escape(_a["message"])}</h3>'
                        f'<p>{_a["count"]} distinct HMS TTPs correlated. '
                        f'Notified: {escape(", ".join(_a["notified"]))}. '
                        f'<a href="/cti/hms">Open HMS TA</a></p></div>')
    except Exception:
        hms_banner=''
    actors=THREAT_ACTORS; investigations=INVESTIGATIONS; reports=REPORTS
    active=[i for i in investigations if i['status'].lower() in {'open','in progress'}]
    ips={e.get('source_ip') for e in events if e.get('source_ip')}; countries={((e.get('geo') or {}).get('country_code')) for e in events if (e.get('geo') or {}).get('country_code')}
    matches=[e for e in events if (e.get('cti') or {}).get('matched')]; high=[e for e in events if str(e.get('risk','')).upper() in {'RED','CRITICAL'} or str(e.get('marker_colour','')).lower()=='red']
    sev_counts={k:0 for k in ['critical','high','medium','low']}
    for i in iocs:
        sev=str(i.get('severity','low')).lower(); sev_counts['critical' if sev=='red' else sev if sev in sev_counts else 'low']+=1
    maxc=max(sev_counts.values() or [1]) or 1
    bars=''.join(f'<div><div class="bar {k}" style="height:{25+120*v/maxc}px"></div><div class="muted">{k}</div></div>' for k,v in sev_counts.items())
    recent_iocs=[]
    for i in iocs[:6]:
        recent_iocs.append([f'<span class="badge">{escape(str(i.get("type","ip")).upper())}</span>', i.get('value',''), _severity_badge(str(i.get('severity','low')))])
    event_rows=[]
    for e in reversed(events[-6:]):
        geo=e.get('geo') or {}; event_rows.append([e.get('timestamp',''), e.get('source_ip',''), e.get('service',''), geo.get('city',''), geo.get('country_code',''), _severity_badge(e.get('risk','low'))])
    inv_rows=[[i['title'], i['status'], _severity_badge(i['severity']), i['summary']] for i in investigations]
    actor_rows=[[a['name'], a['motivation'], a['regions'], a['status'], _severity_badge(a['severity'])] for a in actors]
    body=f"""
{hms_banner}
<div class="grid"><div class="card stat"><div class="label">Total IOCs</div><div class="value">{len(iocs)}</div><div class="red">↑ 12% from last week</div></div><div class="card stat"><div class="label">Threat Actors</div><div class="value">{len(actors)}</div></div><div class="card stat"><div class="label">Active Investigations</div><div class="value">{len(active)}</div></div><div class="card stat"><div class="label">Reports</div><div class="value">{len(reports)}</div></div><div class="card stat"><div class="label">Total Events</div><div class="value">{len(events)}</div></div><div class="card stat"><div class="label">Unique Source IPs</div><div class="value">{len(ips)}</div></div><div class="card stat"><div class="label">Countries</div><div class="value">{len(countries)}</div></div><div class="card stat"><div class="label">High Risk</div><div class="value red">{len(high)}</div></div><div class="card stat"><div class="label">Security Events</div><div class="value">{len(sec)}</div></div><div class="card stat"><div class="label">RACF Violations</div><div class="value red">{len(sec_viol)}</div></div></div>
<div class="grid3"><div class="card"><h3>IOC Severity Distribution</h3><div class="bars">{bars}</div></div><div class="card"><h3>Threat Types</h3><div class="donut"></div><p class="muted"><span class="badge">Malware</span><span class="badge">C2</span><span class="badge">Phishing</span><span class="badge">Exploit</span></p></div><div class="card"><h3>Recent IOCs</h3>{_table(['Type','Indicator','Severity'], recent_iocs)}</div></div>
<div class="grid3"><div class="card"><h3>Recent Events</h3>{_table(['Time','Source IP','Service','City','Country','Risk'], event_rows)}</div><div class="card"><h3>Active Investigations</h3>{_table(['Title','Status','Severity','Summary'], inv_rows)}</div><div class="card"><h3>Tracked Threat Actors</h3>{_table(['Actor','Motivation','Regions','Status','Severity'], actor_rows)}</div></div>
<div class="card"><h3>Connection Map / Geo Markers</h3>{_map_table(events)}<p class="muted"><span class="marker m-orange"></span>Europe/USA <span class="marker m-red"></span>Russia/Iran/China or C2/botnet <span class="marker m-neutral"></span>Local/private</p></div>
<div class="card"><h3>Recent Security Events (SMF Type 80)</h3>{_table(['Time','User','Event','Service','Result'], sec_rows)}<p class="muted">Live RACF/IMS/Endevor/MVP/z/VM/LENNOX telemetry &middot; <a href="/cti/security">all security events</a> &middot; <a href="/cti/api/events">JSON API</a> &middot; <a href="/cti/reports/security.csv">CSV</a></p></div>
"""
    return _cti_layout('Threat Dashboard','Real-time threat intelligence overview',body,state=state,active='/cti/dashboard')


def _map_table(events: list[dict]) -> str:
    rows=[]
    for e in reversed(events[-20:]):
        geo=e.get('geo') or {}; cti=e.get('cti') or {}; color=(e.get('marker_colour') or 'neutral').lower()
        if geo.get('latitude') is None or geo.get('longitude') is None:
            continue
        rows.append([f'<span class="marker m-{escape(color)}"></span>{escape(color)}', e.get('source_ip',''), e.get('user',''), e.get('service',''), geo.get('city',''), geo.get('country_code',''), f"{geo.get('latitude')},{geo.get('longitude')}", ','.join(cti.get('tags',[]) or []), e.get('event_id','')])
    return _table(['Marker','IP','User','Service','City','Country','Lat/Lon','CTI','SMF'], rows)




def _cti_auth_enabled() -> bool:
    return os.getenv('GIBSON_CTI_AUTH_ENABLED','0').upper() in {'1','Y','YES','TRUE'}

def _cti_readonly_public() -> bool:
    return os.getenv('GIBSON_CTI_READONLY_PUBLIC','1').upper() not in {'0','N','NO','FALSE'}

def _cti_credentials() -> tuple[str,str]:
    if os.getenv('GIBSON_CTI_USE_DASHBOARD_AUTH','0').upper() in {'1','Y','YES','TRUE'}:
        return os.getenv('GIBSON_DASHBOARD_USER','admin'), os.getenv('GIBSON_DASHBOARD_PASSWORD','gibson')
    return os.getenv('GIBSON_CTI_USER','ctiadmin'), os.getenv('GIBSON_CTI_PASSWORD','gibson')

def _headers_get(headers, key: str) -> str:
    try: return headers.get(key,'') if headers is not None else ''
    except Exception: return ''

def _cti_check_auth(headers, base: str = "") -> bool:
    force = base.startswith('/cti/hms') or base.startswith('/cti/plonk')
    if not force and not _cti_auth_enabled(): return True
    auth=_headers_get(headers,'Authorization') or _headers_get(headers,'authorization')
    if not auth.startswith('Basic '): return False
    try:
        userpass=base64.b64decode(auth.split(None,1)[1]).decode('utf-8')
        u,pw=userpass.split(':',1)
        eu,ep=_cti_credentials()
        return u == eu and pw == ep
    except Exception:
        return False

def _cti_auth_required_for(path: str) -> bool:
    base=urlparse(path or '').path
    if base.startswith('/cti/hms') or base.startswith('/cti/plonk'):
        return True
    if not _cti_auth_enabled(): return False
    qs=parse_qs(urlparse(path or '').query); base=urlparse(path or '').path
    admin_keys={'action','add','edit','delete','save','key','refresh','seed'}
    if not _cti_readonly_public(): return base.startswith('/cti')
    if base.startswith('/cti/api-keys'): return True
    if any(k in qs for k in admin_keys): return True
    if base.endswith('/add') or '/edit/' in base or '/delete/' in base: return True
    return False

def _auth_response() -> tuple[int,str,str]:
    body='<h1>401</h1><p>GIBSON SENTRY authentication required.</p>'
    return 401, 'text/html; charset=utf-8', body

def _cti_dsn(kind: str) -> str:
    return {'actors':'FIBS.CTI.ACTORS','vulns':'FIBS.CTI.VULNS','ttps':'FIBS.CTI.TTPS','apikeys':'FIBS.CTI.APIKEYS','providers':'FIBS.CTI.PROVIDERS','iocs':'FIBS.CTI.IOCS'}.get(kind, 'FIBS.CTI.'+kind.upper())

def _load_json_rows(state, kind: str, defaults: list[dict]) -> list[dict]:
    if state is None: return list(defaults)
    dsn=_cti_dsn(kind)
    try:
        txt=state.datasets.read('IBMUSER', dsn)
        if txt.strip(): return json.loads(txt)
    except Exception: pass
    try:
        state.datasets.write('IBMUSER', dsn, json.dumps(defaults, indent=2))
    except Exception: pass
    return list(defaults)

def _save_json_rows(state, kind: str, rows: list[dict]) -> None:
    if state is None: return
    try: state.datasets.write('IBMUSER', _cti_dsn(kind), json.dumps(rows, indent=2))
    except Exception: pass

def _maybe_add_row(path: str, state, kind: str, rows: list[dict], fields: list[str]) -> tuple[list[dict], str]:
    qs=parse_qs(urlparse(path or '').query); msg=''
    action=(qs.get('action') or [''])[0].lower()
    if action == 'add':
        row={f: (qs.get(f) or [''])[0].strip() for f in fields}
        if any(row.values()): rows.append(row); _save_json_rows(state, kind, rows); msg=f'<p><span class="badge low">{escape(kind.upper())} item saved</span></p>'
    if action == 'delete':
        idx=int((qs.get('idx') or ['-1'])[0])
        if 0 <= idx < len(rows):
            rows.pop(idx); _save_json_rows(state, kind, rows); msg=f'<p><span class="badge yellow">{escape(kind.upper())} item deleted</span></p>'
    return rows,msg

def _feed_page(state=None) -> str:
    rows=[]
    for i in _ioc_rows(state): rows.append([i.get('value',''), i.get('type',''), _severity_badge(str(i.get('severity','low'))), ','.join(i.get('tags',[]) or []), i.get('confidence',''), i.get('source',''), i.get('description','')])
    return _cti_layout('Threat Feed','Local offline IOC feed and provider status',f'<div class="card"><h3>Feed Health</h3><span class="badge low">LOCAL FEED LOADED</span><span class="badge">ONLINE PROVIDERS DISABLED</span><span class="badge">OFFLINE-FIRST</span></div><div class="card">{_table(["Indicator","Type","Severity","Tags","Confidence","Source","Description"], rows)}</div>',state=state,active='/cti/feed')


def _ioc_search_page(path: str, state=None) -> str:
    qs=parse_qs(urlparse(path).query); q=(qs.get('q') or qs.get('ip') or [''])[0].strip(); result=''
    if q and state is not None:
        try:
            # If the query is not an IP, show matching IOC rows only.
            import ipaddress
            ipaddress.ip_address(q)
            geo=state.geolocator.lookup(q); cti=state.cti_matcher.match_ip(q)
            related=[e for e in _cti_events(state) if e.get('source_ip')==q][-10:]
            result=f'<div class="grid3"><div class="card"><h3>Geolocation</h3><pre>{escape(json.dumps(geo.to_dict(), indent=2))}</pre></div><div class="card"><h3>CTI Match</h3><pre>{escape(json.dumps(cti.to_dict(), indent=2))}</pre></div><div class="card"><h3>Recent Gibson Events</h3>{_table(["Time","Service","Risk","SMF"], [[e.get("timestamp",""),e.get("service",""),e.get("risk",""),e.get("event_id","")] for e in related])}</div></div>'
        except Exception:
            matches=[i for i in _ioc_rows(state) if q.lower() in str(i.get('value','')).lower() or q.lower() in ','.join(i.get('tags',[]) or []).lower()]
            result='<div class="card"><h3>IOC Matches</h3>'+_table(['Indicator','Type','Severity','Tags'], [[m.get('value',''),m.get('type',''),_severity_badge(str(m.get('severity','low'))), ','.join(m.get('tags',[]) or [])] for m in matches])+'</div>'
    body=f'<div class="card"><form class="form" method="get" action="/cti/ioc-search"><input name="q" placeholder="IP, domain, ASN or tag" value="{escape(q)}"><button>Search</button></form><p class="muted">Offline research against Gibson Geo/CTI stores. API providers are optional and disabled by default.</p></div>{result}'
    return _cti_layout('IOC Search','Research IPs, domains, ASNs and indicators',body,state=state,active='/cti/ioc-search')


def _actors_page(path='/cti/threat-actors', state=None) -> str:
    rowsdata,msg=_maybe_add_row(path, state, 'actors', _load_json_rows(state,'actors',THREAT_ACTORS), ['name','aliases','motivation','regions','confidence','severity','tags'])
    rows=[[a.get('name',''),a.get('aliases',''),a.get('motivation',''),a.get('regions',''),a.get('confidence',''),_severity_badge(a.get('severity','medium')),a.get('tags','')] for a in rowsdata]
    form='<form class="form" method="get" action="/cti/actors"><input type="hidden" name="action" value="add"><input name="name" placeholder="Actor"><input name="aliases" placeholder="Aliases"><input name="motivation" placeholder="Motivation"><input name="regions" placeholder="Regions"><input name="confidence" placeholder="Confidence"><input name="severity" placeholder="Severity"><input name="tags" placeholder="Tags"><button>Add actor</button></form>'
    return _cti_layout('Threat Actors','Tracked adversary and campaign profiles',f'<div class="card">{msg}{form}{_table(["Name","Aliases","Motivation","Regions","Confidence","Severity","Tags"], rows)}</div>',state=state,active='/cti/actors')

def _vulnerabilities_page(path='/cti/vulnerabilities', state=None) -> str:
    defaults=[{'cve':'CVE-TRAINING-0001','component':'Tomcat Manager','severity':'critical','ttp':'T1190','summary':'Default credential and WAR deploy training scenario'}]
    rowsdata,msg=_maybe_add_row(path, state, 'vulns', _load_json_rows(state,'vulns',defaults), ['cve','component','severity','ttp','summary'])
    rows=[[v.get('cve',''),v.get('component',''),_severity_badge(v.get('severity','medium')),v.get('ttp',''),v.get('summary','')] for v in rowsdata]
    form='<form class="form" method="get" action="/cti/vulnerabilities"><input type="hidden" name="action" value="add"><input name="cve" placeholder="CVE/ID"><input name="component" placeholder="Component"><input name="severity" placeholder="Severity"><input name="ttp" placeholder="TTP"><input name="summary" placeholder="Summary"><button>Add vulnerability</button></form>'
    return _cti_layout('Vulnerabilities','Tracked vulnerability and lab mappings',f'<div class="card">{msg}{form}{_table(["CVE/ID","Component","Severity","TTP","Summary"], rows)}</div>',state=state,active='/cti/vulnerabilities')

def _ttps_page(path='/cti/ttps', state=None) -> str:
    defaults=[{'mitre':'T1110.002','m4m':'MF-TTP08','tactic':'Credential Access','technique':'Offline RACF hash cracking','evidence':'SMF80/30/92, ZSEC OFFLINEHASH'}]
    rowsdata,msg=_maybe_add_row(path, state, 'ttps', _load_json_rows(state,'ttps',defaults), ['mitre','m4m','tactic','technique','evidence'])
    rows=[[t.get('mitre',''),t.get('m4m',''),t.get('tactic',''),t.get('technique',''),t.get('evidence','')] for t in rowsdata]
    form='<form class="form" method="get" action="/cti/ttps"><input type="hidden" name="action" value="add"><input name="mitre" placeholder="MITRE ID"><input name="m4m" placeholder="M4M ID"><input name="tactic" placeholder="Tactic"><input name="technique" placeholder="Technique"><input name="evidence" placeholder="Evidence"><button>Add TTP</button></form>'
    return _cti_layout('TTPs','Tactics, techniques and evidence mappings',f'<div class="card">{msg}{form}{_table(["MITRE","M4M","Tactic","Technique","Evidence"], rows)}</div>',state=state,active='/cti/ttps')


def _c2_page(state=None) -> str:
    rows=[]
    for i in _ioc_rows(state):
        tags=[t.upper() for t in (i.get('tags',[]) or [])]
        if {'C2','BOTNET','MALWARE'}.intersection(tags): rows.append([i.get('value',''), i.get('type',''), _severity_badge(str(i.get('severity','red'))), ','.join(tags), i.get('confidence',''), i.get('description','')])
    return _cti_layout('C2 Tracker','Command-and-control and botnet fixtures linked to Gibson telemetry',f'<div class="card">{_table(["Indicator","Type","Severity","Tags","Confidence","Description"], rows)}</div>',state=state,active='/cti/c2-tracker')


def _investigations_page(state=None) -> str:
    rows=[[i['title'],i['status'],_severity_badge(i['severity']),i['owner'],i['summary']] for i in INVESTIGATIONS]
    return _cti_layout('Investigations','Case tracking for Gibson telemetry',f'<div class="card">{_table(["Title","Status","Severity","Owner","Summary"], rows)}</div>',state=state,active='/cti/investigations')


def _reports_page(path: str, state=None) -> tuple[int,str,str] | str:
    qs=parse_qs(urlparse(path).query); fmt=(qs.get('format') or ['html'])[0].lower(); events=_cti_events(state); iocs=_ioc_rows(state)
    if fmt=='json': return 200,'application/json; charset=utf-8',json.dumps({'events':events,'iocs':iocs,'reports':REPORTS},indent=2,default=str)
    if fmt=='csv':
        out=io.StringIO(); w=csv.writer(out); w.writerow(['timestamp','source_ip','service','user','risk','city','country','cti_tags','smf'])
        for e in events: geo=e.get('geo') or {}; cti=e.get('cti') or {}; w.writerow([e.get('timestamp'),e.get('source_ip'),e.get('service'),e.get('user'),e.get('risk'),geo.get('city'),geo.get('country_code'),','.join(cti.get('tags',[]) or []),e.get('event_id')])
        return 200,'text/csv; charset=utf-8',out.getvalue()
    rows=[[r['title'],_severity_badge(r['severity']),r['format'],r['summary']] for r in REPORTS]
    body=f'<div class="card"><p><a href="/cti/reports?format=json">Export JSON</a> <a href="/cti/reports?format=csv">Export CSV</a> <a href="/cti/reports?format=smf">SMF-style text</a></p>{_table(["Title","Severity","Format","Summary"], rows)}</div>'
    return _cti_layout('Reports','Export and summary reports',body,state=state,active='/cti/reports')




def _providers_page(path='/cti/providers', state=None) -> str:
    defaults=[dict(p) for p in CTI_PROVIDERS]
    rowsdata,msg=_maybe_add_row(path, state, 'providers', _load_json_rows(state,'providers',defaults), ['name','category','key','free','data','ttl'])
    rows=[]
    for i,pr in enumerate(rowsdata):
        rows.append([pr.get('name',''), pr.get('category',''), pr.get('key',''), pr.get('free',''), pr.get('data',''), pr.get('ttl',''), '<span class="badge low">fixture ready</span> <a href="/cti/providers?action=delete&idx='+str(i)+'">delete</a>'])
    form='<form class="form" method="get" action="/cti/providers"><input type="hidden" name="action" value="add"><input name="name" placeholder="Provider"><input name="category" placeholder="Category"><input name="key" placeholder="Key env name"><input name="free" placeholder="Free tier"><input name="data" placeholder="Data"><input name="ttl" placeholder="TTL"><button>Add provider</button></form>'
    body='<div class="card"><h3>Provider Registry</h3><p>Offline fixture mode remains default. Live calls require explicit API key/configuration and are cached/rate-limited.</p>'+msg+form+_table(["Provider","Category","Key","Free tier","Normalised data","TTL","Status"], rows)+'</div>'
    return _cti_layout('Provider Registry','Free/free-tier OSINT and CTI sources for enrichment',body,state=state,active='/cti/providers')


def _api_keys_page(path='/cti/api-keys', state=None) -> str:
    qs=parse_qs(urlparse(path or '').query); msg=''
    keys=_load_json_rows(state,'apikeys',[])
    if (qs.get('action') or [''])[0].lower() == 'save':
        provider=(qs.get('provider') or [''])[0].strip(); key=(qs.get('key') or [''])[0].strip()
        if provider and key:
            keys=[k for k in keys if k.get('provider') != provider]; keys.append({'provider':provider,'configured':'yes','last4':key[-4:]}); _save_json_rows(state,'apikeys',keys); msg='<p><span class="badge low">API key saved redacted</span></p>'
    configured={k.get('provider'):k for k in keys}
    rows=[]
    for p in CTI_PROVIDERS:
        if p['key']=='not required': continue
        c=configured.get(p['name'])
        rows.append([p['name'], p['key'], 'configured ****'+c.get('last4','') if c else 'not configured', '<span class="badge">test</span>', 'Keys are redacted after save'])
    form='<form class="form" method="get" action="/cti/api-keys"><input type="hidden" name="action" value="save"><input name="provider" placeholder="Provider"><input type="password" name="key" placeholder="API key"><button>Save redacted key</button></form>'
    body='<div class="card"><h3>API Key Management</h3><p>Keys are stored locally and never displayed in clear text.</p>'+msg+form+'</div><div class="card">'+_table(["Provider","Key requirement","Configured","Action","Security note"], rows)+'</div>'
    return _cti_layout('API Keys','Configure and test enrichment providers without exposing secrets',body,state=state,active='/cti/api-keys')


def _events_page(state=None) -> str:
    return sentry_pages.events_page(state, _cti_layout, _table, _severity_badge)

def _iocs_page(state=None) -> str:
    rows=[]
    for i in _ioc_rows(state):
        rows.append([i.get('type',''), i.get('value',''), _severity_badge(str(i.get('severity','low'))), i.get('confidence',''), ','.join(i.get('tags',[]) or []), i.get('source',''), '<a href="/cti/enrichment?q='+escape(str(i.get('value','')))+'">enrich</a>'])
    return _cti_layout('IOCs','Indicators, confidence and provider context', '<div class="card">'+_table(["Type","Value","Severity","Confidence","Tags","Source","Action"], rows)+'</div>', state=state, active='/cti/iocs')


def _enrichment_page(path: str, state=None) -> str:
    qs=parse_qs(urlparse(path).query); q=(qs.get('q') or [''])[0].strip()
    result=''
    if q:
        result='<div class="grid3"><div class="card"><h3>Fixture enrichment</h3><pre>'+escape(json.dumps({'indicator':q,'mode':'fixture','risk_score':72,'confidence':'training','providers':['AbuseIPDB fixture','GreyNoise fixture','OTX fixture'],'note':'Live enrichment requires configured provider keys.'}, indent=2))+'</pre></div><div class="card"><h3>Provider plan</h3><p>Fan-out to enabled providers, normalise fields, cache by indicator type and show failures honestly.</p></div></div>'
    body='<div class="card"><form class="form" method="get" action="/cti/enrichment"><input name="q" placeholder="IP, domain, URL, hash or CVE" value="'+escape(q)+'"><button>Enrich</button></form></div>'+result
    return _cti_layout('Enrichment','Provider fan-out, cache and confidence scoring', body, state=state, active='/cti/enrichment')


def _mitre_layer() -> dict:
    return sentry_pages.navigator_layer()

def _mitre_page(state=None) -> str:
    techniques=[[d,a,c,b,3] for a,b,c,d in M4M_TTPS]
    body='<div class="card"><h3>Navigator-style layer</h3><p><a href="/cti/mitre?format=json">Export Navigator JSON</a></p>'+_table(["ATT&CK ID","Technique","Tactic","Mainframe TTP","Score"], techniques)+'</div><div class="card"><pre>'+escape(json.dumps(_mitre_layer(),indent=2))+'</pre></div>'
    return _cti_layout('MITRE ATT&CK','Navigator-style mapping for Gibson events', body, state=state, active='/cti/mitre')


def _m4m_page(state=None) -> str:
    return sentry_pages.m4m_page(state, _cti_layout)

def _honeypot_page(state=None) -> str:
    rows=[[h['session'],h['ip'],h['country'],h['service'],h['user'],_severity_badge(h['risk']),h['classification'],h['commands'],h['cti']] for h in HONEYPOT_FIXTURE]
    body='<div class="grid"><div class="card stat"><div class="label">Fixture Attacks</div><div class="value">6195</div><p class="muted">From supplied honeypot training deck</p></div><div class="card stat"><div class="label">Unique Attackers</div><div class="value">944</div></div><div class="card stat"><div class="label">Malicious Host Match</div><div class="value">30-40%</div></div><div class="card stat"><div class="label">Top Users</div><div class="value">IBMUSER / GUEST</div></div></div><div class="card"><h3>Honeypot Sessions</h3>'+_table(["Session","IP","Country","Service","User","Risk","Classification","Transcript","CTI"], rows)+'</div>'
    return _cti_layout('Honeypot Telemetry','eZids/eZproxy/eZFTP-inspired attacker views', body, state=state, active='/cti/honeypot')

def _settings_page(state=None) -> str:
    cfg=getattr(state,'config',None)
    providers=[['Geo provider',getattr(cfg,'geo_provider','freeipapi'),'Fixture/cache first, FreeIPAPI for unknown public IPs when enabled'],['Geo online',getattr(cfg,'geo_online_enabled',False),'Enabled by default for public IP only; disable with GIBSON_GEO_ONLINE_ENABLED=0'],['CTI online',getattr(cfg,'cti_online_enabled',False),'Disabled by default unless provider keys are configured; provider hooks use fixture mode'],['Trusted proxy',getattr(cfg,'trusted_proxy_enabled',False),'X-Forwarded-For ignored unless enabled'],['AbuseIPDB API key', 'configured' if False else 'not configured', 'Use environment/config; never rendered'],['GreyNoise API key', 'not configured', 'Optional future provider'],['OTX API key', 'not configured', 'Optional future provider']]
    return _cti_layout('Settings','Provider, API key, feed and privacy settings',f'<div class="card"><h3>Provider Configuration</h3>{_table(["Setting","State","Note"], providers)}</div><div class="card"><h3>Privacy</h3><ul><li>Online geolocation is privacy-scoped. Disabled by default can be enforced with GIBSON_GEO_ONLINE_ENABLED=0.</li><li>Usernames are not sent to external providers.</li><li>API secrets are never displayed in the UI.</li><li>Geolocation is approximate and city/region level only.</li></ul></div>',state=state,active='/cti/settings')


def _documentation_page(state=None) -> str:
    return _cti_layout('Documentation','How Gibson Sentry/OSINT telemetry works',"""<div class="card"><h3>Overview</h3><p>Gibson Sentry is a safe, offline-first CTI dashboard for simulated mainframe and web-service telemetry. It enriches connection/logon events with fixture geolocation, local IOC matches and SMF-style evidence.</p></div><div class="card"><h3>Limitations</h3><ul><li>Geolocation is approximate and not a personal location.</li><li>Fixture feeds are for training and deterministic tests.</li><li>Online providers require explicit configuration and API keys.</li><li>No file-transfer trap service or similarly named legacy route is part of this feature.</li></ul></div>""",state=state,active='/cti/documentation')


def render_page(path: str, state=None, headers=None) -> tuple[int, str, str]:
    base = urlparse(path or "/").path
    if base.startswith("/cti") and _cti_auth_required_for(path) and not _cti_check_auth(headers, base):
        return _auth_response()
    if base == "/health": return 200, "text/plain; charset=utf-8", "OK\n"
    if base in CTI_ALIASES:
        # Keep legacy links working while rendering the richer canonical pages.
        mapped = CTI_ALIASES[base]
        path = path.replace(base, mapped, 1); base = mapped
    if base.startswith("/cti/events/"):
        return 200, "text/html; charset=utf-8", sentry_pages.event_detail_page(base.rsplit("/",1)[-1], state, _cti_layout, _severity_badge)
    if base.startswith("/cti/m4m/technique/"):
        return 200, "text/html; charset=utf-8", sentry_pages.m4m_technique_page(base.rsplit("/",1)[-1], state, _cti_layout, _table, _severity_badge)
    if base.startswith("/cti/m4m/smf-forensics/"):
        return 200, "text/html; charset=utf-8", sentry_pages.smf_forensics_detail_page(base.rsplit("/",1)[-1], state, _cti_layout)
    if base == "/cti/m4m/smf-forensics":
        return 200, "text/html; charset=utf-8", sentry_pages.smf_forensics_page(state, _cti_layout)
    if base == "/cti/rss/status":
        try:
            from gibson.apps import cti_rss
            return 200, "application/json; charset=utf-8", json.dumps(cti_rss.rss_job_status(state), indent=2, default=str)
        except Exception as exc:
            return 500, "application/json; charset=utf-8", json.dumps({"error": str(exc)})
    if base == "/cti/m4m/layer.json":
        return 200, "application/json; charset=utf-8", json.dumps(sentry_pages.navigator_layer(sentry_pages.normalise_events(state)), indent=2)
    if base == "/cti/api/events":
        return 200, "application/json; charset=utf-8", _cti_api_events(state)
    if base == "/cti/reports/security.csv":
        return 200, "text/csv; charset=utf-8", _cti_security_csv(state)
    if base == "/cti/mitre" and (parse_qs(urlparse(path).query).get('format') or [''])[0].lower() == 'json':
        return 200, "application/json; charset=utf-8", json.dumps(_mitre_layer(), indent=2)
    if base in CTI_CANONICAL:
        if base == "/cti": return 200, "text/html; charset=utf-8", _cti_layout('Gibson Sentry','Cyber Threat Intelligence / OSINT and honeypot-style telemetry', '<div class="grid"><div class="card"><h3><a href="/cti/dashboard">Dashboard</a></h3><p>Overview cards, event counts, honeypot waves, indicators and map markers.</p></div><div class="card"><h3><a href="/cti/providers">Providers</a></h3><p>AbuseIPDB, VirusTotal, Shodan, Censys, GreyNoise, URLHaus, ThreatFox, MalwareBazaar, OTX, KEV/NVD/EPSS and more.</p></div><div class="card"><h3><a href="/cti/m4m/navigator">M4M Navigator</a></h3><p>ATT&CK layer export plus Gibson mainframe-specific M4M mappings.</p></div><div class="card"><h3><a href="/cti/honeypot">Honeypot Telemetry</a></h3><p>eZids/eZproxy/eZFTP-inspired source IP, credential, transcript and malicious-host views.</p></div></div>', state=state, active='/cti/dashboard')
        if base == "/cti/dashboard": return 200, "text/html; charset=utf-8", _cti_dashboard(state)
        if base == "/cti/events": return 200, "text/html; charset=utf-8", _events_page(state)
        if base == "/cti/security": return 200, "text/html; charset=utf-8", _security_events_page(state)
        if base == "/cti/hms": return 200, "text/html; charset=utf-8", _hms_page(path, state)
        if base == "/cti/plonk": return 200, "text/html; charset=utf-8", _plonk_page(path, state)
        if base == "/cti/plonk/pcap": return 200, "text/html; charset=utf-8", _plonk_pcap_page(path, state)
        if base == "/cti/plonk/sql": return 200, "text/html; charset=utf-8", _plonk_sql_page(path, state)
        if base == "/cti/iocs": return 200, "text/html; charset=utf-8", _iocs_page(state)
        if base == "/cti/providers": return 200, "text/html; charset=utf-8", _providers_page(path, state)
        if base == "/cti/api-keys": return 200, "text/html; charset=utf-8", _api_keys_page(path, state)
        if base == "/cti/enrichment": return 200, "text/html; charset=utf-8", _enrichment_page(path, state)
        if base == "/cti/mitre": return 200, "text/html; charset=utf-8", _mitre_page(state)
        if base in {"/cti/m4m", "/cti/m4m/navigator"}: return 200, "text/html; charset=utf-8", _m4m_page(state)
        if base == "/cti/honeypot": return 200, "text/html; charset=utf-8", _honeypot_page(state)
        if base == "/cti/rss": return 200, "text/html; charset=utf-8", sentry_pages.rss_page(path, state, _cti_layout, _table)
        if base == "/cti/feed": return 200, "text/html; charset=utf-8", _feed_page(state)
        if base == "/cti/ioc-search": return 200, "text/html; charset=utf-8", _ioc_search_page(path, state)
        if base in {"/cti/threat-actors", "/cti/actors"}: return 200, "text/html; charset=utf-8", _actors_page(path, state)
        if base == "/cti/vulnerabilities": return 200, "text/html; charset=utf-8", _vulnerabilities_page(path, state)
        if base == "/cti/ttps": return 200, "text/html; charset=utf-8", _ttps_page(path, state)
        if base == "/cti/c2-tracker": return 200, "text/html; charset=utf-8", _c2_page(state)
        if base == "/cti/investigations": return 200, "text/html; charset=utf-8", _investigations_page(state)
        if base == "/cti/reports":
            res=_reports_page(path,state)
            if isinstance(res, tuple): return res
            return 200, "text/html; charset=utf-8", res
        if base == "/cti/settings": return 200, "text/html; charset=utf-8", _settings_page(state)
        if base == "/cti/documentation": return 200, "text/html; charset=utf-8", _documentation_page(state)
    if base.startswith("/manual"):
        return 200, "text/html; charset=utf-8", _manual_page(path, state)
    if base not in PAGES:
        return 404, "text/html; charset=utf-8", "<h1>404</h1><p>Welcome route not found.</p>"
    title, body = PAGES[base]
    body_html = f"""
<section class="card hero-card">
  <p class="eyebrow">Python-based mainframe security education</p>
  <h2>{escape(title)}</h2>
  <p class="lede">{escape(body)}</p>
  <p>Gibson is a <strong>safe educational IBM mainframe simulator</strong> for learning TSO, ISPF, CICS, Db2, RACF, PassTickets, MFA, web APIs and mainframe security evidence. It is not z/OS; it is a controlled, resettable Python training environment that models enough mainframe behaviour to support practical teaching, demonstrations and defensive evidence collection.</p>
</section>
<section class="grid3">
  <section class="card"><h3>What is Gibson?</h3><ul><li>A lightweight Python simulator that recreates mainframe-style terminal and web workflows.</li><li>A lab for practising TSO READY commands, ISPF panels, CICS transactions, Db2 paths, RACF identity concepts, SDSF/JES activity and OMVS tools.</li><li>A safe vulnerable-training environment for DVCA, CBSA, Tomcat Manager, PassTicket, MFA and evidence-generation exercises.</li><li>A simulator, not a production system and not a substitute for IBM z/OS.</li></ul></section>
  <section class="card"><h3>How it came into being</h3><p><strong>Mainframe Pen Test Training and Research.</strong> Gibson grew from mainframe security training, research and book/lab development work aimed at making mainframe penetration-testing concepts easier to practise. Neuro Training Ltd and OffensiveSec.org provide the training/research context for these labs. Public project material describes Gibson as a Python-based IBM mainframe simulation for cyber practitioners, students and penetration testers, and external mainframe-security coverage describes it as a free, open-source simulator intended to make mainframe pentesting accessible in a safe learning environment.</p></section>
  <section class="card"><h3>What it is useful for</h3><ul><li>Instructor-led mainframe security courses and self-study.</li><li>Learning RACF, PassTicket, MFA, CICS, Db2, JES/SDSF and OMVS concepts.</li><li>Practising authorised penetration-testing workflows without touching production systems.</li><li>Generating SMF-style and zSecure-style evidence for blue-team and reporting exercises.</li></ul></section>
</section>
<section class="card"><h3>Top 20 Gibson realism features</h3><p class="muted">The current package includes these core learning surfaces and supporting services.</p><h3>What is included in this package</h3><div class="grid"><div><span class="badge green">TSO / ISPF</span><p>READY commands, panels, data sets, editor-style workflows and PF-key navigation.</p></div><div><span class="badge green">CICS / DVCA / CBSA</span><p>CICS transactions, vulnerable-app training, field-protection lessons, banking workflows and PIN labs.</p></div><div><span class="badge green">RACF / zSecure</span><p>Users, groups, DATASET and GENERAL RESOURCE profiles, PassTickets, MFA and audit-style views.</p></div><div><span class="badge green">Db2 / JES / SDSF</span><p>Database, batch, spool and job-submission learning surfaces.</p></div><div><span class="badge green">OMVS / tools</span><p>USS-like shell commands, safe network/security tooling and PassTicket scripts scoped to Gibson data.</p></div><div><span class="badge green">Master Console</span><p>OPERLOG, IPL replies, system processing status and SMF-style alert stream.</p></div></div></section>
<section class="grid3">
  <section class="card"><h3>Start here</h3><ul><li><code>80</code> — Welcome, manual and CTI/OSINT dashboard.</li><li><code>2023</code> — terminal path for TSO, ISPF, CICS, Db2, SDSF and OMVS.</li><li><code>8080</code> — CBSA, DVCA, hack3270 and Tomcat Manager simulation.</li><li><code>9080</code> — FIBS Bank and Security Academy.</li><li><code>8023</code> — optional browser terminal if Guacamole support is enabled.</li></ul></section>
  <section class="card"><h3>Training themes</h3><ul><li>Weak/default credentials and access paths.</li><li>RACF profile review and security option interpretation.</li><li>CICS protected-field and business-logic training.</li><li>PassTicket generation, parsing and abuse concepts in a bounded lab.</li><li>CTI, geolocation, SMF-style event and zSecure-style evidence correlation.</li></ul></section>
  <section class="card"><h3>Safety and scope</h3><p>Use Gibson only in authorised training and research environments. It deliberately models weaknesses for education; those lessons should be applied responsibly to improve real mainframe security.</p><p><a href="https://offensivesec.org/gibson" target="_blank" rel="noopener">OffensiveSec Gibson project page ↗</a> · <a href="/manual">Technical Manual</a> · <a href="/cti">CTI/OSINT Dashboard</a> · <a href="/labs/identity">Identity Labs</a></p></section>
</section>"""
    return 200, "text/html; charset=utf-8", _layout(title, body_html, state=state)
