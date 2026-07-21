from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import Any

_ALLOWED_IPS = {"127.0.0.1"}
_ALLOWED_NAMES = {"mainframe", "localhost"}

@dataclass(frozen=True)
class HostResolution:
    name: str
    address: str
    display: str
    allowed: bool = True
    reason: str = ""


def _alias_file(cwd: str, userid: str | None = None) -> str:
    if cwd and cwd.startswith("/u/"):
        parts = cwd.strip("/").split("/")
        if len(parts) >= 2:
            return f"/u/{parts[1]}/.gibson_hosts"
    if userid:
        return f"/u/{userid.lower()}/.gibson_hosts"
    return "/u/ibmuser/.gibson_hosts"


def _read_aliases(env: Any, cwd: str) -> dict[str, str]:
    path = _alias_file(cwd)
    try:
        text = env.read_text(path)
    except Exception:
        return {}
    aliases: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            aliases[parts[0].lower()] = parts[1]
    return aliases


def _write_aliases(env: Any, cwd: str, aliases: dict[str, str]) -> None:
    path = _alias_file(cwd)
    lines = ["# Gibson simulated host aliases", "# name address"]
    for k in sorted(aliases):
        lines.append(f"{k} {aliases[k]}")
    env.write_text(path, "\n".join(lines) + "\n")


def _safe_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", name or ""))


def _system_name() -> str:
    return (os.getenv("GIBSON_SYSTEM_HOSTNAME", "GIBSON") or "GIBSON").strip().lower()

def _safe_local_address(addr: str) -> bool:
    return addr in _ALLOWED_IPS or addr.lower() in (_ALLOWED_NAMES | {_system_name()})


def resolve_host(target: str, env: Any = None, cwd: str = "/u/ibmuser") -> HostResolution:
    t = (target or "mainframe").strip()
    tl = t.lower()
    if tl == "localhost":
        return HostResolution(t, "127.0.0.1", "localhost (127.0.0.1)")
    if tl == "127.0.0.1":
        return HostResolution(t, "127.0.0.1", "127.0.0.1")
    if tl == _system_name():
        return HostResolution(t, "127.0.0.1", f"{t} (127.0.0.1)")
    if tl == "mainframe":
        aliases = _read_aliases(env, cwd) if env is not None else {}
        addr = aliases.get("mainframe", "127.0.0.1")
        if _safe_local_address(addr):
            address = "127.0.0.1" if addr.lower() in {"mainframe", "localhost"} else addr
            return HostResolution(t, address, f"mainframe ({address})")
        return HostResolution(t, addr, t, False, "mainframe alias is outside Gibson training scope")
    aliases = _read_aliases(env, cwd) if env is not None else {}
    if tl in aliases:
        addr = aliases[tl]
        if _safe_local_address(addr):
            address = "127.0.0.1" if addr.lower() in {"mainframe", "localhost"} else addr
            return HostResolution(t, address, f"{t} ({address})")
        return HostResolution(t, addr, t, False, "alias resolves outside Gibson training scope")
    return HostResolution(t, t, t, False, "target not permitted in Gibson training scope")


def hosts_command(env: Any, cwd: str, argv: list[str]) -> str:
    aliases = _read_aliases(env, cwd)
    if not argv or argv[0].lower() == "list":
        rows = ["Gibson simulated host aliases", "mainframe 127.0.0.1 (built-in unless overridden)", "localhost 127.0.0.1 (built-in)", f"{_system_name()} 127.0.0.1 (current system hostname)"]
        for k in sorted(aliases):
            rows.append(f"{k} {aliases[k]}")
        return "\n".join(rows)
    sub = argv[0].lower()
    if sub == "resolve" and len(argv) >= 2:
        r = resolve_host(argv[1], env, cwd)
        if not r.allowed:
            return f"hosts: {argv[1]} denied: {r.reason}"
        return f"{argv[1]} -> {r.address}"
    if sub == "add" and len(argv) >= 3:
        name = argv[1].lower(); addr = argv[2].lower()
        if not _safe_name(name):
            return "hosts: invalid alias name"
        if not _safe_local_address(addr):
            return "hosts: Gibson training aliases may resolve only to mainframe, localhost or 127.0.0.1"
        aliases[name] = "127.0.0.1" if addr in {"localhost", "mainframe"} else addr
        _write_aliases(env, cwd, aliases)
        return f"hosts: added {name} -> {aliases[name]}"
    if sub == "remove" and len(argv) >= 2:
        name = argv[1].lower()
        aliases.pop(name, None)
        _write_aliases(env, cwd, aliases)
        return f"hosts: removed {name}"
    return "Usage: hosts [list] | hosts add NAME 127.0.0.1 | hosts remove NAME | hosts resolve NAME"


# Enhanced HOSTS.TXT support for VTAM/OMVS tooling v1.
def _hosts_txt_path(cwd: str, userid: str | None = None) -> str:
    if cwd and cwd.startswith('/u/'):
        parts = cwd.strip('/').split('/')
        if len(parts) >= 2:
            return f"/u/{parts[1]}/HOSTS.TXT"
    if userid:
        return f"/u/{userid.lower()}/HOSTS.TXT"
    return "/u/ibmuser/HOSTS.TXT"

