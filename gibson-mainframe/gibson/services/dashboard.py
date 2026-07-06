from __future__ import annotations

import base64
import html
import json
import shutil
import socket
import socketserver
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
import ipaddress

from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.core.security_mode import is_secure_mode, is_noracf_mode
from gibson.net.tls import wrap_server_socket


def _is_port_listening(port: int) -> bool:
    for host in ("127.0.0.1",):
        try:
            with socket.create_connection((host, int(port)), timeout=0.15):
                return True
        except Exception:
            pass
    return False


def _private_ip(ip: str) -> bool:
    try:
        obj = ipaddress.ip_address(str(ip))
        return bool(obj.is_private or obj.is_loopback or obj.is_link_local)
    except Exception:
        return str(ip).startswith(("127.", "10.", "192.168.", "172."))


_GEO_FIXTURES: dict[str, tuple[float, float, str]] = {
    # Offline classroom fixtures.  These avoid external geolocation calls and
    # give stable, testable map placement for known demonstration addresses.
    "82.31.240.198": (51.5074, -0.1278, "London, UK (offline fixture)"),
    "203.0.113.10": (55.9533, -3.1883, "Edinburgh lab fixture"),
    "198.51.100.25": (40.7128, -74.0060, "New York lab fixture"),
}


def _fake_geo(ip: str) -> tuple[float, float, str]:
    """Legacy test compatibility wrapper.

    Production map rendering does not call this function; it uses the
    geolocation provider and geo_events.  This keeps older regression tests
    stable while making the fake/fixture nature explicit.
    """
    ip = str(ip or "")
    if ip in _GEO_FIXTURES:
        return _GEO_FIXTURES[ip]
    if _private_ip(ip):
        return (55.9533, -3.1883, "Private/Lab Gibson fixture")
    return (0.0, 0.0, "Unknown fixture")


def _geo_result(state: GibsonState, ip: str):
    try:
        return state.geolocator.lookup(str(ip or ""), hostname="") if getattr(state, "geolocator", None) else None
    except Exception:
        return None


def _cti_result(state: GibsonState, ip: str):
    try:
        return state.cti_matcher.match_ip(str(ip or "")) if getattr(state, "cti_matcher", None) else None
    except Exception:
        return None


def _marker_colour(state: GibsonState, geo, cti) -> str:
    try:
        return state._geo_marker_colour(geo, cti)
    except Exception:
        return "recent"


def _client_location(*args, **kwargs) -> dict[str, Any]:
    """Compatibility wrapper for old tests and the new state-aware path."""
    if args and isinstance(args[0], GibsonState):
        return _client_location_stateful(*args, **kwargs)
    userid = args[0] if len(args) > 0 else kwargs.get("userid", "UNKNOWN")
    ip = args[1] if len(args) > 1 else kwargs.get("ip", "")
    connected = args[2] if len(args) > 2 else kwargs.get("connected", False)
    last_command = args[3] if len(args) > 3 else kwargs.get("last_command", "")
    last_seen = args[4] if len(args) > 4 else kwargs.get("last_seen", "")
    lat, lon, label = _fake_geo(str(ip))
    return {"userid": str(userid or "UNKNOWN"), "ip": str(ip or ""), "connected": bool(connected), "recent": True, "last_seen": last_seen, "last_command": last_command, "lat": lat, "lon": lon, "geo_label": label, "confidence": "fixture", "source": "legacy-fixture", "marker_type": "recent", "cti": {}, "geo": {"city": label, "latitude": lat, "longitude": lon}}


def _client_location_stateful(state: GibsonState, userid: str, ip: str, connected: bool, last_command: str = "", last_seen: str = "") -> dict[str, Any]:
    geo = _geo_result(state, ip)
    cti = _cti_result(state, ip)
    marker = _marker_colour(state, geo, cti) if geo is not None else "unknown"
    lat = getattr(geo, "latitude", None) if geo is not None else None
    lon = getattr(geo, "longitude", None) if geo is not None else None
    label = "Unknown / no geolocation available"
    if geo is not None:
        label = ", ".join(x for x in [getattr(geo, "city", ""), getattr(geo, "country_code", "")] if x) or getattr(geo, "classification", "unknown")
    return {
        "userid": str(userid or "UNKNOWN"),
        "ip": str(ip or ""),
        "connected": bool(connected),
        "recent": True,
        "last_seen": last_seen,
        "last_command": last_command,
        "lat": lat,
        "lon": lon,
        "geo_label": label,
        "confidence": getattr(geo, "confidence", "unknown") if geo is not None else "unknown",
        "source": getattr(geo, "source", "none") if geo is not None else "none",
        "marker_type": marker,
        "cti": cti.to_dict() if cti else {},
        "geo": geo.to_dict() if geo else {},
    }



