from __future__ import annotations

import html
import ipaddress
import json
from urllib.parse import parse_qs, urlparse
from typing import Any, Callable

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

TTP_MAP = {
    "ANONYMOUS_FTP": ("Initial Access", "T1078", "Anonymous or default service access"),
    "FTP_JES": ("Execution", "T1059", "JES internal reader/job submission abuse"),
    "CICSPWN": ("Discovery", "T1046", "CICS capability discovery and transaction abuse"),
    "NMAP": ("Discovery", "T1046", "Network service discovery / mainframe enumeration"),
    "TSO-ENUM": ("Discovery", "T1087", "Account and TSO user enumeration"),
    "ELV_APF": ("Privilege Escalation", "T1068", "Writable APF library privilege escalation"),
    "APF": ("Privilege Escalation", "T1068", "APF probe or library manipulation"),
    "JCL_REXX": ("Execution", "T1059", "JCL/REXX command execution"),
    "TSHOCKER": ("Execution", "T1059", "Training shell simulation"),
    "PASSTICKET": ("Credential Access", "T1550", "PassTicket issue or misuse"),
    "MSFCONSOLE": ("Command and Control", "T1105", "Exploit framework session started"),
    "TOMCAT": ("Initial Access", "T1190", "Tomcat Manager/default credential/WAR deploy"),
    "SQLI": ("Initial Access", "T1190", "SQL injection against training API"),
    "API": ("Initial Access", "T1190", "API exploitation / authz weakness"),
    "PIN_BRUTE": ("Credential Access", "T1110", "Bounded PIN brute force in simulator"),
    "HACK3270": ("Defense Evasion", "T1562", "3270 field manipulation / AID injection"),
    "RACF": ("Privilege Escalation", "T1098", "RACF privilege or profile change"),
    "SETROPTS": ("Defense Evasion", "T1562", "Security option modification"),
    "ZSEC": ("Discovery", "T1087", "zSecure report access/review"),
    "OMVS": ("Execution", "T1059", "OMVS tool execution"),
}


def _e(value: Any) -> str:
    return html.escape(str(value or ""))


def safe_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False, "Only http/https feed URLs are allowed."
        host = parsed.hostname or ""
        if host.lower() in {"localhost"}:
            return False, "Localhost feeds are blocked by default."
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast:
                return False, "Private, loopback and link-local feed targets are blocked by default."
        except Exception:
            pass
        return True, ""
    except Exception as exc:
        return False, f"Invalid URL: {exc}"


def _rss_service():
    try:
        from gibson.apps import cti_rss
        return cti_rss
    except Exception:
        return None


