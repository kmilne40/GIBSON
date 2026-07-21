#!/usr/bin/env python3
import asyncio
import socket
import threading
import uuid
import datetime
import random
import os
from passlib.hash import md5_crypt
import websockets
import traceback

# ─── Configuration ──────────────────────────────────────────────────────────────
# Support overriding configuration via environment variables.  These
# defaults can be changed without editing this file by setting
# DB2_PORT_TCP, DB2_PORT_WS, USER_FILE or DB2_LOG_DIR in the
# environment.  This makes it easier to run multiple instances for
# different labs or demonstrations.
PORT_TCP      = int(os.getenv("DB2_PORT_TCP", 50000))
PORT_WS       = int(os.getenv("DB2_PORT_WS", 50001))
USER_FILE     = os.getenv("USER_FILE", "GACF.DB")
DB2_SIGNATURE = b"DB2DAS"
LOG_DIR       = os.getenv("DB2_LOG_DIR", "session_logs")

SYSTEM_INFO = {
    "GROUP":     "DB2G1",
    "MEMBER":    "DB2A",
    "SUBSYSTEM": "DB2A",
    "VERSION":   "0.3.2",
    "ID":        "GOSDB2",
}

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# ─── In-memory state ────────────────────────────────────────────────────────────
USERS_DB    = {}
ACTIVE_JOBS = {}

SQL_STATIC_SYSTABLES = [
    # A small catalogue of system tables.  Feel free to extend this list to
    # make demonstrations richer.  Each entry uses real‑world names to help
    # learners recognise DB2 objects during injection testing.
    {"NAME": "EMPLOYEES",    "TYPE": "TABLE", "CREATOR": "SYSIBM"},
    {"NAME": "ACCOUNTS",     "TYPE": "TABLE", "CREATOR": "SYSIBM"},
    {"NAME": "DEPARTMENT",   "TYPE": "TABLE", "CREATOR": "SYSIBM"},
    {"NAME": "SYSPLAN",      "TYPE": "VIEW",  "CREATOR": "SYSIBM"},
    {"NAME": "SYSTABLESPACE", "TYPE": "TABLE", "CREATOR": "SYSIBM"},
]

# ─── Helpers: Load/Write Users ───────────────────────────────────────────────────
def load_users():
    """Load users from USER_FILE into USERS_DB."""
    USERS_DB.clear()
    if not os.path.exists(USER_FILE):
        print(f"[ERROR] {USER_FILE} not found.")
        return
    with open(USER_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) != 4:
                continue
            user, hsh, perm, omvs = parts
            USERS_DB[user] = {"hash": hsh, "perm": perm, "omvs": omvs}
    print(f"[INFO] Loaded {len(USERS_DB)} users.")

def write_users():
    """Persist USERS_DB back to USER_FILE."""
    with open(USER_FILE, "w") as f:
        for u, meta in USERS_DB.items():
            f.write(f"{u}:{meta['hash']}:{meta['perm']}:{meta['omvs']}\n")

# ─── Command Logging ────────────────────────────────────────────────────────────
def log_command(user, command):
    """Append a timestamped command to session_logs/<user>.log."""
    path = os.path.join(LOG_DIR, f"{user}.log")
    with open(path, "a") as f:
        ts = datetime.datetime.now().isoformat()
        f.write(f"{ts} - {command}\n")

# ─── Dynamic SQL Catalog ────────────────────────────────────────────────────────
def build_dynamic_catalog():
    return {
        "SYSIBM.SYSTABLES": SQL_STATIC_SYSTABLES,
        "SYSIBM.SYSUSERS": [
            {"USER": u, "PERM": USERS_DB[u]["perm"], "OMVS": USERS_DB[u]["omvs"]}
            for u in USERS_DB
        ]
    }

