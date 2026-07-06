from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, Optional
import json
import os
import fnmatch
from datetime import datetime
import posixpath
import shlex
import subprocess
import sys
import shutil
import re
import platform

from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.editor import InteractiveEditor
from gibson.render import colors
from gibson.apps.uss_network_clients import GibsonFtpClient, GibsonTelnetClient
from gibson.apps.cti_rss import rss_command, run_cti_rss_interactive
from gibson.tools.omvs_nmap import run_omvs_nmap
from gibson.tools.host_aliases import hosts_command
from gibson.tools.omvs_cicspwn import run_omvs_cicspwn
from gibson.apps.omvs_lynx import lynx_command, run_lynx_interactive
from gibson.tools import safe_http
from gibson.tools.omvs_passticket import genptkt_command, unmaskptkt_command, parseptkt_command
from gibson.tools.racf2john_sim import racf2john_command, john_command
from gibson.apps.msfconsole_sim import run_msfconsole_sim, run_msfvenom_sim, run_msfconsole_interactive
from gibson.tools.omvs_security_tools import subfinder_command, shodan_command, geoloc_command, nikto_command, db2connect_command, task_command, tshocker_command, ezrecon_command
from gibson.core.net_tools import (dig_command, whois_command, nslookup_command,
                                   host_command, ping_command, traceroute_command)


def _omvs_password_prompt(text: str) -> bool:
    """True if OMVS output is requesting a password, so the next line-mode read
    should be hidden (mask the password)."""
    if not text:
        return False
    lines = text.rstrip().splitlines()
    last = lines[-1].strip().lower() if lines else ""
    return (last.endswith("password:") or last.endswith("password :")
            or "send password" in last or last == "password"
            or last.endswith("passphrase:") or last.endswith("password?")
            or last.startswith("331 ") or "enter password" in last)


@dataclass
class OmvsIdentity:
    userid: str
    uid: int
    gid: int
    home: str
    program: str = "/bin/sh"
    superuser: bool = False

    @property
    def prompt_char(self) -> str:
        return "#" if self.superuser else "$"


class ExtAttrStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        self.data = {str(k): "".join(sorted(set(str(v)))) for k, v in dict(raw).items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, relpath: str) -> str:
        return self.data.get(relpath, "")

    def set(self, relpath: str, flags: str) -> None:
        flags = "".join(sorted(set(flags)))
        if flags:
            self.data[relpath] = flags
        else:
            self.data.pop(relpath, None)
        self.save()

    def update_flags(self, relpath: str, op: str, flags: str) -> str:
        current = set(self.data.get(relpath, ""))
        if op == "+":
            current.update(flags)
        else:
            current.difference_update(flags)
        merged = "".join(sorted(current))
        self.set(relpath, merged)
        return merged


class OmvsEnvironment:
    """Compatibility-preserving USS filesystem facade for Gibson."""

    def __init__(self, state: GibsonState):
        self.state = state
        self.root = state.config.sim_root / "uss"
        self.extattrs = ExtAttrStore(state.config.sim_root / "uss_extattrs.json")
        self._bootstrap_site()

    def _bootstrap_site(self) -> None:
        for rel in ["u", "tmp", "var/tmp", "etc", "usr/lpp/IBM/zoau/bin", "usr/lpp/IBM/cyp/v3r11/pyz/bin"]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        self._write_if_missing(
            self.root / "etc" / "profile",
            "# Gibson USS global profile\n"
            "export _BPXK_AUTOCVT=ON\n"
            "export LANG=C\n"
            "export PATH=/bin:/usr/sbin:/usr/lpp/IBM/zoau/bin:/usr/lpp/IBM/cyp/v3r11/pyz/bin\n"
            "export PS1='$LOGNAME:$PWD$ '\n",
        )
        self._write_if_missing(
            self.root / "etc" / "motd",
            "GIBSON z/OS UNIX System Services\nAuthorized classroom simulation system.\n",
        )

    def _write_if_missing(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text, encoding="utf-8")

    def identity_for(self, userid: str, superuser: bool = False) -> OmvsIdentity:
        userid_u = userid.upper()
        # Stable deterministic UID/GID values without changing legacy GACF.DB format.
        base = sum(ord(c) for c in userid_u) % 50000
        uid = 0 if superuser else 10000 + base
        gid = 0 if superuser else 200 + (base % 200)
        home = "/" if superuser else f"/u/{userid_u.lower()}"
        return OmvsIdentity(userid_u if not superuser else "ROOT", uid, gid, home)

    def ensure_user_profile(self, userid: str) -> Path:
        home = self.real_path(f"/u/{userid.lower()}")
        home.mkdir(parents=True, exist_ok=True)
        self._write_if_missing(
            home / ".profile",
            f"# Gibson user profile for {userid.upper()}\n"
            f"export HOME=/u/{userid.lower()}\n"
            f"export LOGNAME={userid.upper()}\n"
            f"export USER={userid.upper()}\n"
            "export _BPXK_AUTOCVT=ON\n"
            "export PATH=/bin:/usr/sbin:/usr/lpp/IBM/zoau/bin:/usr/lpp/IBM/cyp/v3r11/pyz/bin\n",
        )
        self._write_if_missing(home / "README", "Gibson USS home directory\n")
        return home

    def real_path(self, virtual_path: str) -> Path:
        clean = posixpath.normpath(virtual_path)
        if not clean.startswith("/"):
            clean = "/" + clean
        rel = clean.lstrip("/")
        real = (self.root / rel).resolve()
        root_resolved = self.root.resolve()
        if root_resolved not in real.parents and real != root_resolved:
            raise PermissionError("PATH ESCAPES USS ROOT")
        return real

    def virtual_path(self, path: Path) -> str:
        root_resolved = self.root.resolve()
        real = path.resolve()
        rel = real.relative_to(root_resolved)
        return "/" + str(rel).replace(os.sep, "/") if str(rel) != "." else "/"

    def resolve(self, cwd: str, operand: str) -> str:
        if not operand:
            return cwd
        if operand.startswith("/"):
            return posixpath.normpath(operand)
        return posixpath.normpath(posixpath.join(cwd, operand))

    def dsfs_exists(self, virtual_path: str) -> bool:
        try:
            return self._dsfs_stat(virtual_path) is not None
        except Exception:
            return False

    def _dsfs_stat(self, virtual_path: str):
        p = PurePosixPath(posixpath.normpath(virtual_path))
        parts = p.parts
        if parts[:2] == ("/", "dsfs"):
            if len(parts) == 2:
                return {"type": "dir", "entries": [u.userid.lower() for u in self.state.racf.users.values()] + ["sysout"]}
            if len(parts) >= 3 and parts[2] == "sysout":
                if len(parts) == 3:
                    jobs = [j.job_id for j in self.state.jes.list_jobs()]
                    return {"type": "dir", "entries": jobs}
                jobid = parts[3].upper()
                for job in self.state.jes.list_jobs():
                    if job.job_id.upper() == jobid:
                        return {"type": "file", "text": f"{job.job_id} {job.jobname}\n{job.output}\n"}
                return None
            userid = parts[2].upper()
            if not self.state.racf.exists(userid):
                return None
            if len(parts) == 3:
                prefix = userid + "."
                entries: set[str] = set()
                for info in self.state.datasets.listcat(userid):
                    suffix = info.name[len(prefix):] if info.name.startswith(prefix) else info.name
                    head = suffix.split(".", 1)[0].lower()
                    entries.add(head)
                return {"type": "dir", "entries": sorted(entries)}
            dsname = userid + "." + ".".join(part.upper() for part in parts[3:])
            try:
                text = self.state.datasets.read(userid, dsname)
                real = self.state.datasets.ds_path(userid, dsname)
                return {"type": "dir" if real.is_dir() else "file", "text": text if not real.is_dir() else None, "entries": text.splitlines() if real.is_dir() else None}
            except FileNotFoundError:
                return None
        return None

    def exists(self, virtual_path: str) -> bool:
        if virtual_path.startswith("/dsfs"):
            return self.dsfs_exists(virtual_path)
        return self.real_path(virtual_path).exists()

    def is_dir(self, virtual_path: str) -> bool:
        if virtual_path.startswith("/dsfs"):
            stat = self._dsfs_stat(virtual_path)
            return bool(stat and stat.get("type") == "dir")
        return self.real_path(virtual_path).is_dir()

    def listdir(self, virtual_path: str) -> list[str]:
        if virtual_path.startswith("/dsfs"):
            stat = self._dsfs_stat(virtual_path)
            if not stat or stat.get("type") != "dir":
                raise FileNotFoundError(virtual_path)
            entries = stat.get("entries") or []
            return sorted(entries)
        real = self.real_path(virtual_path)
        if not real.is_dir():
            raise NotADirectoryError(virtual_path)
        return sorted(p.name for p in real.iterdir())

    def read_text(self, virtual_path: str) -> str:
        if virtual_path.startswith("/dsfs"):
            stat = self._dsfs_stat(virtual_path)
            if not stat:
                raise FileNotFoundError(virtual_path)
            if stat.get("type") == "dir":
                return "\n".join(stat.get("entries") or [])
            return str(stat.get("text") or "")
        return self.real_path(virtual_path).read_text(encoding="utf-8", errors="ignore")

    def write_text(self, virtual_path: str, text: str) -> None:
        if virtual_path.startswith("/dsfs"):
            raise PermissionError("DSFS view is read-only; use OPUT/OCOPY")
        real = self.real_path(virtual_path)
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text(text, encoding="utf-8")

    def write_bytes(self, virtual_path: str, data: bytes) -> None:
        if virtual_path.startswith("/dsfs"):
            raise PermissionError("DSFS view is read-only; use OPUT/OCOPY")
        real = self.real_path(virtual_path)
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_bytes(data)

    def read_bytes(self, virtual_path: str) -> bytes:
        return self.real_path(virtual_path).read_bytes()

    def rel_for_attr(self, virtual_path: str) -> Optional[str]:
        if virtual_path.startswith("/dsfs"):
            return None
        return self.resolve("/", virtual_path).lstrip("/")

    def attr_string(self, virtual_path: str) -> str:
        rel = self.rel_for_attr(virtual_path)
        stored = self.extattrs.get(rel) if rel is not None else ""
        if "E" not in stored and not virtual_path.startswith("/dsfs"):
            real = self.real_path(virtual_path)
            try:
                text = real.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            if real.suffix in {".sh", ".py", ".rexx"} or text.startswith("#!"):
                stored = "".join(sorted(set(stored + "E")))
        return stored


