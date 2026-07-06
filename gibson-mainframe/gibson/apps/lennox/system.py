"""LENNOX - a tiny standalone training system reached over its own telnet port.

LENNOX is a Linux-style "jump box" that sits on the same network as the Gibson
mainframe.  It is a self-contained capture-the-flag training target: the student
logs in as ``training``, explores a small filesystem, finds credentials that were
left for the mainframe host, and works out the local privilege-escalation path to
root.  Each connection gets its own fresh copy of the world so students never
interfere with one another.

The shell is deliberately small but behaves like a real one: ls/cd/cat/grep/find/
ps/netstat/sudo/uname plus the true-to-life network tools (dig/whois/ping) shared
with the OMVS shell.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HOSTNAME = "lennox"
MF_HOST = "10.0.0.7"          # the mainframe, MFHOST, reachable from LENNOX
FLAG = "GIBSON{lennox_priv_esc_via_sudo_find}"


@dataclass
class Node:
    kind: str                 # "file" | "dir"
    mode: str = "-rw-r--r--"
    owner: str = "training"
    content: str = ""


def _seed_fs() -> Dict[str, Node]:
    d = lambda mode="drwxr-xr-x", owner="root": Node("dir", mode, owner)
    f = lambda content="", mode="-rw-r--r--", owner="training": Node("file", mode, owner, content)
    fs: Dict[str, Node] = {
        "/": d(), "/etc": d(), "/etc/sudoers.d": d(owner="root"), "/home": d(),
        "/home/training": d("drwxr-xr-x", "training"), "/var": d(), "/var/backups": d(),
        "/usr": d(), "/usr/bin": d(), "/root": d("drwx------", "root"), "/tmp": d("drwxrwxrwt", "root"),
    }
    fs["/etc/motd"] = f(
        "  __     _____ _   _ _   _  _____  __  \n"
        " |  |   |  ___| \\ | | \\ | |/ _ \\ \\/ /  LENNOX bastion (training)\n"
        " |  |__ | |__ |  \\| |  \\| | | | \\  /   Ubuntu-like jump host\n"
        " |_____||____||_| \\_|_| \\_|\\___/_/\\_\\  on the GIBSON lab network\n"
        "\n"
        " OBJECTIVE: this box can reach the mainframe (MFHOST). Recover the\n"
        " credentials a careless admin left behind, and find the local path to\n"
        " root. Type 'objective' for the full brief.\n", owner="root")
    fs["/etc/hostname"] = f(HOSTNAME + "\n", owner="root")
    fs["/etc/passwd"] = f(
        "root:x:0:0:root:/root:/bin/bash\n"
        "training:x:1000:1000:Training User:/home/training:/bin/bash\n"
        "backup:x:34:34:backup:/var/backups:/usr/sbin/nologin\n", owner="root")
    fs["/etc/hosts"] = f(
        "127.0.0.1   localhost\n"
        f"{MF_HOST}   mfhost mainframe   # GIBSON z/OS - TSO/TN3270\n", owner="root")
    fs["/home/training/README.txt"] = f(
        "Welcome to LENNOX.\n"
        "I use this box to reach the mainframe (mfhost / " + MF_HOST + ").\n"
        "Check my notes. I think I left a backup of my creds lying around - I really\n"
        "must clean that up.   -- training\n")
    fs["/home/training/notes.txt"] = f(
        "TODO:\n"
        " - rotate the mainframe password (it is in a backup under /var/backups)\n"
        " - the security team keeps nagging about my sudo rights for 'find'\n"
        " - mfhost TSO logon is the usual admin id\n")
    fs["/var/backups/creds.bak"] = f(
        "# mainframe credential backup - DO NOT COMMIT\n"
        "MFHOST  TSO   IBMUSER / IBMPASS\n"
        "MFHOST  TN3270 port 3270\n", mode="-rw-r--r--", owner="training")
    fs["/etc/sudoers.d/training"] = f(
        "# training privileges\n"
        "training ALL=(root) NOPASSWD: /usr/bin/find\n", mode="-r--r--r--", owner="root")
    fs["/root/flag.txt"] = f(FLAG + "\n", mode="-rw-------", owner="root")
    for b in ("bash", "ls", "cat", "find", "grep", "sudo", "ps", "netstat", "dig", "ping"):
        fs[f"/usr/bin/{b}"] = f("", mode="-rwxr-xr-x", owner="root")
    return fs


class LennoxSession:
    def __init__(self, state: Any, addr: str = ""):
        self.state = state
        self.addr = addr
        self.fs = _seed_fs()
        self.user = "training"
        self.is_root = False
        self.cwd = "/home/training"
        self.history: List[str] = []
        self.got_creds = False
        self.got_root = False

    # ----------------------------------------------------------------- paths
    @property
    def whoami(self) -> str:
        return "root" if self.is_root else self.user

    def prompt(self) -> str:
        short = self.cwd.replace("/home/training", "~")
        sig = "#" if self.is_root else "$"
        return f"{self.whoami}@{HOSTNAME}:{short}{sig} "

    def banner(self) -> str:
        m = self.fs.get("/etc/motd")
        return (m.content if m else "") + "\n"

    def _abs(self, path: str) -> str:
        if not path:
            return self.cwd
        if not path.startswith("/"):
            path = (self.cwd.rstrip("/") + "/" + path)
        parts: List[str] = []
        for seg in path.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(seg)
        return "/" + "/".join(parts)

    def _node(self, path: str) -> Optional[Node]:
        return self.fs.get(self._abs(path))

    def _children(self, path: str) -> List[str]:
        base = self._abs(path).rstrip("/") or ""
        out = []
        for p in self.fs:
            if p == "/":
                continue
            parent = p.rsplit("/", 1)[0] or "/"
            if parent == (base or "/"):
                out.append(p.rsplit("/", 1)[1])
        return sorted(out)

    def _readable(self, node: Node) -> bool:
        if self.is_root:
            return True
        # owner read bit vs other read bit
        if node.owner == self.user:
            return node.mode[1] == "r"
        return node.mode[7] == "r"

    # --------------------------------------------------------------- dispatch
    def handle(self, line: str) -> Optional[str]:
        line = (line or "").strip()
        if not line:
            return ""
        self.history.append(line)
        try:
            argv = shlex.split(line)
        except ValueError:
            argv = line.split()
        cmd, args = argv[0], argv[1:]
        fn = getattr(self, f"_c_{cmd}", None)
        if fn is None:
            if cmd in ("exit", "logout", "quit"):
                return None
            return f"{cmd}: command not found"
        return fn(args)

    # --------------------------------------------------------------- commands
    def _c_help(self, a):
        return ("Available: ls cd pwd cat grep find head tail wc whoami id ps netstat "
                "ifconfig uname hostname env echo history clear sudo ssh dig whois ping "
                "objective exit")

    def _c_objective(self, a):
        return ("TRAINING OBJECTIVE\n"
                "  1. This jump box can reach the mainframe (mfhost / " + MF_HOST + ").\n"
                "  2. Recover the mainframe credentials a careless admin left on this host.\n"
                "  3. Escalate from 'training' to 'root' using a local misconfiguration.\n"
                "  4. Read /root/flag.txt to complete the lab.\n"
                "Hints: explore your home dir, /var/backups, and run 'sudo -l'.")

    def _c_pwd(self, a):
        return self.cwd

    def _c_whoami(self, a):
        return self.whoami

    def _c_id(self, a):
        if self.is_root:
            return "uid=0(root) gid=0(root) groups=0(root)"
        return "uid=1000(training) gid=1000(training) groups=1000(training),27(sudo)"

    def _c_hostname(self, a):
        return HOSTNAME

    def _c_uname(self, a):
        if a and a[0] == "-a":
            return "Linux lennox 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux"
        return "Linux"

    def _c_echo(self, a):
        return " ".join(a)

    def _c_clear(self, a):
        return "\033[2J\033[H"

    def _c_history(self, a):
        return "\n".join(f"{i+1:>4}  {h}" for i, h in enumerate(self.history))

    def _c_env(self, a):
        return (f"USER={self.whoami}\nHOME=/home/training\nSHELL=/bin/bash\n"
                f"PATH=/usr/local/bin:/usr/bin:/bin\nHOSTNAME={HOSTNAME}")

    def _c_cd(self, a):
        target = a[0] if a else "/home/training"
        p = self._abs(target)
        n = self.fs.get(p)
        if n is None or n.kind != "dir":
            return f"cd: {target}: No such file or directory"
        self.cwd = p or "/"
        return ""

    def _c_ls(self, a):
        long = any(x.startswith("-") and "l" in x for x in a)
        show_all = any(x.startswith("-") and "a" in x for x in a)
        paths = [x for x in a if not x.startswith("-")] or [self.cwd]
        out = []
        for path in paths:
            n = self._node(path)
            if n is None:
                out.append(f"ls: cannot access '{path}': No such file or directory")
                continue
            names = self._children(path) if n.kind == "dir" else [path.rsplit("/", 1)[-1]]
            if show_all and n.kind == "dir":
                names = [".", ".."] + names
            if long:
                rows = []
                for nm in names:
                    if nm in (".", ".."):
                        rows.append(f"drwxr-xr-x 1 root root 4096 Jan 01 00:00 {nm}")
                        continue
                    cp = self._abs((path.rstrip('/') + '/' + nm) if n.kind == "dir" else path)
                    cn = self.fs.get(cp)
                    if cn is None:
                        continue
                    size = len(cn.content) if cn.kind == "file" else 4096
                    rows.append(f"{cn.mode} 1 {cn.owner:<7} {cn.owner:<7} {size:>5} Jan 01 00:00 {nm}")
                out.append("\n".join(rows))
            else:
                out.append("  ".join(names))
        return "\n".join(out)

    def _c_cat(self, a):
        if not a:
            return "cat: missing operand"
        out = []
        for path in a:
            n = self._node(path)
            if n is None:
                out.append(f"cat: {path}: No such file or directory")
            elif n.kind == "dir":
                out.append(f"cat: {path}: Is a directory")
            elif not self._readable(n):
                out.append(f"cat: {path}: Permission denied")
            else:
                if self._abs(path) == "/var/backups/creds.bak":
                    self.got_creds = True
                if self._abs(path) == "/root/flag.txt" and self.is_root:
                    self.got_root = True
                    out.append(n.content.rstrip("\n"))
                    out.append("\n*** LAB COMPLETE - you recovered the flag as root. ***")
                    continue
                out.append(n.content.rstrip("\n"))
        return "\n".join(out)

    def _c_head(self, a):
        files = [x for x in a if not x.startswith("-")]
        return self._c_cat(files[:1])

    _c_tail = _c_head

    def _c_wc(self, a):
        files = [x for x in a if not x.startswith("-")]
        if not files:
            return "wc: missing operand"
        n = self._node(files[0])
        if n is None or n.kind != "file" or not self._readable(n):
            return f"wc: {files[0]}: cannot read"
        c = n.content
        return f" {c.count(chr(10))} {len(c.split())} {len(c)} {files[0]}"

    def _c_grep(self, a):
        if len(a) < 2:
            return "usage: grep PATTERN FILE"
        pat = a[0]
        out = []
        for path in a[1:]:
            n = self._node(path)
            if n is None or n.kind != "file" or not self._readable(n):
                continue
            for ln in n.content.splitlines():
                if pat.lower() in ln.lower():
                    out.append(ln)
        return "\n".join(out) if out else ""

    def _c_find(self, a):
        # privilege escalation: sudo find ... -exec <shell> ;  -> root
        start = "."
        non_opt = [x for x in a if not x.startswith("-")]
        if non_opt:
            start = non_opt[0]
        base = self._abs(start)
        hits = [p for p in sorted(self.fs) if p == base or p.startswith(base.rstrip("/") + "/")]
        if not self.is_root:
            hits = [p for p in hits if self._readable(self.fs[p]) or self.fs[p].kind == "dir"]
        return "\n".join(hits)

    def _c_sudo(self, a):
        if not a:
            return "usage: sudo -l | sudo <command>"
        if a[0] == "-l":
            return ("Matching Defaults entries for training on lennox:\n"
                    "    env_reset, secure_path=/usr/bin:/bin\n\n"
                    "User training may run the following commands on lennox:\n"
                    "    (root) NOPASSWD: /usr/bin/find")
        if a[0] in ("find", "/usr/bin/find"):
            rest = a[1:]
            joined = " ".join(rest)
            if "-exec" in rest and any(s in joined for s in ("/bin/sh", "/bin/bash", "sh", "bash", "/bin/sh;")):
                self.is_root = True
                self.got_root = True
                return ("# id\nuid=0(root) gid=0(root) groups=0(root)\n"
                        "*** privilege escalation successful - you are now root via sudo find -exec ***\n"
                        "Now read /root/flag.txt")
            # ordinary sudo find runs as root (so it can read everything) but no shell
            self.is_root_find = True
            saved = self.is_root
            self.is_root = True
            try:
                out = self._c_find(rest)
            finally:
                self.is_root = saved
            return out + "\n(hint: find can run -exec ... try: sudo find . -exec /bin/sh \\;)"
        return f"sudo: {a[0]}: command not allowed (see 'sudo -l')"

    def _c_ps(self, a):
        return ("  PID TTY          TIME CMD\n"
                "    1 ?        00:00:01 systemd\n"
                "  412 ?        00:00:00 sshd\n"
                "  880 pts/0    00:00:00 bash\n"
                "  905 pts/0    00:00:00 ps")

    def _c_netstat(self, a):
        return ("Active Internet connections (servers and established)\n"
                "Proto Local Address           Foreign Address         State\n"
                "tcp   0.0.0.0:22              0.0.0.0:*               LISTEN\n"
                f"tcp   {MF_HOST}:0            mfhost:3270             (reachable)\n")

    def _c_ifconfig(self, a):
        return ("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
                "        inet 10.0.0.42  netmask 255.255.255.0  broadcast 10.0.0.255\n"
                "        ether 02:42:0a:00:00:2a  txqueuelen 1000  (Ethernet)")

    _c_ip = _c_ifconfig

    def _c_ssh(self, a):
        host = a[-1] if a else ""
        if "mfhost" in host or MF_HOST in host:
            return ("ssh: connect to host mfhost port 22: Connection refused\n"
                    "(the mainframe speaks TN3270/TSO, not ssh - use a 3270 client on port 3270\n"
                    " with the credentials you recovered)")
        return f"ssh: Could not resolve hostname {host}: Name or service not known"

    # network tools shared with OMVS (true-to-life)
    def _net(self, tool, a):
        from gibson.core import net_tools
        if tool == "dig":
            return net_tools.dig_command(None, None, a)
        if tool == "whois":
            return net_tools.whois_command(None, None, a)
        if tool == "ping":
            cnt = 4
            args = list(a)
            if "-c" in args:
                i = args.index("-c")
                try:
                    cnt = int(args[i + 1])
                    del args[i:i + 2]
                except Exception:
                    pass
            host = ([x for x in args if not x.startswith("-")] or ["mfhost"])[0]
            return net_tools.ping_command(host, cnt)
        return ""

    def _c_dig(self, a):
        return self._net("dig", a)

    def _c_whois(self, a):
        return self._net("whois", a)

    def _c_ping(self, a):
        return self._net("ping", a)
