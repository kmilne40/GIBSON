#!/usr/bin/env python3
import socket
import threading
import time
import os
import argparse
import logging
import json
import subprocess
import select
import pty
import re
import shutil
import psutil
import hashlib
import base64
from datetime import datetime
from passlib.hash import md5_crypt
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
import asyncio
from pyspf_tui import run_ispf
# ISPFSession = ispf.ISPFSession  # force it back to your enhanced one
# Import CICS module
import CICS

# -----------------------------
# Global Variables and Config
# -----------------------------
active_sessions = {}       # Active sessions by username.
simulated_jobs = []        # Global job queue for simulated JES.
login_attempts = {}        # Maps IP -> list of attempt timestamps (seconds)
flagged_ips = []           # List of IP addresses flagged for brute force
connection_status = {}     # Maps IP -> "red" (active) or "green" (disconnected)
ip_locations = {}          # Cache for IP geolocation (IP -> (lat, lon))

def load_config():
    """Load configuration from 'config.json'; use defaults if file not found."""
    default_config = {
        "host": "0.0.0.0",
        "port": 2023,
        "web_dashboard_port": 8443,
        "dashboard_username": "admin",
        "dashboard_password": "gibsonadmin!",
        "base_dir": os.path.expanduser("~/mfsim/f"),
        "commands_dir": os.path.expanduser("~/mfsim/f/commands"),
        "vtam_file": "vtam.txt",
        "ispf_file": "ispf.txt",
        "sdsf_file": "sdsf.txt",
        "tso_logon_file": "tso-logon.txt",
        "welcome_file": "welcome.txt",
        "log_file": "simulator.log"
    }
    try:
        with open("config.json", "r") as f:
            user_config = json.load(f)
        default_config.update(user_config)
    except Exception:
        pass  # Use defaults if config file is missing or unreadable.
    return default_config

config = load_config()
# Ensure paths like "~" are expanded for consistency
config["base_dir"] = os.path.expanduser(config["base_dir"])
config["commands_dir"] = os.path.expanduser(config["commands_dir"])

