from __future__ import annotations

import datetime as _dt
import ftplib
import os
import shlex
import socketserver
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from gibson.core.state import GibsonState

from gibson.core.issues import is_expected_disconnect


class TrainingShellHandler(socketserver.StreamRequestHandler):
    state: GibsonState
    userid: str
    tso_runner_factory: Callable[[str], Callable[[str], str]]
    ttl: int = 300
    shell_id: str = ""

    def _send(self, msg: str = "") -> None:
        try:
            self.wfile.write((msg + "\n").encode("utf-8", errors="ignore"))
            self.wfile.flush()
        except Exception:
            pass

    def _dataset_arg(self, text: str) -> str:
        value = (text or "").strip().strip("\"").strip("'")
        if not value:
            return ""
        if "." in value or value.startswith("SYS1"):
            return value.upper()
        return f"{self.userid}.{value.upper()}"

    def _sysinfo(self) -> str:
        cfg = self.state.config
        return (
            "Computer    : LPAR GIBSON\n"
            "Sysplex     : GIBPLEX\n"
            "OS          : z/OS 03.01 (simulated)\n"
            "Job Entry   : JES2 (Node: MVSC)\n"
            "Security    : RACF\n"
            f"Shell User  : {self.userid}\n"
            f"FTP Service : {cfg.host}:{cfg.ftp_port}"
        )

    def _ipconfig(self) -> str:
        return self.tso("NETSTAT HOME")

    def _ls(self, arg: str) -> str:
        target = arg.strip() or self.userid
        return self.tso(f"LISTCAT LEVEL({target.upper()})")

    def _cat(self, arg: str) -> str:
        ds = self._dataset_arg(arg)
        if not ds:
            return "usage: cat <dataset-or-member>"
        try:
            return self.state.datasets.read(self.userid, ds)
        except Exception as exc:
            return f"cat error: {exc}"

    def _lsmem(self, arg: str) -> str:
        ds = self._dataset_arg(arg)
        if not ds:
            return "usage: lsmem <pds>"
        try:
            text = self.state.datasets.read(self.userid, ds)
        except Exception as exc:
            return f"lsmem error: {exc}"
        lines = [name for name in text.splitlines() if name.strip()]
        if not lines:
            return f"no members found in {ds}"
        return "\n".join(f"--> {ds}({name})" for name in lines)

    def _cp(self, arg: str) -> str:
        parts = shlex.split(arg)
        if len(parts) < 2:
            return "usage: cp <from-dataset> <to-dataset>"
        src = self._dataset_arg(parts[0])
        dst = self._dataset_arg(parts[1])
        try:
            text = self.state.datasets.read(self.userid, src)
            self.state.datasets.write(self.userid, dst, text)
            return f"File {src} copied to {dst}"
        except Exception as exc:
            return f"cp error: {exc}"

    def _delete(self, arg: str) -> str:
        ds = self._dataset_arg(arg)
        if not ds:
            return "usage: delete <dataset>"
        try:
            return self.state.datasets.delete(self.userid, ds)
        except Exception as exc:
            return f"delete error: {exc}"

    def _pwd(self) -> str:
        return f"{self.userid}"

    def _ftp_upload(self, arg: str, *, racf: bool = False) -> str:
        parts = shlex.split(arg)
        if len(parts) < 4:
            return "usage: ftp[_racf] <host> <port> <user> <pass> [dataset-or-destname] [binary]"
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            return "port must be an integer"
        user = parts[2]
        passwd = parts[3]
        if racf:
            dataset = "SYS1.RACFDS"
            destname = parts[4] if len(parts) >= 5 else "SYS1.RACFDS"
        else:
            dataset = self._dataset_arg(parts[4]) if len(parts) >= 5 else ""
            destname = Path(dataset).name if dataset else "UPLOAD.DATA"
        if not dataset:
            return "usage: ftp <host> <port> <user> <pass> <dataset> [binary]"
        try:
            payload = self.state.datasets.read(self.userid, dataset).encode("utf-8", errors="ignore")
        except Exception as exc:
            return f"ftp error: cannot read {dataset}: {exc}"
        try:
            from io import BytesIO
            with ftplib.FTP() as ftp:
                ftp.connect(host, port, timeout=10)
                ftp.login(user, passwd)
                ftp.voidcmd("TYPE I")
                bio = BytesIO(payload)
                ftp.storbinary(f"STOR {destname}", bio)
            return f"Upload complete: {dataset} -> {host}:{port}/{destname}"
        except Exception as exc:
            return f"ftp error: {exc}"

    def handle(self) -> None:
        self.tso = self.tso_runner_factory(self.userid)
        self._send("Welcome to TShOcker training shell. Type 'help'.")
        self._send(f"This listener is simulated and expires automatically after {self.ttl} seconds.")
        while True:
            self._send("Enter command or 'help'> ")
            raw = self.rfile.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                parts = shlex.split(line)
            except Exception:
                parts = line.split()
            cmd = (parts[0] if parts else "").lower()
            arg = line[len(parts[0]):].strip() if parts else ""
            if cmd in {"quit", "exit"}:
                self._send("bye.")
                break
            if cmd == "help":
                self._send(
                    "Core Commands\n"
                    "=============\n"
                    "help              Help menu\n"
                    "exit              Terminate the session\n"
                    "quit              Terminate the session\n\n"
                    "Filesystem Commands\n"
                    "===================\n"
                    "cat <dataset>     Show contents of dataset/member\n"
                    "cp a b            Copy dataset/member\n"
                    "ls [hlq]          List datasets in HLQ\n"
                    "delete <ds>       Delete dataset/member\n"
                    "del <ds>          Alias for delete\n"
                    "lsmem <pds>       List PDS members\n\n"
                    "Networking Commands\n"
                    "===================\n"
                    "ipconfig          Display interfaces\n"
                    "ifconfig          Alias for ipconfig\n"
                    "ftp host port user pass ds [binary]      Upload dataset via FTP\n"
                    "ftp_racf host port user pass [destname]  Upload SYS1.RACFDS via FTP\n\n"
                    "System Commands\n"
                    "===============\n"
                    "getuid            Get current user name\n"
                    "sysinfo           Remote system info\n"
                    "racf              Show RACF database location\n"
                    "execute <cmd>     Execute TSO command\n"
                    "tso <cmd>         Execute TSO command\n"
                    "unix <cmd>        Execute safe OMVS-style command\n"
                    "pwd               Show current HLQ context\n"
                )
                continue
            if cmd == "pwd":
                self._send(self._pwd())
                continue
            if cmd in {"ipconfig", "ifconfig"}:
                self._send(self._ipconfig())
                continue
            if cmd == "getuid":
                self._send(f"Mainframe userID: {self.userid}")
                continue
            if cmd == "sysinfo":
                self._send(self._sysinfo())
                continue
            if cmd == "racf":
                self._send(self.tso("RVARY LIST"))
                continue
            if cmd == "ls":
                self._send(self._ls(arg))
                continue
            if cmd == "lsmem":
                self._send(self._lsmem(arg))
                continue
            if cmd == "cat":
                self._send(self._cat(arg))
                continue
            if cmd == "cp":
                self._send(self._cp(arg))
                continue
            if cmd in {"delete", "del"}:
                self._send(self._delete(arg))
                continue
            if cmd in {"execute", "tso"}:
                self._send(self.tso(arg))
                continue
            if cmd == "unix":
                self._send(self.tso(f"OMVS {arg}") if arg else "usage: unix <command>")
                continue
            if cmd == "ftp_racf":
                self._send(self._ftp_upload(arg, racf=True))
                continue
            if cmd == "ftp":
                self._send(self._ftp_upload(arg, racf=False))
                continue
            self._send("unknown command (try 'help')")


class TrainingShellServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def start_training_shell(state: GibsonState, userid: str, tso_runner_factory: Callable[[str], Callable[[str], str]], *, port: int = 0, ttl: int = 300, shell_id: str = "") -> tuple[TrainingShellServer, int]:
    class _Handler(TrainingShellHandler):
        pass

    _Handler.state = state
    _Handler.userid = userid.upper()
    _Handler.tso_runner_factory = staticmethod(tso_runner_factory)  # type: ignore[assignment]
    _Handler.ttl = ttl
    _Handler.shell_id = shell_id

    server = TrainingShellServer((state.config.host, int(port or 0)), _Handler)
    actual_port = int(server.server_address[1])
    t = threading.Thread(target=server.serve_forever, daemon=True, name=f"TrainingShell-{actual_port}")
    t.start()

    expiry = _dt.datetime.now() + _dt.timedelta(seconds=ttl)
    state.training_shells[shell_id or f"SHELL-{actual_port}"] = {
        "userid": userid.upper(),
        "port": actual_port,
        "expires": expiry.isoformat(timespec="seconds"),
        "server": server,
    }

    def _shutdown() -> None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        state.training_shells.pop(shell_id or f"SHELL-{actual_port}", None)

    timer = threading.Timer(ttl, _shutdown)
    timer.daemon = True
    timer.start()
    return server, actual_port
