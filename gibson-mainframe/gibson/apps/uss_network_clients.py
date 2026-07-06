from __future__ import annotations

import ftplib
import socket
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_TIMEOUT = 5

@dataclass
class FtpClientState:
    host: str = ""
    port: int = 21
    connected: bool = False
    mode: str = "ASCII"
    last_status: str = "NOT CONNECTED"

@dataclass
class TelnetClientState:
    host: str = ""
    port: int = 23
    connected: bool = False
    mode: str = "LINE"
    last_status: str = "NOT CONNECTED"


def _safe_host(host: str) -> bool:
    if not host or len(host) > 255:
        return False
    return all(c.isalnum() or c in ".-_:" for c in host)

class GibsonFtpClient:
    """Timeout-safe USS FTP client facade. Real network use is explicit only."""
    HELP = """FTP - z/OS UNIX FTP client simulation
Usage: ftp [host [port]] | ftp --help
Interactive commands: open <host> [port], user <id> [password], pass <password>, pwd, lpwd,
  cd <dir>, lcd <dir>, ls [path], dir [path], get <remote> [local], put <local> [remote],
  mget <pattern>, mput <pattern>, ascii, binary, quote <cmd>, site <parm>, status, close, bye, quit, help, ?
Safety: no scanning, brute force or automatic connections are performed."""
    def __init__(self):
        self.state = FtpClientState()
        self._client: Optional[ftplib.FTP] = None

    def run_one(self, args: list[str]) -> str:
        if args and args[0] in {"-h", "--help", "?", "HELP"}:
            return self.HELP
        if not args:
            return self.status() + "\nftp> use 'ftp host' or 'open host [port]' in an interactive USS session"
        host = args[0]
        port = int(args[1]) if len(args) > 1 and args[1].isdigit() else 21
        return self.open(host, port)

    def open(self, host: str, port: int = 21) -> str:
        if not _safe_host(host):
            return "EZA1735I Invalid host name"
        self.state.host, self.state.port = host, int(port)
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, int(port), timeout=DEFAULT_TIMEOUT)
            self._client = ftp
            self.state.connected = True
            self.state.last_status = "CONNECTED"
            return f"EZA1450I IBM FTP CS V2R5\nEZA1736I Connected to {host} port {port}\n220 Gibson FTP client ready"
        except Exception as exc:
            self._client = None
            self.state.connected = False
            self.state.last_status = f"OFFLINE/SIMULATED - {type(exc).__name__}"
            return f"EZA1735I Unable to connect to {host} port {port} within timeout\nEZA1701I {type(exc).__name__}: {exc}\nEZA1702I No automatic retry or scanning performed"

    def status(self) -> str:
        return f"FTP STATUS: {self.state.last_status}\nREMOTE: {self.state.host or '-'} PORT: {self.state.port}\nTYPE: {self.state.mode}"

    def command(self, line: str) -> str:
        parts = line.strip().split()
        if not parts:
            return ""
        cmd = parts[0].lower(); args = parts[1:]
        if cmd in {"help", "?"}: return self.HELP
        if cmd == "open": return self.open(args[0], int(args[1]) if len(args)>1 and args[1].isdigit() else 21) if args else "usage: open <host> [port]"
        if cmd == "status": return self.status()
        if cmd in {"ascii", "binary"}: self.state.mode = cmd.upper(); return f"200 Representation type is {self.state.mode}"
        if cmd in {"close", "bye", "quit"}:
            try:
                if self._client: self._client.close()
            except Exception: pass
            self._client = None; self.state.connected = False; self.state.last_status = "CLOSED"
            return "221 Quit command received. Goodbye."
        if not self.state.connected:
            return f"EZA1701I Not connected. Command {cmd.upper()} not sent."
        try:
            if cmd == "pwd": return self._client.pwd() if self._client else "/"
            if cmd in {"ls", "dir"}:
                rows: list[str] = []
                self._client.retrlines("LIST " + (" ".join(args) if args else ""), rows.append)
                return "\n".join(rows)
            if cmd == "cd" and args:
                self._client.cwd(args[0]); return f"250 Directory changed to {args[0]}"
            if cmd in {"user", "pass", "quote", "site", "get", "put", "mget", "mput", "lpwd", "lcd"}:
                return f"EZA9999I {cmd.upper()} accepted by Gibson FTP client simulation; data transfer is safe/operator initiated only"
        except Exception as exc:
            return f"EZA1701I FTP command failed: {type(exc).__name__}: {exc}"
        return f"?Invalid command {cmd}"

