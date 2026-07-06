from __future__ import annotations
from typing import Any
import socketserver
import threading

ALLOWED = {
    "id": "uid=12345(tomcat) gid=1000(tomcat)",
    "whoami": "tomcat",
    "hostname": "mainframe",
    "pwd": "/u/tomcat",
    "ls": "conf\nlogs\nwebapps\nwork",
    "cat /etc/profile": "# Gibson z/OS UNIX training profile\nPATH=/bin:/usr/lpp/java/bin",
    "cat /u/tomcat/conf/server.xml": "<Server port=\"8005\"><Service name=\"Catalina\"><Connector port=\"8080\" protocol=\"HTTP/1.1\" /></Service></Server>",
    "uname": "z/OS UNIX Gibson training simulator",
    "env": "USER=tomcat\nHOME=/u/tomcat\nCATALINA_BASE=/u/tomcat\nGIBSON_SIMULATION=SAFE",
    "help": "Allowed commands: id, whoami, hostname, pwd, ls, cat /etc/profile, cat /u/tomcat/conf/server.xml, uname, env, help, exit",
}
DENY_MARKERS = [";", "&&", "||", "`", "$(", ">", "<", "|", "../", "sh", "bash", "python", "perl", "nc", "ncat", "curl", "wget", "ssh", "scp", "rm", "chmod", "chown"]


def run_command(state: Any, session_id: int, command: str) -> str:
    from .state import get_state
    cmd = (command or "").strip()
    sim = get_state(state)
    sess = sim.sessions.get(int(session_id))
    if not sess or not sess.active:
        return "session closed"
    if cmd.lower() == "exit":
        sess.active = False
        return "logout"
    low = cmd.lower()
    if not cmd:
        return ""
    if any(m in low for m in DENY_MARKERS):
        out = "GIBSON-SAFE-SHELL: command denied by simulator allowlist"
    else:
        out = ALLOWED.get(low, "GIBSON-SAFE-SHELL: command denied by simulator allowlist")
    sess.commands.append({"command": cmd, "result": out[:200]})
    try:
        from .events import record_session_command
        record_session_command(state, sess, cmd, out)
    except Exception:
        pass
    return out


class _BindHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state = self.server.state  # type: ignore[attr-defined]
        from .state import active_sessions
        sessions = active_sessions(state)
        sid = sessions[-1].session_id if sessions else 1
        self.wfile.write(b"Gibson controlled Tomcat training shell. Type help or exit.\n$ ")
        while True:
            line = self.rfile.readline(1024)
            if not line:
                break
            cmd = line.decode("utf-8", errors="ignore").strip()
            out = run_command(state, sid, cmd)
            self.wfile.write((out.rstrip() + "\n").encode("utf-8", errors="ignore"))
            if cmd.lower() == "exit":
                break
            self.wfile.write(b"$ ")


class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_listener(state: Any, port: int = 31337) -> bool:
    from .state import get_state
    sim = get_state(state)
    if sim.listener_started and sim.listener_server is not None:
        return True
    try:
        host = getattr(getattr(state, "config", object()), "host", "127.0.0.1") or "127.0.0.1"
        srv = _ThreadedTCPServer((host, int(port)), _BindHandler)
        srv.state = state  # type: ignore[attr-defined]
        th = threading.Thread(target=srv.serve_forever, name="GibsonTomcat31337", daemon=True)
        th.start()
        sim.listener_started = True
        sim.listener_server = srv
        try:
            state.allowed_high_ports.add(int(port))
        except Exception:
            pass
        try:
            from gibson.core.network import Listener
            if not any(getattr(l, "port", None) == int(port) and getattr(l, "name", "") == "TOMCATSH" for l in state.network.listeners):
                state.network.listeners.append(Listener("TOMCATSH", int(port), jobname="TOMCAT", user="TOMCAT", description="Gibson controlled Tomcat training shell"))
        except Exception:
            pass
        return True
    except OSError:
        # Port may already be held by another test or the current listener. Keep safe state open.
        sim.listener_started = False
        return False