# ─── Fake SQL Parser ────────────────────────────────────────────────────────────
def parse_fake_sql(sql: str):
    qs = sql.strip().rstrip(";").upper()

    # GRANT simulation
    if qs.startswith("GRANT "):
        parts = qs.split()
        if len(parts) == 6 and parts[2] == "ON" and parts[4] == "TO":
            priv, db, tgt = parts[1], parts[3], parts[5]
            if tgt not in USERS_DB:
                raise ValueError(f"SQL0204N  {tgt} is not a valid userid.")
            if tgt == "NIALL" and priv == "DBADM":
                USERS_DB[tgt]["perm"] = "SPECIAL"
                USERS_DB[tgt]["omvs"] = "OMVS"
                write_users()
                return [{"MESSAGE": f"{tgt} upgraded to SPECIAL with OMVS"}]
            raise PermissionError(f'SQL0551N  "{tgt}" does not have the privilege to perform operation "GRANT".')
        raise ValueError("SQLLEA: Invalid GRANT syntax.")

    # REVOKE simulation
    if qs.startswith("REVOKE "):
        parts = qs.split()
        if len(parts) == 6 and parts[2] == "ON" and parts[4] == "FROM":
            priv, db, tgt = parts[1], parts[3], parts[5]
            if tgt not in USERS_DB:
                raise ValueError(f"SQL0204N  {tgt} is not a valid userid.")
            if USERS_DB[tgt]["perm"] == "SPECIAL":
                USERS_DB[tgt]["perm"] = "NONE"
                USERS_DB[tgt]["omvs"] = "NOOMVS"
                write_users()
                return [{"MESSAGE": f"{tgt} reverted to NONE with NOOMVS"}]
            raise PermissionError(f'SQL0551N  "{tgt}" does not have the privilege to perform operation "REVOKE".')
        raise ValueError("SQLLEA: Invalid REVOKE syntax.")

    # Block SYSACCTAUTH
    if "FROM SYSIBM.SYSACCTAUTH" in qs:
        raise PermissionError(
            "DSNT500I -DB2 RESOURCE UNAVAILABLE\n"
            "REASON 00D70024, TYPE 00000200, NAME SYSIBM.SYSACCTAUTH"
        )

    catalog = build_dynamic_catalog()

    # SYSTABLES queries
    if "FROM SYSIBM.SYSTABLES" in qs:
        data = catalog["SYSIBM.SYSTABLES"]
        if " WHERE " in qs:
            cond = qs.split(" WHERE ", 1)[1]
            if "'1'='1'" in cond or " OR " in cond:
                return data
            if "NAME =" in cond and "EMPLOYEES" in cond:
                return [r for r in data if r["NAME"] == "EMPLOYEES"]
            return []
        return data

    # SYSUSERS queries
    if "FROM SYSIBM.SYSUSERS" in qs:
        data = catalog["SYSIBM.SYSUSERS"]
        if " WHERE " in qs:
            cond = qs.split(" WHERE ", 1)[1]
            if "'1'='1'" in cond or " OR " in cond:
                return data
            if "PERM =" in cond:
                val = cond.split("PERM =", 1)[1].strip().strip("'\"")
                return [r for r in data if r["PERM"] == val]
            return []
        return data

    raise ValueError("SQL30082N Security processing failed: UNSUPPORTED SQL SYNTAX.")

# ─── Build DB2DAS Response ───────────────────────────────────────────────────────
def build_db2das_response():
    profile = (
        ";DB2 Server Database Access Profile\r\n"
        "[File_Description]\r\n"
        f"Application=DB2/ZOS {SYSTEM_INFO['VERSION']}\r\n"
        "File_Type=CommonServer\r\n"
        "File_Format_Version=1.0\r\n"
        f"DB2System={SYSTEM_INFO['SUBSYSTEM']}\r\n"
        "ServerVersion=QDB2\r\n"
        "[inst>DB2A]\r\n"
        "DB2Comm=TCPIP\r\n"
        f"PortNumber={PORT_TCP}\r\n"
    ).encode("ascii")

    header = bytearray(41)
    header[0:4]   = b"\x00\x00\x00\x00"
    header[4:10]  = b"DB2DAS"
    header[10:16] = b"\x20" * 6
    header[16:18] = b"\x01\x04"
    header[18:23] = b"\x00\x00\x00\x10\x39"
    header[23:25] = b"\x7A\x00"
    header[25:38] = b"\x00" * 13
    header[38:41] = len(profile).to_bytes(3, "little")
    header.append(0x00)
    return bytes(header) + profile

# ─── Raw TCP Server ─────────────────────────────────────────────────────────────
def raw_tcp_server():
    load_users()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", PORT_TCP))
        srv.listen(5)
        print(f"[TCP] DB2-DAS Simulator listening on port {PORT_TCP}")
        while True:
            conn, addr = srv.accept()
            with conn:
                try:
                    conn.settimeout(5.0)
                    data = conn.recv(1024)
                    if DB2_SIGNATURE in data:
                        print(f"[TCP] Probe from {addr[0]}")
                        conn.sendall(build_db2das_response())
                except Exception as e:
                    print(f"[TCP] Error: {e}")

# ─── WebSocket Shell ─────────────────────────────────────────────────────────────
HELP_TEXT = """\
Available commands:
  HELP
  SHOW DBS
  SHOW USERS
  DISPLAY GROUP
  OMVS STATUS
  ID UID
  RUN SQL <query>
  SUBMIT JOB <name>
  STATUS JOBS
  CANCEL JOB <id>
  GRANT <priv> ON <db> TO <user>
  REVOKE <priv> ON <db> FROM <user>
  LOGOUT
"""