class GibsonTelnetClient:
    HELP = """TELNET - z/OS UNIX telnet client simulation
Usage: telnet [host [port]] | telnet --help
Interactive commands: open <host> [port], send <text>, status, mode line, mode character, close, quit, help, ?
Safety: no scanning, brute force or exploit automation is performed."""
    def __init__(self):
        self.state = TelnetClientState()
        self._sock: Optional[socket.socket] = None

    def run_one(self, args: list[str]) -> str:
        if args and args[0] in {"-h", "--help", "?", "HELP"}: return self.HELP
        if not args: return self.status() + "\ntelnet> use 'telnet host [port]' or 'open host [port]' in an interactive USS session"
        return self.open(args[0], int(args[1]) if len(args)>1 and args[1].isdigit() else 23)

    def open(self, host: str, port: int = 23) -> str:
        if not _safe_host(host): return "telnet: invalid host name"
        self.state.host, self.state.port = host, int(port)
        try:
            s = socket.create_connection((host, int(port)), timeout=DEFAULT_TIMEOUT)
            s.settimeout(DEFAULT_TIMEOUT)
            self._sock = s; self.state.connected=True; self.state.last_status="CONNECTED"
            banner = ""
            try: banner = s.recv(256).decode(errors="ignore")
            except Exception: pass
            return f"Trying {host}...\nConnected to {host}.\nEscape character is '^]'." + (("\n"+banner.strip()) if banner.strip() else "")
        except Exception as exc:
            self._sock=None; self.state.connected=False; self.state.last_status=f"OFFLINE/SIMULATED - {type(exc).__name__}"
            if host in {"127.0.0.1", "localhost"}:
                return f"Trying {host}...\nGIBSON TN3270/TELNET SIMULATED BANNER\nConnection not established: {type(exc).__name__}"
            return f"telnet: unable to connect to {host} {port} within timeout\n{type(exc).__name__}: {exc}\nNo automatic retry or scanning performed"

    def status(self) -> str:
        return f"TELNET STATUS: {self.state.last_status}\nREMOTE: {self.state.host or '-'} PORT: {self.state.port}\nMODE: {self.state.mode}"

    def command(self, line: str) -> str:
        parts=line.strip().split()
        if not parts: return ""
        cmd=parts[0].lower(); args=parts[1:]
        if cmd in {"help", "?"}: return self.HELP
        if cmd == "open": return self.open(args[0], int(args[1]) if len(args)>1 and args[1].isdigit() else 23) if args else "usage: open <host> [port]"
        if cmd == "status": return self.status()
        if cmd == "mode" and args and args[0].lower() in {"line", "character"}: self.state.mode=args[0].upper(); return f"Mode is {self.state.mode}"
        if cmd in {"close", "quit", "bye"}:
            try:
                if self._sock: self._sock.close()
            except Exception: pass
            self._sock=None; self.state.connected=False; self.state.last_status="CLOSED"; return "Connection closed."
        if cmd == "send":
            if not self.state.connected or not self._sock: return "telnet: send requires an open connection"
            try:
                data=(" ".join(args)+"\r\n").encode(); self._sock.sendall(data)
                try: return self._sock.recv(2048).decode(errors="ignore") or "sent"
                except Exception: return "sent"
            except Exception as exc: return f"telnet: send failed: {type(exc).__name__}: {exc}"
        return f"?Invalid command {cmd}"