def _marker_from_geo_event(e: dict[str, Any]) -> dict[str, Any] | None:
    geo = e.get("geo") or {}
    lat = geo.get("latitude")
    lon = geo.get("longitude")
    if lat is None or lon is None:
        return None
    cti = e.get("cti") or {}
    return {
        "id": str(e.get("event_id") or ""),
        "userid": str(e.get("user") or "UNKNOWN"),
        "ip": str(e.get("source_ip") or ""),
        "connected": False,
        "recent": True,
        "last_seen": str(e.get("timestamp") or ""),
        "last_command": str(e.get("action") or ""),
        "lat": lat,
        "lon": lon,
        "geo_label": ", ".join(x for x in [geo.get("city", ""), geo.get("country_code", "")] if x),
        "city": geo.get("city", ""),
        "region": geo.get("region", ""),
        "country": geo.get("country", ""),
        "country_code": geo.get("country_code", ""),
        "continent": geo.get("continent", ""),
        "asn": geo.get("asn", ""),
        "org": geo.get("org", ""),
        "classification": geo.get("classification", ""),
        "confidence": geo.get("confidence", "unknown"),
        "source": geo.get("source", "geo_events"),
        "marker_type": str(e.get("marker_colour") or e.get("risk") or "yellow").lower(),
        "risk": str(e.get("risk") or "YELLOW"),
        "cti": cti,
        "geo": geo,
        "service": str(e.get("service") or ""),
        "port": e.get("port", ""),
        "smf_record_id": str(e.get("event_id") or ""),
        "cti_tags": cti.get("tags", []) or [],
    }

def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    num = float(max(0, value))
    for unit in units:
        if num < 1024 or unit == units[-1]:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def _memory_summary() -> tuple[str, str]:
    total = avail = 0
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                parts = value.strip().split()
                if not parts:
                    continue
                meminfo[key] = int(parts[0]) * 1024
        total = meminfo.get("MemTotal", 0)
        avail = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    except Exception:
        pass
    return _format_bytes(total), _format_bytes(avail)