def rss_page(path: str, state: Any, layout: Callable, table: Callable) -> str:
    svc = _rss_service()
    qs = parse_qs(urlparse(path).query)
    refresh = (qs.get("refresh") or [""])[0].lower() in {"1", "yes", "all"}
    feed_filter = (qs.get("feed") or [""])[0]
    action = (qs.get("action") or [""])[0].lower()
    message = ""
    cache = {"time": "NO STATE", "items": [], "status": [], "feeds": []}
    if state is not None and svc is not None:
        try:
            svc.ensure_rss_datasets(state, "IBMUSER")
            if action == "add":
                name = (qs.get("name") or [""])[0]
                url = (qs.get("url") or [""])[0]
                ok, reason = svc.validate_feed_url(url) if hasattr(svc, 'validate_feed_url') else safe_url(url)
                if name and ok:
                    feeds=[f for f in svc.list_feeds(state, "IBMUSER") if f.get('name') != svc._norm_name(name)]
                    feeds.append({'name': svc._norm_name(name), 'title': name, 'url': url})
                    svc.save_feeds(state, feeds, "IBMUSER")
                    message = '<span class="badge low">Feed added</span>'
                else:
                    message = '<span class="badge red">Feed rejected: '+_e(reason or 'name/url required')+'</span>'
            if action == "delete":
                name=(qs.get("name") or [""])[0]
                feeds=svc.list_feeds(state, "IBMUSER")
                kept=[f for f in feeds if f.get('name') != svc._norm_name(name)]
                svc.save_feeds(state, kept, "IBMUSER")
                message = '<span class="badge yellow">Feed deleted</span>'
            if refresh:
                jid = svc.start_refresh_job(state, "IBMUSER", feed_filter, live=((qs.get('live') or [''])[0].lower() in {'1','yes','true'})) if hasattr(svc, 'start_refresh_job') else ''
                message = f'<span class="badge low">Refresh job started { _e(jid) }</span>' if jid else '<span class="badge low">Refresh started</span>'
            cache = svc.load_cache(state, "IBMUSER")
            cache["feeds"] = svc.list_feeds(state, "IBMUSER")
        except Exception as exc:
            cache = {"time": "ERROR", "items": [], "status": [{"name": "RSS", "status": "ERROR", "error": str(exc)}], "feeds": []}
    if feed_filter:
        wanted = feed_filter.upper()
        cache["items"] = [i for i in cache.get("items", []) if str(i.get("feed", "")).upper() == wanted]
    feed_rows = []
    for f in cache.get("feeds", []):
        ok, reason = (svc.validate_feed_url(f.get("url", "")) if svc and hasattr(svc,'validate_feed_url') else safe_url(f.get("url", "")))
        action_links = f'<a href="/cti/rss?refresh=1&feed={_e(f.get("name", ""))}">refresh</a> · <a href="/cti/rss?action=delete&name={_e(f.get("name", ""))}">delete</a>'
        feed_rows.append([f.get("title") or f.get("name"), f.get("name"), f.get("url"), '<span class="badge low">allowed</span>' if ok else '<span class="badge red">blocked</span> ' + _e(reason), action_links])
    status_rows = [[s.get("name", ""), s.get("status", ""), s.get("items", ""), s.get("error", "")] for s in cache.get("status", [])]
    item_cards = []
    for idx, it in enumerate(cache.get("items", [])[:120], 1):
        item_cards.append(f'<div class="rss-item"><h3>{idx}. {_e(it.get("title", "(no title)"))}</h3><p class="muted">{_e(it.get("feed", ""))} · {_e(it.get("published", ""))}</p><p>{_e(it.get("summary", ""))}</p><p><a target="_blank" rel="noopener" href="{_e(it.get("link", ""))}">Open source ↗</a></p></div>')
    if not item_cards:
        item_cards.append('<p class="muted">No cached RSS items yet. Refresh starts in the background so the page stays responsive.</p>')
    job_block = ''
    try:
        status = svc.rss_job_status(state) if svc and hasattr(svc,'rss_job_status') else {'jobs': []}
        rows = [[j.get('job_id',''), j.get('status',''), j.get('feed',''), j.get('items',''), j.get('errors',''), j.get('message','')] for j in status.get('jobs', [])[-8:]]
        job_block = '<div class="card"><h3>Refresh Jobs</h3><p><a href="/cti/rss/status">JSON status</a></p>'+table(['Job','Status','Feed','Items','Errors','Message'], rows)+'</div>'
    except Exception:
        pass
    body = f'''
<div class="grid3"><div class="card"><h3>RSS controls</h3><p>{message}</p><p><a class="badge low" href="/cti/rss?refresh=1">Refresh cache</a> <a class="badge yellow" href="/cti/rss?refresh=1&live=1">Live refresh</a> <a class="badge" href="/cti/rss">View cache</a></p><form class="form" method="get" action="/cti/rss"><input type="hidden" name="action" value="add"><input name="name" placeholder="Feed name"><input name="url" placeholder="https://example/feed.xml"><button>Add feed</button></form><p class="muted">Refreshes run as background jobs and cached headlines remain visible.</p><p>Last refresh: <strong>{_e(cache.get('time','NEVER'))}</strong></p></div><div class="card"><h3>Security guardrails</h3><ul><li>Only HTTP/HTTPS feeds are accepted.</li><li>Local/private targets are blocked by default.</li><li>Summaries are stripped and escaped before display.</li><li>Feed errors do not break port 80.</li></ul></div></div>
<div class="card"><h3>Configured Feeds</h3>{table(['Title','Key','URL','Validation','Action'], feed_rows)}</div>
{job_block}
<div class="card"><h3>Fetch Status</h3>{table(['Feed','Status','Items','Error'], status_rows)}</div>
<div class="card"><h3>Latest Articles</h3>{''.join(item_cards)}</div>'''
    return layout("RSS Feed", "Threat intelligence headlines from editable Gibson RSS feeds", body, state=state, active="/cti/rss")

