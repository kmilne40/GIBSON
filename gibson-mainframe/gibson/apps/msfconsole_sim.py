from __future__ import annotations

from typing import Any, Callable
import shlex

from gibson.apps.tomcat_sim.state import deploy_war, create_session, active_sessions
from gibson.apps.tomcat_sim.events import record_upload, record_deploy, record_payload_trigger
from gibson.apps.tomcat_sim.session import run_command, start_listener
from gibson.apps.tomcat_sim.config import get_config
from gibson.tools.host_aliases import resolve_host

SUPPORTED_MODULE = "exploit/multi/http/tomcat_mgr_upload"

OPTION_ALIASES = {
    "rhost": "RHOSTS",
    "rhosts": "RHOSTS",
    "rport": "RPORT",
    "targeturi": "TARGETURI",
    "username": "HttpUsername",
    "httpusername": "HttpUsername",
    "httppassword": "HttpPassword",
    "password": "HttpPassword",
    "lhost": "LHOST",
    "lport": "LPORT",
    "payload": "PAYLOAD",
}

class MsfConsoleSim:
    """Stateful, self-contained msfconsole training simulator.

    The simulator intentionally supports only Gibson's safe Tomcat Manager
    upload lab. It never launches Metasploit, never executes WARs and never
    spawns a host shell.
    """

    def __init__(self, state: Any, env: Any | None = None, cwd: str = "/u/ibmuser"):
        self.state = state
        self.env = env
        self.cwd = cwd
        self.module = ""
        self.in_session: int | None = None
        self.options = {
            "RHOSTS": "",
            "RPORT": "8080",
            "TARGETURI": "/manager",
            "HttpUsername": "",
            "HttpPassword": "",
            "LHOST": "127.0.0.1",
            "LPORT": "31337",
            "PAYLOAD": "java/jsp_shell_bind_tcp",
        }

    def prompt(self) -> str:
        if self.in_session is not None:
            return f"shell {self.in_session} > "
        if self.module:
            return f"msf6 exploit({self.module}) > "
        return "msf6 > "

    def execute(self, text: str) -> str:
        out: list[str] = []
        for raw in [x.strip() for x in text.replace(";", "\n").splitlines() if x.strip()]:
            result = self.one(raw)
            if result == "__EXIT__":
                break
            if result:
                out.append(result)
        return "\n".join(out)

    def run_interactive(self, io_or_reader, writer: Callable[[str], None]) -> None:
        writer(self.banner())
        while True:
            result = self._read_line(io_or_reader, self.prompt())
            if getattr(result, "key", "") == "EOF":
                return
            text = (getattr(result, "text", "") or "").strip()
            if not text:
                continue
            output = self.one(text)
            if output == "__EXIT__":
                return
            if output:
                writer(output.rstrip("\n") + "\n")

    @staticmethod
    def _read_line(io_or_reader, prompt: str):
        if hasattr(io_or_reader, "read_line"):
            return io_or_reader.read_line(prompt, hidden=False, mask=False)
        return io_or_reader(prompt, False)

    def banner(self) -> str:
        return "\n".join([
            "Metasploit Framework 6 Gibson Training Console",
            "Gibson supports the safe Tomcat Manager upload simulation only.",
            "Type help for supported commands.",
        ]) + "\n"

    def one(self, raw: str) -> str:
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            return f"syntax error: {exc}"
        if not argv:
            return ""
        if self.in_session is not None:
            return self._session_command(argv)
        cmd = argv[0].lower()
        if cmd in {"help", "?"}:
            return self._help()
        if cmd == "search":
            term = " ".join(argv[1:]).lower()
            if "tomcat" in term or not term:
                return "\n".join([
                    "Matching Modules",
                    "================",
                    "",
                    "   #  Name                                      Disclosure Date  Rank    Check  Description",
                    "   -  ----                                      ---------------  ----    -----  -----------",
                    "   0  exploit/multi/http/tomcat_mgr_upload                       normal  No     Tomcat Manager WAR upload training simulation",
                ])
            return "No results from search"
        if cmd == "use":
            selected = argv[1] if len(argv) > 1 else ""
            if selected == "0":
                selected = SUPPORTED_MODULE
            if selected != SUPPORTED_MODULE:
                return "[-] Gibson msfconsole supports only exploit/multi/http/tomcat_mgr_upload"
            self.module = selected
            return f"[*] Using configured module {selected}"
        if cmd == "back":
            self.module = ""
            return ""
        if cmd == "show" and len(argv) > 1 and argv[1].lower() == "options":
            return self._show_options()
        if cmd == "set" and len(argv) >= 3:
            return self._set_option(argv[1], " ".join(argv[2:]))
        if cmd in {"run", "exploit"}:
            return self._run()
        if cmd == "sessions":
            return self._sessions(argv[1:])
        if cmd in {"exit", "quit"}:
            return "__EXIT__"
        return "Unknown command. Type help."

    def _help(self) -> str:
        return "\n".join([
            "Core Commands",
            "=============",
            "search, use, show options, set, run, exploit, sessions, back, exit, quit",
            "",
            "Gibson supports exploit/multi/http/tomcat_mgr_upload only.",
            "Allowed RHOSTS: mainframe, localhost, 127.0.0.1 or safe local aliases.",
        ])

    def _canonical_key(self, key: str) -> str:
        return OPTION_ALIASES.get(key.lower(), key)

    def _set_option(self, key: str, val: str) -> str:
        canonical = self._canonical_key(key)
        if canonical not in self.options:
            return f"Unknown datastore option: {key}"
        self.options[canonical] = val
        return f"{canonical} => {val}"

    def _show_options(self) -> str:
        if not self.module:
            return "No module selected. Use exploit/multi/http/tomcat_mgr_upload."
        rows = [
            f"Module options ({SUPPORTED_MODULE}):",
            "",
            "   Name          Current Setting  Required  Description",
            "   ----          ---------------  --------  -----------",
        ]
        desc = {
            "RHOSTS": "Target host(s)",
            "RPORT": "Target HTTP port",
            "TARGETURI": "Base path to Tomcat Manager",
            "HttpUsername": "Tomcat Manager username",
            "HttpPassword": "Tomcat Manager password",
        }
        for k in ["RHOSTS", "RPORT", "TARGETURI", "HttpUsername", "HttpPassword"]:
            rows.append(f"   {k:<13} {self.options.get(k,''):<16} yes       {desc[k]}")
        rows += [
            "",
            "Payload options (java/jsp_shell_bind_tcp):",
            "",
            "   Name          Current Setting  Required  Description",
            "   ----          ---------------  --------  -----------",
            f"   LHOST         {self.options.get('LHOST',''):<16} yes       Gibson local handler host",
            f"   LPORT         {self.options.get('LPORT',''):<16} yes       Gibson safe session port",
        ]
        return "\n".join(rows)

    def _run(self) -> str:
        if self.module != SUPPORTED_MODULE:
            return "[-] No module selected. Use exploit/multi/http/tomcat_mgr_upload."
        rhosts = self.options.get("RHOSTS", "") or ""
        if not rhosts:
            return "[-] RHOSTS is required"
        resolved = resolve_host(rhosts, self.env, self.cwd)
        if not resolved.allowed:
            return "[-] Target outside Gibson training scope: " + resolved.reason
        rport = str(self.options.get("RPORT", "8080"))
        if rport != "8080":
            return "[-] Gibson Tomcat Manager simulation is available on RPORT 8080"
        targeturi = (self.options.get("TARGETURI", "/manager") or "/manager").rstrip("/")
        if targeturi != "/manager":
            return "[-] TARGETURI must be /manager for the Gibson Tomcat simulation"
        user = self.options.get("HttpUsername", "")
        pw = self.options.get("HttpPassword", "")
        if not ((user == "tomcat" and pw in {"tomcat", "manager"}) or (user == "manager" and pw == "manager")):
            return "[-] Authentication failed against Tomcat Manager simulation"
        cfg = get_config(self.state)
        try:
            port = int(self.options.get("LPORT", str(cfg.pseudo_bind_port)) or cfg.pseudo_bind_port)
        except Exception:
            port = cfg.pseudo_bind_port
        if port != cfg.pseudo_bind_port:
            return f"[-] Gibson safe Tomcat session port is fixed at {cfg.pseudo_bind_port}"
        body = f"GIBSON-SAFE-WAR payload=java/jsp_shell_bind_tcp LPORT={port}".encode()
        ok, msg, dep = deploy_war(self.state, "/shell_exploit", "ws_shell_exploit.war", body, user, update=True)
        if not ok or dep is None:
            return "[-] " + msg
        record_upload(self.state, dep); record_deploy(self.state, dep)
        sess = create_session(self.state, dep.context, user)
        if cfg.allow_pseudo_bind_listener:
            start_listener(self.state, cfg.pseudo_bind_port)
        record_payload_trigger(self.state, sess)
        try:
            if hasattr(self.state, "security_events"):
                self.state.security_events.append({"source":"MSFCONSOLE","target":resolved.display,"port":8080,"session":sess.session_id,"severity":"HIGH","message":"Tomcat Manager safe session created"})
        except Exception:
            pass
        return "\n".join([
            f"[*] Started bind TCP handler against {self.options.get('LHOST','127.0.0.1')}:{cfg.pseudo_bind_port}",
            f"[*] Authenticating to Tomcat Manager at http://{rhosts}:8080{targeturi}/html",
            f"[+] Authenticated as {user}",
            "[*] Uploading ws_shell_exploit.war",
            "[+] WAR deployed at /shell_exploit",
            "[*] Triggering /shell_exploit",
            f"[+] Command shell session {sess.session_id} opened (tomcat @ mainframe) on port {sess.port}",
        ])

    def _sessions(self, args: list[str]) -> str:
        if args and args[0] in {"-i", "-u"}:
            if len(args) < 2:
                return "Usage: sessions -i <id>"
            try:
                sid = int(args[1])
            except Exception:
                return "Invalid session id"
            sessions = {s.session_id: s for s in active_sessions(self.state)}
            if sid not in sessions:
                return f"No such session: {sid}"
            self.in_session = sid
            return f"[*] Starting interaction with {sid}..."
        sessions = active_sessions(self.state)
        if not sessions:
            return "Active sessions\n===============\n\nNo active sessions."
        lines = [
            "Active sessions",
            "===============",
            "",
            "  Id  Name  Type   Information        Connection",
            "  --  ----  ----   -----------        ----------",
        ]
        for s in sessions:
            lines.append(f"  {s.session_id:<3}       shell  tomcat @ mainframe  127.0.0.1:{s.port}")
        return "\n".join(lines)

    def _session_command(self, argv: list[str]) -> str:
        cmd = " ".join(argv).strip()
        if cmd.lower() in {"exit", "background"}:
            self.in_session = None
            return "[*] Backgrounding session 1..."
        if cmd.lower() == "quit":
            self.in_session = None
            return "__EXIT__"
        dangerous = {"sh","bash","python","python3","perl","nc","ncat","ssh","scp","rm","chmod","chown"}
        if argv and argv[0].lower() in dangerous:
            return "Command denied by Gibson safe-session policy"
        if any(x in cmd for x in [";", "&&", "||", "`", "$(", ">", "<"]):
            return "Command denied by Gibson safe-session policy"
        return run_command(self.state, self.in_session or 1, cmd)