def _system_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("198.51.100.1", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip:
            return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip:
            return ip
    except Exception:
        pass
    return "127.0.0.1"


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


class _DashboardHandler(BaseHTTPRequestHandler):
    state: GibsonState
    username = "admin"
    password = "gibsonadmin!"

    server_version = "GibsonHTTP"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        # Suppress HTTP access noise from the dashboard itself. The Recent Audit
        # panel is reserved for TSO, CICS, CONSOLE, and SMF 80 style security
        # events rather than web access lines.
        return

    def _send_fingerprint_headers(self) -> None:
        return None

    def _auth_ok(self) -> bool:
        auth = self.headers.get("Authorization", "")
        expected = "Basic " + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return auth == expected

    def _require_auth(self) -> None:
        try:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="I3M Gibson Dashboard"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._send_fingerprint_headers()
            self.end_headers()
            self.wfile.write(b"Authentication required.")
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str, indent=2).encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self._send_fingerprint_headers()
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_POST(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.dashboard_port, service="DASHBOARD")
        except Exception:
            pass
        if not self._auth_ok():
            self._require_auth(); return
        if self.path.startswith("/poweron") or self.path.startswith("/quit") or self.path.startswith("/poweroff"):
            try:
                self.state.notify_console("IEE334I QUIT REQUESTED FROM DASHBOARD POWER ON SWITCH", severity="ALERT")
                self.state.raise_dashboard_alert("QUIT REQUESTED FROM DASHBOARD POWER ON SWITCH", severity="ALERT", event_type="POWER_OFF")
                self.state.shutdown_requested = True
                mgr = getattr(self.state, "service_manager", None)
                if mgr is not None:
                    mgr.stop_all()
            except Exception:
                pass
            self.send_response(303); self.send_header("Location", "/"); self.end_headers(); return
        self.send_response(404); self.end_headers()

    def do_GET(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.dashboard_port, service="DASHBOARD")
        except Exception:
            pass
        if not self._auth_ok():
            self._require_auth()
            return
        if self.path.startswith("/api/state"):
            self._json(self._snapshot())
            return
        self._html()

    def _snapshot(self) -> dict[str, Any]:
        state = self.state
        sessions = []
        client_locations: list[dict[str, Any]] = []
        seen_ips: set[str] = set()
        for userid, sess in sorted(state.sessions.sessions.items()):
            commands = [e for e in state.audit.events if e.userid == userid.upper() and e.component in {"TSO", "CICS", "CONSOLE", "SMF80"}]
            last_commands = commands[-10:]
            last_seen = last_commands[-1].ts.strftime("%H:%M:%S") if last_commands else ""
            last_command = last_commands[-1].command if last_commands else ""
            loc = _client_location_stateful(state, userid, sess.addr, sess.connected, last_command, last_seen)
            lat, lon, label = loc.get("lat"), loc.get("lon"), loc.get("geo_label", "")
            if sess.addr and sess.addr not in seen_ips:
                client_locations.append(loc); seen_ips.add(sess.addr)
            sessions.append({
                "userid": userid,
                "addr": sess.addr,
                "connected": sess.connected,
                "lat": lat,
                "lon": lon,
                "geo": label,
                "last_commands": [{"time": e.ts.strftime("%H:%M:%S"), "component": e.component, "command": e.command, "result": e.result} for e in last_commands],
            })
        # Add enriched geo/CTI events to the map feed.  This fixes the old
        # session-only map path: valid SMF119/geolocation events now render even
        # when there is no active terminal session for the source.
        for e in list(getattr(state, "geo_events", []))[-200:]:
            marker = _marker_from_geo_event(e)
            if marker and marker.get("ip") and marker["ip"] not in seen_ips:
                client_locations.append(marker); seen_ips.add(marker["ip"])
        jobs = []
        try:
            for job in state.jes.jobs:
                jobs.append({
                    "jobid": getattr(job, "jobid", ""),
                    "jobname": getattr(job, "jobname", ""),
                    "owner": getattr(job, "owner", ""),
                    "status": getattr(job, "status", ""),
                    "submitted": getattr(job, "submitted", ""),
                })
        except Exception:
            pass
        ports = {
            "VTAM/TSO/CICS": state.config.port,
            "FTP/JES/SQL": state.config.ftp_port,
            "Dashboard": state.config.dashboard_port,
            "DB2DAS": state.config.db2_tcp_port,
            "DB2 WebSocket": state.config.db2_ws_port,
            "USS": getattr(state.config, "uss_port", 2022),
        }
        recent_audit = [
            {"time": e.ts.strftime("%H:%M:%S"), "component": e.component, "userid": e.userid, "command": e.command, "result": e.result}
            for e in state.audit.events
            if e.component in {"TSO", "CICS", "CONSOLE", "SMF80"} and not (e.component == "SMF80" and e.command == "SMF TYPE 80 DATASET ACCESS" and "DATASET=SYS1.UADS" in e.result)
        ][-40:]
        disk = shutil.disk_usage(state.config.sim_root)
        mem_total, mem_avail = _memory_summary()
        uptime_delta = datetime.now() - state.startup_time
        listening = {name: {"port": port, "listening": _is_port_listening(port)} for name, port in ports.items()}
        system_box = {
            "memory_total": mem_total,
            "memory_available": mem_avail,
            "disk_free": _format_bytes(disk.free),
            "disk_total": _format_bytes(disk.total),
            "system_ip": getattr(getattr(state, "network", None), "hostname", "GIBSON") + " / 127.0.0.1",
            "ipl_time": state.startup_time.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": str(uptime_delta).split(".")[0],
            "port_connections": str(sum(1 for s in state.sessions.sessions.values() if s.connected)),
            "listening_ports": ", ".join(str(info["port"]) for info in listening.values() if info["listening"]),
            "sim_time": datetime.now().strftime("%H:%M:%S"),
            "sim_date": datetime.now().strftime("%Y-%m-%d"),
            "loaded_volumes": ", ".join(sorted({getattr(r, "volume", "WORK01") for r in state.datasets.listcat("IBMUSER", prefix="")})) if getattr(state, "datasets", None) else "SBSYS1, WORK01",
            "processing": "PROCESSING" if getattr(state, "console_events", None) else "IDLE",
            "racf_mode": "NORACF" if is_noracf_mode(state) else ("SECURE" if is_secure_mode(state) else "VULN"),
        }
        return {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "users_total": len(state.racf.users),
            "active_count": sum(1 for s in state.sessions.sessions.values() if s.connected),
            "sessions": sessions,
            "jobs": jobs[-50:],
            "ports": listening,
            "recent_audit": recent_audit,
            "client_locations": client_locations,
            "coords": [[c["lat"], c["lon"], c["ip"], c["userid"], c.get("marker_type","yellow"), c.get("geo_label",""), c.get("last_command",""), c.get("last_seen",""), c.get("confidence",""), c.get("service",""), c.get("port",""), c.get("smf_record_id",""), ",".join(c.get("cti_tags",[]) or [])] for c in client_locations if c.get("lat") is not None and c.get("lon") is not None],
            "alerts": state.recent_dashboard_alerts(),
            "system_box": system_box,
        }

    def _html(self) -> None:
        snap = self._snapshot()
        sessions_html = []
        for s in snap["sessions"]:
            cls = "active" if s["connected"] else "inactive"
            cmds = "".join(
                f"<tr><td>{html.escape(c['time'])}</td><td>{html.escape(c['component'])}</td><td>{html.escape(c['command'])}</td></tr>" for c in s["last_commands"]
            ) or "<tr><td colspan='3'>No commands yet</td></tr>"
            sessions_html.append(f"""
            <div class='panel user-panel {cls}'>
              <h3><span class='dot {cls}'></span>{html.escape(s['userid'])}</h3>
              <p><b>IP:</b> {html.escape(s['addr'])} &nbsp; <b>Geo:</b> {html.escape(s['geo'])}</p>
              <table><thead><tr><th>Time</th><th>Area</th><th>Command</th></tr></thead><tbody>{cmds}</tbody></table>
            </div>
            """)
        jobs_rows = "".join(
            f"<tr><td>{html.escape(str(j['jobid']))}</td><td>{html.escape(str(j['jobname']))}</td><td>{html.escape(str(j['owner']))}</td><td>{html.escape(str(j['status']))}</td><td>{html.escape(str(j['submitted']))}</td></tr>" for j in snap["jobs"]
        ) or "<tr><td colspan='5'>No submitted jobs</td></tr>"
        port_rows = "".join(
            f"<tr><td>{html.escape(name)}</td><td>{info['port']}</td><td><span class='dot {'active' if info['listening'] else 'inactive'}'></span>{'LISTENING' if info['listening'] else 'DOWN'}</td></tr>" for name, info in snap["ports"].items()
        )
        audit_rows = "".join(
            f"<tr><td>{html.escape(e['time'])}</td><td>{html.escape(e['component'])}</td><td>{html.escape(e['userid'])}</td><td>{html.escape(e['command'])}</td><td>{html.escape(e['result'])}</td></tr>" for e in snap["recent_audit"]
        ) or "<tr><td colspan='5'>No audit entries</td></tr>"
        coords_json = json.dumps(snap["coords"])
        alerts_json = json.dumps(snap["alerts"])
        sysbox = snap["system_box"]
        try:
            img_path = self.state.config.assets_dir / "system370.png"
            system370_b64 = base64.b64encode(img_path.read_bytes()).decode("ascii") if img_path.exists() else ""
        except Exception:
            system370_b64 = ""
        html_doc = f"""<!doctype html>
<html><head><meta charset='utf-8'>
<title>I3M Gibson Dashboard</title>
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>
<style>
:root {{ --green:#00ff66; --dim:#093; --red:#ff3838; --amber:#ffd84d; --bg:#020402; --panel:#071407; --line:#0b5; --blue:#4da3ff; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--green); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
header {{ padding:14px 18px; border-bottom:1px solid var(--line); background:#030903; display:flex; justify-content:space-between; align-items:center; }}
h1 {{ margin:0; font-size:22px; letter-spacing:1px; }} .sub {{ color:#9f9; font-size:12px; }}
.grid {{ display:grid; grid-template-columns: 1.15fr .85fr; gap:12px; padding:12px; }}
.panel {{ border:1px solid var(--line); background:var(--panel); padding:12px; margin-bottom:12px; box-shadow:0 0 12px rgba(0,255,100,.08); }}
.panel h2,.panel h3 {{ margin:0 0 8px 0; color:#bfffcf; }}
.stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }} .stat {{ border:1px solid #064; padding:10px; background:#031003; }} .stat b {{ font-size:26px; color:white; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ border-bottom:1px solid #064; padding:5px 6px; text-align:left; vertical-align:top; }} th {{ color:#bfffcf; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:7px; }} .dot.active {{ background:var(--red); box-shadow:0 0 8px var(--red); animation:pulse 1s infinite; }} .dot.inactive {{ background:var(--green); }}
.user-panel.active {{ border-color:var(--red); }} .user-panel.inactive {{ opacity:.75; }} #map {{ height:310px; background:#000; position:relative; }}
.map-empty {{ position:absolute; z-index:999; left:12px; bottom:12px; background:#020402cc; color:var(--amber); border:1px solid var(--amber); padding:6px 9px; }}
.gibson-map-marker span {{ display:block; width:18px; height:18px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 12px #00ff66; background:#00ff66; }}
.gibson-map-marker.active span {{ background:#00ff66; animation:pulse 1s infinite; }}
.gibson-map-marker.recent span {{ background:#ffd84d; box-shadow:0 0 12px #ffd84d; }}
.gibson-map-marker.yellow span {{ background:#ffd84d; box-shadow:0 0 12px #ffd84d; }}
.gibson-map-marker.orange span {{ background:#ff9f1c; box-shadow:0 0 14px #ff9f1c; }}
.gibson-map-marker.red span {{ background:#ff3838; box-shadow:0 0 14px #ff3838; }}
.gibson-map-marker.neutral span {{ background:#4da3ff; box-shadow:0 0 12px #4da3ff; }}
.gibson-map-marker.local span {{ background:#4da3ff; box-shadow:0 0 12px #4da3ff; }}
.gibson-map-marker.security_event span {{ background:#ff3838; box-shadow:0 0 14px #ff3838; }}
.gibson-map-marker.lab_private span {{ background:#4da3ff; box-shadow:0 0 12px #4da3ff; }}
.hardware {{ position:relative; text-align:center; }} .system370 {{ max-width:100%; height:auto; border:1px solid #333; background:#111; }}
.power-hotspot {{ position:absolute; top:13.2%; right:6.6%; width:7.2%; height:7.8%; border-radius:50%; border:2px solid rgba(255,80,80,.55); background:rgba(255,0,0,.08); cursor:pointer; }} .power-hotspot:hover,.power-hotspot:focus {{ box-shadow:0 0 14px #ff3838; outline:2px solid #ffd84d; }}
pre {{ white-space:pre-wrap; }} a {{ color:var(--amber); }}
.alert-overlay {{ position:fixed; top:22px; right:22px; max-width:520px; z-index:5000; display:none; }}
.alert-overlay.show {{ display:block; animation:flash 0.8s infinite; }}
.alert-card {{ position:relative; background:#240000; border:3px solid var(--red); color:#fff; box-shadow:0 0 18px rgba(255,56,56,.65); padding:14px 16px 14px 16px; margin-bottom:10px; text-transform:uppercase; }}
.alert-card .meta {{ color:#ffd0d0; font-size:12px; margin-top:6px; }}
.alert-close {{ position:absolute; top:6px; right:8px; background:#5c0000; color:#fff; border:1px solid #ffb3b3; cursor:pointer; font-weight:700; font-size:16px; width:26px; height:26px; }}
.audit-panel .audit-scroll {{ max-height:230px; overflow:auto; }}
.system-mini table td:first-child {{ width:42%; color:#bfffcf; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.45}} }}
@keyframes flash {{ 0%,100%{{transform:scale(1); box-shadow:0 0 12px rgba(255,56,56,.55)}} 50%{{transform:scale(1.01); box-shadow:0 0 22px rgba(255,56,56,.95)}} }}
</style></head><body>
<div id='alertOverlay' class='alert-overlay'></div>
<header><div><h1>I3M Gibson Mainframe Operations Dashboard</h1><div class='sub'>Live sessions, commands, JES activity and service status</div></div><div class='sub'>Generated <span id='generated'>{html.escape(snap['generated'])}</span></div></header>
<div class='grid'><main>
<div class='stats'><div class='stat'>Active users<br><b>{snap['active_count']}</b></div><div class='stat'>Known RACF users<br><b>{snap['users_total']}</b></div><div class='stat'>JES jobs shown<br><b>{len(snap['jobs'])}</b></div></div>
<div class='panel'><h2>Active / Recent Users</h2>{''.join(sessions_html) or '<p>No users have connected yet.</p>'}</div>
<div class='panel audit-panel'><h2>Recent Audit Log</h2><div class='audit-scroll'><table><thead><tr><th>Time</th><th>Area</th><th>User</th><th>Command</th><th>Result</th></tr></thead><tbody>{audit_rows}</tbody></table></div></div>
<div class='panel system-mini'><h2>System Summary</h2><table><tbody>
<tr><td>System memory</td><td>{html.escape(sysbox['memory_available'])} free / {html.escape(sysbox['memory_total'])}</td></tr>
<tr><td>Disk space</td><td>{html.escape(sysbox['disk_free'])} free / {html.escape(sysbox['disk_total'])}</td></tr>
<tr><td>System IP</td><td>{html.escape(sysbox['system_ip'])}</td></tr>
<tr><td>Sim date/time</td><td>{html.escape(sysbox['sim_date'])} {html.escape(sysbox['sim_time'])}</td></tr>
<tr><td>Loaded volumes</td><td>{html.escape(sysbox['loaded_volumes'])}</td></tr>
<tr><td>Processing</td><td>{html.escape(sysbox['processing'])}</td></tr>
<tr><td>RACF mode</td><td>{html.escape(sysbox['racf_mode'])}</td></tr>
<tr><td>System IPL time</td><td>{html.escape(sysbox['ipl_time'])}</td></tr>
<tr><td>Uptime</td><td>{html.escape(sysbox['uptime'])}</td></tr>
<tr><td>Port connections</td><td>{html.escape(sysbox['port_connections'])}</td></tr>
<tr><td>Listening ports</td><td>{html.escape(sysbox['listening_ports'])}</td></tr>
</tbody></table><form method="post" action="/poweroff"><button style="margin-top:8px;background:#5c0000;color:#fff;border:1px solid #ffb3b3;padding:8px 12px;cursor:pointer" type="submit">POWER OFF</button></form></div>
</main><aside>
<div class='panel hardware'><h2>Gibson Control Panel</h2><form method="post" action="/poweron" onsubmit="return confirm('Send QUIT to Gibson and shut down services?');"><div class="gibson-control-panel" role="img" aria-label="Neutral Gibson branded control panel"><strong>GIBSON</strong><span>Training simulator control surface</span></div><button class="power-hotspot" title="POWER ON - send QUIT and shut down Gibson" aria-label="POWER ON switch - send QUIT and shut down Gibson" type="submit"></button></form><p class='sub'>POWER ON switch sends QUIT to the simulated master console shutdown path.</p></div>
<div class='panel'><h2>Connection Map</h2><div id='map'></div><p class='sub'>Geolocation is city-level approximate. Offline fixtures/cache are used by default; private or unknown addresses are not plotted with fake coordinates.</p></div>
<div class='panel'><h2>Service Status</h2><table><thead><tr><th>Service</th><th>Port</th><th>Status</th></tr></thead><tbody>{port_rows}</tbody></table></div>
<div class='panel'><h2>Submitted JES Jobs</h2><table><thead><tr><th>Job ID</th><th>Name</th><th>Owner</th><th>Status</th><th>Submitted</th></tr></thead><tbody>{jobs_rows}</tbody></table></div>
</aside></div>
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
<script>
const coords = {coords_json};
let dismissedAlertIds = new Set();
function esc(s) {{ return String(s ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch])); }}
function dismissAlert(id) {{ dismissedAlertIds.add(Number(id)); pollAlerts(); }}
function renderAlerts(alerts) {{
  const box = document.getElementById('alertOverlay');
  const visible = (alerts || []).filter(a => !dismissedAlertIds.has(Number(a.id))).slice(-3).reverse();
  if (!visible.length) {{ box.className = 'alert-overlay'; box.innerHTML = ''; return; }}
  box.innerHTML = visible.map(a => '<div class="alert-card">' +
    '<button class="alert-close" type="button" onclick="dismissAlert(' + Number(a.id || 0) + ')">×</button>' +
    '<div>SECURITY ALERT: ' + esc(a.event_type) + '</div>' +
    '<div>' + esc(a.message) + '</div>' +
    '<div class="meta">' + esc(a.addr || 'SYSTEM') + ' ' + (a.port ? ('PORT ' + esc(a.port)) : '') + ' ' + esc(a.time) + '</div>' +
    '</div>').join('');
  box.className = 'alert-overlay show';
}}
async function pollAlerts() {{
  try {{
    const res = await fetch('/api/state', {{cache:'no-store', headers: {{'Accept':'application/json'}}}});
    if (!res.ok) return;
    const snap = await res.json();
    document.getElementById('generated').textContent = snap.generated || '';
    renderAlerts(snap.alerts || []);
  }} catch (e) {{}}
}}
try {{
  const map = L.map('map');
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution:'&copy; OpenStreetMap contributors' }}).addTo(map);
  function markerIcon(type) {{
    const cls = 'gibson-map-marker ' + (type || 'recent');
    return L.divIcon({{className: cls, html: '<span></span>', iconSize:[22,22], iconAnchor:[11,11]}});
  }}
  if (coords.length === 0) {{
    map.setView([20,0],2);
    document.getElementById('map').insertAdjacentHTML('beforeend','<div class="map-empty">No active or recent client locations.</div>');
  }} else {{
    const bounds = [];
    coords.forEach(c => {{
      const lat=Number(c[0]), lon=Number(c[1]);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {{
        bounds.push([lat, lon]);
        const popup = '<b>User:</b> '+esc(c[3]||'UNKNOWN')+'<br><b>IP:</b> '+esc(c[2]||'')+'<br><b>Location:</b> '+esc(c[5]||'')+'<br><b>Risk:</b> '+esc(c[4]||'')+'<br><b>Service:</b> '+esc(c[9]||'')+' '+esc(c[10]||'')+'<br><b>SMF:</b> '+esc(c[11]||'')+'<br><b>CTI:</b> '+esc(c[12]||'')+'<br><b>Confidence:</b> '+esc(c[8]||'')+'<br><b>Last:</b> '+esc(c[7]||'')+' '+esc(c[6]||'');
        L.marker([lat, lon], {{icon: markerIcon(c[4])}}).addTo(map).bindPopup(popup);
      }}
    }});
    if (bounds.length === 1) map.setView(bounds[0], 6); else if (bounds.length > 1) map.fitBounds(bounds, {{padding:[28,28]}});
  }}
  setTimeout(() => map.invalidateSize(), 120);
}} catch(e) {{ document.getElementById('map').innerHTML = '<pre>Map unavailable. Clients: ' + coords.map(c => c[2]).join(', ') + '</pre>'; }}
renderAlerts({alerts_json});
setInterval(pollAlerts, 3000);
</script>
</body></html>"""
        data = html_doc.encode("utf-8", errors="ignore")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if hasattr(self, "_send_fingerprint_headers"):
            self._send_fingerprint_headers()
        try:
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def serve_dashboard(state: GibsonState) -> ThreadedHTTPServer:
    _DashboardHandler.state = state
    import os
    _DashboardHandler.username = os.getenv("GIBSON_DASHBOARD_USER", "admin")
    _DashboardHandler.password = os.getenv("GIBSON_DASHBOARD_PASSWORD", "gibsonadmin!")
    server = ThreadedHTTPServer((state.config.host, state.config.dashboard_port), _DashboardHandler)
    try: state.register_open_port(state.config.dashboard_port, "TCP", "DASHBOARD")
    except Exception: pass
    if is_secure_mode(state):
        server = wrap_server_socket(server, state, "HTTPS-DASHBOARD")
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonDashboard").start()
    return server