def _default_hosts_text() -> str:
    sysn = _system_name().upper()
    return "\n".join([
        "# Gibson HOSTS.TXT - active tools require AUTHORIZED=TRUE",
        "[mainframe]",
        "host=127.0.0.1",
        f"aliases=localhost,{sysn.lower()},gibson",
        "ports=21,23,80,443,2023,8080,9080,50000",
        "services=ftp,tn3270,http,tomcat,cics,db2,fibs",
        "authorized=true",
        "vuln_profile=gibson-local",
        "notes=Local Gibson training system",
        "",
        f"[{sysn.lower()}]",
        "host=127.0.0.1",
        "aliases=mainframe,localhost",
        "ports=21,23,80,443,2023,8080,9080,50000",
        "services=ftp,tn3270,http,tomcat,cics,db2,fibs",
        "authorized=true",
        "vuln_profile=gibson-local",
        "notes=Current R05 system hostname",
        "",
    ]) + "\n"

def _read_hosts_txt(env: Any, cwd: str) -> dict[str, dict[str, str]]:
    path = _hosts_txt_path(cwd)
    try:
        text = env.read_text(path)
    except Exception:
        try:
            env.write_text(path, _default_hosts_text())
            text = env.read_text(path)
        except Exception:
            text = _default_hosts_text()
    data: dict[str, dict[str, str]] = {}
    cur = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1].strip().lower()
            data.setdefault(cur, {'name': cur})
            continue
        if '=' in line and cur:
            k, v = line.split('=', 1)
            data[cur][k.strip().lower()] = v.strip()
        elif cur and len(line.split()) >= 2:
            p = line.split()
            data[cur]['host'] = p[1]
    return data

def _enhanced_resolve_host(target: str, env: Any = None, cwd: str = "/u/ibmuser") -> HostResolution:
    t = (target or 'mainframe').strip(); tl = t.lower(); sysn = _system_name()
    if tl in {'localhost','127.0.0.1','mainframe',sysn,'gibson'}:
        return HostResolution(t, '127.0.0.1', f"{t} (127.0.0.1)", True)
    if env is not None:
        hosts = _read_hosts_txt(env, cwd)
        for name, rec in hosts.items():
            aliases = [x.strip().lower() for x in rec.get('aliases','').split(',') if x.strip()]
            if tl == name or tl in aliases:
                addr = rec.get('host', '') or rec.get('address','') or '127.0.0.1'
                auth = rec.get('authorized','false').lower() in {'1','true','yes','y'}
                return HostResolution(t, addr, f"{name} ({addr})", auth, '' if auth else 'HOSTS.TXT entry is not AUTHORIZED=TRUE')
    # legacy aliases as fallback
    try:
        return globals().get('_legacy_resolve_host', resolve_host)(target, env, cwd)  # type: ignore
    except RecursionError:
        return HostResolution(t, t, t, False, 'target not permitted in Gibson training scope')

def _enhanced_hosts_command(env: Any, cwd: str, argv: list[str]) -> str:
    hosts = _read_hosts_txt(env, cwd)
    path = _hosts_txt_path(cwd)
    if not argv or argv[0].lower() == 'list':
        rows=[f"Gibson HOSTS.TXT: {path}", "Name                 Host             Auth  Services"]
        for name, rec in sorted(hosts.items()):
            rows.append(f"{name:<20} {rec.get('host',''):<16} {rec.get('authorized','false'):<5} {rec.get('services','')}")
        rows.append("Built-ins: mainframe, localhost, 127.0.0.1, current R05 hostname -> 127.0.0.1")
        return "\n".join(rows)
    sub=argv[0].lower()
    if sub == 'resolve' and len(argv)>=2:
        r=_enhanced_resolve_host(argv[1], env, cwd)
        if not r.allowed: return f"hosts: {argv[1]} denied: {r.reason}"
        return f"{argv[1]} -> {r.address}"
    if sub == 'show' and len(argv)>=2:
        rec=hosts.get(argv[1].lower())
        if not rec: return f"hosts: no entry {argv[1]}"
        return "\n".join(f"{k}={v}" for k,v in sorted(rec.items()))
    if sub == 'add' and len(argv)>=3:
        name=argv[1].lower(); addr=argv[2]
        if not _safe_name(name): return 'hosts: invalid name'
        auth='false'; services=''; aliases=''
        for a in argv[3:]:
            if a.lower().startswith('authorized='): auth=a.split('=',1)[1]
            elif a.lower().startswith('services='): services=a.split('=',1)[1]
            elif a.lower().startswith('aliases='): aliases=a.split('=',1)[1]
        hosts[name]={'name':name,'host':addr,'authorized':auth,'services':services,'aliases':aliases,'ports':'','vuln_profile':'custom','notes':'Added from OMVS hosts command'}
        lines=[]
        for n, rec in sorted(hosts.items()):
            lines.append(f"[{n}]")
            for k in ['host','aliases','ports','services','authorized','vuln_profile','notes']:
                if k in rec: lines.append(f"{k}={rec[k]}")
            lines.append('')
        env.write_text(path, "\n".join(lines))
        return f"hosts: added {name} -> {addr} authorized={auth}"
    if sub in {'check','showfile'}:
        return env.read_text(path)
    return 'Usage: hosts list|show NAME|resolve NAME|add NAME HOST authorized=true services=ftp,tn3270|check'

try:
    _legacy_resolve_host = resolve_host
except Exception:
    _legacy_resolve_host = None
resolve_host = _enhanced_resolve_host
hosts_command = _enhanced_hosts_command