def run_msfconsole_sim(state: Any, args: list[str], env: Any | None = None, cwd: str = "/u/ibmuser") -> str:
    sim = MsfConsoleSim(state, env=env, cwd=cwd)
    if not args:
        return "msf6 >"
    if args[0].lower() == "chapter8":
        return sim.execute("search tomcat\nuse exploit/multi/http/tomcat_mgr_upload\nshow options\nset RHOSTS mainframe\nset HttpUsername tomcat\nset HttpPassword tomcat\nrun\nsessions")
    if args[0] == "-x" and len(args) > 1:
        cmd_text = " ".join(args[1:])
        # One-shot -x examples in the book/tests often assume the Tomcat module
        # context after a prior training run. If the supplied command goes
        # straight to run/exploit, preselect the only supported safe module.
        lowered = cmd_text.lower()
        if ("run" in lowered or "exploit" in lowered) and "use " not in lowered:
            sim.module = SUPPORTED_MODULE
            sim.options["RHOSTS"] = "mainframe"
            sim.options["HttpUsername"] = "tomcat"
            sim.options["HttpPassword"] = "tomcat"
        return sim.execute(cmd_text)
    return sim.execute(" ".join(args))


def run_msfconsole_interactive(state: Any, args: list[str], env: Any, cwd: str, io_or_reader, writer: Callable[[str], None]) -> None:
    sim = MsfConsoleSim(state, env=env, cwd=cwd)
    if args and args[0] == "-x" and len(args) > 1:
        out = sim.execute(" ".join(args[1:]))
        if out:
            writer(out.rstrip("\n") + "\n")
        return
    sim.run_interactive(io_or_reader, writer)


def run_msfvenom_sim(env: Any, cwd: str, args: list[str]) -> str:
    out = "ws_shell_exploit.war"
    lport = "31337"
    for i, a in enumerate(args):
        if a == "-o" and i + 1 < len(args): out = args[i+1]
        if a.startswith("LPORT="): lport = a.split("=",1)[1]
    data = f"GIBSON-SAFE-WAR\npayload=java/jsp_shell_bind_tcp\nLPORT={lport}\n".encode()
    try:
        vp = env.resolve(cwd, out)
        real = env.real_path(vp)
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_bytes(data)
        return f"Payload size: {len(data)} bytes\nSaved as: {out}\nGibson note: harmless WAR metadata artifact created; no executable JSP/Java payload is present."
    except Exception as exc:
        return f"msfvenom-sim: {exc}"
