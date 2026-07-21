from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gibson.core.state import GibsonState
from gibson.render import colors
from gibson.render.input import SocketInputDriver
from gibson.apps.omvs import OmvsEnvironment


@dataclass
class FtpSessionState:
    host: str
    port: int
    remote_user: str = ""
    authed: bool = False
    remote_prefix: str = ""
    local_prefix: str = ""
    transfer_type: str = "ASCII"
    filetype: str = "FILE"


# Sentinel returned by handle_command() to signal the session should end.
_FTP_QUIT = object()


class TsoFtpClientApp:
    """TSO-style simulated FTP client.

    This is intentionally a training-safe client surface that mirrors the z/OS
    FTP command/subcommand workflow without attempting to emulate every wire
    detail. It supports common subcommands used in classrooms: USER, ASCII,
    BINARY/IMAGE, PWD, CD, LCD, LS, DIR, GET, PUT, SITE FILETYPE, STATUS, and
    QUIT/BYE.
    """

    def __init__(self, state: GibsonState, userid: str, host: str = "127.0.0.1", port: int | None = None):
        self.state = state
        self.userid = userid.upper()
        self.env = OmvsEnvironment(state)
        self.s = FtpSessionState(host=host or "127.0.0.1", port=int(port or state.config.ftp_port), local_prefix=self.userid, remote_prefix=self.userid)

    def _norm_remote(self, operand: str) -> str:
        raw = (operand or "").strip().strip("'").strip('"')
        if not raw:
            return self.s.remote_prefix
        if raw.startswith("/"):
            return raw
        value = raw.upper()
        if value.startswith(self.s.remote_user + ".") or value.startswith(("SYS1.", "TCPIP.", "CEE.")):
            return value
        return f"{self.s.remote_prefix}.{value}" if self.s.remote_prefix else value

    def _norm_local(self, operand: str) -> str:
        raw = (operand or "").strip().strip("'").strip('"')
        if not raw:
            return self.userid
        if raw.startswith("/"):
            return raw
        value = raw.upper()
        if value.startswith(self.userid + ".") or "." in value and value.split(".", 1)[0] in self.state.racf.users:
            return value
        return f"{self.userid}.{value}" if self.userid else value

    def _read_target(self, owner: str, target: str) -> str:
        if target.startswith("/"):
            vp = self.env.resolve(f"/u/{owner.lower()}", target)
            return self.env.read_text(vp)
        return self.state.datasets.read(owner, target)

    def _write_target(self, owner: str, target: str, text: str) -> None:
        if target.startswith("/"):
            vp = self.env.resolve(f"/u/{owner.lower()}", target)
            self.env.write_text(vp, text)
            return
        self.state.datasets.write(owner, target, text)

    def _list_remote(self, prefix: str) -> str:
        if prefix.startswith("/"):
            vp = self.env.resolve(f"/u/{self.s.remote_user.lower()}", prefix)
            real = self.env.real_path(vp)
            if not real.exists():
                return "EZA1701I REMOTE PATH NOT FOUND"
            if real.is_dir():
                return "\n".join(sorted(p.name for p in real.iterdir())) or "EZA1698I NO FILES FOUND"
            return real.name
        rows = self.state.datasets.listcat(self.s.remote_user, prefix=prefix)
        return "\n".join(r.name for r in rows) if rows else "EZA1698I NO FILES FOUND"

    def _banner(self) -> str:
        return (
            f"{colors.CLEAR}{colors.BLUE}EZA1450I IBM FTP CS V2R5\n"
            f"EZA1466I Connecting to {self.s.host},{self.s.port} ...\n"
            f"220 GIBSONFTP READY{colors.RESET}\n"
        )

    def _status(self) -> str:
        return "\n".join([
            f"Connected to {self.s.host}.",
            f"Mode: {self.s.transfer_type}  FILETYPE={self.s.filetype}",
            f"Remote prefix: {self.s.remote_prefix}",
            f"Local prefix: {self.s.local_prefix}",
            f"Logged in as: {self.s.remote_user}",
        ])

    def run(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        send(self._banner())
        user = driver.read_line(f"User ({self.s.host}:(none)): ").text.strip().upper() or self.userid
        pw = driver.read_line("Password: ", hidden=True, mask=True).text.strip()
        self.state.racf.load(merge=True)
        if not self.state.racf.verify_password(user, pw):
            self.state.note_failed_logon(user, "127.0.0.1", port=self.state.config.ftp_port, service="FTP-CLIENT")
            send(colors.RED + "530 Login incorrect.\n" + colors.RESET)
            return
        self.s.remote_user = user
        self.s.remote_prefix = user
        self.s.authed = True
        send(colors.GREEN + f"230 {user} logged in.\n" + colors.RESET)
        while True:
            res = driver.read_line("ftp> ")
            if res.key == "EOF":
                return
            resp = self.handle_command(res.text)
            if resp is _FTP_QUIT:
                send("221 Quit\n")
                return
            if resp:
                send(resp + "\n")

    def handle_command(self, raw: str):
        """Process one ftp> command line and return the response text to show,
        or _FTP_QUIT to end the session.  Single source of truth shared by the
        ASCII loop (run) and the TN3270 FTP sub-mode, so the two paths can't
        drift apart."""
        raw = (raw or "").strip()
        if not raw:
            return ""
        parts = raw.split()
        op = parts[0].upper()
        args = parts[1:]
        try:
            if op in {"QUIT", "BYE", "EXIT"}:
                return _FTP_QUIT
            if op == "HELP":
                return "OPEN USER ASCII BINARY IMAGE PWD CD LCD LS DIR GET PUT SITE STATUS QUIT BYE"
            if op == "OPEN":
                self.s.host = args[0] if args else self.s.host
                if len(args) >= 2 and args[1].isdigit():
                    self.s.port = int(args[1])
                return f"EZA1466I Connecting to {self.s.host},{self.s.port} ...\n220 GIBSONFTP READY"
            if op == "USER":
                if len(args) < 2:
                    return "EZA1618I USER requires userid password"
                user, pw = args[0].upper(), args[1]
                self.state.racf.load(merge=True)
                if not self.state.racf.verify_password(user, pw):
                    return "530 Login incorrect."
                self.s.remote_user = user
                self.s.remote_prefix = user
                self.s.authed = True
                return f"230 {user} logged in."
            if op in {"ASCII"}:
                self.s.transfer_type = "ASCII"
                return "200 Representation type is Ascii NonPrint"
            if op in {"BINARY", "IMAGE"}:
                self.s.transfer_type = "IMAGE"
                return "200 Representation type is Image"
            if op == "SITE":
                arg = " ".join(args).upper()
                if arg.startswith("FILETYPE="):
                    self.s.filetype = arg.split("=", 1)[1]
                    return f"200 FILETYPE set to {self.s.filetype}"
                return "504 Unknown SITE option"
            if op == "PWD":
                return f'257 "{self.s.remote_prefix}" is the current remote prefix'
            if op == "CD":
                if not args:
                    return "EZA1701I CD requires a remote dataset prefix or USS path"
                self.s.remote_prefix = self._norm_remote(args[0])
                return f'250 Remote prefix changed to "{self.s.remote_prefix}"'
            if op == "LCD":
                if not args:
                    return "EZA1702I LCD requires a local dataset prefix or USS path"
                self.s.local_prefix = self._norm_local(args[0])
                return f'250 Local prefix changed to "{self.s.local_prefix}"'
            if op in {"LS", "DIR"}:
                prefix = self._norm_remote(args[0]) if args else self.s.remote_prefix
                return self._list_remote(prefix)
            if op == "GET":
                if not args:
                    return "EZA1735I GET requires a remote name"
                remote = self._norm_remote(args[0])
                local = self._norm_local(args[1]) if len(args) >= 2 else self._norm_local(args[0])
                text = self._read_target(self.s.remote_user, remote)
                self._write_target(self.userid, local, text)
                return f"250 GET successful: {remote} -> {local}"
            if op == "PUT":
                if not args:
                    return "EZA1736I PUT requires a local name"
                local = self._norm_local(args[0])
                remote = self._norm_remote(args[1]) if len(args) >= 2 else self._norm_remote(args[0])
                text = self._read_target(self.userid, local)
                self._write_target(self.s.remote_user, remote, text)
                return f"250 PUT successful: {local} -> {remote}"
            if op == "STATUS":
                return self._status()
            return "502 Command not implemented"
        except PermissionError as exc:
            return f"550 {exc}"
        except FileNotFoundError:
            return "550 File not found"
        except Exception as exc:
            return f"550 Command failed: {exc}"
