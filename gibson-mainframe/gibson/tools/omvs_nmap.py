from __future__ import annotations

import contextlib
import importlib
import socket
import io
import datetime as dt
from pathlib import Path
from typing import Iterable
from gibson.tools.host_aliases import resolve_host
from gibson.tools.security_events import emit_omvs_tool_event, format_corr_line

ALLOWED_TARGETS = {"127.0.0.1", "localhost", "mainframe"}
OUTPUT_OPTS = {"-oN", "-oJ", "--script-args-file", "-u", "--userdb", "-P", "--passdb"}
BOUNDED_INT_OPTS = {"--max-guesses": (1, 100), "--max-retries": (1, 5)}
BOUNDED_FLOAT_OPTS = {"--host-timeout": (0.2, 10.0), "--delay": (0.0, 5.0)}


def _is_option_value_expected(prev: str) -> bool:
    return prev in {"-p", "--port", "--script", "--script-args", "--script-args-file", "-u", "--userdb", "-P", "--passdb", "-oN", "-oJ", "--max-retries", "--host-timeout", "--delay", "--max-guesses"}


def _target_operands(argv: list[str]) -> list[str]:
    targets: list[str] = []
    prev = ""
    for a in argv:
        if _is_option_value_expected(prev):
            prev = ""
            continue
        if a in {"-s", "--screen", "--cicspwn", "--tso-brute", "-M", "--menu", "--firstonly", "--version", "-v", "--verbose"}:
            prev = ""
            continue
        if a.startswith("--") and "=" in a:
            opt = a.split("=", 1)[0]
            if opt in {"--host", "--port", "--script", "--script-args", "--script-args-file", "--max-retries", "--host-timeout", "--delay", "--max-guesses"}:
                val = a.split("=", 1)[1]
                if opt == "--host":
                    targets.append(val)
                prev = ""
                continue
        if a in {"-H", "--host"}:
            prev = "__HOST__"
            continue
        if prev == "__HOST__":
            targets.append(a)
            prev = ""
            continue
        if a.startswith("-"):
            prev = a
            continue
        targets.append(a)
        prev = ""
    return targets


def _reject_target(t: str, env=None, cwd: str = "/u/ibmuser") -> bool:
    bad_tokens = ["/", ",", "-", "*", "?", "[", "]", "..", ":"]
    if any(x in t for x in bad_tokens):
        return True
    return not resolve_host(t, env, cwd).allowed


def _safe_virtual_path(env, cwd: str, item: str, *, must_exist: bool = False) -> str:
    if not item or item.startswith("-"):
        raise ValueError("invalid output path")
    vp = env.resolve(cwd, item)
    # Output and script-args files are constrained to the current OMVS user
    # workspace, not merely the broader simulated USS root. This prevents
    # ../../ traversal from /u/ibmuser into shared top-level paths.
    home = cwd.rstrip("/") or "/"
    if not (vp == home or vp.startswith(home + "/")):
        raise ValueError("output path escapes OMVS workspace")
    real = env.real_path(vp)
    root = env.root.resolve()
    if root not in real.resolve().parents and real.resolve() != root:
        raise ValueError("output path escapes OMVS workspace")
    if must_exist and not real.exists():
        raise ValueError("script args file not found in OMVS workspace")
    real.parent.mkdir(parents=True, exist_ok=True)
    return str(real)



def _rewrite_script_args_value(value: str, env, cwd: str) -> str:
    # Support common NSE style: --script-args userdb=file,tso-enum.commands=...
    parts = []
    for item in value.split(','):
        if '=' not in item:
            parts.append(item); continue
        k, v = item.split('=', 1)
        if k.strip() in {"userdb", "passdb", "tso-enum.userdb", "cics-user-enum.userdb", "cics-enum.idlist", "idlist"}:
            vv = v.strip().strip('\"\'')
            if vv and not vv.startswith('/') and not vv.startswith('-'):
                try:
                    v = _safe_virtual_path(env, cwd, vv, must_exist=True)
                except ValueError:
                    # Preserve original so the simulator returns its own readable error.
                    v = vv
        parts.append(k + '=' + v)
    return ','.join(parts)

