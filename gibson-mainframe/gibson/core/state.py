from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
import time
from gibson.security import mfa_pin
from pathlib import Path as _Path
from typing import Any, Callable, Deque, Dict, Optional
import re
from .config import GibsonConfig
from .racf import RacfRepository
from .racf_dynamic import DynamicRacfStore
from .datasets import DatasetCatalog, DatasetSecurity
from .catalog import CatalogManager
from .jes import JesSpool
from .nje import NJENetwork
from .network import NetworkState
from .aliases import AliasRegistry
from .templates import TemplateRegistry
from .audit import AuditLog
from .consolelog import ConsoleLog
from .service_control import ServiceManager
from .issues import IssueLog
from .security_freeze import PasswordPolicy, UadsStore, MfaManager

@dataclass
class SessionInfo:
    userid: str
    addr: str
    connected: bool = True
    notifier: Optional[Callable[[str], None]] = None

class SessionRegistry:
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}

    def add(self, userid: str, addr: str, notifier: Optional[Callable[[str], None]] = None) -> None:
        self.sessions[userid.upper()] = SessionInfo(userid.upper(), addr, True, notifier)

    def remove(self, userid: str) -> None:
        if userid.upper() in self.sessions:
            info = self.sessions[userid.upper()]
            info.connected = False
            info.notifier = None

    def notify(self, userid: str, message: str) -> bool:
        info = self.sessions.get((userid or '').upper())
        if not info or not info.connected or not info.notifier:
            return False
        try:
            info.notifier(message)
            return True
        except Exception:
            return False

