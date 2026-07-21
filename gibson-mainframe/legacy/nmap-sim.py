#!/usr/bin/env python3
"""Training-safe Nmap/CICSPWN/TSO simulation helper for Gibson.

This tool is separate from Gibson. It probes a running Gibson instance and
prints staged, realistic-enough training output for tso-enum, tso-brute, and
CICSPWN-style CICS discovery. It does not exploit a host or execute arbitrary
code. The CICSPWN mode branches on the target responses and classifies findings
as available, denied, disabled, unavailable, inferred, or confirmed.
"""
from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import os
import select
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

BLUE="\033[34m"; GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; CYAN="\033[36m"; RESET="\033[0m"

log_file: Optional[Path] = None
spinning = False

@dataclasses.dataclass
class Finding:
    stage: str
    name: str
    state: str
    detail: str = ""
    evidence: str = ""


def colour(text: str, level: str = "info") -> str:
    if level == "success": return GREEN + text + RESET
    if level == "error": return RED + text + RESET
    if level == "warn": return YELLOW + text + RESET
    if level == "stage": return CYAN + text + RESET
    return BLUE + text + RESET


def log(msg: str) -> None:
    global log_file
    if log_file is None:
        Path("logs").mkdir(exist_ok=True)
        log_file = Path("logs") / f"nmap-sim-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {strip_ansi(msg)}\n")


def strip_ansi(text: str) -> str:
    for token in (BLUE, GREEN, RED, YELLOW, CYAN, RESET):
        text = text.replace(token, "")
    return text


def emit(msg: str, level: str = "info") -> None:
    text = colour(msg, level)
    print(text)
    log(msg)


def _recv_available(sock: socket.socket, deadline: float, max_bytes: int, marker_u: str | None = None) -> str:
    chunks: list[bytes] = []
    total = 0
    previous_timeout = sock.gettimeout()
    try:
        sock.setblocking(False)
        while total < max_bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(0.2, remaining))
            if not readable:
                if marker_u is None:
                    break
                continue
            try:
                data = sock.recv(min(4096, max_bytes - total))
            except BlockingIOError:
                continue
            if not data:
                break
            chunks.append(data)
            total += len(data)
            if marker_u is not None and marker_u in b"".join(chunks).decode("ascii", "ignore").upper():
                break
    finally:
        sock.setblocking(True)
        sock.settimeout(previous_timeout)
    return b"".join(chunks).decode("ascii", "ignore")


def recv_some(sock: socket.socket, timeout: float = 1.0, max_bytes: int = 65535) -> str:
    """Receive currently available ASCII text with a hard wall-clock bound."""

    return _recv_available(sock, time.monotonic() + max(0.0, timeout), max_bytes)


def recv_until(sock: socket.socket, marker: str, timeout: float = 10.0) -> str:
    """Receive until marker is seen or the hard wall-clock deadline expires."""

    marker_u = marker.upper()
    deadline = time.monotonic() + max(0.0, timeout)
    chunks: list[str] = []
    previous_timeout = sock.gettimeout()
    try:
        sock.setblocking(False)
        while time.monotonic() < deadline and marker_u not in "".join(chunks).upper():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(0.2, remaining))
            if not readable:
                continue
            try:
                data = sock.recv(1024)
            except BlockingIOError:
                continue
            if not data:
                break
            chunks.append(data.decode("ascii", "ignore"))
    finally:
        sock.setblocking(True)
        sock.settimeout(previous_timeout)
    return "".join(chunks)


def recv_tso_login_response(sock: socket.socket, timeout: float = 3.0) -> str:
    """Receive a TSO userid/password response with rejection-aware stopping.

    A non-existent userid does not produce the password marker; it produces an
    IKJ/authorization rejection and may return to the userid prompt.  Waiting
    only for PASSWORD made enumeration/brute modes spend the full socket wait,
    or longer against chatty line-mode echoes.  Stop as soon as a positive or
    negative TSO authentication marker is visible.
    """

    terminal_markers = (
        "PASSWORD",
        "IKJ56420I",
        "NOT AUTHORIZED",
        "NOTAUTH",
        "INVALID",
        "ENTER USERID",
        "LOGON TYPE",
    )
    deadline = time.monotonic() + max(0.0, timeout)
    chunks: list[str] = []
    previous_timeout = sock.gettimeout()
    try:
        sock.setblocking(False)
        while time.monotonic() < deadline:
            text_u = "".join(chunks).upper()
            if any(marker in text_u for marker in terminal_markers):
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(0.2, remaining))
            if not readable:
                continue
            try:
                data = sock.recv(1024)
            except BlockingIOError:
                continue
            if not data:
                break
            chunks.append(data.decode("ascii", "ignore"))
    finally:
        sock.setblocking(True)
        sock.settimeout(previous_timeout)
    return "".join(chunks)