def _rewrite_paths(argv: list[str], env, cwd: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--script-args":
            if i + 1 >= len(argv):
                raise ValueError(f"{a}: missing value")
            out.extend([a, _rewrite_script_args_value(argv[i + 1], env, cwd)])
            i += 2
            continue
        if a in OUTPUT_OPTS:
            if i + 1 >= len(argv):
                raise ValueError(f"{a}: missing path")
            must = a in {"--script-args-file", "-u", "--userdb", "-P", "--passdb"}
            out.extend([a, _safe_virtual_path(env, cwd, argv[i + 1], must_exist=must)])
            i += 2
            continue
        if a.startswith("--script-args="):
            opt, val = a.split("=", 1)
            out.append(f"{opt}={_rewrite_script_args_value(val, env, cwd)}")
            i += 1
            continue
        if a.startswith("-oN=") or a.startswith("-oJ=") or a.startswith("--script-args-file=") or a.startswith("--userdb=") or a.startswith("--passdb="):
            opt, val = a.split("=", 1)
            must = opt in {"--script-args-file", "--userdb", "--passdb"}
            out.append(f"{opt}={_safe_virtual_path(env, cwd, val, must_exist=must)}")
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def _bounded_args(argv: list[str]) -> list[str]:
    out = list(argv)
    for i, a in enumerate(out):
        opt = None; val = None
        if a in BOUNDED_INT_OPTS or a in BOUNDED_FLOAT_OPTS:
            opt = a
            if i + 1 < len(out): val = out[i + 1]
        elif a.startswith("--") and "=" in a:
            opt, val = a.split("=", 1)
        if not opt or val is None: continue
        if opt in BOUNDED_INT_OPTS:
            lo, hi = BOUNDED_INT_OPTS[opt]
            try: n = max(lo, min(hi, int(val)))
            except Exception: n = lo
            if a == opt: out[i + 1] = str(n)
            else: out[i] = f"{opt}={n}"
        if opt in BOUNDED_FLOAT_OPTS:
            lo, hi = BOUNDED_FLOAT_OPTS[opt]
            try: n = max(lo, min(hi, float(val)))
            except Exception: n = lo
            if a == opt: out[i + 1] = str(n)
            else: out[i] = f"{opt}={n}"
    return out



def _extract_port(args: list[str]) -> int:
    for i, a in enumerate(args):
        if a == "-p" and i + 1 < len(args):
            try: return int(args[i + 1])
            except Exception: return 0
        if a.startswith("-p") and len(a) > 2:
            try: return int(a[2:])
            except Exception: return 0
        if a.startswith("--port="):
            try: return int(a.split("=", 1)[1])
            except Exception: return 0
    return 2023



def _all_open_scan(args: list[str], env) -> str | None:
    joined = " ".join(args)
    if "-p-" not in joined and "--open" not in args:
        return None
    active31337 = False
    try:
        from gibson.apps.tomcat_sim.state import active_sessions
        active31337 = bool(active_sessions(env.state))
    except Exception:
        active31337 = False
    rows = [
        "Starting Nmap 7.98 ( https://nmap.org ) at " + dt.datetime.now().isoformat(timespec="seconds"),
        "",
        "PORT      STATE SERVICE",
        "2023/tcp  open  gibson-vtam",
        "80/tcp    open  gibson-welcome",
        "8080/tcp  open  http",
        "9080/tcp  open  fibs-bank",
    ]
    if active31337:
        rows.append("31337/tcp open  tomcat-bind-safe")
    rows += ["", "Nmap done: Gibson training port sweep complete"]
    return "\n".join(rows)

def _tomcat_scan(args: list[str], env) -> str | None:
    port = _extract_port(args)
    scripts = " ".join(args).lower()
    if port not in {8080, 31337} and not any(x in scripts for x in ["http-title", "http-auth", "http-tomcat", "http-default-accounts"]):
        return None
    if port == 31337:
        active = False
        try:
            from gibson.apps.tomcat_sim.state import active_sessions
            active = bool(active_sessions(env.state))
        except Exception:
            active = False
        state = "open" if active else "closed"
        service = "tomcat-bind-safe" if active else "unknown"
        extra = "\n|_ Gibson: controlled Tomcat training shell active" if active else ""
        now = dt.datetime.now().isoformat(timespec="seconds")
        return f"Starting Nmap 7.98 ( https://nmap.org ) at {now}\nNmap scan report for mainframe (127.0.0.1)\nHost is up (0.0010s latency).\n\nPORT      STATE  SERVICE\n31337/tcp {state:<6} {service}{extra}\n\nNmap done: 1 IP address (1 host up) scanned in 0.01 seconds"
    lines = [
        "Starting Nmap 7.98 ( https://nmap.org ) at " + dt.datetime.now().isoformat(timespec="seconds"),
        "",
        "PORT     STATE SERVICE VERSION",
        "8080/tcp open  http    Apache-Coyote/1.1 Tomcat Manager (Gibson safe simulator)",
        "| http-title: Apache Tomcat/9.0.x - Gibson training simulator",
        "| http-auth: Basic realm=\"Tomcat Manager Application\"",
        "| http-tomcat-manager: /manager/html requires authentication",
        "| http-default-accounts:",
        "|   tomcat:tomcat - VALID (intentional vulnerable training default)",
        "|_  tomcat:manager - VALID (intentional vulnerable training default)",
        "",
        "Nmap done: 1 IP address (1 host up) scanned in 0.01 seconds",
    ]
    return "\n".join(lines)


def _ftp_db2_scan(args: list[str], env) -> str | None:
    port = _extract_port(args)
    scripts = " ".join(args).lower()
    now = dt.datetime.now().isoformat(timespec="seconds")
    vuln = bool(getattr(env.state.config, "security_mode", "vuln") == "vuln")
    if port == 21 or "ftp-anon" in scripts:
        anon = vuln
        lines=[f"Starting Nmap 7.98 ( https://nmap.org ) at {now}", "Nmap scan report for mainframe (127.0.0.1)", "Host is up (0.0010s latency).", "", "PORT   STATE SERVICE VERSION", "21/tcp open  ftp     IBM OS/390 ftpd V2R5"]
        if "ftp-anon" in scripts:
            if anon:
                lines += ["| ftp-anon: Anonymous FTP login allowed (FTP code 230)", "|_-rw-r--r-- 1 0 0 64 Dec 01  2022 TEXT.DS"]
            else:
                lines += ["| ftp-anon: Anonymous FTP login not allowed (FTP code 530)", "|_  Gibson secure profile rejects anonymous access"]
        lines += ["Service Info: Host: IPFTP1; OS: OS/390; CPE: cpe:/o:ibm:os_390", "", "Nmap done: 1 IP address (1 host up) scanned in 0.03 seconds"]
        return "\n".join(lines)
    if "vtam-enum" in scripts:
        return "\n".join([f"Starting Nmap 7.98 ( https://nmap.org ) at {now}", "Nmap scan report for mainframe (127.0.0.1)", "Host is up (0.0010s latency).", "", "PORT     STATE SERVICE", "2023/tcp open  tn3270", "| vtam-enum:", "|   VTAM Application ID:", "|     applid:TSO  - Valid application", "|     applid:CICS - Valid application", "|     applid:DB2  - Valid application", "|_  Statistics: Performed 24 guesses in 1.2 seconds, average tps: 20.0", "", "Nmap done: 1 IP address (1 host up) scanned in 1.24 seconds"])
    if port in {50000, 44650000} or "db2-das-info" in scripts or "drda-info" in scripts:
        return "\n".join([f"Starting Nmap 7.98 ( https://nmap.org ) at {now}", "Nmap scan report for mainframe (127.0.0.1)", "Host is up (0.0010s latency).", "", "PORT      STATE SERVICE VERSION", "50000/tcp open  drda    IBM DB2 Database Server (QDB2)", "| db2-das-info:", "|   DB2 Version: DSN12015", "|   Server Platform: QDB2", "|   Instance Name: ZDB2A", "|   Location Name: GIBSONDB", "|_  Security: RACF external authentication", "", "Nmap done: 1 IP address (1 host up) scanned in 0.02 seconds"])
    if "-a" in scripts or ("-sv" in scripts and ("21,23,443,50000" in scripts or "21,2023,443,50000" in scripts)):
        return "\n".join([f"Starting Nmap 7.98 ( https://nmap.org ) at {now}", "Nmap scan report for mainframe (127.0.0.1)", "Host is up (0.0029s latency).", "", "PORT      STATE SERVICE VERSION", "21/tcp    open  ftp     IBM OS/390 ftpd V2R5", "2023/tcp  open  tn3270  IBM Telnet TN3270 (Gibson dual-mode)", "80/tcp    open  http    Gibson Welcome/CTI", "8080/tcp  open  http    Apache Tomcat Manager (Gibson)", "9080/tcp  open  http    FIBS Security Academy", "50000/tcp open  drda    IBM DB2 Database Server (QDB2)", "", "Nmap done: 1 IP address (1 host up) scanned in 0.04 seconds"])
    return None

def _normalise_port_aliases(args: list[str]) -> tuple[list[str], list[str]]:
    out: list[str] = []
    notes: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args):
            val = args[i + 1]
            if val in {"23", "3270"}:
                notes.append(f"Gibson compatibility: requested {val}, mapped to 2023")
                val = "2023"
            out.extend([a, val]); i += 2; continue
        if a in {"--port"} and i + 1 < len(args):
            val = args[i + 1]
            if val in {"23", "3270"}:
                notes.append(f"Gibson compatibility: requested {val}, mapped to 2023")
                val = "2023"
            out.extend([a, val]); i += 2; continue
        if a.startswith("-p") and len(a) > 2 and a[2:] in {"23", "3270"}:
            notes.append(f"Gibson compatibility: requested {a[2:]}, mapped to 2023")
            out.append("-p2023"); i += 1; continue
        if a.startswith("--port=") and a.split("=", 1)[1] in {"23", "3270"}:
            notes.append(f"Gibson compatibility: requested {a.split('=',1)[1]}, mapped to 2023")
            out.append("--port=2023"); i += 1; continue
        out.append(a); i += 1
    return out, notes


