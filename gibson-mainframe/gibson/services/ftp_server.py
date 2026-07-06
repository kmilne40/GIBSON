from __future__ import annotations

import datetime
import io
import os
import socket
import socketserver
import threading
from pathlib import Path
from typing import Optional

from gibson.apps.tso import TsoCommandProcessor
from gibson.core.state import GibsonState
from gibson.core.issues import is_expected_disconnect
from gibson.services.ftp import GibsonFtpAdapter
from gibson.net.fingerprints import ftp_feat_response, ftp_greeting, ftp_help_response, zos_ftp_syst

DATA_ACCEPT_TIMEOUT = 15


def _safe_name(name: str) -> str:
    return os.path.basename(name.strip().strip("'\"") or "NONAME")


def _pasv_ip(sock: socket.socket) -> str:
    try:
        ip = sock.getsockname()[0]
        if ip and ip not in ("0.0.0.0", "::"):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


class SharedFtpHandler(socketserver.StreamRequestHandler):
    state: GibsonState

    def setup(self):
        super().setup()
        try:
            self.state.note_port_touch(self.client_address[0], self.state.config.ftp_port, service="FTP")
        except Exception:
            pass
        self.username: Optional[str] = None
        self.authed = False
        self.cwd = Path(".")
        self.filetype = "FILE"
        self.passive_server: Optional[socket.socket] = None

    def send_raw(self, msg: str) -> None:
        self.wfile.write(msg.encode("utf-8", errors="ignore"))
        self.wfile.flush()

    def send_response(self, msg: str) -> None:
        if not msg.endswith("\r\n"):
            msg += "\r\n"
        self.send_raw(msg)

    def handle(self) -> None:
        self.send_raw(ftp_greeting(getattr(self.state.network, "hostname", "GIBSON")))
        for raw in self.rfile:
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            parts = text.split(None, 1)
            cmd = parts[0].upper()
            arg = parts[1] if len(parts) > 1 else ""
            try:
                if cmd == "USER":
                    self.username = arg.strip().upper()
                    self.send_response("331 Password required")
                elif cmd == "PASS":
                    self._pass(arg)
                elif cmd == "SYST":
                    self.send_raw(zos_ftp_syst())
                elif cmd == "FEAT":
                    self.send_raw(ftp_feat_response())
                elif cmd == "HELP":
                    self.send_raw(ftp_help_response())
                elif cmd == "NOOP":
                    self.send_response("200 OK")
                elif cmd == "OPTS":
                    self.send_response("501 command OPTS aborted -- no options supported for UTF8")
                elif cmd == "PWD":
                    self.send_response(f'257 "{self.cwd}" is the current dataset prefix')
                elif cmd == "TYPE":
                    mode = arg.strip().upper()
                    if mode in ("I", "IMAGE", "L 8"):
                        self.send_response("200 Representation type is Image")
                    elif mode in ("A", "ASCII"):
                        self.send_response("200 Representation type is ASCII NonPrint")
                    else:
                        self.send_response("504 Type not supported")
                elif cmd == "PASV":
                    self._pasv(False)
                elif cmd == "EPSV":
                    self._pasv(True)
                elif cmd in ("LIST", "NLST"):
                    self._list(arg, names_only=(cmd == "NLST"))
                elif cmd in ("STOR", "PUT"):
                    self._stor(arg)
                elif cmd == "RETR":
                    self._retr(arg)
                elif cmd == "SITE":
                    self._site(arg)
                elif cmd == "CWD":
                    self.cwd = Path(arg.strip() or ".")
                    self.send_response("250 Dataset prefix changed")
                elif cmd == "QUIT":
                    self.send_response("221 Goodbye")
                    return
                else:
                    self.send_response("502 Command not implemented")
            except Exception as exc:
                self.send_response(f"550 Command failed: {exc}")

    def _pass(self, password: str) -> None:
        if not self.username:
            self.send_response("503 Login with USER first")
            return
        self.state.racf.load(merge=True)
        vuln_mode = getattr(self.state.config, "security_mode", "vuln") == "vuln" or os.getenv("GIBSON_VULN_MODE", "0") in ("1", "true", "TRUE")
        if self.username == "ANONYMOUS" and vuln_mode:
            self.authed = True
            self.username = "GUEST"
            self.state.racf.ensure_user_dir(self.state.config.files_root, self.username)
            self.state.record_security_event("ANONYMOUS", "FTP ANON LOGON", "Anonymous FTP login allowed", service="FTP")
            self.send_response("230 Anonymous access granted")
        elif self.state.racf.verify_password(self.username, password):
            self.authed = True
            self.state.clear_failed_logon(self.username, self.client_address[0], port=self.state.config.ftp_port)
            self.state.racf.ensure_user_dir(self.state.config.files_root, self.username)
            self.state.record_security_event(self.username, "LOGON", "PASSWORD", service="FTP")
            self.send_response("230 Login successful")
        else:
            self.state.note_failed_logon(self.username, self.client_address[0], port=self.state.config.ftp_port, service="FTP")
            self.state.record_security_event(self.username, "LOGON", "PASSWORD FAILURE", result="FAILURE", service="FTP")
            self.send_response("530 Login incorrect")

    def _require(self) -> bool:
        if not self.authed or not self.username:
            self.send_response("530 Not logged in")
            return False
        return True

    def _pasv(self, epsv: bool) -> None:
        if self.passive_server:
            try:
                self.passive_server.close()
            except Exception:
                pass
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.state.config.host, 0))
        srv.listen(1)
        self.passive_server = srv
        port = srv.getsockname()[1]
        if epsv:
            self.send_response(f"229 Entering Extended Passive Mode (|||{port}|)")
        else:
            ip = _pasv_ip(self.request).replace(".", ",")
            self.send_response(f"227 Entering Passive Mode ({ip},{port // 256},{port % 256})")

    def _accept(self):
        if not self.passive_server:
            self.send_response("425 Use PASV or EPSV first")
            return None
        self.passive_server.settimeout(DATA_ACCEPT_TIMEOUT)
        try:
            conn, _addr = self.passive_server.accept()
            return conn
        finally:
            try:
                self.passive_server.close()
            except Exception:
                pass
            self.passive_server = None

    def _list(self, arg: str, names_only: bool = False) -> None:
        if not self._require():
            return
        self.send_response("150 Opening data connection")
        conn = self._accept()
        if not conn:
            return
        try:
            adapter = GibsonFtpAdapter(self.state)
            if self.filetype == "JES":
                payload = adapter.list_jes(self.username)
            else:
                rows = self.state.datasets.listcat(self.username)  # type: ignore[arg-type]
                lines = []
                for row in rows or []:
                    size = row.path.stat().st_size if row.path.exists() and row.path.is_file() else 0
                    if names_only:
                        lines.append(f"{row.name}\r\n")
                    else:
                        lines.append(
                            f"-rw-r--r-- 1 {self.username} SYS1 {size:8d} {datetime.datetime.now():%b %d %H:%M} {row.name}\r\n"
                        )
                payload = "".join(lines)
            conn.sendall(payload.encode("utf-8", errors="ignore"))
            self.send_response("226 Directory send OK")
        finally:
            conn.close()

    def _stor(self, arg: str) -> None:
        if not self._require():
            return
        name = _safe_name(arg)
        self.send_response("150 Opening data connection")
        conn = self._accept()
        if not conn:
            return
        buf = io.BytesIO()
        try:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf.write(chunk)
        finally:
            conn.close()
        content = buf.getvalue()
        adapter = GibsonFtpAdapter(self.state)
        if self.filetype == "JES" or name.upper().endswith(".JCL") or content.lstrip().startswith(b"//"):
            runner = TsoCommandProcessor(self.state, self.username).run  # type: ignore[arg-type]
            try:
                resp = adapter.stor_jes(self.username, name, content, tso_runner=runner)  # type: ignore[arg-type]
            except Exception:
                resp = "550 Job not submitted - JES internal reader error"
            self.send_response(resp)
            return
        if self.filetype == "SQL" or name.upper().endswith(".SQL"):
            self.send_response(adapter.stor_sql(self.username, name, content))  # type: ignore[arg-type]
            return
        try:
            self.state.datasets.write(self.username, name, content.decode("utf-8", errors="ignore"))  # type: ignore[arg-type]
        except PermissionError:
            self.send_response("550 Not authorized")
            return
        self.send_response("226 Transfer complete")

    def _retr(self, arg: str) -> None:
        if not self._require():
            return
        name = _safe_name(arg)
        adapter = GibsonFtpAdapter(self.state)
        try:
            if self.filetype == "JES" and name.upper().startswith("JOB"):
                text = adapter.retr_jes(self.username, name)
            else:
                text = self.state.datasets.read(self.username, name)  # type: ignore[arg-type]
        except PermissionError:
            self.send_response("550 Not authorized")
            return
        except Exception:
            self.send_response("550 File not found")
            return
        self.send_response("150 Opening data connection")
        conn = self._accept()
        if not conn:
            return
        try:
            # A binary dataset (the racf2john SYS1.RACFDS.BACKUP image) is stored
            # marker-wrapped; send the reconstituted raw bytes so a binary-mode
            # GET retrieves the real image, not base64 text.
            payload = None
            try:
                from gibson.core.racf_db_binary import decode_from_dataset
                payload = decode_from_dataset(text)
            except Exception:
                payload = None
            conn.sendall(payload if payload is not None else text.encode("utf-8", errors="ignore"))
            self.send_response("226 Transfer complete")
        finally:
            conn.close()

    def _site(self, arg: str) -> None:
        opt = arg.strip().upper()
        if opt.startswith("FILETYPE="):
            ft = opt.split("=", 1)[1]
            if ft in ("FILE", "JES", "SQL"):
                self.filetype = ft
                self.send_response(f"200 FILETYPE set to {ft}")
            else:
                self.send_response("504 Unknown FILETYPE")
            return
        if opt.startswith("JES STATUS"):
            lines = [f"{j.jobid}:{j.status.value}:RC={j.rc:04d}" for j in self.state.jes.list_jobs(owner=self.username)]
            self.send_response("200 " + ("; ".join(lines) if lines else "NO JOBS"))
            return
        if opt.startswith("JES PURGE"):
            parts = opt.split()
            if len(parts) < 3:
                self.send_response("501 Usage: SITE JES PURGE <JOBID>")
                return
            jobid = parts[2].upper()
            if self.state.jes.purge(jobid):
                shell = self.state.training_shells.pop(jobid, None)
                server = shell.get("server") if shell else None
                if server is not None:
                    try:
                        server.shutdown()
                        server.server_close()
                    except Exception:
                        pass
                self.send_response(f"200 {jobid} purged")
            else:
                self.send_response("550 Unknown job")
            return
        self.send_response("504 Unknown SITE option")


class ThreadedFtpServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if exc is not None and is_expected_disconnect(exc):
            return
        return super().handle_error(request, client_address)


def serve_ftp(state: GibsonState) -> ThreadedFtpServer:
    SharedFtpHandler.state = state
    server = ThreadedFtpServer((state.config.host, state.config.ftp_port), SharedFtpHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="GibsonFTP").start()
    return server