def recv_tso_password_result(sock: socket.socket, timeout: float = 3.0) -> str:
    """Receive the post-password TSO result and stop on known outcomes."""

    terminal_markers = (
        "READY",
        "LOGON COMPLETE",
        "LAST ACCESS",
        "PASSWORD INCORRECT",
        "NOT AUTHORIZED",
        "NOTAUTH",
        "INVALID",
        "IKJ56420I",
        "ENTER USERID",
    )
    deadline = time.monotonic() + max(0.0, timeout)
    chunks: list[str] = []
    previous_timeout = sock.gettimeout()
    try:
        sock.setblocking(False)
        while time.monotonic() < deadline:
            text_u = "".join(chunks).upper()
            if any(marker in text_u for marker in terminal_markers):
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(0.2, remaining))
            if not readable:
                continue
            try:
                data = sock.recv(2048)
            except BlockingIOError:
                continue
            if not data:
                break
            chunks.append(data.decode("ascii", "ignore"))
    finally:
        sock.setblocking(True)
        sock.settimeout(previous_timeout)
    return "".join(chunks)


def sendline(sock: socket.socket, text: str) -> str:
    sock.sendall((text + "\r\n").encode("ascii", "ignore"))
    return recv_some(sock, timeout=1.2)


def recv_cics_response(sock: socket.socket, timeout: float = 3.0, max_bytes: int = 8192) -> str:
    """Receive a CICS command response, stopping at the next command prompt."""

    deadline = time.monotonic() + max(0.0, timeout)
    chunks: list[str] = []
    total = 0
    previous_timeout = sock.gettimeout()
    try:
        sock.setblocking(False)
        while time.monotonic() < deadline and total < max_bytes:
            text = "".join(chunks)
            text_u = text.upper()
            if "===>" in text or "COMMAND NOT RECOGNIZED" in text_u or "DFHCE" in text_u or "CICSPWN" in text_u or "PF 1 HELP" in text_u:
                if chunks:
                    break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(0.2, remaining))
            if not readable:
                continue
            try:
                data = sock.recv(min(2048, max_bytes - total))
            except BlockingIOError:
                continue
            if not data:
                break
            total += len(data)
            chunks.append(data.decode("ascii", "ignore"))
    finally:
        sock.setblocking(True)
        sock.settimeout(previous_timeout)
    return "".join(chunks)


def send_cics(sock: socket.socket, text: str) -> str:
    sock.sendall((text + "\r\n").encode("ascii", "ignore"))
    return recv_cics_response(sock, timeout=3.0)


def connect(host: str, port: int) -> socket.socket:
    return socket.create_connection((host, int(port)), timeout=15)


def spinner():
    for c in itertools.cycle("|/-\\"):
        if not spinning: break
        print(f"\rScanning... {c}", end="", flush=True)
        time.sleep(0.1)
    print("\r", end="", flush=True)


def classify_transaction(name: str, output: str) -> Finding:
    u = output.upper()
    if "NOT AUTHORIZED" in u or "NOTAUTH" in u or "DENIED" in u:
        return Finding("transaction", name, "denied", "protected by transaction security", short(output))
    if "DISABLED" in u:
        return Finding("transaction", name, "disabled", "defined but disabled", short(output))
    if "NOT DEFINED" in u or "NOT FOUND" in u or "COMMAND NOT RECOGNIZED" in u:
        return Finding("transaction", name, "unavailable", "transaction not usable", short(output))
    if name in u or any(tok in u for tok in ("INQUIRE", "DISPLAY", "COMMAND LEVEL", "TEMPORARY STORAGE", "SIGN")):
        return Finding("transaction", name, "available", "transaction responded", short(output))
    return Finding("transaction", name, "inferred", "ambiguous response", short(output))


def short(text: str, n: int = 140) -> str:
    return " ".join(text.replace("\x1b[2J", " ").replace("\x1b[H", " ").split())[:n]


def display_welcome_screen(args) -> None:
    try:
        with connect(args.host, args.port) as s:
            ws = recv_until(s, "Logon Type:", timeout=10)
            emit("[+] Welcome screen captured", "success")
            print(ws)
    except Exception as e:
        emit(f"[-] Error reading screen: {e}", "error")