def _nmap_header(target_display: str) -> str:
    return "\n".join([
        "Starting Nmap 7.98 ( https://nmap.org ) at " + dt.datetime.now().isoformat(timespec="seconds"),
        f"Nmap scan report for {target_display}",
        "Host is up (0.0010s latency).",
    ])


def _normalise_nmap_text(text: str, target_display: str, notes: list[str]) -> str:
    lines = text.splitlines()
    # Drop nmap-sim banner and any explicit fallback transport mode in normal output.
    filtered: list[str] = []
    for line in lines:
        if line.startswith("Transport mode:"):
            continue
        if line.startswith("Starting nmap-sim"):
            continue
        if line.startswith("Nmap-sim done"):
            continue
        filtered.append(line)
    body = "\n".join(filtered).strip("\n")
    trailer = f"Nmap done: 1 IP address (1 host up) scanned in 0.01 seconds"
    note_text = "\n".join("|_ " + n for n in notes)
    parts = [_nmap_header(target_display)]
    if note_text:
        parts.append(note_text)
    if body:
        parts.append(body)
    parts.append(trailer)
    return "\n\n".join(parts)


def _nmap_script(args: list[str]) -> str:
    joined = " ".join(args)
    m = None
    for i, a in enumerate(args):
        if a == "--script" and i + 1 < len(args):
            m = args[i + 1]; break
        if a.startswith("--script="):
            m = a.split("=", 1)[1]; break
    if not m:
        if "tso-brute" in joined: return "tso-brute"
        if "tso-enum" in joined: return "tso-enum"
        if "cics" in joined: return "cics-enum"
        if "ftp-anon" in joined: return "ftp-anon"
        if "db2" in joined or "drda" in joined: return "db2-das-info"
        return "SCAN"
    return str(m).split(",")[0]