class OmvsShellSession:
    def __init__(self, state: GibsonState, userid: str, processor: Optional[TsoCommandProcessor] = None, mode: str = "OMVS"):
        self.state = state
        self.env = OmvsEnvironment(state)
        self.real_userid = userid.upper()
        self.mode = mode.upper()
        self.processor = processor or TsoCommandProcessor(state, self.real_userid)
        self.identity = self.env.identity_for(self.real_userid)
        self.cwd = self.identity.home
        self.history: list[str] = []
        self.file_meta: Dict[str, Dict[str, str]] = {}
        self.ftp_client = GibsonFtpClient()
        self.telnet_client = GibsonTelnetClient()
        self.msf = None  # MsfConsoleSim when the user is inside the msfconsole REPL
        self.environment: Dict[str, str] = {
            "HOME": self.identity.home,
            "LOGNAME": self.real_userid,
            "USER": self.real_userid,
            "PWD": self.cwd,
            "HOSTNAME": state.network.hostname,
            "SHELL": self.identity.program,
            "TERM": "xterm-3270" if self.mode == "OMVS3270" else "xterm",
            "LANG": "C",
            "_BPXK_AUTOCVT": "ON",
            "PATH": "/bin:/usr/sbin:/usr/lpp/IBM/zoau/bin:/usr/lpp/IBM/cyp/v3r11/pyz/bin",
        }
        self.env.ensure_user_profile(self.real_userid)

    def banner(self) -> str:
        profile = self.env.read_text("/etc/motd").rstrip("\n")
        mode = "OMVS/3270" if self.mode == "OMVS3270" else "USS/TTY"
        return colors.CLEAR + colors.BLUE + profile + colors.RESET + f"\nSession type: {mode}\n"

    def prompt(self) -> str:
        path = self.environment.get("PWD", self.cwd)
        return colors.WHITE + f"{self.environment.get('LOGNAME', self.real_userid)}:{path}{self.identity.prompt_char} " + colors.RESET

    def pf6_ready(self) -> bool:
        return self.mode == "OMVS3270"

    def shell_prompt(self) -> str:
        """Plain (non-ANSI) prompt for the 3270 scroll panel, msf-aware."""
        if self.msf is not None:
            return self.msf.prompt().rstrip()
        return f"{self.cwd} $"

    def _read_line_result(self, io_or_reader, prompt: str, hidden: bool = False):
        if hasattr(io_or_reader, "read_line"):
            return io_or_reader.read_line(prompt, hidden=hidden, mask=hidden)
        return io_or_reader(prompt, hidden)

    def run_interactive(self, io_or_reader, writer: Callable[[str], None]) -> None:
        self._interactive_io = io_or_reader if hasattr(io_or_reader, "read_key") else None
        writer(self.banner())
        next_hidden = False
        while True:
            result = self._read_line_result(io_or_reader, self.prompt(), next_hidden)
            key = getattr(result, "key", "")
            text = getattr(result, "text", "")
            if key == "EOF":
                return
            if key and key.upper() in {"PF6", "F6"} and self.pf6_ready():
                writer(colors.BLUE + "Returning to TSO READY.\n" + colors.RESET)
                return
            cmd = text.strip()
            if not cmd:
                next_hidden = False
                continue
            if self._handle_interactive_command(cmd, io_or_reader, writer):
                next_hidden = False
                continue
            outcome = self.execute(cmd)
            if outcome is None:
                return
            if outcome:
                writer(outcome.rstrip("\n") + "\n")
            # if the program is now asking for a password, hide the next input
            next_hidden = _omvs_password_prompt(outcome or "")

    def execute(self, raw: str) -> Optional[str]:
        self.history.append(raw)
        # msfconsole REPL sub-mode: while active, every line goes to the msf
        # simulator until the user exits it (exit/quit/back).
        if self.msf is not None:
            out = self.msf.one((raw or "").strip())
            if out == "__EXIT__":
                self.msf = None
                return ""
            return out
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            return f"FSUM7332 syntax error: {exc}"
        if not argv:
            return ""
        cmd = argv[0]
        lower = cmd.lower()
        if self._is_help_request(argv):
            return self._command_help(lower)
        if lower in {"exit", "logout", "quit"}:
            return None
        if lower in {"pf6", "f6"} and self.pf6_ready():
            return None
        if lower == "help":
            return self._help() if len(argv) == 1 else self._command_help(argv[1].lower())
        if lower in {"whatis", "apropos"}:
            return self._apropos(argv[1:] if len(argv) > 1 else [], whatis=(lower == "whatis"))
        if lower == "ftp":
            return self.ftp_client.run_one(argv[1:])
        if lower == "telnet":
            return self.telnet_client.run_one(argv[1:])
        if lower == "nmap":
            return run_omvs_nmap(argv[1:], self.env, self.cwd)
        if lower == "hosts":
            return hosts_command(self.env, self.cwd, argv[1:])
        if lower in {"cicspwn", "pwnprobe"}:
            return run_omvs_cicspwn(argv[1:], self.env, self.cwd)
        if lower in {"cicsshell", "cics-shell"}:
            from gibson.tools.cics_shell import run_cics_shell
            return run_cics_shell(self.state, argv[1:], self.env, self.cwd)
        if lower in {"msfconsole", "msfconsole-sim", "msf6"}:
            # `msfconsole -x ...` stays one-shot; a bare invocation drops into
            # the interactive msf6 REPL (handled line-by-line via self.msf).
            if argv[1:] and argv[1] == "-x":
                return run_msfconsole_sim(self.state, argv[1:], self.env, self.cwd)
            from gibson.apps.msfconsole_sim import MsfConsoleSim
            self.msf = MsfConsoleSim(self.state, env=self.env, cwd=self.cwd)
            return self.msf.banner().rstrip("\n")
        if lower in {"msfvenom", "msfvenom-sim"}:
            return run_msfvenom_sim(self.env, self.cwd, argv[1:])
        if lower in {"rss", "cti-rss"}:
            return rss_command(self.state, self.real_userid, lower + " " + " ".join(argv[1:]))
        if lower == "subfinder":
            return subfinder_command(self.env, self.cwd, argv[1:])
        if lower == "dig":
            return dig_command(self.env, self.cwd, argv[1:])
        if lower == "whois":
            return whois_command(self.env, self.cwd, argv[1:])
        if lower == "nslookup":
            return nslookup_command(self.env, self.cwd, argv[1:])
        if lower == "host":
            return host_command(self.env, self.cwd, argv[1:])
        if lower == "shodan":
            return shodan_command(self.env, self.cwd, argv[1:])
        if lower == "geoloc":
            return geoloc_command(self.env, self.cwd, argv[1:])
        if lower == "nikto":
            return nikto_command(self.env, self.cwd, argv[1:])
        if lower in {"db2connect", "db2"}:
            return db2connect_command(self.env, self.cwd, argv[1:])
        if lower == "task":
            return task_command(self.env, self.cwd, self.real_userid, argv[1:])
        if lower in {"tshocker", "tsh0cker"}:
            return tshocker_command(self.env, self.cwd, argv[1:])
        if lower == "ezrecon":
            return ezrecon_command(self.env, self.cwd, argv[1:])
        if lower == "racf2john":
            return racf2john_command(self.state, self.real_userid, argv[1:])
        if lower == "john":
            return john_command(self.state, self.real_userid, argv[1:])
        if lower in {"genptkt", "gen_passticket.py"}:
            return genptkt_command(self.state, self.real_userid, argv[1:])
        if lower in {"unmaskptkt", "unmask_passticket.py"}:
            return unmaskptkt_command(self.state, self.real_userid, argv[1:])
        if lower in {"parseptkt", "parse_db_ptkt.py"}:
            return parseptkt_command(self.state, self.real_userid, argv[1:])
        if lower == "lynx":
            return lynx_command(argv[1:], self.state, self.real_userid)
        if lower == "curl":
            return self._curl(argv[1:])
        if lower == "wget":
            return self._wget(argv[1:])
        if lower == "pwd":
            return self.cwd
        if lower == "cd":
            return self._cd(argv[1] if len(argv) > 1 else self.identity.home)
        if lower == "ls":
            return self._ls(argv[1:])
        if lower == "cat":
            return self._cat(argv[1:])
        if lower == "echo":
            return " ".join(argv[1:])
        if lower == "touch":
            return self._touch(argv[1:])
        if lower == "mkdir":
            return self._mkdir(argv[1:])
        if lower == "rmdir":
            return self._rmdir(argv[1:])
        if lower in {"more", "head", "tail"}:
            return self._display_text_command(lower, argv[1:])
        if lower in {"chmod", "chown", "chgrp"}:
            return self._metadata_cmd(lower, argv[1:])
        if lower == "date":
            return datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y").replace("  ", " ")
        if lower == "grep":
            return self._grep(argv[1:])
        if lower == "find":
            return self._find(argv[1:])
        if lower == "wc":
            return self._wc(argv[1:])
        if lower in {"sort", "uniq", "cut", "tr"}:
            return self._text_filter(lower, argv[1:])
        if lower == "du":
            return self._du(argv[1:])
        if lower == "kill":
            return self._kill(argv[1:])
        if lower in {"set", "umask"}:
            return self._set_umask(lower, argv[1:])
        if lower == "ln":
            return self._ln(argv[1:])
        if lower == "tar":
            return self._tar(argv[1:])
        if lower in {"gzip", "gunzip"}:
            return self._gzip_cmd(lower, argv[1:])
        if lower in {"od", "hexdump"}:
            return self._hex_dump(argv[1:])
        if lower == "iconv":
            return self._iconv(argv[1:])
        if lower == "chtag":
            return self._chtag(argv[1:])
        if lower == "man":
            return self._man(argv[1:])
        if lower == "rm":
            return self._rm(argv[1:])
        if lower == "cp":
            return self._cp(argv[1:])
        if lower == "mv":
            return self._mv(argv[1:])
        if lower == "id":
            return self._id()
        if lower == "whoami":
            return self.environment.get("LOGNAME", self.real_userid)
        if lower == "hostname":
            return self.state.network.hostname
        if lower == "uname":
            return self._uname(argv[1:])
        if lower in {"env", "printenv"}:
            return self._env(argv[1:])
        if lower == "export":
            return self._export(argv[1:])
        if lower == "extattr":
            return self._extattr(argv[1:])
        if lower in {"vi", "view", "ex", "edit"}:
            return "vi: available in interactive OMVS/USS sessions"
        if lower == "oedit":
            return "oedit: available in interactive OMVS/USS sessions"
        if lower in {"tso", "tsocmd"}:
            return self._tso(argv[1:])
        if lower in {"oget", "oput", "ocopy"}:
            return self._mvs_copy(lower, argv[1:])
        if lower in {"netstat", "onetstat"}:
            return self._netstat(argv[1:])
        if lower in {"ping", "oping"}:
            return self._ping(argv[1:])
        if lower in {"traceroute", "otracert", "tracerte", "tracert"}:
            return self._traceroute(argv[1:])
        if lower == "su":
            return self._su(argv[1:])
        if lower == "sudo":
            return self._sudo(argv[1:])
        if lower in {"python", "python3"}:
            return self._python(argv)
        if lower == "df":
            return self._df()
        if lower == "ps":
            return self._ps()
        if lower == "clear":
            # In the 3270 scroll panel a raw ANSI clear sequence would be
            # cp037-mangled (the [2J[H -> bracket corruption). Signal the host
            # panel to reset its scroll buffer instead.
            return "__CLEAR__" if self.mode == "OMVS3270" else colors.CLEAR
        return f"FSUM7351 {cmd}: not found"

    @staticmethod
    def supported_commands() -> list[str]:
        return [
            "pwd", "ls", "cd", "mkdir", "rmdir", "touch", "cat", "more",
            "head", "tail", "cp", "mv", "rm", "chmod", "chown", "chgrp",
            "id", "whoami", "hostname", "uname", "date", "echo", "grep",
            "find", "wc", "sort", "uniq", "cut", "tr", "df", "du", "ps",
            "nmap", "hosts", "CICSPWN", "msfconsole", "msfconsole-sim", "msf6", "msfvenom", "msfvenom-sim",
            "subfinder", "nikto", "dig", "whois", "shodan", "geoloc", "ezrecon", "db2connect", "db2", "tshocker", "task",
            "lynx",
            "racf2john", "john", "kill", "env", "export", "set", "umask", "ln", "tar", "gzip",
            "gunzip", "od", "hexdump", "iconv", "chtag", "man", "help",
            "OPUT", "OGET", "OCOPY", "extattr", "tso", "tsocmd", "vi",
            "oedit", "su", "sudo", "python", "python3", "netstat", "ping",
            "traceroute", "ftp", "telnet", "rss", "cti-rss", "curl", "wget", "clear",
        ]

    def _is_help_request(self, argv: list[str]) -> bool:
        if not argv:
            return False
        # Some OMVS tools use -h as a normal option (nikto -h URL, shodan host, etc.).
        if len(argv) >= 2 and argv[1].upper() in {"HELP", "?", "--HELP"}:
            return True
        if len(argv) >= 2 and argv[1].upper() == "-H" and argv[0].lower() not in {"nikto"}:
            return True
        if argv[0].lower() == "help" and len(argv) >= 2:
            return True
        return False

    def _command_help(self, command: str) -> str:
        cmd = command.lower()
        if cmd == "help" and len(self.history) >= 1:
            try:
                parts = shlex.split(self.history[-1])
                if len(parts) > 1:
                    cmd = parts[1].lower()
            except Exception:
                pass
        usage = {
            "ls": "ls [-l] [-a] [-E] [path] - list USS files and tags",
            "cp": "cp source target - copy USS files or //MVS.DATA.SET operands",
            "OPUT": "OPUT dataset path [-t|-b] - copy MVS dataset to USS file",
            "OGET": "OGET path dataset [-t|-b] - copy USS file to MVS dataset",
            "OCOPY": "OCOPY source target | INDATASET(...) OUTPATH(...) | INPATH(...) OUTDATASET(...)",
            "find": "find [path] [-name pattern] [-type f|d] - search simulated USS tree",
            "grep": "grep [-i] [-n] pattern file... - search file text",
            "tar": "tar -cf archive files | tar -tf archive | tar -xf archive - simulated archive",
            "iconv": "iconv [-f from] [-t to] file - simulate ASCII/EBCDIC conversion labels",
            "chtag": "chtag [-t text|-b binary|-c ccsid] file - set/display simulated file tag",
            "man": "man command - display Gibson USS command help",
            "ftp": "ftp [host [port]] - prompts for Name and Password before ftp>; use ftp HELP",
            "telnet": "telnet [host [port]] - remote login/password flow appears before telnet>; use telnet HELP",
            "rss": "rss | rss refresh | rss lynx <feed-no> <item-no> - live RSS/Atom latest-five reader with Lynx article opening",
            "racf2john": "racf2john SYS1.RACFDS [> OUT.DATASET] - extract only Gibson legacy-DES RACF hashes",
            "john": "john [--wordlist=DATASET] HASH.DATASET | john --show HASH.DATASET - bounded Gibson RACF hash cracker simulator",
            "cti-rss": "cti-rss | cti-rss --refresh | cti-rss --lynx <feed-no> <item-no> - CTI RSS live latest-five reader",
            "curl": "curl [-I] [-L] [-s] [-o file] [--max-time N] [-H 'Header: value'] URL - safe HTTP client",
            "wget": "wget [-O file] [-q] [--spider] [--timeout=N] URL - safe HTTP downloader",
            "nmap": "nmap [options] 127.0.0.1|mainframe - Gibson NSE training simulator. Use nmap -M for guided menu.",
            "hosts": "hosts list|add|remove|resolve - manage simulated Gibson OMVS host aliases",
            "cicspwn": "CICSPWN mainframe --port 2023 --mode forensic --safe - safe CICS assessment simulator",
            "msfconsole": "msfconsole -x 'search tomcat; use exploit/multi/http/tomcat_mgr_upload; run' - deterministic safe Tomcat Manager training console",
            "msfconsole-sim": "msfconsole-sim chapter8 | -x 'commands' - deterministic safe Tomcat Manager training console",
            "msfvenom": "msfvenom -p java/jsp_shell_bind_tcp LPORT=31337 -f war -o ws_shell_exploit.war - create harmless WAR artifact",
            "msfvenom-sim": "msfvenom-sim -p java/jsp_shell_bind_tcp LPORT=31337 -f war -o ws_shell_exploit.war - create harmless WAR artifact",
            "netstat": "Usage: netstat [HOME|CONFIG|CONN|ALL|DEVLINKS|ROUTE|ARP|PORTLIST|TELNET|FTP] | netstat -h | netstat --help\nGibson displays simulated z/OS UNIX / TCPIP stack information.\nCanonical host: mainframe\nCanonical IP:   127.0.0.1",
            "onetstat": "Usage: netstat [HOME|CONFIG|CONN|ALL|DEVLINKS|ROUTE|ARP|PORTLIST|TELNET|FTP] | netstat -h | netstat --help\nCanonical host: mainframe\nCanonical IP:   127.0.0.1",
            "lynx": "lynx [-dump] URL - Gibson native text browser; external HTTP/HTTPS enabled by default; no JavaScript",
            "subfinder": "subfinder -d DOMAIN [-resolve] [-json] [-o file] - passive fixture subdomain discovery",
            "dig": "dig [@server] NAME [TYPE] [+short] | dig -x IP - DNS lookup (BIND)",
            "whois": "whois DOMAIN|IP - registrar / RIR allocation lookup",
            "nslookup": "nslookup NAME [server] - resolve a name or address",
            "host": "host NAME|IP - DNS lookup, one line per record",
            "shodan": "shodan search QUERY | shodan host HOST | shodan info - fixture Shodan-style OSINT",
            "geoloc": "geoloc IP | geoloc -f file [--json|--csv -o file] - geolocation with Livingston override",
            "nikto": "nikto -h URL [-id user:pass] [-C all] - Gibson web/Tomcat scanner simulation",
            "db2connect": "db2connect mainframe USER PASS - Gibson DB2/DRDA client simulation",
            "db2": "db2 connect to GIBSONDB user IBMUSER using SYS1 - Gibson DB2 CLP simulation",
            "tshocker": "tshocker --print|-l|-r TARGET USER PASS - safe FTP/JES/CATSO training simulator",
            "task": "task add|list|ID done|projects|tags - simple Taskwarrior-style local task manager",
            "ezrecon": "ezrecon dork|subdomains|email-scrape|report sighberbank.com - passive OSINT workflow",
        }
        key = command if command in {"OPUT", "OGET", "OCOPY"} else cmd
        if key in usage:
            return usage[key]
        if cmd in [c.lower() for c in self.supported_commands()]:
            return f"{cmd}: Gibson USS simulated command. Use {cmd} HELP or man {cmd} for examples."
        return self._help()

    def _help(self) -> str:
        docs = self._help_registry()
        groups: dict[str, list[str]] = {}
        for cmd, meta in docs.items():
            groups.setdefault(meta.get("category", "Misc"), []).append(cmd)
        lines = ["Gibson USS help - grouped commands", "Use: help <command>, man <command>, whatis <command>, apropos <keyword>", ""]
        for cat in ["Filesystem", "Networking", "Mainframe / zOS", "Security tools", "OSINT tools", "Web tools", "Db2 tools", "RSS / CTI feeds", "Task management", "Misc"]:
            cmds = sorted(groups.get(cat, []))
            if cmds:
                lines.append(cat + ":")
                for c in cmds:
                    lines.append(f"  {c:<14} {docs[c].get('summary','')}")
                lines.append("")
        lines.append("Active security tools remain scoped by HOSTS.TXT. Lynx/RSS may fetch external HTTP/HTTPS by default.")
        return "\n".join(lines).rstrip()

    def _apropos(self, args: list[str], whatis: bool = False) -> str:
        docs = self._help_registry()
        if not args:
            return ("whatis COMMAND" if whatis else "apropos KEYWORD")
        term = " ".join(args).lower()
        rows = []
        for cmd, meta in sorted(docs.items()):
            hay = (cmd + " " + meta.get("summary", "") + " " + meta.get("category", "")).lower()
            if (cmd == term if whatis else term in hay):
                rows.append(f"{cmd:<14} - {meta.get('summary','')}")
        return "\n".join(rows) if rows else f"{term}: nothing appropriate"

    def _help_registry(self) -> dict:
        return {
            "nmap": {"category":"Security tools", "summary":"NSE-style Gibson mainframe scanner; active targets require HOSTS.TXT authorisation"},
            "cicspwn": {"category":"Security tools", "summary":"CICS enumeration and safe vulnerability simulation"},
            "nikto": {"category":"Web tools", "summary":"Tomcat/web vulnerability scanner simulation"},
            "lynx": {"category":"Web tools", "summary":"Gibson native text browser with external HTTP/HTTPS enabled by default"},
            "rss": {"category":"RSS / CTI feeds", "summary":"Fetch and display RSS/Atom feeds; open stories with Lynx"},
            "cti-rss": {"category":"RSS / CTI feeds", "summary":"CTI RSS feed reader with latest 5 stories per feed and Lynx integration"},
            "dig": {"category":"OSINT tools", "summary":"DNS lookup utility"}, "whois": {"category":"OSINT tools", "summary":"WHOIS lookup utility"}, "nslookup": {"category":"Networking", "summary":"DNS resolver lookup"}, "host": {"category":"Networking", "summary":"DNS host lookup"},
            "shodan": {"category":"OSINT tools", "summary":"Shodan-style fixture/optional search client"}, "geoloc": {"category":"OSINT tools", "summary":"IP geolocation with local overrides"},
            "subfinder": {"category":"OSINT tools", "summary":"Passive subdomain discovery"}, "ezrecon": {"category":"OSINT tools", "summary":"Passive OSINT workflow"},
            "db2connect": {"category":"Db2 tools", "summary":"Db2/DRDA client simulation"}, "db2": {"category":"Db2 tools", "summary":"Db2 CLP simulation"},
            "tshocker": {"category":"Security tools", "summary":"Safe FTP/JES/CATSO training simulator"},
            "genptkt": {"category":"Security tools", "summary":"Generate simulated RACF PassTicket from Gibson PTKTDATA"},
            "unmaskptkt": {"category":"Security tools", "summary":"Decode simulated KEYMASKED PTKTDATA key for Chapter 8 lab"},
            "parseptkt": {"category":"Security tools", "summary":"List simulated RACF PTKTDATA profiles"}, "task": {"category":"Task management", "summary":"Taskwarrior-style local task list"},
            "ftp": {"category":"Networking", "summary":"FTP client simulation"}, "telnet": {"category":"Networking", "summary":"Telnet client simulation"}, "ping": {"category":"Networking", "summary":"Ping utility"}, "tracerte": {"category":"Networking", "summary":"Trace route utility"}, "netstat": {"category":"Networking", "summary":"Network status"},
            "ls": {"category":"Filesystem", "summary":"List files"}, "cat": {"category":"Filesystem", "summary":"Display files"}, "grep": {"category":"Filesystem", "summary":"Search text"}, "find": {"category":"Filesystem", "summary":"Find files"},
            "pwd": {"category":"Filesystem", "summary":"Print working directory"}, "cd": {"category":"Filesystem", "summary":"Change directory"}, "mkdir": {"category":"Filesystem", "summary":"Make directory"}, "rmdir": {"category":"Filesystem", "summary":"Remove directory"}, "touch": {"category":"Filesystem", "summary":"Create or update file timestamp"},
            "more": {"category":"Filesystem", "summary":"Page through a file"}, "head": {"category":"Filesystem", "summary":"Show first lines"}, "tail": {"category":"Filesystem", "summary":"Show last lines"}, "chmod": {"category":"Filesystem", "summary":"Change permissions"}, "chown": {"category":"Filesystem", "summary":"Change owner"}, "chgrp": {"category":"Filesystem", "summary":"Change group"},
            "wc": {"category":"Filesystem", "summary":"Count lines, words, bytes"}, "sort": {"category":"Filesystem", "summary":"Sort lines"}, "uniq": {"category":"Filesystem", "summary":"Remove repeated lines"}, "cut": {"category":"Filesystem", "summary":"Select columns"}, "tr": {"category":"Filesystem", "summary":"Translate characters"}, "du": {"category":"Filesystem", "summary":"Disk usage"},
            "ln": {"category":"Filesystem", "summary":"Create links"}, "tar": {"category":"Filesystem", "summary":"Create/list/extract tar archive"}, "gzip": {"category":"Filesystem", "summary":"Compress file"}, "gunzip": {"category":"Filesystem", "summary":"Decompress gzip file"}, "od": {"category":"Filesystem", "summary":"Octal/hex dump"}, "hexdump": {"category":"Filesystem", "summary":"Hex dump"},
            "iconv": {"category":"Mainframe / zOS", "summary":"Convert encodings"}, "chtag": {"category":"Mainframe / zOS", "summary":"Tag USS file encoding"}, "OPUT": {"category":"Mainframe / zOS", "summary":"Copy MVS dataset/member to USS"}, "OGET": {"category":"Mainframe / zOS", "summary":"Copy USS file to MVS dataset/member"}, "OCOPY": {"category":"Mainframe / zOS", "summary":"Copy between MVS and USS"},
            "date": {"category":"Misc", "summary":"Display date/time"}, "kill": {"category":"Task management", "summary":"Terminate local simulated process"}, "set": {"category":"Misc", "summary":"Display/set shell variables"}, "umask": {"category":"Misc", "summary":"Display/set file creation mask"}, "man": {"category":"Misc", "summary":"Manual page lookup"},
        }


    def _curl(self, args: list[str]) -> str:
        if not args or args[0] in {"--help", "-h", "HELP"}:
            return "curl [-I] [-L] [-s] [-o file] [--max-time N] [-H 'Header: value'] URL"
        head = False; silent = False; output = ""; timeout = 12.0; method = "GET"; headers: dict[str, str] = {}; data: bytes | None = None; url = ""
        i = 0
        while i < len(args):
            a = args[i]
            if a == "-I": head = True
            elif a == "-s": silent = True
            elif a == "-L": pass
            elif a == "-o" and i + 1 < len(args): i += 1; output = args[i]
            elif a == "--max-time" and i + 1 < len(args):
                i += 1
                try: timeout = max(1.0, min(30.0, float(args[i])))
                except Exception: return "curl: invalid --max-time"
            elif a.startswith("--max-time="):
                try: timeout = max(1.0, min(30.0, float(a.split("=",1)[1])))
                except Exception: return "curl: invalid --max-time"
            elif a == "-H" and i + 1 < len(args):
                i += 1
                if ":" not in args[i]: return "curl: invalid header"
                k, v = args[i].split(":", 1); headers[k.strip()] = v.strip()
            elif a == "-X" and i + 1 < len(args): i += 1; method = args[i].upper()
            elif a == "--json" and i + 1 < len(args):
                i += 1
                if method == "GET":
                    method = "POST"
                headers["Content-Type"] = "application/json"; data = args[i].encode("utf-8")
            elif a.startswith("-"):
                return f"curl: unsupported option {a}"
            else:
                if url: return "curl: multiple URLs are not supported in Gibson OMVS"
                url = a
            i += 1
        if not url: return "curl: no URL specified"
        res = safe_http.fetch(url, method=method, headers=headers, data=data, timeout=timeout, head=head)
        if output:
            try:
                real = safe_http.safe_workspace_path(self.env, self.cwd, output)
                Path(real).write_bytes(res.body)
                prefix = "" if silent else f"curl: wrote {len(res.body)} bytes to {output}"
                return prefix if res.ok else (prefix + ("\n" if prefix else "") + f"curl: {res.error}")
            except Exception as exc:
                return f"curl: {exc}"
        if head:
            return safe_http.render_headers(res) if res.ok or res.headers else f"curl: {res.error}"
        if not res.ok:
            body = safe_http.render_body(res).strip()
            return f"curl: {res.error}" + (("\n" + body) if body else "")
        return safe_http.render_body(res)

    def _wget(self, args: list[str]) -> str:
        if not args or args[0] in {"--help", "-h", "HELP"}:
            return "wget [-O file] [-q] [--spider] [--timeout=N] [--user-agent=VALUE] URL"
        quiet = False; output = ""; timeout = 12.0; spider = False; headers: dict[str, str] = {}; url = ""
        i = 0
        while i < len(args):
            a = args[i]
            if a == "-q": quiet = True
            elif a == "--spider": spider = True
            elif a == "-O" and i + 1 < len(args): i += 1; output = args[i]
            elif a.startswith("--timeout="):
                try: timeout = max(1.0, min(30.0, float(a.split("=",1)[1])))
                except Exception: return "wget: invalid timeout"
            elif a == "--timeout" and i + 1 < len(args):
                i += 1
                try: timeout = max(1.0, min(30.0, float(args[i])))
                except Exception: return "wget: invalid timeout"
            elif a.startswith("--user-agent="):
                headers["User-Agent"] = a.split("=",1)[1]
            elif a.startswith("-"):
                return f"wget: unsupported option {a}"
            else:
                if url: return "wget: multiple URLs are not supported in Gibson OMVS"
                url = a
            i += 1
        if not url: return "wget: no URL specified"
        res = safe_http.fetch(url, headers=headers, timeout=timeout, head=spider)
        if spider:
            return f"Spider mode: {'OK' if res.ok else 'FAILED'} {res.status} {res.reason}".rstrip() if res.ok else f"wget: {res.error}"
        name = output
        if not name:
            from urllib.parse import urlparse
            base = Path(urlparse(url).path).name or "index.html"
            name = base
        try:
            real = safe_http.safe_workspace_path(self.env, self.cwd, name)
            Path(real).write_bytes(res.body)
            msg = "" if quiet else f"Saved {len(res.body)} bytes to {name}"
            return msg if res.ok else (msg + ("\n" if msg else "") + f"wget: {res.error}")
        except Exception as exc:
            return f"wget: {exc}"

    def _resolved(self, operand: str) -> str:
        return self.env.resolve(self.cwd, operand)

    def _cd(self, operand: str) -> str:
        target = self._resolved(operand)
        if not self.env.exists(target) or not self.env.is_dir(target):
            return f"FSUM7351 cd: {operand}: No such directory"
        self.cwd = target
        self.environment["PWD"] = self.cwd
        return ""

    def _format_mode(self, virtual_path: str) -> str:
        if self.env.is_dir(virtual_path):
            prefix = "d"
        else:
            prefix = "-"
        attrs = self.env.attr_string(virtual_path)
        return prefix + "rwxr-xr-x" + (f" +{attrs}" if attrs else "")

    def _ls(self, args: list[str]) -> str:
        flags = "".join(a[1:] for a in args if a.startswith("-"))
        show_long = "l" in flags or "E" in flags
        show_all = "a" in flags
        targets = [a for a in args if not a.startswith("-")] or [self.cwd]
        blocks: list[str] = []
        for target in targets:
            vp = self._resolved(target)
            if not self.env.exists(vp):
                blocks.append(f"ls: {target}: No such file or directory")
                continue
            if self.env.is_dir(vp):
                entries = self.env.listdir(vp)
                if show_all:
                    entries = [".", ".."] + entries
                else:
                    entries = [e for e in entries if not e.startswith(".")]
                if not show_long:
                    blocks.append("  ".join(entries))
                else:
                    rows = []
                    for name in entries:
                        child = vp if name == "." else self.env.resolve(vp, ".." if name == ".." else name)
                        rows.append(f"{self._format_mode(child):<16} {self._display_name(child)}")
                    blocks.append("\n".join(rows))
            else:
                blocks.append(self._format_mode(vp) if show_long else self._display_name(vp))
        return "\n\n".join(blocks)

    def _display_name(self, virtual_path: str) -> str:
        p = PurePosixPath(virtual_path)
        return p.name or "/"

    def _handle_interactive_command(self, raw: str, reader: Callable[[str, bool], object], writer: Callable[[str], None]) -> bool:
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            writer(f"FSUM7332 syntax error: {exc}\n")
            return True
        if not argv:
            return False
        if argv[0].lower() in {"msfconsole", "msfconsole-sim", "msf6"}:
            run_msfconsole_interactive(self.state, argv[1:], self.env, self.cwd, reader, writer)
            return True
        if argv[0].lower() == "lynx":
            run_lynx_interactive(argv[1:], self.state, self.real_userid, reader, writer)
            return True
        if argv[0].lower() in {"cti-rss", "rss"}:
            run_cti_rss_interactive(self.state, self.real_userid, reader, writer)
            return True
        if argv[0].lower() == "more":
            self._more_interactive(argv[1:], reader, writer)
            return True
        if argv[0].lower() in {"vi", "view", "ex", "edit"}:
            self._vi_interactive(argv[1:], reader, writer, readonly=(argv[0].lower()=="view"))
            return True
        if argv[0].lower() != "oedit":
            return False
        self._oedit_interactive(argv[1:], reader, writer)
        return True

    def _more_interactive(self, args: list[str], reader, writer: Callable[[str], None]) -> None:
        if not args:
            writer("more: missing operand\n")
            return
        text, err = self._read_operand_text(args[0])
        if err:
            writer(f"more: {err}\n")
            return
        self._page_lines(text.splitlines(), reader, writer)

    def _page_lines(self, lines: list[str], reader, writer: Callable[[str], None], page_size: int = 22) -> None:
        idx = 0
        if not lines:
            return
        while idx < len(lines):
            end = min(len(lines), idx + page_size)
            if end > idx:
                writer("\n".join(lines[idx:end]) + "\n")
            idx = end
            if idx >= len(lines):
                return
            writer("--More--")
            key = ""
            if hasattr(reader, "read_key"):
                res = reader.read_key()
                key = (getattr(res, "key", "") or getattr(res, "text", "") or "").lower()
            else:
                try:
                    key = (getattr(self._read_line_result(reader, "", False), "text", "") or "").lower()
                except Exception:
                    key = "q"
            writer("\r        \r")
            if key in {"q", "quit", "pf3", "f3", "eof"}:
                return
            if key in {"enter", "", "\n", "\r"}:
                page_size = 1
            elif key in {"h", "?"}:
                writer("more keys: SPACE next page, ENTER next line, Q quit\n")
                page_size = 22
            else:
                page_size = 22

    def _vi_interactive(self, args: list[str], io_or_reader, writer: Callable[[str], None], readonly: bool = False) -> None:
        path = args[0] if args else getattr(self._read_line_result(io_or_reader, "vi file: ", False), "text", "").strip()
        if not path:
            writer("vi: missing file operand\n"); return
        vp = self._resolved(path.strip().strip("'\""))
        if vp.startswith("/dsfs"):
            writer("vi: /dsfs is read-only\n"); return
        try:
            text = self.env.read_text(vp)
        except Exception:
            text = ""
        lines = text.splitlines()
        modified = False; number = False; yank = ""; cur = 0
        writer(f'"{vp}" {len(lines)} lines\n')
        writer("Gibson vi simulation. Commands: i/a/o, dd, yy, p, j/k, :w, :q, :q!, :wq, :set number, :set nonumber, :help\n")
        while True:
            display = []
            window = lines[max(0, cur-5):cur+10]
            base = max(0, cur-5)
            for off, line in enumerate(window):
                prefix = f"{base+off+1:4d} " if number else ""
                mark = ">" if base+off == cur else " "
                display.append(f"{mark}{prefix}{line}")
            writer("\n".join(display or [">~"]) + f"\n\"{vp}\" {'[Modified]' if modified else ''} line {cur+1 if lines else 0} of {len(lines)}\nvi> ")
            res = self._read_line_result(io_or_reader, "", False)
            if getattr(res, "key", "") == "EOF": return
            cmd = (getattr(res, "text", "") or "").rstrip("\n")
            if cmd in {"i", "a", "o"}:
                if readonly: writer("E45: 'readonly' option is set\n"); continue
                insert_at = cur if cmd in {"i","a"} else cur+1
                writer("-- INSERT -- enter a single dot '.' on a line to finish\n")
                new=[]
                while True:
                    r=self._read_line_result(io_or_reader, "", False)
                    if getattr(r,"key","")=="EOF": return
                    t=getattr(r,"text","")
                    if t == ".": break
                    new.append(t)
                for n,line in enumerate(new): lines.insert(insert_at+n, line)
                cur = max(0, insert_at); modified = True; continue
            if cmd == "j": cur=min(cur+1, max(0,len(lines)-1)); continue
            if cmd == "k": cur=max(cur-1,0); continue
            if cmd == "dd":
                if readonly: writer("E45: 'readonly' option is set\n"); continue
                if lines: yank=lines.pop(cur); cur=min(cur, max(0,len(lines)-1)); modified=True
                continue
            if cmd == "yy": yank = lines[cur] if lines else ""; writer("1 line yanked\n"); continue
            if cmd == "p":
                if readonly: writer("E45: 'readonly' option is set\n"); continue
                lines.insert(cur+1, yank); cur += 1; modified=True; continue
            if cmd == "x":
                if readonly: writer("E45: 'readonly' option is set\n"); continue
                if lines and lines[cur]: lines[cur]=lines[cur][1:]; modified=True
                continue
            if cmd.startswith(":"):
                c=cmd[1:].strip()
                if c == "help": writer("vi help: i a o Esc simulated by '.' end insert; :w :q :q! :wq :x :set number/nonumber dd yy p j k\n"); continue
                if c == "set number": number=True; continue
                if c == "set nonumber": number=False; continue
                if c in {"w", "wq", "x"}:
                    if readonly: writer("E45: 'readonly' option is set\n"); continue
                    try:
                        self.env.write_text(vp, "\n".join(lines) + ("\n" if lines else "")); modified=False; writer(f'"{vp}" {len(lines)} lines written\n')
                    except Exception as exc:
                        writer(f"vi: write failed: {exc}\n"); continue
                    if c in {"wq", "x"}: return
                    continue
                if c == "q":
                    if modified: writer("E37: No write since last change (add ! to override)\n"); continue
                    return
                if c == "q!": return
            writer("?\n")

    def _oedit_interactive(self, args: list[str], io_or_reader, writer: Callable[[str], None]) -> None:
        recfm = "VB"
        lrecl = 255
        tail = list(args)
        if len(tail) >= 2 and tail[0] == "-r":
            try:
                lrecl = int(tail[1])
            except ValueError:
                writer("OEDIT: invalid record length\n")
                return
            recfm = "FB"
            tail = tail[2:]
        pathname = tail[0] if tail else getattr(self._read_line_result(io_or_reader, "Pathname ===> ", False), "text", "").strip()
        if not pathname:
            writer("OEDIT: missing pathname\n")
            return
        vp = self._resolved(pathname.strip().strip("'").strip('"'))
        if vp.startswith("/dsfs"):
            writer("OEDIT: /dsfs is read-only; copy the data set with OPUT/OGET first\n")
            return
        real = self.env.real_path(vp)
        real.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = self.env.read_text(vp)
        except Exception:
            text = ""
        driver = io_or_reader if hasattr(io_or_reader, "read_key") else getattr(self, "_interactive_io", None)
        if driver is None:
            writer("OEDIT: interactive editor unavailable in this session\n")
            return
        InteractiveEditor(vp, text, mode="EDIT", recfm=recfm, lrecl=lrecl, save_callback=lambda new_text, target=vp: self.env.write_text(target, new_text)).run(driver, writer)
        self.environment["PWD"] = self.cwd

    def _shell_path_operand(self, operand: str) -> str:
        return operand.strip().strip("'").strip('"')

    def _parse_dataset_operand(self, operand: str) -> Optional[str]:
        raw = (operand or "").strip()
        if not raw.startswith("//"):
            return None
        value = raw[2:].strip()
        if len(value) >= 2 and ((value[0] == "'" and value[-1] == "'") or (value[0] == '"' and value[-1] == '"')):
            value = value[1:-1]
        value = value.strip()
        return value.upper() if value else None

    def _dataset_operand(self, operand: str) -> str:
        parsed = self._parse_dataset_operand(operand)
        if parsed is not None:
            return parsed
        return self._shell_path_operand(operand).upper()

    def _is_dataset_operand(self, operand: str) -> bool:
        return self._parse_dataset_operand(operand) is not None

    def _is_path_operand(self, operand: str) -> bool:
        if self._is_dataset_operand(operand):
            return False
        value = self._shell_path_operand(operand)
        return value.startswith("/") or value.startswith("./") or value.startswith("../")

    def _cat(self, args: list[str]) -> str:
        if not args:
            return "cat: missing operand"
        chunks = []
        for item in args:
            dsn = self._parse_dataset_operand(item)
            if dsn is not None:
                try:
                    chunks.append(self.state.datasets.read(self.real_userid, dsn))
                except FileNotFoundError:
                    chunks.append(f"cat: {item}: data set not found")
                except PermissionError:
                    chunks.append(f"cat: {item}: permission denied")
                continue
            vp = self._resolved(item)
            try:
                chunks.append(self.env.read_text(vp))
            except Exception:
                chunks.append(f"cat: {item}: No such file or directory")
        return "\n".join(chunk.rstrip("\n") for chunk in chunks)

    def _touch(self, args: list[str]) -> str:
        if not args:
            return "touch: missing operand"
        for item in args:
            vp = self._resolved(item)
            if vp.startswith("/dsfs"):
                return "touch: /dsfs is read-only"
            real = self.env.real_path(vp)
            real.parent.mkdir(parents=True, exist_ok=True)
            real.touch(exist_ok=True)
        return ""

    def _mkdir(self, args: list[str]) -> str:
        if not args:
            return "mkdir: missing operand"
        for item in args:
            vp = self._resolved(item)
            if vp.startswith("/dsfs"):
                return "mkdir: /dsfs is read-only"
            self.env.real_path(vp).mkdir(parents=True, exist_ok=True)
        return ""

    def _rm(self, args: list[str]) -> str:
        if not args:
            return "rm: missing operand"
        recursive = False
        targets: list[str] = []
        for arg in args:
            if arg == "-r":
                recursive = True
            else:
                targets.append(arg)
        for item in targets:
            vp = self._resolved(item)
            if vp.startswith("/dsfs"):
                return "rm: /dsfs is read-only"
            real = self.env.real_path(vp)
            if real.is_dir():
                if not recursive:
                    return f"rm: {item}: is a directory"
                for child in sorted(real.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        child.rmdir()
                real.rmdir()
            elif real.exists():
                real.unlink()
        return ""

    def _cp(self, args: list[str]) -> str:
        if len(args) != 2:
            return "cp: usage cp source target"
        src_arg, dst_arg = args
        src_dsn = self._parse_dataset_operand(src_arg)
        dst_dsn = self._parse_dataset_operand(dst_arg)
        try:
            if src_dsn is not None and dst_dsn is not None:
                text = self.state.datasets.read(self.real_userid, src_dsn)
                self.state.datasets.write(self.real_userid, dst_dsn, text)
                return ""
            if src_dsn is not None:
                text = self.state.datasets.read(self.real_userid, src_dsn)
                dst = self._resolved(dst_arg)
                # A binary dataset (e.g. the racf2john SYS1.RACFDS.BACKUP image)
                # is stored marker-wrapped; reconstitute the real bytes so the
                # USS copy is binary, not base64 text.
                try:
                    from gibson.core.racf_db_binary import decode_from_dataset
                    raw = decode_from_dataset(text)
                except Exception:
                    raw = None
                if raw is not None:
                    self.env.write_bytes(dst, raw)
                else:
                    self.env.write_text(dst, text)
                return ""
            if dst_dsn is not None:
                src = self._resolved(src_arg)
                if src.startswith("/dsfs"):
                    text = self.env.read_text(src)
                else:
                    real_src = self.env.real_path(src)
                    if not real_src.exists() or real_src.is_dir():
                        return f"cp: {src_arg}: unsupported source"
                    text = real_src.read_text(encoding="utf-8", errors="ignore")
                self.state.datasets.write(self.real_userid, dst_dsn, text)
                return ""
        except FileNotFoundError:
            return f"cp: {src_arg}: data set not found"
        except PermissionError:
            return "cp: permission denied"

        src, dst = (self._resolved(a) for a in args)
        if src.startswith("/dsfs"):
            text = self.env.read_text(src)
            self.env.write_text(dst, text)
            return ""
        real_src = self.env.real_path(src)
        if not real_src.exists() or real_src.is_dir():
            return f"cp: {args[0]}: unsupported source"
        self.env.write_text(dst, real_src.read_text(encoding="utf-8", errors="ignore"))
        return ""

    def _mv(self, args: list[str]) -> str:
        if len(args) != 2:
            return "mv: usage mv source target"
        src, dst = (self._resolved(a) for a in args)
        if src.startswith("/dsfs") or dst.startswith("/dsfs"):
            return "mv: /dsfs is read-only"
        real_src = self.env.real_path(src)
        real_dst = self.env.real_path(dst)
        real_dst.parent.mkdir(parents=True, exist_ok=True)
        real_src.replace(real_dst)
        return ""

    def _id(self) -> str:
        groups = f"groups={self.identity.gid}({self.environment.get('LOGNAME', self.real_userid)})"
        return f"uid={self.identity.uid}({self.environment.get('LOGNAME', self.real_userid)}) gid={self.identity.gid}({self.environment.get('LOGNAME', self.real_userid)}) {groups}"

    def _uname(self, args: list[str]) -> str:
        if args and args[0] == "-a":
            return "OS/390 GIBSON 03.01 1090 POSIX(ON) ZFS DSFS"
        return "OS/390"

    def _env(self, args: list[str]) -> str:
        if args:
            key = args[0]
            return self.environment.get(key, "")
        return "\n".join(f"{k}={v}" for k, v in sorted(self.environment.items()))

    def _export(self, args: list[str]) -> str:
        if not args:
            return self._env([])
        for item in args:
            if "=" not in item:
                self.environment[item] = self.environment.get(item, "")
            else:
                k, v = item.split("=", 1)
                self.environment[k] = v
                if k == "PWD":
                    self.cwd = v
        return ""

    def _extattr(self, args: list[str]) -> str:
        if not args:
            return "extattr: usage extattr [+flags|-flags] file"
        if len(args) == 1:
            vp = self._resolved(args[0])
            attrs = self.env.attr_string(vp)
            return f"{self._display_name(vp)} +{attrs}" if attrs else self._display_name(vp)
        op_flags, target = args[0], args[1]
        if not op_flags or op_flags[0] not in "+-":
            return "extattr: invalid flag syntax"
        vp = self._resolved(target)
        rel = self.env.rel_for_attr(vp)
        if rel is None:
            return "extattr: /dsfs is read-only"
        self.env.extattrs.update_flags(rel, op_flags[0], op_flags[1:])
        updated = self.env.attr_string(vp)
        return f"{self._display_name(vp)} +{updated}" if updated else self._display_name(vp)

    def _rmdir(self, args: list[str]) -> str:
        if not args:
            return "rmdir: missing operand"
        for item in args:
            vp = self._resolved(item)
            if vp.startswith("/dsfs"):
                return "rmdir: /dsfs is read-only"
            real = self.env.real_path(vp)
            if not real.exists():
                return f"rmdir: {item}: No such directory"
            if not real.is_dir():
                return f"rmdir: {item}: Not a directory"
            try:
                real.rmdir()
            except OSError:
                return f"rmdir: {item}: Directory not empty"
        return ""

    def _read_operand_text(self, item: str) -> tuple[str, str | None]:
        dsn = self._parse_dataset_operand(item)
        if dsn is not None:
            try:
                return self.state.datasets.read(self.real_userid, dsn), None
            except FileNotFoundError:
                return "", f"{item}: data set not found"
            except PermissionError:
                return "", f"{item}: permission denied"
        vp = self._resolved(item)
        try:
            return self.env.read_text(vp), None
        except Exception:
            return "", f"{item}: No such file or directory"

    def _display_text_command(self, verb: str, args: list[str]) -> str:
        if not args:
            return f"{verb}: missing operand"
        n = 10
        if len(args) >= 2 and args[0] == "-n":
            try:
                n = max(0, int(args[1]))
                args = args[2:]
            except ValueError:
                return f"{verb}: invalid line count"
        outs = []
        for item in args:
            text, err = self._read_operand_text(item)
            if err:
                outs.append(f"{verb}: {err}")
                continue
            lines = text.splitlines()
            if verb == "head":
                outs.append("\n".join(lines[:n]))
            elif verb == "tail":
                outs.append("\n".join(lines[-n:]))
            else:
                outs.append("\n".join(lines))
        return "\n".join(o.rstrip("\n") for o in outs)

    def _metadata_cmd(self, verb: str, args: list[str]) -> str:
        if len(args) < 2:
            return f"{verb}: usage {verb} value file"
        value, target = args[0], args[1]
        vp = self._resolved(target)
        if not self.env.exists(vp):
            return f"{verb}: {target}: No such file or directory"
        meta = self.file_meta.setdefault(vp, {})
        if verb == "chmod":
            meta["mode"] = value
        elif verb == "chown":
            if not self._can_elevate():
                return f"{verb}: BPX.SUPERUSER required"
            meta["owner"] = value.upper()
        elif verb == "chgrp":
            meta["group"] = value.upper()
        return f"{verb}: {target}: attributes updated in simulated USS metadata"

    def _grep(self, args: list[str]) -> str:
        if len(args) < 2:
            return "grep: usage grep [-i] [-n] pattern file..."
        ignore = False; number = False
        while args and args[0].startswith("-"):
            ignore |= "i" in args[0]
            number |= "n" in args[0]
            args = args[1:]
        if len(args) < 2:
            return "grep: usage grep [-i] [-n] pattern file..."
        pattern, files = args[0], args[1:]
        out=[]
        pat = pattern.lower() if ignore else pattern
        for item in files:
            text, err = self._read_operand_text(item)
            if err:
                out.append(f"grep: {err}"); continue
            for idx,line in enumerate(text.splitlines(),1):
                hay=line.lower() if ignore else line
                if pat in hay:
                    prefix=f"{idx}:" if number else ""
                    out.append(prefix+line)
        return "\n".join(out)

    def _find(self, args: list[str]) -> str:
        path = args[0] if args and not args[0].startswith("-") else self.cwd
        rest = args[1:] if args and not args[0].startswith("-") else args
        name_pat = None; type_filter = None
        i=0
        while i < len(rest):
            if rest[i] == "-name" and i+1 < len(rest):
                name_pat = rest[i+1]; i += 2; continue
            if rest[i] == "-type" and i+1 < len(rest):
                type_filter = rest[i+1]; i += 2; continue
            i += 1
        vp=self._resolved(path)
        if vp.startswith("/dsfs"):
            return vp if self.env.exists(vp) else f"find: {path}: No such file or directory"
        root=self.env.real_path(vp)
        if not root.exists(): return f"find: {path}: No such file or directory"
        rows=[]
        for real in [root] + list(root.rglob("*")):
            rel=self.env.virtual_path(real)
            if name_pat and not fnmatch.fnmatch(real.name, name_pat):
                continue
            if type_filter == "f" and not real.is_file():
                continue
            if type_filter == "d" and not real.is_dir():
                continue
            rows.append(rel)
        return "\n".join(rows)

    def _wc(self, args: list[str]) -> str:
        if not args:
            return "wc: missing operand"
        rows=[]
        for item in args:
            text, err = self._read_operand_text(item)
            if err:
                rows.append(f"wc: {err}"); continue
            lines=text.splitlines(); words=text.split(); bytes_len=len(text.encode())
            rows.append(f"{len(lines):7d} {len(words):7d} {bytes_len:7d} {item}")
        return "\n".join(rows)

    def _text_filter(self, verb: str, args: list[str]) -> str:
        if verb == "tr":
            if len(args) < 3:
                return "tr: usage tr set1 set2 file"
            src,dst,file=args[0],args[1],args[2]
            text,err=self._read_operand_text(file)
            if err: return f"tr: {err}"
            table=str.maketrans(src,dst)
            return text.translate(table).rstrip("\n")
        if verb == "cut":
            if len(args) < 3 or args[0] != "-c":
                return "cut: usage cut -c list file"
            spec=args[1]; file=args[2]
            text,err=self._read_operand_text(file)
            if err: return f"cut: {err}"
            try:
                if "-" in spec:
                    a,b=spec.split("-",1); start=int(a or 1)-1; end=int(b or 999999)
                else:
                    start=int(spec)-1; end=start+1
            except Exception:
                return "cut: invalid character list"
            return "\n".join(line[start:end] for line in text.splitlines())
        if not args:
            return f"{verb}: missing operand"
        text,err=self._read_operand_text(args[-1])
        if err: return f"{verb}: {err}"
        lines=text.splitlines()
        if verb == "sort": lines=sorted(lines)
        elif verb == "uniq":
            out=[]; prev=None
            for line in lines:
                if line != prev: out.append(line)
                prev=line
            lines=out
        return "\n".join(lines)

    def _du(self, args: list[str]) -> str:
        target=self._resolved(args[0] if args else self.cwd)
        if target.startswith("/dsfs"):
            return f"4\t{target}"
        real=self.env.real_path(target)
        if not real.exists(): return f"du: {args[0] if args else target}: No such file or directory"
        size=0
        if real.is_file(): size=real.stat().st_size
        else:
            for p in real.rglob("*"):
                if p.is_file(): size += p.stat().st_size
        blocks=max(1,(size+511)//512)
        return f"{blocks}\t{target}"

    def _kill(self, args: list[str]) -> str:
        if not args:
            return "kill: usage kill [-signal] pid"
        pid=args[-1]
        if pid not in {"100", "101"}:
            return f"kill: {pid}: no such simulated process"
        return f"kill: signal sent to simulated process {pid}"

    def _set_umask(self, verb: str, args: list[str]) -> str:
        if verb == "set":
            return "\n".join(f"{k}={v}" for k,v in sorted(self.environment.items()))
        if not args:
            return self.environment.get("UMASK", "022")
        self.environment["UMASK"] = args[0]
        return ""

    def _ln(self, args: list[str]) -> str:
        symbolic = False
        if args and args[0] == "-s": symbolic=True; args=args[1:]
        if len(args) != 2: return "ln: usage ln [-s] source target"
        src=self._resolved(args[0]); dst=self._resolved(args[1])
        if dst.startswith("/dsfs"): return "ln: /dsfs is read-only"
        try:
            text = self.env.read_text(src) if not symbolic else f"SYMLINK->{src}\n"
            self.env.write_text(dst, text)
            return ""
        except Exception:
            return f"ln: {args[0]}: No such file or directory"

    def _tar(self, args: list[str]) -> str:
        if len(args) < 2: return "tar: usage tar -cf archive files | tar -tf archive | tar -xf archive"
        mode=args[0]; archive=args[1]
        if mode == "-tf":
            text,err=self._read_operand_text(archive)
            if err: return f"tar: {err}"
            try:
                data=json.loads(text); return "\n".join(data.keys())
            except Exception: return "tar: invalid simulated archive"
        if mode == "-cf":
            data={}
            for item in args[2:]:
                text,err=self._read_operand_text(item)
                if err: return f"tar: {err}"
                data[item]=text
            self.env.write_text(self._resolved(archive), json.dumps(data))
            return ""
        if mode == "-xf":
            text,err=self._read_operand_text(archive)
            if err: return f"tar: {err}"
            try: data=json.loads(text)
            except Exception: return "tar: invalid simulated archive"
            for name,text in data.items(): self.env.write_text(self._resolved(posixpath.basename(name)), text)
            return ""
        return "tar: unsupported option"

    def _gzip_cmd(self, verb: str, args: list[str]) -> str:
        if not args: return f"{verb}: missing operand"
        src=self._resolved(args[0])
        if verb == "gzip":
            text,err=self._read_operand_text(args[0])
            if err: return f"gzip: {err}"
            self.env.write_text(src + ".gz", "GZIP-SIMULATED\n" + text)
            return f"{args[0]} compressed to {args[0]}.gz"
        text,err=self._read_operand_text(args[0])
        if err: return f"gunzip: {err}"
        out=src[:-3] if src.endswith(".gz") else src + ".out"
        if text.startswith("GZIP-SIMULATED\n"): text=text.split("\n",1)[1]
        self.env.write_text(out, text)
        return f"{args[0]} expanded to {out}"

    def _hex_dump(self, args: list[str]) -> str:
        if not args: return "hexdump: missing operand"
        text,err=self._read_operand_text(args[0])
        if err: return f"hexdump: {err}"
        b=text.encode()[:256]
        rows=[]
        for i in range(0,len(b),16):
            chunk=b[i:i+16]
            hx=" ".join(f"{x:02x}" for x in chunk)
            asc="".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
            rows.append(f"{i:08x}  {hx:<47}  |{asc}|")
        return "\n".join(rows)

    def _iconv(self, args: list[str]) -> str:
        from_code="IBM-1047"; to_code="ISO8859-1"; files=[]; i=0
        while i < len(args):
            if args[i] == "-f" and i+1 < len(args): from_code=args[i+1]; i+=2; continue
            if args[i] == "-t" and i+1 < len(args): to_code=args[i+1]; i+=2; continue
            files.append(args[i]); i+=1
        if not files: return "iconv: missing file operand"
        text,err=self._read_operand_text(files[0])
        if err: return f"iconv: {err}"
        return f"# iconv simulated {from_code}->{to_code}\n" + text.rstrip("\n")

    def _chtag(self, args: list[str]) -> str:
        if not args: return "chtag: usage chtag [-t|-b|-c ccsid] file"
        tag="text"; files=[]; i=0
        while i < len(args):
            if args[i] in {"-t","-b"}: tag="text" if args[i]=="-t" else "binary"; i+=1; continue
            if args[i] == "-c" and i+1 < len(args): tag=f"ccsid={args[i+1]}"; i+=2; continue
            files.append(args[i]); i+=1
        if not files: return "chtag: missing file operand"
        for f in files:
            vp=self._resolved(f)
            if not self.env.exists(vp): return f"chtag: {f}: No such file"
            rel=self.env.rel_for_attr(vp)
            if rel: self.env.extattrs.set(rel, self.env.extattrs.get(rel)+"t")
        return "\n".join(f"{f}: TAG={tag}" for f in files)

    def _man(self, args: list[str]) -> str:
        if not args: return "What manual page do you want?"
        return "GIBSON USS MANUAL PAGE\n" + self._command_help(args[0])

    def _tso(self, args: list[str]) -> str:
        if not args:
            return "tso: missing TSO command"
        out = self.processor.run(" ".join(args))
        if out.startswith("GIBSON-INTERACTIVE:"):
            return f"{args[0]} requires READY mode; use PF6/EXIT to return to TSO"
        return out

    def _mvs_copy(self, verb: str, args: list[str]) -> str:
        if not args or any(a.upper() in {"HELP", "?"} for a in args):
            return self._command_help(verb.upper())
        mode = "text"
        cleaned=[]
        for a in args:
            if a in {"-t", "--text"}:
                mode = "text"; continue
            if a in {"-b", "--binary"}:
                mode = "binary"; continue
            cleaned.append(a)
        args = cleaned
        # OCOPY keyword forms used by z/OS UNIX Services examples.
        if verb == "ocopy" and any("(" in a and a.endswith(")") for a in args):
            pairs={}
            for a in args:
                if "(" in a and a.endswith(")"):
                    k,v=a.split("(",1); pairs[k.upper()]=v[:-1]
            if "INDATASET" in pairs and "OUTPATH" in pairs:
                return self._mvs_copy("oput", [pairs["INDATASET"], pairs["OUTPATH"]])
            if "INPATH" in pairs and "OUTDATASET" in pairs:
                return self._mvs_copy("oget", [pairs["INPATH"], pairs["OUTDATASET"]])
            if "INDD" in pairs and "OUTDD" in pairs:
                return "OCOPY: DDNAME COPY ACCEPTED IN SIMULATION"
            return "ocopy: unsupported OCOPY keyword combination"
        if len(args) != 2:
            return f"{verb}: requires source and target"
        src, dst = args
        src_is_path = self._is_path_operand(src)
        dst_is_path = self._is_path_operand(dst)
        if verb == "oget":
            source = self._resolved(self._shell_path_operand(src))
            try:
                text = self.env.read_text(source)
            except Exception:
                return f"{verb}: {src}: file not found"
            dsname = self._dataset_operand(dst)
            self.state.datasets.write(self.real_userid, dsname, text)
            return f"{source} copied to {dsname}"
        if verb == "oput":
            dsname = self._dataset_operand(src)
            target = self._resolved(self._shell_path_operand(dst))
            try:
                text = self.state.datasets.read(self.real_userid, dsname)
            except FileNotFoundError:
                return f"{verb}: {dsname}: data set not found"
            except PermissionError:
                return f"{verb}: {dsname}: permission denied"
            # A binary dataset (the racf2john image) is reconstituted to raw bytes
            # so OPUT lands a binary file, not base64 text.
            try:
                from gibson.core.racf_db_binary import decode_from_dataset
                raw = decode_from_dataset(text)
            except Exception:
                raw = None
            if raw is not None or mode == "binary":
                self.env.write_bytes(target, raw if raw is not None else text.encode("utf-8", "ignore"))
            else:
                self.env.write_text(target, text)
            return f"{dsname} copied to {target}"
        if src_is_path and not dst_is_path:
            return self._mvs_copy("oget", [src, dst])
        if not src_is_path and dst_is_path:
            return self._mvs_copy("oput", [src, dst])
        if src_is_path and dst_is_path:
            return self._cp([src, dst])
        try:
            text = self.state.datasets.read(self.real_userid, self._dataset_operand(src))
        except FileNotFoundError:
            return f"ocopy: {src}: data set not found"
        self.state.datasets.write(self.real_userid, self._dataset_operand(dst), text)
        return f"{self._dataset_operand(src)} copied to {self._dataset_operand(dst)}"

    def _can_elevate(self) -> bool:
        rec = self.state.racf.get(self.real_userid)
        return bool(rec and rec.special)

    def _become(self, userid: str, superuser: bool = False) -> str:
        self.identity = self.env.identity_for(userid, superuser=superuser)
        self.environment["LOGNAME"] = self.identity.userid
        self.environment["USER"] = self.identity.userid
        self.environment["HOME"] = self.identity.home
        self.environment["SHELL"] = self.identity.program
        self.cwd = self.identity.home
        self.environment["PWD"] = self.cwd
        if not superuser:
            self.env.ensure_user_profile(userid)
        return ""

    def _su(self, args: list[str]) -> str:
        target = self.real_userid
        if args and args[0] == "-":
            args = args[1:]
        if args:
            target = args[0].upper()
        if target in {"ROOT", "OMVSKERN"}:
            if not self._can_elevate():
                return "su: insufficient authority for BPX.SUPERUSER"
            self._become("ROOT", superuser=True)
            return ""
        if target != self.real_userid and not self._can_elevate():
            return f"su: insufficient authority to switch to {target}"
        if not self.state.racf.exists(target):
            return f"su: unknown user {target}"
        self._become(target)
        return ""

    def _sudo(self, args: list[str]) -> str:
        if not args:
            return "sudo: usage sudo <command>"
        if args[0] == "-l":
            if self._can_elevate():
                return f"User {self.real_userid} may run all commands in Gibson USS via RACF SPECIAL/BPX.SUPERUSER"
            return f"User {self.real_userid} is not in the sudoers file"
        if not self._can_elevate():
            return f"sudo: {self.real_userid} is not permitted to elevate"
        if args[0] == "su":
            return self._su(args[1:])
        old = self.identity
        old_env = dict(self.environment)
        self.identity = self.env.identity_for("ROOT", superuser=True)
        self.environment["LOGNAME"] = self.identity.userid
        self.environment["USER"] = self.identity.userid
        self.environment["HOME"] = self.identity.home
        self.environment["PWD"] = self.cwd
        out = self.execute(" ".join(args))
        if out is None:
            out = ""
        if self.identity.userid == "ROOT":
            self.identity = old
            self.environment = old_env
        return out

    def _python(self, argv: list[str]) -> str:
        exe = sys.executable
        args = list(argv[1:])
        if args and args[0] in {"-V", "--version"}:
            cp = subprocess.run([exe, *args], capture_output=True, text=True, cwd=self.env.real_path(self.cwd), timeout=10)
            return (cp.stdout or cp.stderr).strip()
        # Validate any path operands after switches.
        safe_args: list[str] = []
        skip_next_is_path = False
        for i, arg in enumerate(args):
            if skip_next_is_path:
                skip_next_is_path = False
                safe_args.append(arg)
                continue
            if arg in {"-c", "-m"}:
                safe_args.append(arg)
                skip_next_is_path = False
                continue
            if arg.startswith("-"):
                safe_args.append(arg)
                continue
            if i == 0 and not arg.startswith("-") and arg not in {"-c", "-m"}:
                vp = self._resolved(arg)
                safe_args.append(str(self.env.real_path(vp)))
            else:
                safe_args.append(arg)
        cp = subprocess.run([exe, *safe_args], capture_output=True, text=True, cwd=self.env.real_path(self.cwd), timeout=15)
        return (cp.stdout + cp.stderr).rstrip("\n")

    def _netstat(self, args: list[str]) -> str:
        if args and args[0].lower() in {"-h", "--help", "help"}:
            return "\n".join([
                "Usage: netstat [HOME|CONFIG|CONN|ALL|DEVLINKS|ROUTE|ARP|PORTLIST|TELNET|FTP]",
                "       netstat -h",
                "       netstat --help",
                "Gibson displays simulated z/OS UNIX / TCPIP stack information.",
                "Canonical host: mainframe",
                "Canonical IP:   127.0.0.1",
            ])
        option = args[0] if args else "ALL"
        return self.state.network.format(option, self.state.sessions.sessions)

    def _ping(self, args: list[str]) -> str:
        if not args:
            return "ping: missing host operand"
        host = ""
        count = 5
        i = 0
        while i < len(args):
            a = args[i]
            if a in {"-c", "-n"} and i + 1 < len(args):
                i += 1
                try:
                    count = int(args[i])
                except ValueError:
                    return f"ping: bad number of packets to transmit: {args[i]}"
            elif a.startswith("-c") and len(a) > 2:
                try:
                    count = int(a[2:])
                except ValueError:
                    return f"ping: bad number of packets to transmit: {a[2:]}"
            elif a.startswith("-"):
                return f"ping: unsupported option {a}"
            else:
                if host:
                    return "ping: multiple hosts are not supported"
                host = a
            i += 1
        if not host:
            return "ping: missing host operand"
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", host) or any(x in host for x in [";", "|", "&", "`", "$", "<", ">", "..", "/"]):
            return "ping: invalid host"
        return ping_command(host, count)

    def _traceroute(self, args: list[str]) -> str:
        hosts = [a for a in args if not a.startswith("-")]
        if not hosts:
            return "traceroute: missing host operand"
        host = hosts[0]
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", host) or any(x in host for x in [";", "|", "&", "`", "$", "<", ">", "..", "/"]):
            return "traceroute: invalid host"
        return traceroute_command(host)

    def _df(self) -> str:
        return (
            "Filesystem   512-blocks      Used Available Capacity Mounted on\n"
            "OMVSROOT        2097152    65536   2031616     4%   /\n"
            "USER.ZFS         262144     1024    261120     1%   /u\n"
            "DSFS             131072     4096    126976     3%   /dsfs"
        )

    def _ps(self) -> str:
        user = self.environment.get("LOGNAME", self.real_userid)
        return (
            " PID  PPID USER     COMMAND\n"
            f"   1     0 OMVSKERN BPXOINIT\n"
            f" 100     1 {user:<8} sh\n"
            f" 101   100 {user:<8} omvs-shell"
        )

# Production USS FTP/Telnet sub-session integration.
try:
    from gibson.apps.uss_ftp_client import FtpSubsession
    from gibson.apps.uss_telnet_client import TelnetSubsession
except Exception:  # pragma: no cover
    FtpSubsession = None  # type: ignore
    TelnetSubsession = None  # type: ignore

_OMVS_ORIG_EXECUTE_PROD = OmvsShellSession.execute

def _omvs_prod_execute(self, raw: str):
    sub = getattr(self, '_network_subsession', None)
    if sub is not None and not (raw.strip().lower().startswith('ftp') or raw.strip().lower().startswith('telnet')):
        out = sub.handle(raw)
        if getattr(sub, 'done', False):
            self._network_subsession = None
        return out
    if sub is not None:
        self._network_subsession = None
    try:
        argv = shlex.split(raw)
    except Exception:
        return _OMVS_ORIG_EXECUTE_PROD(self, raw)
    if argv and argv[0].lower() == 'ftp' and FtpSubsession is not None:
        sub = FtpSubsession(self.env, lambda: self.cwd, lambda p: setattr(self, 'cwd', self.env.resolve(self.cwd, p)))
        self._network_subsession = sub
        if len(argv) >= 2 and argv[1].upper() not in {'HELP','?','-H','--HELP'}:
            return sub.connect_banner() + '\n' + sub.handle('open ' + ' '.join(argv[1:]))
        if len(argv) >= 2:
            self._network_subsession = None
            return sub.help()
        return sub.banner()
    if argv and argv[0].lower() == 'telnet' and TelnetSubsession is not None:
        sub = TelnetSubsession()
        self._network_subsession = sub
        if len(argv) >= 2 and argv[1].upper() not in {'HELP','?','-H','--HELP'}:
            return sub.connect_banner() + '\n' + sub.handle('open ' + ' '.join(argv[1:]))
        if len(argv) >= 2:
            self._network_subsession = None
            return sub.help()
        return sub.banner()
    return _OMVS_ORIG_EXECUTE_PROD(self, raw)

OmvsShellSession.execute = _omvs_prod_execute

# Production-grade persistent USS FTP/Telnet sub-session integration v2.
# Stores active network clients on GibsonState so web/line-oriented callers
# that recreate OmvsShellSession still retain the explicit user sub-session.
try:
    from gibson.apps.uss_ftp_client import FtpSubsession as _ProdFtpSubsession2
    from gibson.apps.uss_telnet_client import TelnetSubsession as _ProdTelnetSubsession2
except Exception:  # pragma: no cover
    _ProdFtpSubsession2 = None  # type: ignore
    _ProdTelnetSubsession2 = None  # type: ignore

_OMVS_EXECUTE_BEFORE_PERSISTENT_NET = OmvsShellSession.execute

def _omvs_persistent_network_execute(self, raw: str):
    try:
        _argv_for_help = shlex.split(raw or '')
    except Exception:
        _argv_for_help = []
    if _argv_for_help and _argv_for_help[0].lower() in {'help', 'man'} and len(_argv_for_help) > 1 and _argv_for_help[1].lower() == 'nmap':
        return self._command_help('nmap')
    if _argv_for_help and _argv_for_help[0].lower() == 'nmap' and len(_argv_for_help) > 1 and _argv_for_help[1].lower() in {'help', '-h', '--help', '?'}:
        return self._command_help('nmap')
    if not hasattr(self.state, '_omvs_network_subsessions'):
        setattr(self.state, '_omvs_network_subsessions', {})
    subs = getattr(self.state, '_omvs_network_subsessions')
    key = (self.real_userid, self.mode)
    sub = subs.get(key)
    text = (raw or '').strip()
    # If a sub-session is active, route all non-new-client commands to it.
    if sub is not None and text.split(maxsplit=1)[0].lower() not in {'ftp', 'telnet'}:
        out = sub.handle(text)
        if getattr(sub, 'done', False):
            subs.pop(key, None)
        return out
    try:
        argv = shlex.split(raw)
    except Exception:
        return _OMVS_EXECUTE_BEFORE_PERSISTENT_NET(self, raw)
    if argv and argv[0].lower() == 'ftp' and _ProdFtpSubsession2 is not None:
        sub = _ProdFtpSubsession2(self.env, lambda: self.cwd,
                                  lambda p: setattr(self, 'cwd', self.env.resolve(self.cwd, p)))
        if len(argv) >= 2 and argv[1].upper() in {'HELP', '?', '-H', '--HELP'}:
            return sub.help()
        subs[key] = sub
        if len(argv) >= 2:
            return sub.connect_banner() + '\n' + sub.handle('open ' + ' '.join(argv[1:]))
        return sub.banner()
    if argv and argv[0].lower() == 'telnet' and _ProdTelnetSubsession2 is not None:
        sub = _ProdTelnetSubsession2()
        if len(argv) >= 2 and argv[1].upper() in {'HELP', '?', '-H', '--HELP'}:
            return sub.help()
        subs[key] = sub
        if len(argv) >= 2:
            return sub.connect_banner() + '\n' + sub.handle('open ' + ' '.join(argv[1:]))
        return sub.banner()
    return _OMVS_EXECUTE_BEFORE_PERSISTENT_NET(self, raw)

OmvsShellSession.execute = _omvs_persistent_network_execute