def probe_user_exists(args, username: str) -> Finding:
    user = username.strip().upper()
    try:
        with connect(args.host, args.port) as s:
            recv_until(s, "Logon Type:", timeout=10)
            prompt = sendline(s, "L TSO")
            if "ENTER USERID" not in prompt.upper():
                prompt += recv_until(s, "ENTER USERID", timeout=5)
            if "ENTER USERID" not in prompt.upper():
                return Finding("tso-enum", user, "unavailable", "TSO userid prompt not reached", short(prompt))
            s.sendall((user + "\r\n").encode())
            resp = recv_tso_login_response(s, timeout=3)
            resp_u = resp.upper()
            if "PASSWORD" in resp_u:
                return Finding("tso-enum", user, "confirmed", "userid exists; password prompt reached", short(resp))
            if any(tok in resp_u for tok in ("IKJ56420I", "NOT AUTHORIZED", "NOTAUTH", "INVALID", "ENTER USERID")):
                return Finding("tso-enum", user, "unavailable", "userid rejected", short(resp))
            return Finding("tso-enum", user, "inferred", "ambiguous prompt behaviour", short(resp))
    except Exception as e:
        return Finding("tso-enum", user, "unavailable", str(e))


def enumerate_users(args) -> None:
    if not args.userfile:
        emit("[-] User file required for enumeration (--userfile <file>)", "error"); return
    global spinning
    if not args.no_spinner:
        spinning = True; th = threading.Thread(target=spinner, daemon=True); th.start()
    else:
        th = None
    findings = []
    for line in Path(args.userfile).read_text(encoding="utf-8", errors="ignore").splitlines():
        user = line.strip()
        if not user: continue
        f = probe_user_exists(args, user)
        findings.append(f)
        level = "success" if f.state == "confirmed" else ("warn" if f.state == "inferred" else "error")
        emit(f"[{f.state.upper():11}] {f.name:<8} {f.detail}", level)
    spinning = False
    if th: th.join(timeout=1)
    if args.json:
        print(json.dumps([dataclasses.asdict(x) for x in findings], indent=2))


def attempt_tso_login(args, username: str, password: str) -> Finding:
    user = username.strip().upper()
    try:
        with connect(args.host, args.port) as s:
            recv_until(s, "Logon Type:", 10)
            prompt = sendline(s, "L TSO")
            if "ENTER USERID" not in prompt.upper():
                prompt += recv_until(s, "ENTER USERID", 5)
            if "ENTER USERID" not in prompt.upper():
                return Finding("tso-brute", user, "unavailable", "TSO userid prompt not reached", short(prompt))
            s.sendall((user + "\r\n").encode())
            resp = recv_tso_login_response(s, timeout=4)
            if "PASSWORD" not in resp.upper():
                return Finding("tso-brute", user, "unavailable", "no password prompt", short(resp))
            s.sendall((password + "\r\n").encode())
            out = recv_tso_password_result(s, timeout=3.0)
            u = out.upper()
            if "READY" in u or "LOGON COMPLETE" in u or "LAST ACCESS" in u:
                return Finding("tso-brute", user, "confirmed", "valid credentials", "password accepted")
            if "PASSWORD INCORRECT" in u or "NOT AUTHORIZED" in u or "INVALID" in u:
                return Finding("tso-brute", user, "denied", "password rejected", short(out))
            return Finding("tso-brute", user, "inferred", "ambiguous login result", short(out))
    except Exception as e:
        return Finding("tso-brute", user, "unavailable", str(e))