def _nmap_finalize(env, args: list[str], target: str, port: int, text: str, result: str = "OK") -> str:
    script = _nmap_script(args)
    import re as _re
    m = _re.search(r'(?:Correlation ID:|CORRID=)\s*([A-Z0-9_.:-]+)', text or '', _re.I)
    existing_corr = m.group(1).strip().upper() if m else None
    corr = emit_omvs_tool_event(env, tool="NMAP", script=script.upper(), target=target, target_port=port, result=result,
                                severity="WARN" if any(x in script.lower() for x in ["brute", "cicspwn"]) else "INFO",
                                details={"args":" ".join(args), "script":script, "target":target, "port":port}, correlation_id=existing_corr, command_line="nmap " + " ".join(args))
    if "Correlation ID:" not in text and "CORRID=" not in text:
        text = text.rstrip() + format_corr_line(corr)
    elif "Forensic event written" not in text:
        text = text.rstrip() + "\nForensic event written to SMF80, OPERLOG, audit.log and dashboard activity."
    return text

def run_omvs_nmap(argv: Iterable[str], env, cwd: str) -> str:
    args = list(argv)
    args, port_notes = _normalise_port_aliases(args)
    if not args:
        args = ["127.0.0.1"]
    if "-M" in args or "--menu" in args:
        from gibson.tools.nmap_menu_engine import NmapMenuState, render_menu, run_action
        idx = args.index("-M") if "-M" in args else args.index("--menu")
        rest = args[:idx] + args[idx + 1:]
        if not rest:
            return render_menu()
        selection = rest[0]
        extra = rest[1:]
        # Convert virtual OMVS output paths before invoking export actions.
        if selection == "9":
            try:
                extra = _rewrite_paths(extra, env, cwd)
            except ValueError as exc:
                return f"nmap: {exc}"
        return run_action(selection, extra, state=NmapMenuState())
    if "--help" in args or "-h" in args or "help" in args:
        mod = importlib.import_module("gibson.tools.omvs_nmap_sim")
        try:
            return mod.build_parser().format_help().rstrip()
        except Exception:
            return "nmap [options] 127.0.0.1|mainframe - Gibson NSE training simulator"
    if "--version" in args:
        mod = importlib.import_module("gibson.tools.omvs_nmap_sim")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try: mod.main(["--version"])
            except SystemExit as exc:
                if exc.code not in (0, None): return buf.getvalue().strip() or f"nmap exited {exc.code}"
        return buf.getvalue().strip()
    targets = _target_operands(args)
    if len(targets) > 1:
        return "nmap: multiple targets are not permitted in Gibson training mode\nAllowed targets: 127.0.0.1, mainframe"
    target = targets[0] if targets else "127.0.0.1"
    if _reject_target(target, env, cwd):
        return "nmap: target denied - not permitted in Gibson training mode\nAllowed targets: 127.0.0.1, localhost, mainframe, or configured local aliases"
    all_scan = _all_open_scan(args, env)
    if all_scan is not None:
        return _nmap_finalize(env, args, target, _extract_port(args), all_scan)
    tomcat_scan = _tomcat_scan(args, env)
    if tomcat_scan is not None:
        return _nmap_finalize(env, args, target, _extract_port(args), tomcat_scan)
    ftp_db2_scan = _ftp_db2_scan(args, env)
    if ftp_db2_scan is not None:
        return _nmap_finalize(env, args, target, _extract_port(args), ftp_db2_scan)
    res = resolve_host(target, env, cwd)
    target_display = "mainframe (127.0.0.1)" if res.address == "127.0.0.1" else res.display
    safe_args = []
    replaced_target = False
    skip_next_host = False
    for a in args:
        if skip_next_host:
            safe_args.append(res.address); replaced_target = True; skip_next_host = False; continue
        if a in {"-H", "--host"}:
            safe_args.append(a); skip_next_host = True; continue
        if a == target:
            safe_args.append(res.address); replaced_target = True
        elif a.startswith("--host=") and a.split("=",1)[1] == target:
            safe_args.append("--host=" + res.address); replaced_target = True
        else:
            safe_args.append(a)
    if not targets:
        safe_args.append("127.0.0.1")
    try:
        safe_args = _rewrite_paths(_bounded_args(safe_args), env, cwd)
    except ValueError as exc:
        return f"nmap: {exc}"
    # In a unit-test or offline OMVS shell there may be no listener bound to
    # 2023. The supplied simulator has an explicit offline mode; use it only
    # when the target is the permitted local mainframe and the port is closed,
    # so classroom enumeration still produces useful Gibson output rather than
    # transport failures.
    port = 2023
    for i, a in enumerate(safe_args):
        if a in {"-p", "--port"} and i + 1 < len(safe_args):
            if safe_args[i + 1] in {"23", "3270"}:
                safe_args[i + 1] = "2023"
            try: port = int(safe_args[i + 1])
            except Exception: port = 2023
        elif a.startswith("--port="):
            if a.split("=", 1)[1] in {"23", "3270"}:
                safe_args[i] = "--port=2023"; a = safe_args[i]
            try: port = int(a.split("=", 1)[1])
            except Exception: port = 2023
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            pass
    except OSError:
        if "--offline" not in safe_args:
            safe_args.append("--offline")
    mod = importlib.import_module("gibson.tools.omvs_nmap_sim")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            rc = mod.main(safe_args)
        except SystemExit as exc:
            rc = exc.code or 0
    text = buf.getvalue().rstrip()
    if replaced_target:
        text = text.replace("host: 127.0.0.1", "host: " + res.display)
    normalised = _normalise_nmap_text(text, target_display, port_notes)
    return _nmap_finalize(env, args, target, port, normalised + ("" if rc == 0 else f"\n[nmap simulator exit status {rc}]"), "OK" if rc == 0 else "ERROR")