def _map_ttp(blob: str) -> tuple[str, str, str]:
    upper = (blob or "").upper()
    for key, val in TTP_MAP.items():
        if key in upper:
            return val
    return ("Discovery", "T1082", "System or training telemetry event")


def normalise_events(state: Any = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    def add(raw: dict, source: str, title: str, blob: str, severity: str = "medium"):
        tactic, technique, note = _map_ttp(blob + " " + title)
        eid = str(raw.get("event_id") or raw.get("id") or raw.get("correlation_id") or f"EV-{len(events)+1:04d}")
        events.append({"id": eid, "timestamp": str(raw.get("timestamp") or raw.get("time") or ""), "title": title, "source": source, "severity": severity.lower(), "user": str(raw.get("user") or raw.get("userid") or "UNKNOWN"), "service": str(raw.get("service") or raw.get("subsystem") or raw.get("component") or raw.get("channel") or source), "action": str(raw.get("action") or raw.get("command") or raw.get("event_type") or title), "result": str(raw.get("result") or raw.get("status") or ""), "source_ip": str(raw.get("source_ip") or raw.get("addr") or ""), "tactic": tactic, "technique": technique, "ttp_note": note, "smf": {"type": raw.get("smf_type") or ("80" if "RACF" in blob.upper() else "110" if "CICS" in blob.upper() else "30"), "record_id": eid, "simulated": True}, "network": {"src": raw.get("source_ip") or raw.get("addr") or "lab-client", "dst_service": raw.get("service") or raw.get("component") or source, "ids_signature": f"GIBSON {title.upper()}"}, "raw": raw})
    if state is not None:
        for r in list(getattr(state, "security_training_events", []) or []): add(r, "SMF", str(r.get("action") or "Security training event"), json.dumps(r), str(r.get("severity", "medium")).lower())
        for r in list(getattr(state, "backend_trace_events", []) or []): add(r, "TRACE", str(r.get("action") or "Backend trace event"), json.dumps(r), str(r.get("severity", "medium")).lower())
        for r in list(getattr(state, "dashboard_alerts", []) or []): add(r, "ALERT", str(r.get("event_type") or "Dashboard alert"), json.dumps(r), str(r.get("severity", "medium")).lower())
        for r in list(getattr(state, "geo_events", []) or []): add(r, "GEO", str(r.get("action") or r.get("service") or "Geo/CTI event"), json.dumps(r), str(r.get("risk", "medium")).lower())
    if not events:
        fixtures = [
            ({"event_id": "CTI-FIX-DVCA", "user": "IBMUSER", "service": "CICS", "action": "DVCA PIN_BRUTE SUCCESS", "result": "SUCCESS", "source_ip": "192.168.0.97"}, "CICS", "DVCA PIN BRUTE FORCE", "DVCA PIN_BRUTE"),
            ({"event_id": "CTI-FIX-FTP", "user": "ANON", "service": "FTP/JES", "action": "ANONYMOUS_FTP JES SUBMIT", "result": "ALERT", "source_ip": "198.51.100.25"}, "FTP", "Anonymous FTP/JES submission", "ANONYMOUS_FTP FTP_JES"),
            ({"event_id": "CTI-FIX-TOMCAT", "user": "tomcat", "service": "Tomcat", "action": "TOMCAT WAR DEPLOY", "result": "EXPLOITED", "source_ip": "198.51.100.66"}, "WEB8080", "Tomcat Manager exploited", "TOMCAT WAR"),
            ({"event_id": "CTI-FIX-NMAP", "user": "IBMUSER", "service": "OMVS", "action": "NMAP TSO-ENUM", "result": "OK", "source_ip": "203.0.113.10"}, "OMVS", "NMAP tso-enum response", "NMAP TSO-ENUM"),
        ]
        for raw, src, title, blob in fixtures:
            add(raw, src, title, blob, "high")
    return events[-300:]


def events_page(state: Any, layout: Callable, table: Callable, severity_badge: Callable) -> str:
    rows = []
    for e in reversed(normalise_events(state)[-150:]):
        rows.append([e.get("timestamp", ""), e.get("service", ""), e.get("source_ip", ""), e.get("user", ""), e.get("action", ""), e.get("result", ""), severity_badge(e.get("severity", "low")), e.get("tactic", ""), e.get("technique", ""), f'<a href="/cti/events/{_e(e.get("id", ""))}">analysis</a>'])
    return layout("Events", "Gibson Sentry alerts mapped to SMF, network, IDS and MITRE/M4M evidence", '<div class="card">' + table(["Time", "Subsystem", "Source", "User", "Action", "Result", "Risk", "Tactic", "Technique", "Analysis"], rows) + '</div>', state=state, active="/cti/events")


def event_detail_page(event_id: str, state: Any, layout: Callable, severity_badge: Callable) -> str:
    ev = next((e for e in normalise_events(state) if e["id"] == event_id), None)
    if ev is None:
        return layout("Event not found", "No matching CTI event", '<div class="card"><h3>Event not found</h3><p><a href="/cti/events">Back to events</a></p></div>', state=state, active="/cti/events")
    body = f'''
<div class="card event-detail"><h3>{_e(ev['title'])}</h3><p>{severity_badge(ev['severity'])} <span class="badge">{_e(ev['tactic'])}</span> <span class="badge">{_e(ev['technique'])}</span></p><p>{_e(ev['ttp_note'])}</p></div>
<div class="grid3"><div class="card"><h3>Timeline</h3><p>{_e(ev['timestamp'] or 'fixture')}</p><p>User: {_e(ev['user'])}</p><p>Service: {_e(ev['service'])}</p><p>Action: {_e(ev['action'])}</p></div><div class="card"><h3>SMF-style Evidence</h3><pre>{_e(json.dumps(ev['smf'], indent=2))}</pre></div><div class="card"><h3>Network / IDS Evidence</h3><pre>{_e(json.dumps(ev['network'], indent=2))}</pre></div></div>
<div class="card event-detail"><h3>Raw simulated event JSON</h3><pre>{_e(json.dumps(ev['raw'], indent=2, default=str))}</pre></div>'''
    return layout("Event Analysis", "SMF, network, IDS and MITRE/M4M evidence", body, state=state, active="/cti/events")


def navigator_layer(events: list[dict] | None = None) -> dict:
    techniques = []
    seen = set()
    for a, b, c, d in M4M_TTPS:
        if d.startswith("T") and d not in seen:
            techniques.append({"techniqueID": d, "score": 2, "comment": f"{a} {b}"})
            seen.add(d)
    for ev in events or []:
        tid = ev.get("technique")
        if tid and tid.startswith("T") and tid not in seen:
            techniques.append({"techniqueID": tid, "score": 3, "comment": ev.get("title", "Gibson event")})
            seen.add(tid)
    return {"name": "Gibson Mainframe Training Layer - Gibson Sentry M4M Navigator", "version": "4.5", "domain": "enterprise-attack", "description": "Local Gibson mainframe security training coverage and emitted event mapping.", "techniques": techniques}


def m4m_page(state: Any, layout: Callable) -> str:
    by_tactic: dict[str, list[dict[str, Any]]] = {}
    for a, b, c, d in M4M_TTPS:
        by_tactic.setdefault(c, []).append({"id": d, "name": b, "score": 2, "comment": a})
    for ev in normalise_events(state):
        by_tactic.setdefault(ev["tactic"], []).append({"id": ev["technique"], "name": ev["title"], "score": 3, "comment": ev["id"]})
    cols = []
    for tactic, techniques in by_tactic.items():
        cells = "".join(f'<a class="tech score{int(t.get("score", 2))}" href="/cti/m4m/technique/{_e(t.get("id", ""))}"><strong>{_e(t.get("id", ""))}</strong><br>{_e(t.get("name", ""))}<br><span class="muted">{_e(t.get("comment", ""))}</span></a>' for t in techniques[:18])
        cols.append(f'<div class="tactic"><h3>{_e(tactic)}</h3>{cells}</div>')
    body = f'<div class="card"><h3>M4M Navigator</h3><p>Navigator-style matrix for Gibson Sentry events and mainframe-specific training TTPs.</p><p><a href="/cti/m4m/layer.json">Export ATT&CK Navigator layer JSON</a></p></div><div class="matrix">{"".join(cols)}</div>'
    return layout("M4M Navigator", "MITRE Navigator-style mainframe TTP coverage", body, state=state, active="/cti/m4m/navigator")


def m4m_technique_page(technique_id: str, state: Any, layout: Callable, table: Callable, severity_badge: Callable) -> str:
    tid = technique_id.upper()
    events = [e for e in normalise_events(state) if e.get("technique", "").upper() == tid]
    rows = [[f'<a href="/cti/events/{_e(e["id"])}">{_e(e["id"])}</a>', e["title"], e["user"], e["service"], severity_badge(e["severity"])] for e in events]
    body = f'<div class="card"><h3>{_e(tid)}</h3><p>Gibson Sentry technique detail with related lab events, evidence and investigation notes.</p><p><a target="_blank" rel="noopener" href="https://attack.mitre.org/techniques/{_e(tid)}/">Open MITRE ATT&CK reference ↗</a></p></div><div class="card"><h3>Related Gibson Events</h3>{table(["Event", "Title", "User", "Service", "Severity"], rows)}</div>'
    return layout("M4M Technique", "Technique evidence and related Gibson telemetry", body, state=state, active="/cti/m4m/navigator")


def table_simple(headers, rows):
    h = ''.join('<th>' + _e(x) + '</th>' for x in headers)
    r = ''.join('<tr>' + ''.join('<td>' + str(cell) + '</td>' for cell in row) + '</tr>' for row in rows)
    return '<table><thead><tr>' + h + '</tr></thead><tbody>' + r + '</tbody></table>'


def smf_forensics_page(state: Any, layout: Callable) -> str:
    from gibson.core.smf.m4m_smf import SCENARIOS
    rows = []
    for sc in SCENARIOS:
        link = '<a href="/cti/m4m/smf-forensics/' + _e(sc['attack_id']) + '">' + _e(sc['attack_id']) + '</a>'
        rows.append([link, _e(sc['mitre_attack_id']), _e(sc['tactic']), _e(sc['description']), _e(', '.join(sc['expected_smf_records']))])
    body = '<div class="card"><h3>M4M SMF Forensic Scenarios</h3><p>Structured SMF evidence requirements for the Navigator-style mainframe attack layer.</p></div><div class="card">' + table_simple(["Scenario", "ATT&CK", "Tactic", "Description", "SMF records"], rows) + '</div>'
    return layout('M4M SMF Forensics', 'SMF record requirements for mainframe attack scenarios', body, state=state, active='/cti/m4m/navigator')


def smf_forensics_detail_page(attack_id: str, state: Any, layout: Callable) -> str:
    from gibson.core.smf.m4m_smf import scenario_by_id
    sc = scenario_by_id(attack_id)
    if not sc:
        body = '<div class="card"><h3>Scenario not found</h3></div>'
        return layout('M4M SMF Forensics', 'Scenario not found', body, state=state, active='/cti/m4m/navigator')
    body = '<div class="card"><h3>' + _e(sc['attack_id']) + ' - ' + _e(sc['description']) + '</h3>'
    body += '<p><strong>ATT&CK:</strong> ' + _e(sc['mitre_attack_id']) + ' <strong>Tactic:</strong> ' + _e(sc['tactic']) + '</p>'
    body += '<p><strong>Expected SMF records:</strong> ' + _e(', '.join(sc['expected_smf_records'])) + '</p>'
    body += '<p><strong>zSecure views:</strong> ' + _e(', '.join(sc['zsecure_views'])) + '</p></div>'
    body += '<div class="grid"><div class="card"><h3>Forensic Questions</h3><ul>' + ''.join('<li>' + _e(x) + '</li>' for x in sc['forensic_questions']) + '</ul></div>'
    body += '<div class="card"><h3>Investigation Steps</h3><ol>' + ''.join('<li>' + _e(x) + '</li>' for x in sc['investigation_steps']) + '</ol></div></div>'
    return layout('M4M SMF Forensics', 'Scenario detail and expected evidence', body, state=state, active='/cti/m4m/navigator')