# Set up centralized logging.
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(config["log_file"], maxBytes=1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -----------------------------
# MD5CRYPT FUNCTIONS
# -----------------------------
def is_hashed(pw):
    """Return True if the stored password appears to be MD5-crypt (starts with "$1$")."""
    return pw.startswith("$1$")

def hash_password(pw):
    """Return the MD5-crypt hash of the password."""
    return md5_crypt.hash(pw)

def check_password(pw, stored):
    """Return True if the provided password matches the stored MD5-crypt hash."""
    try:
        return md5_crypt.verify(pw, stored)
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False

# -----------------------------
# UTILITY FUNCTIONS
# -----------------------------
def universal_replace(content, username, attrib):
    """
    Replace placeholders:
      - "xxxxxxx" with the given username.
      - "ATTRIB" with the given privilege.
      - "T1ME" with the current system time.
      - "D4TE" with the current system date.
      - "xxx.xxx.xxx.xxx" with the current system IP address.
    """
    content = content.replace("xxxxxxx", username)
    content = content.replace("ATTRIB", attrib)
    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%Y-%m-%d")
    try:
        current_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        current_ip = "127.0.0.1"
    content = content.replace("T1ME", current_time)
    content = content.replace("D4TE", current_date)
    content = content.replace("xxx.xxx.xxx.xxx", current_ip)
    return content

def display_with_prompt(conn, content):
    """
    Searches for the literal "HERE" in content, removes it,
    sends the modified content, and positions the cursor at that point.
    """
    lines = content.splitlines()
    row, col = None, None
    for i, line in enumerate(lines):
        if "HERE" in line:
            idx = line.find("HERE")
            row = i + 1
            col = idx + 1
            lines[i] = line.replace("HERE", "")
            break
    new_content = "\n".join(lines)
    conn.sendall(new_content.encode("utf-8"))
    if row is not None and col is not None:
        cursor_cmd = f"\033[{row};{col}H"
        conn.sendall(cursor_cmd.encode("utf-8"))

def clear_screen(conn):
    """Clear the terminal screen using ANSI escape codes."""
    conn.sendall("\033[2J\033[H".encode("utf-8"))

def display_login_screen(conn, client_ip):
    """Display the VTAM logon screen if available; otherwise, show a default welcome screen."""
    clear_cmd = "\033[2J\033[H"
    screen = clear_cmd
    vtam_file = config["vtam_file"]
    if os.path.exists(vtam_file):
        try:
            with open(vtam_file, "r") as f:
                vtam_content = f.read()
            vtam_content = vtam_content.replace("xxx.xxx.xxx.xxx", client_ip)
            screen += vtam_content
        except Exception:
            pass
    else:
        screen += (
            "**************************************************\n"
            "*         WELCOME TO THE MAINFRAME SIM           *\n"
            "**************************************************\n\n"
        )
    screen += "LOGON using L TSO, L CICS or L DB2.\n"
    conn.sendall(screen.encode("utf-8"))

# -----------------------------
# USER MANAGEMENT FUNCTIONS
# -----------------------------
def load_users():
    """Load user credentials from 'GACF.DB'."""
    users = {}
    try:
        with open("GACF.DB", "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(':')
                    username = parts[0].strip().upper()
                    password = parts[1].strip() if len(parts) >= 2 else ""
                    privilege = parts[2].strip().upper() if len(parts) >= 3 else "NONE"
                    omvs_flag = parts[3].strip().upper() if len(parts) >= 4 else "NOOMVS"
                    users[username] = (password, privilege, omvs_flag)
    except Exception as e:
        logger.error("Error loading users file: %s", e)
    return users

def update_users_file(users):
    """Write out the current user records to 'GACF.DB'."""
    try:
        with open("GACF.DB", "w") as f:
            for username, (password, privilege, omvs_flag) in users.items():
                f.write(f"{username}:{password}:{privilege}:{omvs_flag}\n")
    except Exception as e:
        logger.error("Error updating users file: %s", e)

# -----------------------------
# COMMAND HANDLER FUNCTIONS (ADDUSER and ALTUSER)
# -----------------------------
def handle_adduser(cmd, current_users):
    try:
        parts = cmd.split()
        if len(parts) < 5:
            return "Error: Incorrect format for ADDUSER. Format: ADDUSER username pass(password) PRIVILEGE OMVSFLAG"
        new_username = parts[1].strip().upper()
        pass_token = parts[2]
        if not (pass_token.lower().startswith("pass(") and pass_token.endswith(")")):
            return "Error: Password must be enclosed in pass( )."
        new_password = pass_token[5:-1]
        new_privilege = parts[3].strip().upper()
        if new_privilege not in ("SPECIAL", "NONE"):
            return "Error: PRIVILEGE must be either SPECIAL or NONE."
        new_omvs_flag = parts[4].strip().upper()
        if new_omvs_flag not in ("OMVS", "NOOMVS"):
            return "Error: OMVS flag must be either OMVS or NOOMVS."
        if len(new_username) > 7:
            return "Warning: Username can only be a max of 7 characters."
        if len(new_password) > 8:
            return "Warning: Password can only be a max of 8 characters."
        new_password_hashed = hash_password(new_password)
        with open("GACF.DB", "a") as f:
            f.write(f"{new_username}:{new_password_hashed}:{new_privilege}:{new_omvs_flag}\n")
        current_users[new_username] = (new_password_hashed, new_privilege, new_omvs_flag)
        return f"User {new_username} added successfully."
    except Exception as e:
        logger.error("Error processing ADDUSER command: %s", e)
        return f"Error processing ADDUSER command: {e}"

def handle_altuser(cmd, current_users):
    try:
        tokens = cmd.split()
        if len(tokens) < 2:
            return "Error: ALTUSER command requires at least a username."
        username = tokens[1].strip().upper()
        if username not in current_users:
            return f"User {username} not found."
        current_pass, current_privilege, current_omvs = current_users[username]
        new_pass = None
        new_privilege = None
        new_omvs = None
        for token in tokens[2:]:
            if token.lower().startswith("pass(") and token.endswith(")"):
                new_pass = token[5:-1]
            elif token.upper() in ("SPECIAL", "NONE"):
                new_privilege = token.upper()
            elif token.upper() in ("OMVS", "NOOMVS"):
                new_omvs = token.upper()
        if new_pass is not None:
            if len(new_pass) > 8:
                return "Warning: Password can only be a max of 8 characters."
            new_pass_hashed = hash_password(new_pass)
        else:
            new_pass_hashed = current_pass
        if new_privilege is None:
            new_privilege = current_privilege
        if new_omvs is None:
            new_omvs = current_omvs
        with open("GACF.DB", "r") as f:
            lines = f.readlines()
        updated = False
        with open("GACF.DB", "w") as f:
            for line in lines:
                if line.strip().split(":")[0].strip().upper() == username:
                    f.write(f"{username}:{new_pass_hashed}:{new_privilege}:{new_omvs}\n")
                    updated = True
                else:
                    if not line.endswith("\n"):
                        line += "\n"
                    f.write(line)
        if not updated:
            return f"User {username} not found."
        current_users[username] = (new_pass_hashed, new_privilege, new_omvs)
        return f"User {username} updated successfully."
    except Exception as e:
        logger.error("Error processing ALTUSER command: %s", e)
        return f"Error processing ALTUSER command: {e}"

# -----------------------------
# ISPF IMPLEMENTATION
# -----------------------------
class Session:
    """
    Represents an interactive session for a connected user.
    Handles login, command processing, and session-specific actions.
    """
    def __init__(self, conn, addr, users):
        self.conn = conn
        self.addr = addr
        self.reader = conn.makefile("r", encoding="utf-8")
        self.users = users
        self.username = None
        self.privilege = None
        self.omvs_flag = None
        self.user_dir = None
        self.ftp_process = None
        self.session_log_file = None
        self.login_time = None         # Record login time
        self.command_count = 0         # Count commands executed
        self.command_history = []      # Command history for dashboard and autocomplete
        self.history_index = None
        self.help_commands = {
            "START": "Launches the ISPF menu.",
            "ISPF": "Launches the ISPF menu.",
            "EXIT": "Exits the session.",
            "LOGOFF": "Logs off the current user.",
            "CONSOLE": "Enters the system console mode (SPECIAL only).",
            "SDSF": "Displays the SDSF screen.",
            "OMVS": "Launches the OMVS shell.",
            "ADDUSER": "Adds a new user. Format: ADDUSER username pass(password) PRIVILEGE OMVSFLAG.",
            "ALTUSER": "Alters an existing user.",
            "IPLINFO": "Restricted command.",
            "SETROPTS LIST": "Displays system options (restricted).",
            "SEARCH CLASS(USER)": "Lists users with SPECIAL privileges.",
            "LISTCAT LEVEL(SYS1)": "Lists SYS1 level files.",
            "RACLIST": "Displays RACF profile details.",
            "LISTUSER": "Displays user details.",
            "SEND": "Sends a message to another user. Format: SEND 'message' USER(username) NOW|LOGON.",
            "EDIT": "Edits a file.",
            "REXX": "Executes a REXX script.",
            "LISTCAT": "Lists files in your directory.",
            "VIEW": "Views a file's content.",
            "CLEAR": "Clears the screen.",
            "IND$FILE": "Not implemented.",
            "DEL": "Deletes a file.",
            "SUBMIT": "Submits a JCL job.",
            "SESSIONSTATS": "Displays session statistics (login duration, command count).",
            "HELP": "Displays this help information.",
            "JES": "Simulated Job Entry Subsystem commands (e.g., JES STATUS, JES SUBMIT <job description>)."
        }
        self.available_commands = list(self.help_commands.keys())

    def log_command(self, cmd, outcome):
        now = datetime.now().strftime("%H:%M:%S")
        ip = self.addr[0]
        log_line = f"{ip}: {cmd} : {outcome} : {now}\n"
        if self.session_log_file:
            self.session_log_file.write(log_line)
            self.session_log_file.flush()
        logger.info("%s", log_line.strip())

    def send(self, s):
        self.conn.sendall(s.encode("utf-8"))

    def clear(self):
        clear_screen(self.conn)

    def send_ready_prompt(self):
        self.send("\nREADY\n")

    def reload_users(self):
        self.users = load_users()

    def has_full_access(self):
        if self.username.upper() in ("IBMUSER", "KEVIN"):
            return True
        return self.privilege.upper() == "SPECIAL"

    def get_command_file_content(self, filename):
        commands_dir = config["commands_dir"]  # Already expanded above
        file_path = os.path.join(commands_dir, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                content = universal_replace(content, self.username, self.privilege)
                return content
            except Exception as e:
                return f"Error reading {filename}: {e}\n"
        return None

    def show_file(self, filename):
        content = self.get_command_file_content(filename)
        if content is None:
            content = "Command file not found in restricted commands directory.\n"
        self.send("\n" + content + "\n")

    def read_password(self):
        self.send("\033[30m")
        password = self.reader.readline().rstrip("\n")
        self.send("\033[31m")
        return password.strip()

    def read_command(self):
        self.send("> ")
        buf = ""
        self.history_index = len(self.command_history)
        while True:
            try:
                ch = self.conn.recv(1).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if not ch:
                continue
            if ch in ("\r", "\n"):
                self.send("\n")
                break
            if ch in ("\x08", "\x7f"):
                if buf:
                    buf = buf[:-1]
                    self.send("\b \b")
                continue
            if ch == "\x1b":
                seq = self.conn.recv(2).decode("utf-8", errors="ignore")
                if seq == "[A":  # Up arrow
                    if self.history_index > 0:
                        self.history_index -= 1
                        buf = self.command_history[self.history_index]
                        self.send("\r" + " " * 80 + "\r> " + buf)
                    continue
                elif seq == "[B":  # Down arrow
                    if self.history_index < len(self.command_history) - 1:
                        self.history_index += 1
                        buf = self.command_history[self.history_index]
                        self.send("\r" + " " * 80 + "\r> " + buf)
                    else:
                        self.history_index = len(self.command_history)
                        buf = ""
                        self.send("\r" + " " * 80 + "\r> ")
                    continue
                else:
                    continue
            if ch == "\t":
                suggestions = [cmd for cmd in self.available_commands if cmd.startswith(buf.upper())]
                if suggestions:
                    if len(suggestions) == 1:
                        completion = suggestions[0]
                        extra = completion[len(buf):]
                        buf += extra
                        self.send(extra)
                    else:
                        self.send("\n" + " ".join(suggestions) + "\n> " + buf)
                continue
            buf += ch
            self.send(ch)
        if buf.strip():
            self.command_history.append(buf.strip())
        return buf.strip()

    def read_menu_choice(self):
        chars = []
        while True:
            r, _, _ = select.select([self.conn], [], [], 0.1)
            if r:
                c = self.conn.recv(1).decode("utf-8", errors="ignore")
                if not c:
                    continue
                if c == "\x1b":
                    r2, _, _ = select.select([self.conn], [], [], 0.05)
                    if r2:
                        seq = self.conn.recv(2).decode("utf-8", errors="ignore")
                        if seq == "OR":
                            return "\x1bOR"
                        else:
                            chars.append(c)
                            chars.extend(list(seq))
                            continue
                if c in ("\r", "\n"):
                    break
                else:
                    chars.append(c)
            else:
                continue
        return "".join(chars).strip()

    def list_all_users(self):
        users_sorted = sorted(self.users.items())
        output_lines = []
        detailed_template = (
            "USER={user}  NAME={user}           OWNER=#SYSPROG  CREATED=24.271\n"
            " DEFAULT-GROUP=SYS1     PASSDATE=25.020 PASS-INTERVAL= 30 PHRASEDATE=N/A\n"
            " ACCESS LEVEL={privilege}\n"
            " REVOKE DATE=NONE   RESUME DATE=NONE\n"
            " LAST-ACCESS=25.041/00:09:58\n"
            " CLASS AUTHORIZATIONS=NONE\n"
            " INSTALLATION-DATA=DEADLY DIGITS OF DEATH\n"
            " MODEL-NAME=IBMUSER\n"
            " LOGON ALLOWED   (DAYS)          (TIME)"
        )
        for username, (password, privilege, omvs_flag) in users_sorted:
            out = detailed_template.format(user=username, privilege=self.users[username][1])
            output_lines.append(out)
            output_lines.append("")
        page_size = 20
        line_count = 0
        for line in "\n".join(output_lines).split("\n"):
            self.send(line + "\n")
            line_count += 1
            if line_count >= page_size:
                self.send("Press Enter to continue...")
                self.reader.readline()
                line_count = 0

    def handle_listuser(self, cmd_input):
        detailed_template = (
            "USER={user}  NAME={user}           OWNER=#SYSPROG  CREATED=24.271\n"
            " DEFAULT-GROUP=SYS1     PASSDATE=25.020 PASS-INTERVAL= 30 PHRASEDATE=N/A\n"
            " ACCESS LEVEL={privilege}\n"
            " REVOKE DATE=NONE   RESUME DATE=NONE\n"
            " LAST-ACCESS=25.041/00:09:58\n"
            " CLASS AUTHORIZATIONS=NONE\n"
            " INSTALLATION-DATA=DEADLY DIGITS OF DEATH\n"
            " MODEL-NAME=IBMUSER\n"
            " LOGON ALLOWED   (DAYS)          (TIME)"
        )
        parts = cmd_input.split(maxsplit=1)
        if len(parts) == 1 or parts[1].strip() == "":
            username_requested = self.username
            output = detailed_template.format(user=username_requested, privilege=self.users[username_requested.upper()][1])
            self.send("\n" + output + "\n")
        elif parts[1].strip() == "*":
            self.list_all_users()
        else:
            username_requested = parts[1].strip().upper()
            if username_requested in self.users:
                output = detailed_template.format(user=username_requested, privilege=self.users[username_requested][1])
                self.send("\n" + output + "\n")
            else:
                self.send(f"User {username_requested} not found.\n")
        self.send_ready_prompt()

    def handle_ispf(self):
        self.clear()
        self.send("\nStarting ISPF session...\n")
        time.sleep(0.5)

    # pass Gibson’s job list so SDSF DA can render it
        run_ispf(self.conn, self.username, get_jobs=lambda: simulated_jobs)

        self.clear()
        self.send("\nReturning to mainframe...\n")
        time.sleep(0.5)
        self.send_ready_prompt()

    def ispf_menu(self):
        """Display and maintain the ISPF menu until an exit command is received."""
        while True:
            self.clear()
            if os.path.exists(config["ispf_file"]):
                try:
                    with open(config["ispf_file"], "r") as f:
                        content = f.read()
                except Exception:
                    content = "Error reading ispf.txt\n"
            else:
                content = "ispf.txt not found.\n"
            content = "\033[32m" + content
            now = datetime.now()
            content = content.replace("xxxxxxx", f"\033[37m{self.username}\033[32m")
            content = content.replace("DATE", f"\033[37m{now.strftime('%Y-%m-%d')}\033[32m")
            content = content.replace("TIME", f"\033[37m{now.strftime('%H:%M:%S')}\033[32m")
            content = universal_replace(content, self.username, self.privilege)
            self.clear()
            display_with_prompt(self.conn, content)
            choice = self.read_menu_choice()
            if choice.upper() in ("X", "EXIT", "\x1bOR", "F3"):
                break
            if self.process_command(choice) is False:
                break
        self.clear()
        self.send_ready_prompt()

    def handle_console(self):
        self.clear()
        self.send("CONSOLE\n")
        while True:
            self.send("CONSOLE> ")
            cmd = self.read_command()
            if cmd.upper() == "P FTD":
                cmd = "P FTPD"
            cmd_upper = cmd.upper()
            if self.username.upper() == "GUEST":
                if not (cmd_upper.startswith("LISTCAT") or cmd_upper.startswith("LISTUSER") or
                        cmd_upper == "LOGOFF" or cmd_upper.startswith("VIEW") or cmd_upper.startswith("HELP") or cmd_upper.startswith("SEND")):
                    self.send("Command not permitted for guest user.\n")
                    self.log_command(cmd, "denied")
                    continue
            outcome = "executed"
            try:
                if cmd_upper == "START":
                    self.ispf_menu()
                    return
                if cmd_upper == "END":
                    break
                elif cmd_upper == "DISPLAY TIME":
                    self.show_file("DT.TXT")
                elif cmd_upper == "DISPLAY IPLINFO":
                    self.show_file("DISPLAY IPLINFO")
                elif cmd_upper == "DISPLAY LOGGER":
                    self.show_file("DISPLAY LOGGER")
                elif cmd_upper == "DISPLAY SMS":
                    self.show_file("DISPLAY SMS")
                elif cmd_upper == "DISPLAY TCPIP":
                    self.show_file("DISPLAY TCPIP")
                elif cmd_upper == "DISPLAY A,L":
                    self.show_file("DAL.TXT")
                elif cmd_upper == "SETPROG APF,ADD,DSNAME=SYS1.VULNLIB,VOLUME=MVSRES1":
                    self.show_file("SETPROG APF,ADD,DSNAME=SYS1.VULNLIB,VOLUME=MVSRES1")
                elif cmd_upper == "HELP":
                    self.handle_help(cmd)
                elif cmd_upper == "S FTPD":
                    try:
                        self.ftp_process = subprocess.Popen(["python3", "gibftpmulti.py", "--ftp", "2111"])
                        time.sleep(0.5)
                        ftp_file = "ftp.txt"
                        if os.path.exists(ftp_file):
                            with open(ftp_file, "r") as f:
                                for line in f:
                                    self.send(line)
                                    time.sleep(0.5)
                        else:
                            self.send("ftp.txt file not found.\n")
                    except Exception as e:
                        self.send(f"Error starting FTP server: {e}\n")
                        outcome = "denied"
                elif cmd_upper == "P FTPD":
                    try:
                        if self.ftp_process is not None:
                            self.ftp_process.terminate()
                            self.ftp_process.wait()
                            self.ftp_process = None
                            ftpdown_file = "ftpdown.txt"
                            if os.path.exists(ftpdown_file):
                                with open(ftpdown_file, "r") as f:
                                    for line in f:
                                        self.send(line)
                                        time.sleep(0.2)
                            else:
                                self.send("ftpdown.txt file not found.\n")
                        else:
                            self.send("No FTP process is currently running.\n")
                    except Exception as e:
                        self.send(f"Error stopping FTP server: {e}\n")
                        outcome = "denied"
                elif cmd_upper == "DISPLAY PROG,APF":
                    self.show_file("DPROGAPF")
                    self.send_ready_prompt()
                elif cmd_upper.startswith("PING "):
                    parts = cmd.split()
                    if len(parts) >= 2:
                        ip_address = parts[1]
                        try:
                            result = subprocess.run(["ping", ip_address, "-c", "3"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                            self.send(result.stdout)
                            if result.stderr:
                                self.send(result.stderr)
                        except Exception as e:
                            self.send(f"Error executing ping: {e}\n")
                    else:
                        self.send("Usage: PING <ip address>\n")
                    self.send_ready_prompt()
                elif cmd_upper.startswith("SUBMIT"):
                    parts = cmd.split()
                    if len(parts) < 2:
                        self.send("Usage: SUBMIT (FILENAME).JCL\n")
                        self.send_ready_prompt()
                    else:
                        jcl_spec = parts[1]
                        if jcl_spec.upper() in ("(NEWCOMMAND).JCL", "NEWCOMMAND.JCL"):
                            newcmd_path = os.path.join(self.user_dir, "NEWCOMMAND.JCL")
                            if not os.path.exists(newcmd_path):
                                self.send("NEWCOMMAND.JCL not found in your directory.\n")
                            else:
                                try:
                                    with open(newcmd_path, "r") as f:
                                        for line in f:
                                            if ":" not in line:
                                                continue
                                            command_name, text_file = line.split(":", 1)
                                            command_name = command_name.strip()
                                            text_file = text_file.strip()
                                            source_path = os.path.join(self.user_dir, text_file)
                                            dest_dir = config["commands_dir"]
                                            if not os.path.exists(dest_dir):
                                                os.makedirs(dest_dir)
                                            dest_path = os.path.join(dest_dir, text_file)
                                            if os.path.exists(source_path):
                                                shutil.move(source_path, dest_path)
                                    self.send("New commands added successfully.\n")
                                except Exception as e:
                                    self.send(f"Error processing NEWCOMMAND.JCL: {e}\n")
                            self.send_ready_prompt()
                        else:
                            if jcl_spec.startswith("(") and jcl_spec.endswith(").JCL"):
                                filename = jcl_spec[1:-5]
                            elif jcl_spec.endswith(".JCL"):
                                filename = jcl_spec[:-4]
                            else:
                                self.send("Invalid JCL file format. Use SUBMIT (FILENAME).JCL\n")
                                self.send_ready_prompt()
                                return True
                            jcl_path = os.path.join(self.user_dir, filename + ".JCL")
                            if not os.path.exists(jcl_path):
                                self.send(f"JCL file {filename}.JCL not found in your directory.\n")
                                self.send_ready_prompt()
                                return True
                            try:
                                with open(jcl_path, "r") as f:
                                    lines = f.readlines()
                            except Exception as e:
                                self.send(f"Error reading JCL file: {e}\n")
                                self.send_ready_prompt()
                                return True
                            jobname = None
                            for line in lines:
                                if "JOBNAME" in line.upper():
                                    tokens = line.split()
                                    for i, token in enumerate(tokens):
                                        if token.upper() == "JOBNAME" and i+1 < len(tokens):
                                            jobname = tokens[i+1]
                                            break
                                    if jobname:
                                        break
                            if not jobname:
                                self.send("JOBNAME not found in the JCL file.\n")
                                self.send_ready_prompt()
                                return True
                            counter_file = "job_counter.txt"
                            try:
                                if os.path.exists(counter_file):
                                    with open(counter_file, "r") as cf:
                                        count = int(cf.read().strip())
                                else:
                                    count = 1
                            except Exception:
                                count = 1
                            job_number = f"JOB{count:05d}"
                            try:
                                with open(counter_file, "w") as cf:
                                    cf.write(str(count+1))
                            except Exception:
                                pass
                            self.send(f"Job {jobname} submitted as {job_number}\n")
                            simulated_jobs.append({
                                "job_number": job_number,
                                "jobname": jobname,
                                "submitted": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            self.send_ready_prompt()
                else:
                    self.send("not implemented yet\n")
            finally:
                self.log_command(cmd, outcome)
        self.clear()
        self.send_ready_prompt()

    def handle_edit(self, raw_cmd):
        parts = raw_cmd.split(maxsplit=1)
        if len(parts) == 2:
            filename = parts[1].strip()
            if (filename.startswith("'") and filename.endswith("'")) or (filename.startswith('"') and filename.endswith('"')):
                filename = filename[1:-1]
        else:
            self.send("Enter file name: ")
            filename = self.reader.readline().strip()
        filepath = os.path.join(self.user_dir, filename)
        self.clear()
        self.send(f"Editing {filename}\n")
        line_num = 10
        lines = []
        while True:
            prompt = f"{line_num} "
            self.send(prompt)
            input_line = self.reader.readline().rstrip("\n")
            if input_line == "":
                break
            else:
                lines.append(input_line)
                line_num += 10
        while True:
            self.send("Type SAVE to save file: ")
            cmd = self.reader.readline().strip().upper()
            if cmd == "SAVE":
                break
        while True:
            self.send("Type END to exit editor: ")
            cmd = self.reader.readline().strip().upper()
            if cmd == "END":
                break
        try:
            with open(filepath, "w") as f:
                f.write("\n".join(lines))
            listcat_path = os.path.join(self.user_dir, "LISTCAT")
            with open(listcat_path, "a") as f:
                f.write("\n" + filename)
            self.send(f"File {filename} saved successfully in your directory.\n")
        except Exception as e:
            self.send(f"Error saving file: {e}\n")
        self.send_ready_prompt()

    def handle_rexx(self, cmd_input):
        parts = cmd_input.split(" ", 1)
        if len(parts) < 2:
            self.send("Usage: REXX <filename>\n")
            return
        filename = parts[1].strip()
        script_path = os.path.join(self.user_dir, filename)
        if not os.path.exists(script_path):
            self.send(f"File {filename} not found in your directory.\n")
            return
        try:
            result = subprocess.run(["regina", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            self.send(output + "\n")
        except Exception as e:
            self.send(f"Error executing REXX script: {e}\n")

    def handle_listcat(self):
        try:
            files = os.listdir(self.user_dir)
            output_lines = [f"{self.username}.{file}" for file in files]
            listing = "\n".join(output_lines)
            self.send("\n" + listing + "\n")
        except Exception as e:
            self.send("Error listing catalog.\n")

    def handle_view(self, cmd_input):
        parts = cmd_input.split(" ", 1)
        if len(parts) < 2:
            self.send("Usage: VIEW <filename>\n")
            return
        filename = parts[1].strip()
        filepath = os.path.join(self.user_dir, filename)
        if not os.path.exists(filepath):
            self.send(f"File {filename} not found in your directory.\n")
            return
        try:
            with open(filepath, "r") as f:
                content = f.read()
            content = universal_replace(content, self.username, self.privilege)
            self.send("\n" + content + "\n")
        except Exception as e:
            self.send(f"Error reading file {filename}: {e}\n")

    def handle_omvs(self):
        if self.omvs_flag != "OMVS":
            self.send("ACCESS DENIED, INSUFFICIENT PRIVILEGES.\n")
            self.send_ready_prompt()
            return
        self.clear()
        self.send("\033[34m")
        os.environ["PS1"] = 'USS@:\\W\\ => '
        self.send("Entering OMVS shell (restricted). Type 'exit' to return to the mainframe.\n")
        pid, master_fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(self.user_dir)
            except Exception:
                pass
            os.execv("/bin/bash", ["/bin/bash", "--restricted"])
            os._exit(1)
        else:
            input_buffer = ""
            while True:
                r, _, _ = select.select([master_fd, self.conn], [], [], 1)
                try:
                    pid_status = os.waitpid(pid, os.WNOHANG)
                    if pid_status[0] != 0:
                        break
                except ChildProcessError:
                    break
                if self.conn in r:
                    data = self.conn.recv(1024)
                    if not data:
                        break
                    input_buffer += data.decode("utf-8", errors="ignore")
                    while "\n" in input_buffer:
                        line, input_buffer = input_buffer.split("\n", 1)
                        stripped_line = line.strip()
                        if stripped_line.upper().startswith("TSOCMD "):
                            if self.privilege.upper() == "NONE" and "RVARY" in stripped_line.upper():
                                self.send("\nINSUFFICIENT ACCESS.\n")
                            elif not self.has_full_access():
                                self.send("\nACCESS DENIED, INSUFFICIENT PRIVILEGES.\n")
                            else:
                                tso_command = stripped_line[7:].strip()
                                if tso_command.upper() == "RVARY":
                                    content = self.get_command_file_content("RVARY.TXT")
                                    if content:
                                        self.send(content + "\n")
                                    else:
                                        self.send("\n[RVARY not implemented]\n")
                                elif tso_command.upper() == "LISTUSER":
                                    parts = tso_command.split(maxsplit=1)
                                    if len(parts) == 1:
                                        detailed_template = (
                                            "USER={user}  NAME={user}           OWNER=#SYSPROG  CREATED=24.271\n"
                                            " DEFAULT-GROUP=SYS1     PASSDATE=25.020 PASS-INTERVAL= 30 PHRASEDATE=N/A\n"
                                            " ACCESS LEVEL={privilege}\n"
                                            " REVOKE DATE=NONE   RESUME DATE=NONE\n"
                                            " LAST-ACCESS=25.041/00:09:58\n"
                                            " CLASS AUTHORIZATIONS=NONE\n"
                                            " INSTALLATION-DATA=DEADLY DIGITS OF DEATH\n"
                                            " MODEL-NAME=IBMUSER\n"
                                            " LOGON ALLOWED   (DAYS)          (TIME)"
                                        )
                                        out = detailed_template.format(user=self.username, privilege=self.users[self.username.upper()][1])
                                        self.send("\n" + out + "\n")
                                    else:
                                        param = parts[1].strip()
                                        self.handle_listuser("LISTUSER " + param)
                                elif tso_command.upper() == "LISTCAT":
                                    self.handle_listcat()
                                elif tso_command.upper() == "SETROPTS LIST":
                                    if self.privilege.upper() == "SPECIAL":
                                        content = self.get_command_file_content("SETROPTS")
                                        if content:
                                            self.send(content + "\n")
                                        else:
                                            self.send("\n[SETROPTS LIST not implemented]\n")
                                    else:
                                        self.send("\nINSUFFICIENT ACCESS.\n")
                                else:
                                    self.send(f"\n[TSOCMD {tso_command} not recognized]\n")
                        else:
                            if stripped_line.lower().startswith("sudo"):
                                self.send("\nSudo is not allowed in OMVS shell.\n")
                                continue
                            os.write(master_fd, (line + "\n").encode("utf-8"))
                if master_fd in r:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    self.conn.sendall(data)
            try:
                os.waitpid(pid, 0)
            except Exception:
                pass
            self.send("\033[0m")
            self.send("\nExiting OMVS shell. Returning to mainframe...\n")
            time.sleep(1)
            self.send_ready_prompt()

    def handle_del(self, cmd_input):
        parts = cmd_input.split(maxsplit=1)
        if len(parts) < 2:
            self.send("Usage: DEL <filename>\n")
            return
        filename = parts[1].strip()
        file_path = os.path.join(self.user_dir, filename)
        if not os.path.exists(file_path):
            self.send(f"Error: File {filename} not found.\n")
            return
        try:
            os.remove(file_path)
            self.send(f"IDC0550I ENTRY {filename} SUCCESSFULLY DELETED\n")
        except Exception as e:
            self.send(f"Error deleting file {filename}: {e}\n")

    def handle_send(self, cmd_input):
        pattern = r"SEND\s+'([^']+)'\s+USER\(([^)]+)\)\s+(NOW|LOGON)"
        match = re.match(pattern, cmd_input, re.IGNORECASE)
        if not match:
            self.send("Invalid SEND command format. Usage: SEND 'message' USER(username) NOW|LOGON\n")
            return
        message = match.group(1)
        target = match.group(2).strip().upper()
        option = match.group(3).upper()
        if target not in self.users:
            self.send(f"Target user {target} does not exist.\n")
            return
        if option == "NOW":
            if target in active_sessions:
                active_sessions[target].send("\033[32m" + f"\nMessage from {self.username}: {message}\n")
                active_sessions[target].send("\033[31m")
                self.send(f"Message sent immediately to {target}.\n")
            else:
                self.send(f"User {target} is not currently logged in.\n")
        else:
            target_dir = os.path.join(config["base_dir"], target)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            pending_path = os.path.join(target_dir, "pending_messages.txt")
            try:
                with open(pending_path, "a") as pf:
                    pf.write(f"Message from {self.username}: {message}\n")
                self.send(f"Message queued for {target} on next logon.\n")
            except Exception as e:
                self.send(f"Error queuing message: {e}\n")

    def handle_help(self, cmd_input):
        parts = cmd_input.split(maxsplit=1)
        if len(parts) == 1:
            self.send("\nAvailable Commands:\n")
            for cmd, desc in self.help_commands.items():
                self.send(f"  {cmd}: {desc}\n")
            self.send("\nType HELP <command> for detailed info.\n")
        else:
            command = parts[1].strip().upper()
            if command in self.help_commands:
                self.send(f"\n{command}: {self.help_commands[command]}\n")
            else:
                self.send(f"\nNo help available for {command}\n")
        self.send_ready_prompt()

    def handle_jes(self, cmd_input):
        parts = cmd_input.split(maxsplit=2)
        if len(parts) < 2:
            self.send("Usage: JES STATUS or JES SUBMIT <job description>\n")
            self.send_ready_prompt()
            return
        action = parts[1].upper()
        if action == "STATUS":
            if simulated_jobs:
                self.send("\nSimulated JES Job Queue:\n")
                for job in simulated_jobs:
                    self.send(f"{job['job_number']} - {job['jobname']} submitted at {job['submitted']}\n")
            else:
                self.send("\nNo jobs in the JES queue.\n")
        elif action == "SUBMIT":
            if len(parts) < 3:
                self.send("Usage: JES SUBMIT <job description>\n")
            else:
                job_desc = parts[2]
                job_number = f"JOB{len(simulated_jobs)+1:05d}"
                job = {
                    "job_number": job_number,
                    "jobname": job_desc,
                    "submitted": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                simulated_jobs.append(job)
                self.send(f"Job submitted: {job_number} - {job_desc}\n")
        else:
            self.send("Unknown JES command. Use JES STATUS or JES SUBMIT <job description>\n")
        self.send_ready_prompt()

    def handle_cics(self):
        """Handle CICS session by calling the CICS module"""
        try:
            # Start CICS session
            self.clear()
            self.send("\nStarting CICS session...\n")
            time.sleep(1)

            # Call the CICS session handler
            CICS.start_cics_session(self.conn)

            # After CICS session ends
            self.clear()
            self.send("\nReturning to mainframe...\n")
            time.sleep(1)
            self.send_ready_prompt()
        except Exception as e:
            self.send(f"\nError starting CICS session: {e}\n")
            self.send_ready_prompt()

    def handle_sdsf(self):
        self.clear()
        sdsf_file = config["sdsf_file"]
        if os.path.exists(sdsf_file):
            try:
                with open(sdsf_file, "r") as f:
                    content = f.read()
            except Exception:
                content = "Error reading sdsf.txt\n"
        else:
            content = "sdsf.txt not found.\n"
        content = "\033[37m" + content
        content = universal_replace(content, self.username, self.privilege)
        display_with_prompt(self.conn, content)
        self.reader.readline()
        self.clear()
        self.send_ready_prompt()

    def process_command(self, cmd_input):
        self.command_count += 1  # Increment command count.
        outcome = "executed"
        try:
            self.reload_users()
            cmd_upper = cmd_input.upper()
            restricted_commands = ["RVARY", "ADDUSER", "ALTUSER", "CONSOLE", "IPLINFO", "SETROPTS LIST"]
            if self.privilege.upper() == "NONE":
                for rc in restricted_commands:
                    if cmd_upper.startswith(rc):
                        self.send("INSUFFICIENT ACCESS.\n")
                        self.log_command(cmd_input, "denied")
                        return True
            if self.username.upper() == "GUEST":
                if not (cmd_upper.startswith("LISTCAT") or cmd_upper.startswith("LISTUSER") or
                        cmd_upper == "LOGOFF" or cmd_upper.startswith("VIEW") or cmd_upper.startswith("HELP") or cmd_upper.startswith("SEND")):
                    self.send("Command not permitted for guest user.\n")
                    self.log_command(cmd_input, "denied")
                    return True
            if cmd_upper in ("START", "ISPF"):
                self.handle_ispf()
                return True
            if cmd_upper == "EXIT":
                self.send("Goodbye!\n")
                return False
            elif cmd_upper == "LOGOFF":
                self.send("Exiting Production Mainframe- ")
                for count in [3, 2, 1]:
                    self.send(f"{count}\n")
                    time.sleep(1)
                self.login()
            elif cmd_upper.startswith("CONSOLE"):
                if self.privilege.upper() == "SPECIAL":
                    self.handle_console()
                else:
                    self.send("INSUFFICIENT ACCESS.\n")
                    self.log_command(cmd_input, "denied")
                return True
            elif cmd_upper == "SDSF":
                self.handle_sdsf()
            elif cmd_upper == "ISPF":
                self.handle_ispf()  # Runs ISPF session
                return True         # ← Tells processor we handled this command
            elif cmd_upper == "OMVS":
                self.handle_omvs()
            elif cmd_upper.startswith("ADDUSER"):
                result = handle_adduser(cmd_input, self.users)
                self.send(result + "\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("ALTUSER"):
                result = handle_altuser(cmd_input, self.users)
                self.send(result + "\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("IPLINFO"):
                self.send("INSUFFICIENT ACCESS.\n")
                self.log_command(cmd_input, "denied")
                return True
            elif cmd_upper.startswith("SETROPTS LIST"):
                if self.privilege.upper() == "SPECIAL":
                    self.show_file("SETROPTS")
                    self.send("\n\n")
                    self.send_ready_prompt()
                else:
                    self.send("INSUFFICIENT ACCESS.\n")
                    self.log_command(cmd_input, "denied")
                    return True
            elif cmd_upper.startswith("SEARCH CLASS(USER)"):
                special_users = [username for username, rec in self.users.items() if rec[1].upper() == "SPECIAL"]
                response = "Special users:\n" + "\n".join(special_users) if special_users else "No special users found."
                self.send(response + "\n\n")
                self.send_ready_prompt()
            elif cmd_upper == "LISTCAT LEVEL(SYS1)":
                sys1_dir = config["base_dir"]
                try:
                    files = os.listdir(sys1_dir)
                    sys1_files = [f for f in files if f.upper().startswith("SYS1")]
                    if sys1_files:
                        output_lines = "\n".join(sys1_files)
                        self.send("\n" + output_lines + "\n")
                    else:
                        self.send("No SYS1 files found.\n")
                except Exception as e:
                    self.send("Error listing SYS1 directory.\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("RACLIST"):
                pattern = r"RACLIST\s+CLASS\(([^)]+)\)\s+ID\(([^)]+)\)(\s+DETAIL)?"
                match = re.search(pattern, cmd_input, re.IGNORECASE)
                if match:
                    rac_class = match.group(1).upper()
                    rac_id = match.group(2).strip().upper()
                    if rac_class == "USER":
                        if rac_id in self.users:
                            stored_pw, user_privilege, omvs_flag = self.users[rac_id]
                            ps_status = "ENCRYPTED" if is_hashed(stored_pw) else "CLEAR"
                            template = self.get_command_file_content("RACLIST.TXT")
                            if template is None:
                                self.send("RACLIST command template not found.\n")
                            else:
                                template = template.replace("{RACID}", rac_id)
                                template = template.replace("{PSSTATUS}", ps_status)
                                template = universal_replace(template, rac_id, user_privilege)
                                self.send(template)
                        else:
                            self.send(f"RACF profile for {rac_id} not found.\n")
                    else:
                        self.send(f"RACLIST for RACF class {rac_class} is not implemented.\n")
                else:
                    self.send("Invalid RACLIST command format. Usage: RACLIST CLASS(USER) ID(username) [DETAIL]\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("LISTUSER"):
                self.handle_listuser(cmd_input)
            elif cmd_upper.startswith("SEND"):
                self.handle_send(cmd_input)
                self.send_ready_prompt()
            elif cmd_upper.startswith("EDIT"):
                self.handle_edit(cmd_input)
            elif cmd_upper.startswith("REXX"):
                self.handle_rexx(cmd_input)
            elif cmd_upper == "LISTCAT":
                self.handle_listcat()
                self.send("\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("VIEW"):
                self.handle_view(cmd_input)
            elif cmd_upper == "CLEAR":
                self.clear()
                self.send_ready_prompt()
            elif cmd_upper.startswith("IND$FILE"):
                self.send("IND$FILE command not implemented yet.\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("DEL"):
                self.handle_del(cmd_input)
                self.send_ready_prompt()
            elif cmd_upper.startswith("SUBMIT"):
                parts = cmd_input.split()
                if len(parts) < 2:
                    self.send("Usage: SUBMIT (FILENAME).JCL\n")
                    self.send_ready_prompt()
                else:
                    jcl_spec = parts[1]
                    if jcl_spec.upper() in ("(NEWCOMMAND).JCL", "NEWCOMMAND.JCL"):
                        newcmd_path = os.path.join(self.user_dir, "NEWCOMMAND.JCL")
                        if not os.path.exists(newcmd_path):
                            self.send("NEWCOMMAND.JCL not found in your directory.\n")
                        else:
                            try:
                                with open(newcmd_path, "r") as f:
                                    for line in f:
                                        if ":" not in line:
                                            continue
                                        command_name, text_file = line.split(":", 1)
                                        command_name = command_name.strip()
                                        text_file = text_file.strip()
                                        source_path = os.path.join(self.user_dir, text_file)
                                        dest_dir = config["commands_dir"]
                                        if not os.path.exists(dest_dir):
                                            os.makedirs(dest_dir)
                                        dest_path = os.path.join(dest_dir, text_file)
                                        if os.path.exists(source_path):
                                            shutil.move(source_path, dest_path)
                                self.send("New commands added successfully.\n")
                            except Exception as e:
                                self.send(f"Error processing NEWCOMMAND.JCL: {e}\n")
                        self.send_ready_prompt()
                    else:
                        if jcl_spec.startswith("(") and jcl_spec.endswith(").JCL"):
                            filename = jcl_spec[1:-5]
                        elif jcl_spec.endswith(".JCL"):
                            filename = jcl_spec[:-4]
                        else:
                            self.send("Invalid JCL file format. Use SUBMIT (FILENAME).JCL\n")
                            self.send_ready_prompt()
                            return True
                        jcl_path = os.path.join(self.user_dir, filename + ".JCL")
                        if not os.path.exists(jcl_path):
                            self.send(f"JCL file {filename}.JCL not found in your directory.\n")
                            self.send_ready_prompt()
                            return True
                        try:
                            with open(jcl_path, "r") as f:
                                lines = f.readlines()
                        except Exception as e:
                            self.send(f"Error reading JCL file: {e}\n")
                            self.send_ready_prompt()
                            return True
                        jobname = None
                        for line in lines:
                            if "JOBNAME" in line.upper():
                                tokens = line.split()
                                for i, token in enumerate(tokens):
                                    if token.upper() == "JOBNAME" and i+1 < len(tokens):
                                        jobname = tokens[i+1]
                                        break
                                if jobname:
                                    break
                        if not jobname:
                            self.send("JOBNAME not found in the JCL file.\n")
                            self.send_ready_prompt()
                            return True
                        counter_file = "job_counter.txt"
                        try:
                            if os.path.exists(counter_file):
                                with open(counter_file, "r") as cf:
                                    count = int(cf.read().strip())
                            else:
                                count = 1
                        except Exception:
                            count = 1
                        job_number = f"JOB{count:05d}"
                        try:
                            with open(counter_file, "w") as cf:
                                cf.write(str(count+1))
                        except Exception:
                            pass
                        self.send(f"Job {jobname} submitted as {job_number}\n")
                        simulated_jobs.append({
                            "job_number": job_number,
                            "jobname": jobname,
                            "submitted": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        self.send_ready_prompt()
            elif cmd_upper.startswith("SESSIONSTATS"):
                duration = datetime.now() - self.login_time
                self.send(f"\nSession Statistics:\n  Login Time: {self.login_time.strftime('%Y-%m-%d %H:%M:%S')}\n  Duration: {str(duration).split('.')[0]}\n  Command Count: {self.command_count}\n")
                self.send_ready_prompt()
            elif cmd_upper.startswith("HELP"):
                self.handle_help(cmd_input)
            elif cmd_upper.startswith("JES"):
                self.handle_jes(cmd_input)
            else:
                commands_dir = config["commands_dir"]
                file_path = os.path.join(commands_dir, cmd_input)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r") as f:
                            response = f.read()
                    except Exception as e:
                        response = f"Error reading {cmd_input}\n"
                else:
                    response = f"Unknown command: {cmd_input}\n"
                response = universal_replace(response, self.username, self.privilege)
                self.send(response)
                self.send("\n\n")
                self.send_ready_prompt()
            return True
        finally:
            self.log_command(cmd_input, outcome)
        self.clear()
        self.send_ready_prompt()

    def login(self):
        # --- Brute Force / Enumeration Detection ---
        ip = self.addr[0]
        now_time = time.time()
        if ip not in login_attempts:
            login_attempts[ip] = []
        login_attempts[ip].append(now_time)
        # Keep only attempts within the last 15 seconds
        login_attempts[ip] = [t for t in login_attempts[ip] if now_time - t < 15]
        if len(login_attempts[ip]) > 3 and ip not in flagged_ips:
            flagged_ips.append(ip)
        # -----------------------------------------------
        display_login_screen(self.conn, self.addr[0])
        valid_types = {"L TSO", "LTSO", "L CICS", "LOGON APPLID(CICS)", "L DB2", "LDB2", "LOGON APPLID(TSO)"}
        self.send("Logon Type: ")
        logon_type = self.reader.readline().strip().upper()
        if logon_type not in valid_types:
            self.send("\nInvalid logon type. Please try again.\n")
            time.sleep(2)
            return self.login()

        if logon_type in {"L CICS", "LOGON APPLID(CICS)"}:
            # Directly start the external CICS session
            self.clear()
            self.send("Starting external CICS session...\n")
            self.handle_cics()
            return

        elif logon_type in {"L TSO", "LTSO", "LOGON APPLID(TSO)"}:
            self.clear()
            self.send("LOGON\n\nIKJ56700A ENTER USERID : ")
            username = self.reader.readline().strip().upper()
            self.reload_users()
            if username not in self.users:
                self.send(f"\nIKJ56420I USERID ({username}) NOT AUTHORIZED FOR TSO:- RE-ENTER -\n")
                time.sleep(2)
                return self.login()
            self.send(f"ENTER CURRENT PASSWORD FOR {username}-")
        else:
            self.clear()
            self.send("LOGON\n\nIKJ56700A ENTER USERID : ")
            username = self.reader.readline().strip().upper()
            self.reload_users()
            if username not in self.users:
                self.send("\nUSER DOES NOT EXIST\n")
                time.sleep(2)
                return self.login()
            self.send("Password: ")

        password = self.read_password()
        stored_pw, privilege, omvs_flag = self.users[username]
        if is_hashed(stored_pw):
            valid = check_password(password, stored_pw)
        else:
            valid = (password == stored_pw)
            if valid:
                new_hash = hash_password(password)
                stored_pw = new_hash
                self.users[username] = (stored_pw, privilege, omvs_flag)
                update_users_file(self.users)
        if not valid:
            self.send("\nPASSWORD INCORRECT\n")
            time.sleep(2)
            return self.login()
        if username in ("IBMUSER", "KEVIN"):
            privilege = "SPECIAL"
            omvs_flag = "OMVS"
        self.users[username] = (stored_pw, privilege.strip().upper(), omvs_flag.strip().upper())
        update_users_file(self.users)
        self.username = username
        self.privilege = privilege.strip().upper()
        self.omvs_flag = omvs_flag.strip().upper()
        base_dir = config["base_dir"]
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        self.user_dir = os.path.join(base_dir, self.username)
        if not os.path.exists(self.user_dir):
            os.makedirs(self.user_dir)
        if self.username == "GUEST" and "GUEST" not in self.users:
            guest_pass = hash_password("GUEST")
            self.users["GUEST"] = (guest_pass, "GUEST", "NOOMVS")
            update_users_file(self.users)
        session_log_name = f"{self.username}.3270SESSION.{datetime.now().strftime('%Y%m%d')}"
        self.session_log_file = open(os.path.join(self.user_dir, session_log_name), "a")
        active_sessions[self.username] = self
        self.login_time = datetime.now()  # record login time
        # Set connection status to active ("red") upon successful login.
        connection_status[self.addr[0]] = "red"
        self.show_tso_and_welcome()

    def show_tso_and_welcome(self):
        if os.path.exists(config["tso_logon_file"]):
            try:
                with open(config["tso_logon_file"], "r") as f:
                    content = f.read()
            except Exception:
                content = ""
            self.clear()
            content = "\033[37m" + content
            content = content.replace("ACCT#", "\033[31mACCT#\033[37m")
            content = content.replace("xxxxxxx", "\033[34m" + self.username + "\033[37m")
            content = universal_replace(content, self.username, self.privilege)
            self.send(content)
            r, _, _ = select.select([self.conn], [], [], 5)
            if r:
                self.reader.readline()
        if os.path.exists(config["welcome_file"]):
            try:
                with open(config["welcome_file"], "r") as f:
                    content = f.read()
            except Exception:
                content = ""
            now = datetime.now()
            content = content.replace("xxxxxx", self.username)
            content = content.replace("DATE", now.strftime("%Y-%m-%d"))
            content = content.replace("TIME", now.strftime("%H:%M:%S"))
            content = "\033[31m" + content
            content = universal_replace(content, self.username, self.privilege)
            lines = content.splitlines()
            self.clear()
            if lines:
                self.send(lines[0] + "\n")
            time.sleep(3)
            self.clear()
            remaining = "\n".join(lines[1:]) if len(lines) > 1 else ""
            self.send(remaining + "\n\n")
        self.send_ready_prompt()
        pending_path = os.path.join(self.user_dir, "pending_messages.txt")
        if os.path.exists(pending_path):
            try:
                with open(pending_path, "r") as pf:
                    pending_message = pf.read()
                self.send("\033[32m" + "\n*** You have new messages: ***\n" + pending_message + "\n")
                os.remove(pending_path)
            except Exception:
                pass
            self.send("\033[31m")
            self.send_ready_prompt()

    def run(self):
        self.login()
        try:
            while True:
                cmd_input = self.read_command()
                if not cmd_input:
                    continue
                logger.debug("%s@%s: %s", self.username, self.addr[0], cmd_input)
                if not self.process_command(cmd_input):
                    break
        finally:
            if self.username in active_sessions:
                del active_sessions[self.username]
            if self.session_log_file:
                self.session_log_file.close()
            # Mark the connection as disconnected ("green")
            connection_status[self.addr[0]] = "green"

# -----------------------------
# MAINFRAME SIMULATOR CLASS
# -----------------------------
class MainframeSimulator:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.users = load_users()
        self.logger = logger

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"I3M Gibson g/OS 0.3.2 listening on {self.host}:{self.port}")
            while True:
                client_conn, client_addr = server_socket.accept()
                self.logger.info(f"Connection from {client_addr}")
                session = Session(client_conn, client_addr, self.users)
                client_thread = threading.Thread(target=session.run)
                client_thread.daemon = True
                client_thread.start()

# -----------------------------
# WEB DASHBOARD CODE
# -----------------------------
class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # HTTP Basic Authentication
            auth_header = self.headers.get('Authorization')
            dashboard_user = config.get("dashboard_username")
            dashboard_pass = config.get("dashboard_password")
            expected_auth = "Basic " + base64.b64encode(f"{dashboard_user}:{dashboard_pass}".encode("utf-8")).decode("utf-8")
            if auth_header != expected_auth:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="I3M Gibson Dashboard"')
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Authentication required.")
                return

            # ----------------------
            # Calculate System Metrics
            # ----------------------
            cpu_util = psutil.cpu_percent(interval=1)
            net_io = psutil.net_io_counters(pernic=True)
            eth0_packet_count = (net_io['eth0'].packets_recv + net_io['eth0'].packets_sent) if 'eth0' in net_io else 'N/A'

            def is_port_active(port):
                for conn in psutil.net_connections():
                    if conn.status == 'LISTEN' and conn.laddr.port == port:
                        return True
                return False

            active_2023 = is_port_active(2023)
            if is_port_active(21):
                ftp_port = 21
            elif is_port_active(2111):
                ftp_port = 2111
            else:
                ftp_port = None
            active_8080 = is_port_active(8443)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # Take snapshots of session data for thread-safe iteration
            sessions_snapshot = list(active_sessions.items())
            conn_status_snapshot = connection_status.copy()

            total_users = len(load_users())
            active_count = len(active_sessions)

            # ----------------------
            # Build HTML for the dashboard.
            # ----------------------
            html = f"""
<html>
<head>
  <meta http-equiv="refresh" content="20">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css" integrity="sha256-kLaT2GOSpHechhsozzB+flnD+zUyjE2LlfWPgU04xyI=" crossorigin=""/>
  <style>
    body {{
      background-color: black;
      color: green;
      font-family: monospace;
      margin: 0;
      padding: 0;
    }}
    .container {{
      display: flex;
      flex-wrap: wrap;
    }}
    .left-column {{
      width: 50%;
      padding: 10px;
      box-sizing: border-box;
    }}
    .right-column {{
      width: 50%;
      padding: 10px;
      box-sizing: border-box;
    }}
    .user-panel {{
      border: 1px solid green;
      margin-bottom: 10px;
      padding: 10px;
    }}
    .special {{
      color: red;
    }}
    .home-network {{
      color: yellow;
    }}
    pre {{
      background-color: #111;
      padding: 10px;
    }}
    .status-dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 5px;
    }}
    .active {{
      background-color: red;
      animation: flash 1s infinite;
    }}
    .inactive {{
      background-color: green;
    }}
    @keyframes flash {{
      0% {{ opacity: 1; }}
      50% {{ opacity: 0.5; }}
      100% {{ opacity: 1; }}
    }}
    .map-dot {{
      width: 15px;
      height: 15px;
      background: red;
      border-radius: 50%;
      opacity: 0.8;
      animation: pulse 1s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.8); opacity: 0.8; }}
      50% {{ transform: scale(1.5); opacity: 0.2; }}
      100% {{ transform: scale(0.8); opacity: 0.8; }}
    }}
  </style>
  <title>eZmainframe Dashboard</title>
</head>
<body>
  <div id="mapid" style="height: 300px; width: 100%;"></div>
  <div class="container">
    <div class="left-column">
      <h2>Active Users</h2>
"""
            # Left column: Active sessions list
            for username, session in sessions_snapshot:
                panel_class = "user-panel special" if session.privilege and session.privilege.upper() == "SPECIAL" else "user-panel"
                commands = session.command_history[-10:]
                command_history_html = "<br>".join(commands) if commands else "No commands executed."
                client_ip = session.addr[0]
                if client_ip.startswith("192.") or client_ip.startswith("127."):
                    ip_display = "Latitude: 27.4705 Longitude: 153.0260 Edinburgh, UK"
                else:
                    ip_display = client_ip
                duration = datetime.now() - session.login_time if session.login_time else "N/A"
                duration_str = str(duration).split('.')[0]
                status = connection_status.get(client_ip, "green")
                dot_class = "active" if status == "red" else "inactive"
                html += f"""
      <div class="{panel_class}">
        <strong>{username}</strong><br>
        Logged in at: {session.login_time.strftime('%Y-%m-%d %H:%M:%S')}<br>
        Duration: {duration_str}<br>
        <span class="status-dot {dot_class}"></span> IP: {ip_display}<br>
        <h4>Last 10 Commands:</h4>
        <pre>{command_history_html}</pre>
      </div>
"""
            html += """
    </div>
    <div class="right-column">
      <h2>Logs and Submitted Jobs</h2>
"""
            # Right column: User stats and system metrics
            html += f"""
      <h3>User Statistics</h3>
      <p>Total Users: {total_users}</p>
      <p>Logged In: {active_count}</p>
      <h3>System Metrics</h3>
      <p>CPU Utilization: {cpu_util}%</p>
      <p>eth0 Packet Count: {eth0_packet_count}</p>
"""
            if active_2023:
                html += """
      <p class="home-network">Gibson Mainframe Active on port 2023</p>
"""
            if ftp_port is not None:
                html += f"""
      <p class="home-network">FTP ACTIVE on port {ftp_port}</p>
"""
            if active_8080:
                html += """
      <p class="home-network">Gibson Active on port 8443</p>
"""
            html += """
      <h3>Submitted Jobs</h3>
      <ul>
"""
            if simulated_jobs:
                for job in simulated_jobs:
                    html += f"<li>{job['job_number']} - {job['jobname']} submitted at {job['submitted']}</li>"
            else:
                html += "<li>No submitted jobs.</li>"
            html += """
      </ul>
      <h3>Connection Status</h3>
      <ul>
"""
            for ip, status in conn_status_snapshot.items():
                if ip.startswith("192.") or ip.startswith("127."):
                    geo = "Latitude: 27.4705 Longitude: 153.0260 Edinburgh, UK"
                else:
                    geo = ip
                dot_class = "active" if status == "red" else "inactive"
                html += f"<li><span class='status-dot {dot_class}'></span> {geo}</li>"
            html += """
      <h3>Recent Log Entries</h3>
      <pre>
"""
            try:
                with open(config["log_file"], "r") as f:
                    lines = f.readlines()[-20:]
                    html += "".join(lines)
            except Exception as e:
                html += f"Error reading log file: {e}"
            html += """
      </pre>
    </div>
  </div>
"""
            # Determine coordinates for active connections
            coords = []
            for ip, status in conn_status_snapshot.items():
                if status == "red":
                    if ip not in ip_locations or ip_locations[ip] is None:
                        try:
                            if ip.startswith("192.") or ip.startswith("10.") or ip.startswith("127.") or ip.startswith("172."):
                                ip_locations[ip] = (55.9029, -3.5226)
                            else:
                                url = f"http://ip-api.com/json/{ip}"
                                with subprocess.Popen(["curl", "-s", url], stdout=subprocess.PIPE) as proc:
                                    data = proc.stdout.read().decode("utf-8", errors="ignore")
                                info = json.loads(data) if data else {}
                                if info.get("status") == "success":
                                    lat = info.get("lat")
                                    lon = info.get("lon")
                                    ip_locations[ip] = (lat, lon) if lat is not None and lon is not None else None
                                else:
                                    ip_locations[ip] = None
                        except Exception as e:
                            logger.error("Geo lookup failed for %s: %s", ip, e)
                            ip_locations[ip] = None
                    if ip in ip_locations and ip_locations[ip] is not None:
                        lat, lon = ip_locations[ip]
                        coords.append([lat, lon])
            coords_list = coords
            html += f"""
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js" integrity="sha256-WBkoXOwTeyKclOHuWtc+i2uENFpDZ9YPdf5Hf+D7ewM=" crossorigin=""></script>
  <script>
    var map = L.map('mapid');
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
    var coords = {coords_list};
    if (coords.length === 1) {{
      map.setView(coords[0], 4);
    }} else if (coords.length > 1) {{
      map.fitBounds(coords);
    }} else {{
      map.setView([20, 0], 2);
    }}
    for (var i = 0; i < coords.length; i++) {{
      L.marker(coords[i], {{
        icon: L.divIcon({{
          className: 'map-dot',
          html: '<div></div>',
          iconSize: [15,15],
          iconAnchor: [7.5,7.5]
        }})
      }}).addTo(map);
    }}
  </script>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))
        except Exception as e:
            logger.error("Error in WebDashboardHandler: %s", e)

def start_web_dashboard():
    try:
        dashboard_port = config.get("web_dashboard_port", 8443)
        server = HTTPServer((config["host"], dashboard_port), WebDashboardHandler)
        logger.info("Web dashboard started on port %s", dashboard_port)
        server.serve_forever()
    except Exception as e:
        logger.error("Web dashboard error: %s", e)


# -----------------------------
# MAIN ENTRY POINT
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="I3M Gibson Simulator")
    parser.add_argument("--port", "-p", type=int, default=config["port"],
                        help="Port to listen on (default from config)")
    args = parser.parse_args()
    # Start the web dashboard in a separate thread.
    dashboard_thread = threading.Thread(target=start_web_dashboard, daemon=True)
    dashboard_thread.start()
    simulator = MainframeSimulator(config["host"], args.port)
    simulator.start()

if __name__ == "__main__":
    main()

# ----------------------------------------------------------------
# Override so that ISPFSession is the enhanced one from ispf.py
# ----------------------------------------------------------------
ISPFSession = ispf.ISPFSession
