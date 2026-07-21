#!/usr/bin/env python3
import datetime
import logging
import os
from passlib.hash import md5_crypt
from collections import deque

# Disable mandatory CESN
AUTH_REQUIRED = False

# Logging Configuration
LOG_FILE = "cics-simulator.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BASE_DIR = os.path.dirname(__file__)
SECURE_FILE = os.path.join(BASE_DIR, "GACF.DB")

# Load GACF.DB (still available for CESN if used)
def load_secure_users():
    users = {}
    try:
        with open(SECURE_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) >= 2:
                    userid = parts[0].upper()
                    password = parts[1].strip()
                    privilege = parts[2].upper() if len(parts) >= 3 else "NONE"
                    omvs_flag = parts[3].upper() if len(parts) >= 4 else "NOOMVS"
                    users[userid] = (password, privilege, omvs_flag)
    except Exception as e:
        logging.error(f"Error loading GACF.DB: {e}")
    return users

SECURE_USERS = load_secure_users()

# Load Menus
def load_screen(name):
    try:
        with open(os.path.join(BASE_DIR, name), "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"*** Missing {name} ***\n"

BANNER = load_screen("cics-screen.txt")
CEMT_MENU = load_screen("CEMT.txt")
CEDA_MENU = load_screen("CEDA.txt")
CESF_MENU = load_screen("CESF.txt")
CECI_MENU = load_screen("CECI.txt")

# Resource definitions
PROGRAMS = {
    "MYPROG": {"length": 123, "status": "ENABLED"},
    "DEMO001": {"length": 456, "status": "DISABLED"},
}
FILES = {
    "FILEA": {"dsn": "DATA.FILEA", "status": "AVAILABLE"},
    "FILEB": {"dsn": "DATA.FILEB", "status": "IN-USE"},
}
TRANSACTIONS = {
    "CEMT": {"status": "ENABLED"},
    "CECI": {"status": "ENABLED"},
    "CEDA": {"status": "ENABLED"},
}

SYSTEM_STATE = {"running": True, "uptime": datetime.datetime.now()}

# ANSI Helpers
def blue(s): return "\033[34m" + s + "\033[0m"
def clear_screen(): return "\033[2J\033[H"

class CICSSession:
    def __init__(self, request):
        self.request = request
        self.menu_stack = []
        self.running = True
        self.logged_in = True  # start already logged in
        self.userid = "DEFAULT"
        self.privilege = "NONE"
        self.omvs_flag = "NOOMVS"

    def safe_send(self, s, clear=False):
        try:
            if clear:
                self.request.sendall((clear_screen() + blue(s)).encode("utf-8"))
            else:
                self.request.sendall(blue(s).encode("utf-8"))
        except BrokenPipeError:
            logging.warning("Broken pipe in CICS session")
            self.running = False

    def read_line(self, echo=True):
        buf = ""
        while True:
            try:
                ch = self.request.recv(1)
            except ConnectionResetError:
                return None
            if not ch:
                return None
            c = ch.decode("utf-8", errors="ignore")
            if c in ("\r", "\n"):
                if echo:
                    self.safe_send("\n")
                break
            if not echo:
                continue
            if c in ("\x08", "\x7f"):  # backspace
                if buf:
                    buf = buf[:-1]
                continue
            buf += c
            if echo:
                self.safe_send(c)
        return buf.strip()

    def run(self):
        logging.info("CICS session started")
        self.safe_send(BANNER, clear=True)

        # Wait for ENTER to continue
        while True:
            line = self.read_line()
            if line in ("", None):
                break

        while self.running:
            self.safe_send("===> ")
            cmd = (self.read_line() or "").upper()
            if not cmd:
                continue

            logging.info(f"CICS Command: {cmd}")
            if cmd in ("EXIT", "LOGOFF", "SIGNOFF"):
                self.safe_send("DFHCE3555 SIGNOFF SUCCESSFUL.\n", clear=True)
                self.running = False
                break
            elif cmd.startswith("CESN"):
                self.handle_cesn()
            elif cmd.startswith("CEMT"):
                self.handle_cemt(cmd)
            elif cmd.startswith("CEDA"):
                self.handle_ceda(cmd)
            elif cmd.startswith("CESF"):
                self.handle_cesf()
            elif cmd.startswith("CECI"):
                self.handle_ceci(cmd)
            elif cmd.startswith("CESL"):
                self.handle_cesl()
            elif cmd == "HELP":
                self.show_help()
            else:
                self.safe_send("DFHCE3551 COMMAND NOT RECOGNIZED.\n")

        logging.info("CICS session ended")

    # CESN remains available but optional
    def handle_cesn(self):
        screen = (
            " DFHCE3545 SIGNON TO CICS\n"
            " ------------------------------\n"
            " USERID   ===> ________\n"
            " PASSWORD ===> ________\n"
            " PF12=CANCEL\n"
        )
        self.safe_send(screen, clear=True)
        self.safe_send("\033[2A\033[16C")
        userid = self.read_line().upper()
        self.safe_send("\033[B\033[16C")
        password = self.read_line(echo=False).strip()

        user_rec = SECURE_USERS.get(userid)
        if user_rec and md5_crypt.verify(password, user_rec[0]):
            self.logged_in = True
            self.userid = userid
            self.privilege, self.omvs_flag = user_rec[1], user_rec[2]
            self.safe_send(f"\nDFHCE3548 USERID {userid} SIGNED ON SUCCESSFULLY.\n", clear=True)
        else:
            self.safe_send("\nDFHCE3549 INVALID USERID OR PASSWORD.\n")

    # CEMT
    def handle_cemt(self, cmd):
        if cmd.strip() == "CEMT":
            self.safe_send(CEMT_MENU, clear=True)
            return
        parts = cmd.split()
        if len(parts) < 2:
            return
        action, obj = parts[1], parts[2] if len(parts) > 2 else ""
        if action in ("INQUIRE", "I"):
            if obj.startswith("PROG"):
                self.safe_send(self.generate_programs(), clear=True)
            elif obj.startswith("FILE"):
                self.safe_send(self.generate_files(), clear=True)
            elif obj.startswith("TASK"):
                self.safe_send(self.generate_tasks(), clear=True)
            elif obj.startswith("TRAN"):
                self.safe_send(self.generate_trans(), clear=True)
            else:
                self.safe_send("DFHCE3552 INVALID INQUIRE OPTION.\n")
        elif action == "SET" and obj == "PROGRAM":
            if len(parts) >= 5:
                prog, state = parts[3], parts[4]
                if prog in PROGRAMS and state in ("ENABLED", "DISABLED"):
                    PROGRAMS[prog]["status"] = state
                    self.safe_send(f"DFHCE3553 PROGRAM {prog} SET TO {state}.\n", clear=True)

    # CEDA
    def handle_ceda(self, cmd):
        if cmd.strip() == "CEDA":
            self.safe_send(CEDA_MENU, clear=True)
            return
        parts = cmd.split()
        if len(parts) < 2:
            return
        action = parts[1].upper()
        if action == "DEFINE":
            form = (
                " DFHCE3560 CEDA DEFINE - ENTER DETAILS\n"
                " --------------------------------------\n"
                " TYPE      ===> ________\n"
                " NAME      ===> ________\n"
                " LENGTH    ===> ________\n"
                " STATUS    ===> ________\n"
                " PF12=CANCEL\n"
            )
            self.safe_send(form, clear=True)
            self.safe_send("\033[4A\033[16C")
            rtype = self.read_line().upper()
            self.safe_send("\033[B\033[16C")
            rname = self.read_line().upper()
            self.safe_send("\033[B\033[16C")
            rlen = self.read_line()
            self.safe_send("\033[B\033[16C")
            rstat = self.read_line().upper()
            if rtype == "PROGRAM":
                PROGRAMS[rname] = {"length": int(rlen or 100), "status": rstat}
                self.safe_send(f"DFHCE3561 PROGRAM {rname} DEFINED SUCCESSFULLY.\n", clear=True)

        elif action in ("DISPLAY", "INQUIRE"):
            if len(parts) < 3:
                return
            res = parts[2].upper()
            if res.startswith("PROG"):
                self.safe_send(self.generate_programs(), clear=True)
            elif res.startswith("FILE"):
                self.safe_send(self.generate_files(), clear=True)
            elif res.startswith("TRAN"):
                self.safe_send(self.generate_trans(), clear=True)

    # CESF
    def handle_cesf(self):
        self.safe_send(self.generate_stats(), clear=True)

    # CECI
    def handle_ceci(self, cmd):
        if cmd.strip() == "CECI":
            self.safe_send(CECI_MENU, clear=True)
            return
        verb = cmd.split()[1] if len(cmd.split()) > 1 else ""
        self.safe_send(f"DFHCE3570 SIMULATED EXECUTION OF {verb}.\n", clear=True)

    # CESL
    def handle_cesl(self):
        try:
            with open(LOG_FILE, "r") as f:
                lines = deque(f, maxlen=20)
                log_output = "".join(lines)
        except FileNotFoundError:
            log_output = "*** NO LOGS FOUND ***\n"
        self.safe_send(
            "DFHCE3580 CESL - SYSTEM LOGS (LAST 20 ENTRIES)\n"
            + "-" * 50 + "\n"
            + log_output,
            clear=True
        )

    # HELP
    def show_help(self):
        help_screen = (
            "DFHCE3590 HELP - AVAILABLE TRANSACTIONS\n"
            "  CESN - LOGON (optional)\n"
            "  CEMT - MASTER TERMINAL\n"
            "  CEDA - DEFINE RESOURCES\n"
            "  CESF - STATS / SIGNOFF\n"
            "  CECI - COMMAND INTERPRETER\n"
            "  CESL - SYSTEM LOGS\n"
            "  EXIT/LOGOFF/SIGNOFF - END SESSION\n"
        )
        self.safe_send(help_screen, clear=True)

    # Generators
    def generate_programs(self):
        return "\n".join(
            [f"PROG({k}) LENG({v['length']:06d}) STAT({v['status']})"
             for k, v in PROGRAMS.items()]
        ) + "\n"

    def generate_files(self):
        return "\n".join(
            [f"FILE({k}) DSN({v['dsn']}) STAT({v['status']})"
             for k, v in FILES.items()]
        ) + "\n"

    def generate_tasks(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return f"TASK(000001) TRAN(CEMT) STAT(ACTIVE) TIME({now})\n"

    def generate_trans(self):
        return "\n".join(
            [f"TRAN({k}) STAT({v['status']})" for k, v in TRANSACTIONS.items()]
        ) + "\n"

    def generate_stats(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = datetime.datetime.now() - SYSTEM_STATE["uptime"]
        return (
            f"DFHCE3600 CICS STATISTICS AT {now}\n"
            f"UPTIME: {uptime}\n"
            "CPU%             5.3\n"
            "Transactions/Sec 0.45\n"
            "Transient Tasks  3\n"
            "TS Queue Length  0\n"
        )

# Entry point for gibsonmf.py
def start_cics_session(request):
    session = CICSSession(request)
    session.run()