def run_tso_brute(args) -> None:
    if not args.userfile:
        emit("[-] --userfile is required for --tso-brute", "error"); return
    passwords = []
    if args.passfile and Path(args.passfile).exists():
        passwords = [x.strip() for x in Path(args.passfile).read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
    elif args.password:
        passwords = [args.password]
    else:
        emit("[-] Provide --passfile or --password for --tso-brute", "error"); return
    users = [x.strip() for x in Path(args.userfile).read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
    findings = []
    for user in users:
        for pw in passwords:
            f = attempt_tso_login(args, user, pw)
            findings.append(f)
            masked = "*" * len(pw)
            level = "success" if f.state == "confirmed" else ("warn" if f.state == "inferred" else "error")
            emit(f"[{f.state.upper():11}] {user:<8} password={masked:<12} {f.detail}", level)
            if f.state == "confirmed" and args.stop_on_success:
                break
    if args.json:
        print(json.dumps([dataclasses.asdict(x) for x in findings], indent=2))


def enter_cics(args) -> socket.socket:
    s = connect(args.host, args.port)
    intro = recv_until(s, "Logon Type:", timeout=8)
    if "LOGON TYPE" in intro.upper():
        sendline(s, "L CICS")
    # CICS screen often waits for an empty ENTER before command prompt.
    recv_some(s, timeout=1.0)
    send_cics(s, "")
    return s


def run_cicspwn(args) -> None:
    emit("[*] CICSPWN simulation starting - staged discovery only", "stage")
    findings: list[Finding] = []
    try:
        with enter_cics(args) as s:
            # Optional sign-on: Gibson's basic CESN trusts the selected user in lab mode.
            emit("[*] Stage 1: CICS entry and sign-on discovery", "stage")
            out = send_cics(s, "CESN")
            f = classify_transaction("CESN", out); findings.append(f); emit_finding(f)

            emit("[*] Stage 2: supplied transaction capability assessment", "stage")
            for tx, cmd in [("CEMT", "CEMT I SYSTEM"), ("CEDA", "CEDA DISPLAY TRANSACTION"), ("CECI", "CECI ASSIGN"), ("CEBR", "CEBR")]:
                out = send_cics(s, cmd)
                f = classify_transaction(tx, out); findings.append(f); emit_finding(f)

            emit("[*] Stage 3: resource enumeration", "stage")
            for name, cmd in [("FILES", "CEMT I FILE"), ("PROGRAMS", "CEMT I PROG"), ("TRANSACTIONS", "CEMT I TRAN"), ("TSQ", "CEMT I TSQUEUE")]:
                out = send_cics(s, cmd)
                state = "confirmed" if any(tok in out.upper() for tok in ("FILE(", "PROG(", "TRA(", "TSQ(")) else "inferred"
                f = Finding("enumeration", name, state, f"command={cmd}", short(out)); findings.append(f); emit_finding(f)
            for skipped_name, detail in [("TDQ", "TDQ omitted from fast live scan after TSQ to avoid terminal-state collisions"), ("TASKS", "task listing omitted from fast live scan; use CICS/SDSF panels for task drill-down")]:
                f = Finding("enumeration", skipped_name, "inferred", detail, "")
                findings.append(f); emit_finding(f)

            emit("[*] Stage 4: bounded CICSPWN probe", "stage")
            # Use a fresh command-level CICS session for the exploit-style stages.
            # Some 3270-style resource panels leave terminal state that is useful
            # for realism but inconvenient for a scanner transcript.  Re-entering
            # CICS mirrors a cautious tool reconnect and keeps the fast scan bounded.
            with enter_cics(args) as probe_s:
                out = send_cics(probe_s, "CICSPWN PROBE")
                if "CORRID=" in out.upper():
                    corr = ""
                    for part in out.replace("\n", " ").split():
                        if part.upper().startswith("CORRID="):
                            corr = part.split("=",1)[1]
                            break
                    f = Finding("cicspwn", "PWNPROBE", "confirmed", "target returned structured staged probe output", corr or short(out),)
                elif "NOT AUTHORIZED" in out.upper():
                    f = Finding("cicspwn", "PWNPROBE", "denied", "probe blocked by security", short(out))
                else:
                    f = Finding("cicspwn", "PWNPROBE", "inferred", "probe not directly supported; using discovered transactions only", short(out))
                findings.append(f); emit_finding(f)

                emit("[*] Stage 5: safe abuse-path simulation", "stage")
                if any(x.name in {"CECI", "CEDA", "CEMT"} and x.state in {"available", "confirmed"} for x in findings):
                    out = send_cics(probe_s, "CECI WRITEQ TSQUEUE(PWNLOG) FROM('GIBSON CICSPWN TRAINING EVENT')")
                    state = "confirmed" if "NORMAL" in out.upper() or "COMPLETED" in out.upper() else "inferred"
                    f = Finding("simulation", "WRITEQ", state, "safe queue-write simulation; no host code execution", short(out))
                else:
                    f = Finding("simulation", "WRITEQ", "denied", "no usable administrative transaction found")
                findings.append(f); emit_finding(f)
    except Exception as e:
        emit(f"[-] CICSPWN simulation failed: {e}", "error")
        findings.append(Finding("error", "cicspwn", "unavailable", str(e)))
    emit("[*] Evidence hint: review Gibson SDSF SMF80 and OPERLOG for CICS/CICSPWN correlation records.", "stage")
    if args.json:
        print(json.dumps([dataclasses.asdict(x) for x in findings], indent=2))
    if args.listen_shell:
        start_shell_listener(args.shell_port)


def emit_finding(f: Finding) -> None:
    level = "success" if f.state in {"available", "confirmed"} else ("warn" if f.state in {"inferred", "disabled"} else "error")
    emit(f"[{f.state.upper():11}] {f.stage:<14} {f.name:<12} {f.detail} {('evidence=' + f.evidence) if f.evidence else ''}", level)


def start_shell_listener(port: int) -> None:
    emit(f"[+] Optional restricted training listener on port {port}; use only inside the lab", "warn")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", int(port)))
    listener.listen(1)
    conn, addr = listener.accept()
    emit(f"[+] Connection received from {addr}; bounded shell transcript only", "success")
    conn.sendall(b"/u/ibmuser $ ")
    try:
        while True:
            data = conn.recv(1024)
            if not data: break
            cmd = data.decode("ascii", "ignore").strip().lower()
            table = {"whoami": "IBMUSER\n", "uname": "z/OS v3.1 (Gibson simulated)\n", "tsocmd rvary": "SYS1.RACF.DS Primary\n", "ps": "  PID   TCB   STATE   CPU\n 0001   IPA0  ACTIVE  0.1\n"}
            conn.sendall(table.get(cmd, "Command not available in restricted training shell.\n").encode())
            conn.sendall(b"/u/ibmuser $ ")
    finally:
        conn.close(); listener.close()


def cli_params(args, require_userfile=False) -> bool:
    args.host = input("Host: ").strip()
    try:
        args.port = int(input("Port: ").strip())
    except Exception:
        emit("[-] Invalid port", "error"); return False
    if require_userfile:
        args.userfile = input("User file path: ").strip()
    return True


def interactive_menu(args) -> None:
    while True:
        print("\n1) View VTAM Screen\n2) Enumerate Users\n3) Run CICSPWN\n4) Run TSO Brute Force\nX) Exit")
        c = input("Choice: ").strip().upper()
        if c == "X": break
        if c == "1" and cli_params(args): display_welcome_screen(args)
        elif c == "2" and cli_params(args, True): enumerate_users(args)
        elif c == "3" and cli_params(args): run_cicspwn(args)
        elif c == "4" and cli_params(args, True): run_tso_brute(args)
        else: emit("Invalid selection", "error")


def parse_args(argv: Optional[Iterable[str]] = None):
    p = argparse.ArgumentParser(description="Gibson-safe Telnet, TSO, and CICSPWN training simulator")
    p.add_argument("-H", "--host", help="Target host/IP")
    p.add_argument("-p", "--port", type=int, help="Target port")
    p.add_argument("-u", "--userfile", help="Username file")
    p.add_argument("-P", "--passfile", help="Password file for --tso-brute")
    p.add_argument("--password", help="Single password for --tso-brute")
    p.add_argument("-s", "--screen", action="store_true", help="Display initial VTAM welcome screen")
    p.add_argument("-M", "--menu", action="store_true", help="Interactive menu")
    p.add_argument("--cicspwn", action="store_true", help="Run staged CICSPWN-style simulation")
    p.add_argument("--tso-brute", action="store_true", help="Run bounded TSO brute-force training loop")
    p.add_argument("--script", help="Script name such as tso-enum")
    p.add_argument("--shell-port", type=int, default=4444, help="Optional restricted listener port")
    p.add_argument("--listen-shell", action="store_true", help="Open the optional restricted shell listener after CICSPWN")
    p.add_argument("--json", action="store_true", help="Emit JSON result objects after human-readable output")
    p.add_argument("--stop-on-success", action="store_true", help="Stop trying passwords for a user after first success")
    p.add_argument("--no-spinner", action="store_true", help="Disable spinner")
    return p.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.menu:
        interactive_menu(args); return 0
    if args.script == "tso-enum" and args.host and args.port and args.userfile:
        enumerate_users(args); return 0
    if args.cicspwn and args.host and args.port:
        run_cicspwn(args); return 0
    if args.screen and args.host and args.port:
        display_welcome_screen(args); return 0
    if args.tso_brute and args.host and args.port:
        run_tso_brute(args); return 0
    parse_args(["--help"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