@dataclass
class GibsonState:
    config: GibsonConfig
    racf: RacfRepository
    datasets: DatasetCatalog
    jes: JesSpool = field(default_factory=JesSpool)
    sessions: SessionRegistry = field(default_factory=SessionRegistry)
    templates: TemplateRegistry = None  # type: ignore
    dynamic_racf: DynamicRacfStore = field(default_factory=DynamicRacfStore.seeded)
    catalog: CatalogManager = None  # type: ignore
    aliases: AliasRegistry = None  # type: ignore
    nje: NJENetwork = field(default_factory=NJENetwork.seeded)
    audit: AuditLog = None  # type: ignore
    network: NetworkState = None  # type: ignore
    console_log: ConsoleLog = None  # type: ignore
    service_manager: ServiceManager = None  # type: ignore
    issue_log: IssueLog = None  # type: ignore
    apf_libraries: list[str] = field(default_factory=lambda: ["SYS1.LINKLIB", "SYS1.SVCLIB", "SYS1.LPALIB", "SYS1.PROCLIB", "SYS1.PARMLIB", "SYS1.VULNLIB", "TCPIP.SEZALOAD", "CEE.SCEERUN"])
    console_events: Deque[tuple[str, str]] = field(default_factory=deque)
    failed_logons: Dict[tuple[str, str, int], int] = field(default_factory=dict)
    dashboard_alerts: Deque[dict[str, Any]] = field(default_factory=deque)
    alert_sequence: int = 0
    startup_time: datetime = field(default_factory=datetime.now)
    training_shells: Dict[str, dict[str, Any]] = field(default_factory=dict)
    transmit_packages: Dict[str, dict[str, Any]] = field(default_factory=dict)
    indfile_history: Deque[dict[str, Any]] = field(default_factory=deque)
    health_checks: Dict[str, dict[str, Any]] = field(default_factory=dict)
    ispexec_shared: Dict[str, str] = field(default_factory=dict)
    mfa_enabled: bool = False
    mfa_pin_state: object = None  # simulator-only salted PIN metadata
    icsf_state: object = None  # simulator-only ICSF control-plane metadata
    pending_messages: Dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    port_touch: Dict[str, dict[int, float]] = field(default_factory=dict)
    allowed_high_ports: set[int] = field(default_factory=set)
    shutdown_requested: bool = False
    system_hostname: str = "GIBSON"
    geo_events: Deque[dict[str, Any]] = field(default_factory=deque)
    geo_alert_cache: Dict[str, float] = field(default_factory=dict)
    geolocator: object = None
    cti_matcher: object = None
    password_policy: object = None
    uads: object = None
    mfa_manager: object = None


    def set_system_hostname(self, hostname: str, actor: str = "CONSOLE") -> str:
        from gibson.render.block_letters import validate_hostname
        ok, name, reason = validate_hostname(hostname, max_len=15)
        if not ok:
            raise ValueError(reason)
        self.system_hostname = name
        if self.network is not None:
            self.network.set_hostname(name)
        try:
            import os as _os
            _os.environ["GIBSON_SYSTEM_HOSTNAME"] = name
            identity_path = self.config.sim_root / "system_identity.json"
            identity_path.write_text(__import__("json").dumps({"system_hostname": name}, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            self.record_security_event(actor, "SYSTEM HOSTNAME", f"HOSTNAME={name}", service="IPL")
        except Exception:
            pass
        return name

    def get_system_hostname(self) -> str:
        return (getattr(self, "system_hostname", "") or getattr(getattr(self, "network", None), "hostname", "GIBSON") or "GIBSON").upper()

    def _geo_marker_colour(self, geo, cti) -> str:
        if getattr(cti, "matched", False) and (getattr(cti, "severity", "").upper() in {"RED", "CRITICAL"} or {"C2", "BOTNET", "MALWARE"}.intersection(set(getattr(cti, "tags", ()) or ()))):
            return "red"
        cc = (getattr(geo, "country_code", "") or "").upper()
        continent = (getattr(geo, "continent", "") or "").upper()
        if getattr(geo, "classification", "") in {"localhost", "private", "private_home_network", "reserved", "link-local", "cgnat"}:
            return "neutral"
        if cc in {"RU", "IR", "CN"}:
            return "red"
        if cc == "US" or continent == "EUROPE":
            return "orange"
        return "yellow"

    def record_geo_connection(self, addr: str, *, port: int = 0, service: str = "", userid: str = "UNKNOWN", action: str = "CONNECTION", result: str = "SUCCESS") -> dict[str, Any]:
        ip = str(addr or "").strip()
        if not ip:
            ip = "127.0.0.1"
        # The welcome80 site (the public landing page) generates a high volume of
        # GEO LOGON SMF80 records that swamp the security log with noise. Geo
        # telemetry (SMF119) is still recorded; only the noisy GEO LOGON event is
        # suppressed for welcome80 traffic.
        _welcome_port = int(getattr(self.config, "welcome_port", 80) or 80)
        _suppress_geo_logon = (str(service or "").upper().startswith("WELCOME")
                               or int(port or 0) == _welcome_port)
        try:
            geo = self.geolocator.lookup(ip, hostname="") if self.geolocator else None
        except Exception:
            geo = None
        try:
            cti = self.cti_matcher.match_ip(ip) if self.cti_matcher else None
        except Exception:
            cti = None
        marker = self._geo_marker_colour(geo, cti) if geo is not None else "unknown"
        now = datetime.now()
        corr = f"GEO-{int(now.timestamp())}-{len(self.geo_events)+1:04d}"
        event = {
            "event_id": corr,
            "timestamp": now.isoformat(timespec="seconds"),
            "system": self.get_system_hostname(),
            "source_ip": ip,
            "service": (service or "UNKNOWN").upper(),
            "port": int(port or 0),
            "source_port": int(0),
            "user": (userid or "UNKNOWN").upper(),
            "action": (action or "CONNECTION").upper(),
            "result": (result or "SUCCESS").upper(),
            "geo": geo.to_dict() if geo else {},
            "cti": cti.to_dict() if cti else {},
            "marker_colour": marker,
            "risk": "RED" if marker == "red" else ("ORANGE" if marker == "orange" else ("INFO" if marker == "neutral" else "YELLOW")),
        }
        self.geo_events.append(event)
        while len(self.geo_events) > 500:
            self.geo_events.popleft()
        # Record SMF-style telemetry.  No usernames are sent outside Gibson.
        try:
            if self.audit is not None:
                tags = ','.join(event['cti'].get('tags', []) or []) if event.get('cti') else ''
                geo_city = str(event['geo'].get('city') or 'UNKNOWN')
                geo_country = str(event['geo'].get('country_code') or 'UNKNOWN')
                detail = f"SRCIP={ip} SERVICE={event['service']} PORT={event['port']} GEO={geo_city},{geo_country} ASN={event['geo'].get('asn','')} ORG={event['geo'].get('org','')} RISK={event['risk']} CTI={tags}"
                self.audit.record((userid or "SYSTEM").upper(), "SMF TYPE 119 GEO CONNECTION", detail, "SMF119", extra={
                    "RECORD_TYPE":"119", "SUBTYPE":"GEO-CONN", "EVENT":"GEO CONNECTION", "SYSTEM":event["system"], "STACK":"TCPIP", "JOBNAME":event["service"][:8],
                    "USERID":event["user"], "SRCIP":ip, "SRCPORT":str(event.get("source_port", "0")), "DESTIP":"127.0.0.1", "DESTPORT":str(event["port"]),
                    "PROTOCOL":"TCP", "SERVICE":event["service"], "RESULT":event["result"], "BYTES_IN":"0", "BYTES_OUT":"0", "PACKETS_IN":"0", "PACKETS_OUT":"0",
                    "RISK":event["risk"], "MARKER":marker, "CORRID":corr, "CITY":geo_city, "REGION":str(event['geo'].get('region','')), "COUNTRY":geo_country,
                    "CONTINENT":str(event['geo'].get('continent','')), "LAT":str(event['geo'].get('latitude','')), "LON":str(event['geo'].get('longitude','')),
                    "ASN":str(event['geo'].get('asn','')), "ORG":str(event['geo'].get('org','')), "GEO_SRC":str(event['geo'].get('source','')), "GEO_CONF":str(event['geo'].get('confidence','')),
                    "CTI_MATCH":str(bool(event.get('cti', {}).get('matched'))), "CTI_TAGS": tags, "CTI_CONF":str(event.get('cti', {}).get('confidence','')),
                })
                if action.upper() in {"LOGON", "CONNECTION"} and not _suppress_geo_logon:
                    self.audit.record_smf80((userid or "SYSTEM").upper(), "GEO LOGON", detail, result=result, extra={"EVENT":"GEO LOGON", "SYSTEM":event["system"], "USERID":event["user"], "ADDR":ip, "SERVICE":event["service"], "CORRID":corr, "RISK":event["risk"], "CITY":geo_city, "COUNTRY":geo_country, "CTI_TAGS":tags})
        except Exception:
            pass
        try:
            classification = event.get("geo", {}).get("classification")
            is_external = classification not in {"localhost", "private", "private_home_network", "reserved", "link-local", "cgnat"}
            if is_external and getattr(self.config, "cti_master_console_alerts_enabled", True):
                key = f"{ip}:{port}:{event['service']}:{event['risk']}"
                last = self.geo_alert_cache.get(key, 0)
                if time.time() - last > 60:
                    self.geo_alert_cache[key] = time.time()
                    city = event['geo'].get('city') or 'UNKNOWN'
                    country = event['geo'].get('country_code') or 'UNKNOWN'
                    region = event['geo'].get('continent') or event['geo'].get('region') or 'UNKNOWN'
                    tags = ','.join(event.get('cti', {}).get('tags', []) or []) if event.get('cti') else 'GEO'
                    asn = event['geo'].get('asn') or 'UNKNOWN'
                    if marker == "red":
                        msg = f"GIBCTI119A HIGH RISK SOURCE DETECTED USER({event['user']}) SRCIP({ip}) CITY({city}) COUNTRY({country}) ASN({asn}) TAG({tags}) RISK(RED) SMF({corr})"
                        sev = "ALERT"
                    else:
                        msg = f"GIBGEO080W EXTERNAL LOGON GEOLOCATED USER({event['user']}) SRCIP({ip}) CITY({city}) COUNTRY({country}) REGION({region}) ASN({asn}) RISK({event['risk']}) SMF({corr})"
                        sev = "INFO"
                    self.notify_console(msg, severity=sev)
                    self.raise_dashboard_alert(msg, severity=sev, addr=ip, port=port, event_type="GEO_CTI")
        except Exception:
            pass
        return event

    def mfa_token(self) -> str:
        # Legacy compatibility: if no IPL PIN has been set, retain HHMM-only token.
        return time.strftime("%H%M")

    def set_mfa_pin(self, pin: str, actor: str = "CONSOLE") -> str:
        return mfa_pin.set_pin(self, pin, actor)

    def mfa_pin_set(self) -> bool:
        return mfa_pin.is_pin_set(self)

    def validate_mfa_token(self, token: str) -> bool:
        return mfa_pin.validate_token(self, token)

    def mfa_status_lines(self) -> list[str]:
        return mfa_pin.status_lines(self)

    def mfa_required_for(self, userid: str) -> bool:
        who = (userid or "").upper()
        if self.mfa_enabled and who == "IBMUSER" and getattr(self.config, "security_mode", "vuln") == "secure":
            self.record_break_glass(who, "MFA EXEMPTION")
            return False
        return self.mfa_enabled and who != "IBMUSER"

    def record_break_glass(self, userid: str = "IBMUSER", detail: str = "") -> None:
        who = (userid or "IBMUSER").upper()
        msg = "IBMUSER secure-mode break-glass exemption used"
        if detail:
            msg += f" ({detail})"
        try:
            self.record_security_event(who, "BREAK-GLASS", msg, service="SECURE-MODE")
        except Exception:
            pass
        try:
            self.notify_console(f"GIBSON SECURE MODE BREAK-GLASS EVENT {msg}", severity="ALERT")
        except Exception:
            pass
        try:
            self.raise_dashboard_alert(msg, severity="ALERT", event_type="BREAK_GLASS")
        except Exception:
            pass

    def set_mfa(self, enabled: bool, actor: str = "IBMUSER") -> str:
        self.mfa_enabled = bool(enabled)
        detail = "MFA ENABLED" if self.mfa_enabled else "MFA DISABLED"
        try:
            self.record_security_event(actor, "MFA", detail, service="TSO")
        except Exception:
            pass
        return detail

    def __post_init__(self):
        try:
            mfa_pin.configure_from_environment(self)
        except Exception:
            pass

    def _resolve_user_group(self, userid: str) -> str:
        who = (userid or "").upper()
        try:
            rec = self.racf.get(who)
            if rec and rec.default_group:
                return rec.default_group.upper()
        except Exception:
            pass
        try:
            groups = sorted(self.dynamic_racf.groups_for_user(who))
            if groups:
                return groups[0].upper()
        except Exception:
            pass
        return "UNKNOWN"

    def _last_access_display(self, userid: str) -> str:
        prev = self.audit.last_successful_logon(userid) if self.audit is not None else None
        if not prev:
            return "**:**:** ON ********"
        return prev.ts.strftime("%H:%M:%S ON %A, %B %d, %Y").upper()

    def record_security_event(self, userid: str, event: str, details: str = "", *, result: str = "SUCCESS", service: str = "TSO", addr: str = "", terminal: str = "") -> None:
        who = (userid or "UNKNOWN").upper()
        evt = (event or "SECURITY EVENT").upper()
        det = (details or "").strip()
        service_u = (service or "TSO").upper()
        result_u = (result or "SUCCESS").upper()
        if evt == "LOGON" and result_u == "SUCCESS":
            try:
                from gibson.apps.cti_hms import note_logon_alert
                note_logon_alert(self, who, service_u, addr)
            except Exception:
                pass
        try:
            from gibson.apps.cti_hms import observe_security_event
            observe_security_event(self, who, evt, service_u, result_u, details, addr)
        except Exception:
            pass
        system = getattr(getattr(self, "network", None), "hostname", "MVSC").upper() or "MVSC"
        group = self._resolve_user_group(who)
        resource = service_u.split("/")[-1] if service_u else "TSO"
        if resource in {"VTAM", "TSO"}:
            profile = "TSO"
        elif resource in {"TN3270", "TN3270E"}:
            profile = "TSO"
        else:
            profile = resource
        jobname = who if evt == "LOGON" else (resource[:8] if resource else who)
        message_id = "ICH70001I" if evt == "LOGON" and result_u == "SUCCESS" else ("ICH70004I" if evt == "LOGON" else "ICH408I")
        detail = det or f"SERVICE={service_u}"
        last_access = self._last_access_display(who) if evt == "LOGON" and result_u == "SUCCESS" else ""
        if last_access:
            detail = f"{detail} LAST_ACCESS={last_access}".strip()
        extra = {
            "USERID": who,
            "GROUP": group,
            "EVENT": evt,
            "RESULT": result_u,
            "TIME": datetime.now().strftime("%H:%M:%S"),
            "DATE": datetime.now().strftime("%Y-%m-%d"),
            "SYSTEM": system,
            "JOBNAME": jobname,
            "CLASS": "APPL" if evt == "LOGON" else "RACF",
            "RESOURCE": resource,
            "PROFILE": profile,
            "SERVICE": service_u,
            "MESSAGE_ID": message_id,
            "TERMINAL": terminal or "TTY",
            "ADDR": addr or "",
            "DETAIL": detail,
        }
        if self.audit is not None:
            self.audit.record_smf80(who, evt, detail, result=result_u, extra=extra)
            try:
                from gibson.core.smf.records.type80 import racf_event
                racf_event(self, userid=who, event_name=evt, result=result_u,
                           class_name=extra.get("CLASS", "RACF"),
                           resource_name=extra.get("RESOURCE", resource),
                           profile_name=extra.get("PROFILE", profile),
                           access_requested="READ",
                           access_allowed="READ" if result_u == "SUCCESS" else "NONE",
                           reason_code="OK" if result_u == "SUCCESS" else "DENIED",
                           applid=extra.get("APPLID", ""),
                           terminal=extra.get("TERMINAL", "TTY"),
                           source_ip=extra.get("ADDR", ""),
                           correlation_id=extra.get("CORRID", ""),
                           detail=detail)
            except Exception:
                pass
            if evt == "LOGON" and result_u == "SUCCESS":
                smf30_extra = dict(extra)
                smf30_extra["EVENT"] = "SESSION START"
                smf30_extra["RECORD_TYPE"] = "30"
                self.audit.record_smf30(who, "SESSION START", detail, result="SUCCESS", extra=smf30_extra)
                try:
                    from gibson.core.smf.records.type30 import job_step
                    job_step(self, userid=who, jobname=who[:8], stepname="LOGON",
                             program=service_u[:8], result="SUCCESS",
                             correlation_id=extra.get("CORRID", ""), detail=detail)
                except Exception:
                    pass
        if evt == "LOGON" and addr:
            try:
                if getattr(self.config, "geo_enabled", True):
                    self.record_geo_connection(addr, port=0, service=service_u, userid=who, action="LOGON", result=result_u)
            except Exception:
                pass

        if self.config.console_security_audit:
            if evt == "LOGON" and result_u == "SUCCESS":
                self.notify_console(f"ICH70001I {who} LAST ACCESS AT {last_access} LOGON TO {profile} RESULT=SUCCESS METHOD={det or 'PASSWORD'}".strip(), severity="INFO")
            elif evt == "LOGON":
                now = datetime.now().strftime("%H:%M:%S ON %B %d, %Y")
                self.notify_console(
                    f"ICH70004I USER({who}) GROUP({group}) NAME({who}) ATTEMPTED 'LOGON' ACCESS OF ENTITY '{profile}' IN CLASS 'APPL' AT {now} RESULT={result_u} DETAIL={det or 'FAILURE'}".strip(),
                    severity="ALERT",
                )
            else:
                self.notify_console(f"ICH4080I {evt} USER={who} RESULT={result_u} SERVICE={service_u} {det}".strip(), severity="INFO" if result_u == "SUCCESS" else "ALERT")

    def add_indfile_event(self, direction: str, target: str, user: str, note: str = "") -> None:
        entry = {"TIME": datetime.now().isoformat(timespec="seconds"), "DIRECTION": direction.upper(), "TARGET": target.upper(), "USER": user.upper(), "NOTE": note}
        self.indfile_history.append(entry)
        while len(self.indfile_history) > 40:
            self.indfile_history.popleft()

    def seed_health_checks(self) -> None:
        checks = {
            "GIBAPF01": {"NAME": "Broad APF exposure", "SEVERITY": "MED", "STATUS": "ACTIVE", "DETAIL": "Writable APF libraries should be restricted and reviewed."},
            "GIBPTK01": {"NAME": "PassTicket profile review", "SEVERITY": "MED", "STATUS": "ACTIVE", "DETAIL": "Review PTKTDATA profiles for replay and APPL scoping."},
            "GIBNET01": {"NAME": "TN3270/TELNET parameters", "SEVERITY": "LOW", "STATUS": "ACTIVE", "DETAIL": "Verify TELNETPARMS and TN3270E member settings."},
            "GIBSUR01": {"NAME": "SURROGAT delegation", "SEVERITY": "HIGH", "STATUS": "ACTIVE", "DETAIL": "Overbroad *.SUBMIT or user.SUBMIT access can enable delegated batch abuse."},
            "GIBAUD01": {"NAME": "Console security audit echo", "SEVERITY": "LOW", "STATUS": "ACTIVE", "DETAIL": "Enable console security audit echo during demonstrations when desired."},
        }
        for key, value in checks.items():
            self.health_checks.setdefault(key, value.copy())

    def _apf_persist_path(self):
        try:
            return self.config.sim_root / "apf_libraries.json"
        except Exception:
            return None

    def persist_apf_libraries(self) -> None:
        """Write the dynamic APF list to disk so additions survive a restart and
        are shared with a separately-run console process."""
        p = self._apf_persist_path()
        if p is None:
            return
        try:
            import json
            p.write_text(json.dumps(list(self.apf_libraries), indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_apf_libraries(self) -> None:
        """Merge any persisted APF additions over the seeded defaults (defaults
        first so system libraries keep their order, then persisted extras)."""
        p = self._apf_persist_path()
        if p is None:
            return
        try:
            import json
            if p.exists():
                persisted = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(persisted, list):
                    defaults = [str(x) for x in self.apf_libraries]
                    extra = [str(x) for x in persisted if str(x) not in defaults]
                    self.apf_libraries = list(dict.fromkeys(defaults + extra))
        except Exception:
            pass

    def refresh_health_checks(self) -> None:
        self.seed_health_checks()
        writable = []
        for lib in self.apf_libraries:
            prof = self.dynamic_racf._find_profile("DATASET", lib)
            if prof and any(acc in {"UPDATE", "CONTROL", "ALTER"} for acc in prof.permits.values()):
                writable.append(lib)
        self.health_checks["GIBAPF01"]["FINDING"] = ", ".join(writable) if writable else "NO WRITABLE APF LIBRARIES DETECTED"
        self.health_checks["GIBAUD01"]["FINDING"] = "ENABLED" if self.config.console_security_audit else "DISABLED"
        ptk_names = sorted([n for n in self.dynamic_racf.profiles.get("PTKTDATA", {}) if not n.startswith("IRRPTAUTH.")])
        self.health_checks["GIBPTK01"]["FINDING"] = ", ".join(ptk_names) or "NO PTKTDATA PROFILES"
        sur = sorted(self.dynamic_racf.profiles.get("SURROGAT", {}))
        self.health_checks["GIBSUR01"]["FINDING"] = ", ".join(sur) if sur else "NO SURROGAT PROFILES"

    def notify_console(self, text: str, severity: str = "INFO") -> None:
        severity_u = (severity or "INFO").upper()
        self.console_events.append((severity_u, text))
        if self.console_log is not None:
            self.console_log.record(text)

    def drain_console_events(self) -> list[tuple[str, str]]:
        items = list(self.console_events)
        self.console_events.clear()
        return items

    def raise_dashboard_alert(self, message: str, severity: str = "ALERT", *, addr: str = "", port: int | None = None, event_type: str = "GENERAL") -> dict[str, Any]:
        self.alert_sequence += 1
        entry = {
            "id": self.alert_sequence,
            "time": datetime.now().isoformat(timespec="seconds"),
            "severity": (severity or "ALERT").upper(),
            "message": message,
            "addr": addr or "",
            "port": int(port) if port is not None else None,
            "event_type": (event_type or "GENERAL").upper(),
        }
        self.dashboard_alerts.append(entry)
        while len(self.dashboard_alerts) > 30:
            self.dashboard_alerts.popleft()
        return entry

    def recent_dashboard_alerts(self, limit: int = 8) -> list[dict[str, Any]]:
        items = list(self.dashboard_alerts)
        return items[-limit:]

    def note_failed_logon(self, userid: str, addr: str = "", *, port: int = 0, service: str = "TSO") -> int:
        key = ((userid or "UNKNOWN").upper(), addr or "", int(port or 0))
        current = self.failed_logons.get(key, 0) + 1
        self.failed_logons[key] = current
        if current >= 3:
            who = (userid or "UNKNOWN").upper()
            suffix = f" FROM {addr}" if addr else ""
            port_text = f" PORT {port}" if port else ""
            service_text = (service or "TSO").upper()
            message = f"IRR421I MULTIPLE FAILED LOGON ATTEMPTS DETECTED FOR {who}{suffix}{port_text} SERVICE={service_text} COUNT={current}"
            self.notify_console(message, severity="ALERT")
            if port in (self.config.port, self.config.ftp_port) and current == 3:
                self.raise_dashboard_alert(message, severity="ALERT", addr=addr, port=port, event_type="BRUTE_FORCE")
        return current

    def clear_failed_logon(self, userid: str, addr: str = "", *, port: int = 0) -> None:
        key = ((userid or "UNKNOWN").upper(), addr or "", int(port or 0))
        self.failed_logons.pop(key, None)


    def note_port_touch(self, addr: str, port: int, service: str = "") -> None:
        try:
            now = time.time()
            key = addr or "UNKNOWN"
            # v30.283: suppress localhost nmap/scan noise by default. This only
            # suppresses horizontal port-scan alerts; it does not suppress
            # normal local administrative/security events.
            suppress_local = bool(getattr(self.config, "suppress_localhost_scan", True))
            if suppress_local and key in {"127.0.0.1", "::1", "localhost", "LOCALHOST"}:
                ports = self.port_touch.setdefault(key, {})
                ports[int(port)] = now
                window = float(getattr(self.config, "port_scan_window", 30.0))
                self.port_touch[key] = {p: t for p, t in ports.items() if now - t <= window}
                return
            ports = self.port_touch.setdefault(key, {})
            ports[int(port)] = now
            try:
                # Geo/CTI telemetry is independent of port-scan detection and uses
                # privacy-safe offline fixtures/cache by default.
                if getattr(self.config, "geo_enabled", True):
                    self.record_geo_connection(key, port=int(port), service=service or str(port), userid="UNKNOWN", action="CONNECTION")
            except Exception:
                pass
            window = float(getattr(self.config, "port_scan_window", 30.0))
            recent = {p: t for p, t in ports.items() if now - t <= window}
            self.port_touch[key] = recent
            threshold = int(getattr(self.config, "port_scan_threshold", 4))
            if len(recent) >= threshold:
                cooldown = float(getattr(self.config, "port_scan_cooldown", 20.0))
                last = getattr(self, "_port_scan_last_alert", {})
                sig = tuple(sorted(recent))
                prior = last.get(key) if isinstance(last, dict) else None
                if prior and now - prior.get("time", 0) < cooldown and prior.get("ports") == sig:
                    return
                if not isinstance(last, dict):
                    last = {}
                last[key] = {"time": now, "ports": sig}
                self._port_scan_last_alert = last
                msg = f"EZD1287I POSSIBLE PORT SCAN DETECTED FROM {key} PORTS({','.join(str(p) for p in sorted(recent))}) COUNT({len(recent)})"
                self.notify_console(msg, severity="ALERT")
                self.raise_dashboard_alert(msg, severity="ALERT", addr=key, port=int(port), event_type="PORT_SCAN")
                try:
                    from gibson.apps.cti_hms import observe_port_scan
                    observe_port_scan(self, key, len(recent))
                except Exception:
                    pass
                try:
                    from gibson.core import v26_features
                    v26_features.security_event(self, "PORT_SCAN", msg, userid="SYSTEM", severity="ALERT", resource=service or str(port), result="WARNING", addr=key, service=service)
                except Exception:
                    pass
                if self.audit is not None:
                    self.audit.record_smf80("SYSTEM", "PORT SCAN", msg, result="WARNING", extra={"EVENT":"PORT_SCAN", "ADDR":key, "RESOURCE":service or str(port), "DETAIL":msg})
        except Exception:
            pass

    def register_open_port(self, port: int, protocol: str = "TCP", component: str = "") -> None:
        try:
            p = int(port)
            known = {l.port for l in getattr(self.network, "listeners", [])}
            known.update(getattr(self, "allowed_high_ports", set()) or set())
            if p > 1024 and p not in known:
                msg = f"EZD1288I UNKNOWN HIGH PORT OPENED PORT={p} PROTOCOL={protocol.upper()} COMPONENT={component or 'UNKNOWN'}"
                self.notify_console(msg, severity="ALERT")
                self.raise_dashboard_alert(msg, severity="ALERT", port=p, event_type="UNKNOWN_HIGH_PORT")
                try:
                    from gibson.core import v26_features
                    v26_features.security_event(self, "UNKNOWN_HIGH_PORT", msg, userid="SYSTEM", severity="ALERT", resource=str(p), result="WARNING", service=component or "UNKNOWN")
                except Exception:
                    pass
                if self.audit is not None:
                    self.audit.record_smf80("SYSTEM", "UNKNOWN HIGH PORT", msg, result="WARNING", extra={"EVENT":"UNKNOWN_HIGH_PORT", "RESOURCE":str(p), "DETAIL":msg})
        except Exception:
            pass

    @classmethod
    def create(cls, config: Optional[GibsonConfig] = None) -> "GibsonState":
        cfg = config or GibsonConfig.from_env()
        cfg.ensure()
        # Seed GACF from package assets if no external GACF exists.
        # If an operator has placed GACF.DB in the project/current directory,
        # use it instead of silently seeding a new ~/mfsim/GACF.DB.
        if not cfg.gacf_path.exists():
            cwd_gacf = _Path.cwd() / "GACF.DB"
            asset_gacf = cfg.assets_dir / "GACF.DB"
            if cwd_gacf.exists():
                cfg.gacf_path = cwd_gacf
            elif asset_gacf.exists():
                cfg.gacf_path.write_text(asset_gacf.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            else:
                cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS\n", encoding="utf-8")
        racf = RacfRepository(cfg.gacf_path)
        racf.load()
        try:
            if racf.get("CICSUSER") is None:
                racf.adduser("CICSUSER", "", special=False, omvs=False, default_group="SYS1", protected=True, nopassword=True, name="CICS DEFAULT USER")
                racf.load()
        except Exception:
            pass
        try:
            racf.config = cfg  # used by secure-mode RACF access evaluation
        except Exception:
            pass
        datasets = DatasetCatalog(cfg.files_root)
        state = cls(cfg, racf, datasets, dynamic_racf=DynamicRacfStore.load_or_seed(cfg.sim_root / "racf_dynamic.json"))
        state.password_policy = PasswordPolicy.load(cfg.sim_root / "setropts_password_policy.json")
        state.mfa_enabled = bool(getattr(state.password_policy, "mfa_active", False))
        try:
            state.racf.password_policy = state.password_policy
        except Exception:
            pass
        state.uads = UadsStore(cfg.sim_root / "SYS1.UADS.json")
        state.uads.sync_from_racf(state.racf, state.password_policy)
        state.mfa_manager = MfaManager(state.uads, state.password_policy)
        try:
            from gibson.core.mfa import MfaPolicyStore
            state.mfa_policy = MfaPolicyStore.seeded()
        except Exception:
            state.mfa_policy = None
        state.audit = AuditLog(cfg.sim_root / "audit.log")
        state.datasets.security = DatasetSecurity(state.dynamic_racf, state.racf, state.audit, state)
        state.datasets.seed_defaults()
        try:
            state.datasets.write("IBMUSER", "SYS1.UADS", "\n".join(state.uads.list_lines()) + "\n")
        except Exception:
            pass
        try:
            from gibson.core.racf_database import materialise_racfds
            materialise_racfds(state)
        except Exception:
            pass
        def _provision_user_datasets(uid: str) -> None:
            """Create the default training datasets + DATASET profiles for a user,
            identical to what the seeded users (e.g. GUEST) receive. Used both at
            startup and whenever a new user is created via ADDUSER."""
            try:
                state.datasets.seed_user_training(uid)
                for profile in (f"{uid}.PDS.CODE", f"{uid}.SQL.LAB", f"{uid}.JCL.LAB"):
                    if state.dynamic_racf._find_profile("DATASET", profile) is None:
                        prof = state.dynamic_racf.define("DATASET", profile, owner=uid, uacc="READ", volume="WORK01")
                        prof.permits[uid] = "ALTER"
            except Exception:
                pass

        for uid in sorted(state.racf.users):
            _provision_user_datasets(uid)
        # New users created later via ADDUSER get the same defaults as GUEST.
        try:
            state.racf.on_user_added = lambda uid: _provision_user_datasets(uid.upper())
        except Exception:
            pass
        sys1_profiles = (
            "SYS1.*", "SYS1.PARMLIB", "SYS1.PROCLIB", "SYS1.LINKLIB", "SYS1.LPALIB", "SYS1.SVCLIB",
            "SYS1.NUCLEUS", "SYS1.MACLIB", "SYS1.MODGEN", "SYS1.SAMPLIB", "SYS1.CLIST",
            "SYS1.REXX", "SYS1.JCLLIB", "SYS1.VTAMLST", "SYS1.TCPPARMS", "SYS1.RACFDS",
            "SYS1.RACFDS.BACKUP", "SYS1.MANA", "SYS1.MANB", "SYS1.MANC", "SYS1.UADS", "SYS1.CKDS", "SYS1.PKDS", "SYS1.TKDS", "SYS1.BRODCAST", "SYS1.MIGLIB", "SYS1.CSSLIB", "SYS1.SERBLINK", "SYS1.SISPLPA",
            "SYS1.SISPMENU", "SYS1.SISPPLIB", "SYS1.SISPSENU", "SYS1.SISTCLIB", "SYS1.SDSF",
            "SYS1.SISPEXEC", "SYS1.SISPCLIB", "SYS1.DB2.PROCLIB", "SYS1.CICS.PROCLIB",
        )
        for profile in sys1_profiles:
            prof = state.dynamic_racf._find_profile("DATASET", profile)
            if prof is None:
                prof = state.dynamic_racf.define("DATASET", profile, "IBMUSER", "READ", volume="SBSYS1")
            prof.permits.setdefault("GUEST", "NONE")
            prof.permits.setdefault("IBMUSER", "ALTER")
        try:
            p = state.dynamic_racf._find_profile("DATASET", "SYS1.PARMLIB")
            if p is not None:
                p.warning = True
        except Exception:
            pass
        state.dynamic_racf.save()
        state.templates = TemplateRegistry(cfg.commands_dir, cfg.assets_dir)
        state.catalog = CatalogManager.load(cfg.sim_root / "catalog_aliases.json")
        state.aliases = AliasRegistry.load(cfg.sim_root / "aliases.json")
        state.network = NetworkState.seeded(cfg)
        try:
            persisted = None
            try:
                identity_path = cfg.sim_root / "system_identity.json"
                if identity_path.exists():
                    persisted = __import__("json").loads(identity_path.read_text(encoding="utf-8")).get("system_hostname")
            except Exception:
                persisted = None
            state.system_hostname = (persisted or getattr(cfg, "default_system_hostname", "GIBSON")).upper() or "GIBSON"
            state.network.set_hostname(state.system_hostname)
            try:
                __import__("os").environ["GIBSON_SYSTEM_HOSTNAME"] = state.system_hostname
            except Exception:
                pass
        except Exception:
            pass
        try:
            from gibson.core.geo import Geolocator
            from gibson.core.geo.providers import FixtureGeoProvider, FreeIpApiGeoProvider, FallbackGeoProvider
            from gibson.core.cti import CTIMatcher
            online_enabled = bool(getattr(cfg, "geo_online_enabled", True))
            provider_name = str(getattr(cfg, "geo_provider", "freeipapi") or "freeipapi").lower()
            online_provider = None
            if online_enabled and provider_name in {"freeipapi", "online", "auto", "fixture"}:
                online_provider = FreeIpApiGeoProvider(timeout=float(getattr(cfg, "geo_provider_timeout", 10.0)))
            provider = FallbackGeoProvider(FixtureGeoProvider(), online_provider, online_enabled=online_enabled)
            state.geolocator = Geolocator(provider=provider)
            state.cti_matcher = CTIMatcher()
        except Exception:
            state.geolocator = None; state.cti_matcher = None
        logs_dir = cfg.sim_root / "logs"
        state.console_log = ConsoleLog(logs_dir / "OPERLOG.log", logs_dir / "SYSLOG.log")
        state.issue_log = IssueLog(logs_dir / "ISSUES.LOG")
        state.service_manager = ServiceManager(state, state.console_log)
        try:
            from .service_control import ManagedService
            defaults = [
                ("JES2", None, "Job Entry Subsystem"), ("RACF", None, "Security authentication service"),
                ("SDSF", None, "System Display and Search Facility"), ("CICS", 2323, "CICS transaction region"),
                ("DB2", getattr(cfg, "db2_tcp_port", None), "Db2 subsystem"), ("OMVS", getattr(cfg, "uss_port", None), "z/OS UNIX"),
                ("TCPIP", None, "Communications Server"), ("VTAM", getattr(cfg, "port", None), "VTAM/TSO"),
                ("TSO", getattr(cfg, "port", None), "TSO logon"), ("ICSF", None, "Integrated Cryptographic Service Facility"),
                ("NJE", None, "Network Job Entry"), ("FTPD", getattr(cfg, "ftp_port", None), "FTP daemon"),
                ("GIBDASH", getattr(cfg, "dashboard_port", None), "Dashboard"),
            ]
            for name, port, desc in defaults:
                if state.service_manager.get(name) is None:
                    state.service_manager.register(ManagedService(name, port=port, description=desc, state="STARTED" if name not in {"FTPD"} else "STOPPED"))
        except Exception:
            pass
        try:
            state.allowed_high_ports = {l.port for l in state.network.listeners}
        except Exception:
            pass
        state.load_apf_libraries()
        state.seed_health_checks()
        state.refresh_health_checks()
        return state