async def handle_ws(ws):
    """
    Simplified admin shell exposed over WebSocket.

    This coroutine implements a minimal command shell for the DB2/zOS
    simulator.  It is intentionally basic and does not implement the
    complete DRDA protocol; rather it provides a handful of commands
    (displaying system information, running fake SQL, submitting jobs
    and altering user privileges) to demonstrate how a privileged
    interface might behave.  The WebSocket interface makes it easy to
    test with browser consoles or tools like `websocat`, but it should
    not be mistaken for a real DB2 admin channel.  All messages are
    plain text and authentication uses weak MD5 hashes for training
    purposes.
    """
    path = getattr(ws, "path", "/")
    print(f"[WS] New connection: path={path}")
    try:
        load_users()
        await ws.send("Welcome to DB2/zOS simulator.\nLogin: LOGIN <username> <password>")
        authenticated = False
        user = None

        async for msg in ws:
            cmd = msg.strip()
            print(f"[WS] <<< {user or 'anon'}: {cmd}")

            if not authenticated:
                parts = cmd.split()
                if len(parts) == 3 and parts[0].upper() == "LOGIN":
                    u, pw = parts[1], parts[2]
                    if u in USERS_DB and md5_crypt.verify(pw, USERS_DB[u]["hash"]):
                        if USERS_DB[u]["omvs"] != "NOOMVS":
                            authenticated = True
                            user = u
                            await ws.send(f"Login successful. Welcome, {u}!\nType HELP")
                        else:
                            await ws.send("Login failed: OMVS segment missing.")
                    else:
                        await ws.send("Login failed: Unknown user or bad password.")
                else:
                    await ws.send("Please login first. Format: LOGIN <username> <password>")
                continue

            log_command(user, cmd)
            uc = cmd.upper()

            try:
                if uc == "HELP":
                    await ws.send(HELP_TEXT)
                elif uc == "SHOW DBS":
                    await ws.send("Databases: SAMPLE, PRODDB, TESTDB")
                elif uc == "SHOW USERS":
                    if USERS_DB[user]["perm"] in ("SPECIAL", "ADMIN"):
                        await ws.send("Users:\n" + "\n".join(USERS_DB.keys()))
                    else:
                        await ws.send("Permission denied.")
                elif uc == "DISPLAY GROUP":
                    si = SYSTEM_INFO
                    txt = (
                        f"DSN7100I -{si['SUBSYSTEM']} DISPLAY GROUP REPORT\n"
                        f"  SYSTEM: {si['MEMBER']} GROUP: {si['GROUP']} VERSION: {si['VERSION']}\n"
                        f"  SUBSYSTEM ID: {si['ID']}"
                    )
                    await ws.send(txt)
                elif uc == "OMVS STATUS":
                    status = "Present" if USERS_DB[user]["omvs"] != "NOOMVS" else "Missing"
                    await ws.send(f"OMVS segment: {status}")
                elif uc == "ID UID":
                    uid = 1000 + abs(hash(user)) % 9000
                    await ws.send(f"UID={uid} GID={uid} HOME=/u/{user.lower()} SHELL=/bin/sh")
                elif uc.startswith("RUN SQL "):
                    query = cmd[len("RUN SQL "):]
                    rows = parse_fake_sql(query)
                    if not rows:
                        await ws.send("SQLCODE=100, NO ROWS FOUND")
                    else:
                        keys = list(rows[0].keys())
                        hdr = "  ".join(keys) + "\n"
                        body = "\n".join("  ".join(str(r[k]) for k in keys) for r in rows)
                        await ws.send(hdr + body)
                elif uc.startswith("SUBMIT JOB "):
                    name = cmd[len("SUBMIT JOB "):].strip()
                    jid = str(uuid.uuid4())[:8].upper()
                    ACTIVE_JOBS[jid] = {"name": name, "status": random.choice(["ACCEPTED","RUNNING","ENDED OK"])}
                    await ws.send(f"JOB {jid} submitted.")
                elif uc == "STATUS JOBS":
                    if not ACTIVE_JOBS:
                        await ws.send("No active jobs.")
                    else:
                        lines = ["JOB ID     NAME      STATUS"]
                        for jid, inf in ACTIVE_JOBS.items():
                            lines.append(f"{jid}  {inf['name']:<8} {inf['status']}")  
                        await ws.send("\n".join(lines))
                elif uc.startswith("CANCEL JOB "):
                    jid = cmd[len("CANCEL JOB "):].strip()
                    if jid in ACTIVE_JOBS:
                        del ACTIVE_JOBS[jid]
                        await ws.send(f"JOB {jid} cancelled.")
                    else:
                        await ws.send("Job ID not found.")
                elif uc.startswith(("GRANT ", "REVOKE ")):
                    try:
                        res = parse_fake_sql(cmd)
                        await ws.send(res[0].get("MESSAGE", str(res)))
                    except (PermissionError, ValueError) as e:
                        await ws.send(str(e))
                elif uc == "LOGOUT":
                    await ws.send("Goodbye.")
                    break
                else:
                    await ws.send("Unknown command. Type HELP.")
            except Exception as e:
                print(f"[WS] Cmd error: {e}")
                traceback.print_exc()
                await ws.send(f"Error processing command: {e}")
    except Exception as e:
        print(f"[WS] Unhandled exception: {e}")
        traceback.print_exc()
        try:
            await ws.close(code=1011, reason="Internal server error")
        except:
            pass

# ─── Server Startup ─────────────────────────────────────────────────────────────
async def start_ws():
    print(f"[WS] WebSocket shell listening on port {PORT_WS}")
    async with websockets.serve(handle_ws, "0.0.0.0", PORT_WS):
        await asyncio.Future()

def run_ws():
    asyncio.run(start_ws())

# ─── Main Entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=raw_tcp_server, daemon=True).start()
    run_ws()
