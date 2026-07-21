from __future__ import annotations

import html
import json
import socket
import threading
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, Optional

from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response
from websockets.datastructures import Headers
from websockets.sync.server import ServerConnection, serve

from gibson.core.state import GibsonState

_KEY_BYTES: dict[str, bytes] = {
    "PF3": b"PF3\r", "F3": b"PF3\r",
    "PF7": b"PF7\r", "F7": b"PF7\r",
    "PF8": b"PF8\r", "F8": b"PF8\r",
    "TAB": b"\t", "ENTER": b"\r", "CLEAR": b"CLEAR\r",
    "PA1": b"PA1\r", "PA2": b"PA2\r",
}
_MAX_MESSAGE = 65536
_BACKEND_READ_SIZE = 8192


def _backend_host_for(config_host: str) -> str:
    # 0.0.0.0 is a bind address, not a connection target.
    if config_host in ("", "0.0.0.0", "::", "::0"):
        return "127.0.0.1"
    if config_host in ("127.0.0.1", "localhost", "::1"):
        return "127.0.0.1"
    # The browser bridge is local to the Gibson process; connect to the local listener.
    return "127.0.0.1"


def _json_response(status: int, payload: dict[str, Any]) -> Response:
    body = json.dumps(payload, indent=2).encode("utf-8")
    return Response(status, "OK" if status < 400 else "ERROR", Headers([
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Length", str(len(body))),
    ]), body)


def _html_response(body_text: str, status: int = 200) -> Response:
    body = body_text.encode("utf-8", errors="ignore")
    return Response(status, "OK" if status < 400 else "ERROR", Headers([
        ("Content-Type", "text/html; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Length", str(len(body))),
    ]), body)


def _text_response(body_text: str, status: int = 200) -> Response:
    body = body_text.encode("utf-8", errors="ignore")
    return Response(status, "OK" if status < 400 else "ERROR", Headers([
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(body))),
    ]), body)


class TerminalBridgeSession:
    """A WebSocket-to-raw-Gibson-terminal bridge.

    The browser terminal is a frontend transport only.  It opens a local TCP
    connection to the existing Gibson raw terminal listener (normally
    127.0.0.1:2023) and bridges bytes in both directions.  The raw telnet/ncat
    path remains the source of truth and is not replaced.
    """

    mode = "xtermjs-websocket-bridge"

    def __init__(self, state: GibsonState, client_ip: str):
        self.state = state
        self.client_ip = client_ip
        self.session_id = uuid.uuid4().hex
        self.created = time.time()
        self.last_input: Optional[float] = None
        self.last_output: Optional[float] = None
        self.bytes_in = 0
        self.bytes_out = 0
        self.state_name = "CONNECTING"
        self.last_error: Optional[str] = None
        self.closed = False
        self.backend_host = _backend_host_for(str(getattr(state.config, "host", "127.0.0.1")))
        self.backend_port = int(getattr(state.config, "port", 2023))
        self.backend: Optional[socket.socket] = None
        self._send_lock = threading.Lock()

    def connect_backend(self) -> None:
        try:
            sock = socket.create_connection((self.backend_host, self.backend_port), timeout=5.0)
            sock.settimeout(0.25)
            self.backend = sock
            self.state_name = "CONNECTED"
            try:
                self.state.record_security_event(
                    "WEBTERM", "SESSION", "WEB TERMINAL BRIDGE SESSION START",
                    service="WEBTERM", addr=self.client_ip,
                    backend=f"{self.backend_host}:{self.backend_port}",
                )
            except Exception:
                pass
        except Exception as exc:
            self.state_name = "ERROR"
            self.last_error = f"Could not connect to Gibson terminal backend on {self.backend_host}:{self.backend_port}: {exc}"
            raise ConnectionError(self.last_error) from exc

    def send_backend(self, data: bytes) -> None:
        if not self.backend or self.closed:
            raise ConnectionError("backend terminal session is not connected")
        if len(data) > _MAX_MESSAGE:
            raise ValueError("terminal input too large")
        self.backend.sendall(data)
        self.bytes_in += len(data)
        self.last_input = time.time()

    def send_key(self, key: str) -> None:
        k = (key or "").strip().upper()
        self.send_backend(_KEY_BYTES.get(k, (k + "\r").encode("utf-8", errors="ignore")))

    def close(self) -> None:
        self.closed = True
        if self.state_name not in {"ERROR"}:
            self.state_name = "DISCONNECTED"
        try:
            if self.backend is not None:
                try:
                    self.backend.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.backend.close()
        except Exception:
            pass
        try:
            self.state.record_security_event("WEBTERM", "SESSION", "WEB TERMINAL BRIDGE SESSION END", service="WEBTERM", addr=self.client_ip)
        except Exception:
            pass

    def to_diag(self) -> dict[str, Any]:
        def iso(ts: Optional[float]) -> Optional[str]:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None
        return {
            "session_id": self.session_id,
            "state": self.state_name,
            "client_ip": self.client_ip,
            "backend_host": self.backend_host,
            "backend_port": self.backend_port,
            "created": iso(self.created),
            "last_input": iso(self.last_input),
            "last_output": iso(self.last_output),
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "last_error": self.last_error,
        }


class WebTerminalState:
    def __init__(self, gibson_state: GibsonState):
        self.gibson_state = gibson_state
        self.sessions: Dict[str, TerminalBridgeSession] = {}
        self.lock = threading.Lock()
        self.last_error: Optional[str] = None

    def add(self, session: TerminalBridgeSession) -> None:
        with self.lock:
            self.sessions[session.session_id] = session

    def remove(self, session: TerminalBridgeSession) -> None:
        with self.lock:
            self.sessions.pop(session.session_id, None)
        session.close()

    def diagnostics(self) -> dict[str, Any]:
        self.cleanup()
        state = self.gibson_state
        host = _backend_host_for(str(getattr(state.config, "host", "127.0.0.1")))
        port = int(getattr(state.config, "port", 2023))
        backend_connectable = False
        connect_error: Optional[str] = None
        try:
            with socket.create_connection((host, port), timeout=0.5):
                backend_connectable = True
        except Exception as exc:
            connect_error = f"Backend terminal not connectable on {host}:{port}: {exc}"
            self.last_error = connect_error
        with self.lock:
            sessions = [s.to_diag() for s in self.sessions.values()]
        return {
            "web_terminal": "STARTED",
            "web_port": int(getattr(state.config, "web_terminal_port", 8023)),
            "mode": "xtermjs-websocket-bridge",
            "backend": "raw-gibson-terminal",
            "backend_host": host,
            "backend_port": port,
            "backend_connectable": backend_connectable,
            "raw_telnet_port": port,
            "active_browser_sessions": len(sessions),
            "last_error": self.last_error or connect_error,
            "sessions": sessions,
        }

    def cleanup(self) -> None:
        with self.lock:
            expired = [sid for sid, sess in self.sessions.items() if sess.closed]
            for sid in expired:
                self.sessions.pop(sid, None)


class WebTerminalServerWrapper:
    def __init__(self, state: GibsonState):
        self.state = state
        self.host = state.config.host
        self.port = int(state.config.web_terminal_port)
        self.server_address = (self.host, self.port)
        self.wt_state = WebTerminalState(state)
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> "WebTerminalServerWrapper":
        def handler(conn: ServerConnection) -> None:
            self._handle_ws(conn)

        def process_request(conn: ServerConnection, request) -> Optional[Response]:
            try:
                client_ip = "unknown"
                try:
                    client_ip = str(conn.remote_address[0]) if conn.remote_address else "unknown"
                    self.state.note_port_touch(client_ip, self.port, service="WEBTERM")
                except Exception:
                    pass
                path = request.path.split("?", 1)[0]
                if path == "/ws/terminal":
                    return None
                if path == "/health":
                    return _json_response(200, {"ok": True, "service": "Gibson Browser Terminal", "mode": "xtermjs-websocket-bridge"})
                if path == "/api/diagnostics":
                    return _json_response(200, self.wt_state.diagnostics())
                if path == "/api/state":
                    return _json_response(200, {"service": "Gibson Browser Terminal", "mode": "xtermjs-websocket-bridge", "raw_telnet_port": int(getattr(self.state.config, "port", 2023)), "buttons": list(_KEY_BYTES)})
                if path in {"/", "/index.html"}:
                    return _html_response(self._page())
                return _text_response("Not found", 404)
            except Exception as exc:
                self.wt_state.last_error = f"HTTP request failed: {type(exc).__name__}: {exc}"
                return _json_response(500, {"ok": False, "message": self.wt_state.last_error})

        self._server = serve(
            handler,
            self.host,
            self.port,
            process_request=process_request,
            compression=None,
            max_size=_MAX_MESSAGE,
            ping_interval=20,
            ping_timeout=20,
            server_header="GibsonWebTerminal/30.288",
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="GibsonWebTerminalXtermBridge")
        self._thread.start()
        try:
            self.state.allowed_high_ports.add(self.port)
            self.state.register_open_port(self.port, "TCP", "WEBTERM")
        except Exception:
            pass
        return self

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
        with self.wt_state.lock:
            sessions = list(self.wt_state.sessions.values())
            self.wt_state.sessions.clear()
        for sess in sessions:
            sess.close()

    def server_close(self) -> None:
        self.shutdown()

    def _send_json(self, conn: ServerConnection, payload: dict[str, Any], lock: threading.Lock) -> None:
        with lock:
            conn.send(json.dumps(payload))

    def _handle_ws(self, conn: ServerConnection) -> None:
        session = TerminalBridgeSession(self.state, self._client_ip(conn))
        send_lock = threading.Lock()
        stop = threading.Event()
        try:
            session.connect_backend()
            self.wt_state.add(session)
            self._send_json(conn, {"type": "status", "state": "CONNECTED", "session_id": session.session_id}, send_lock)
            self._send_json(conn, {"type": "diagnostics", "data": session.to_diag()}, send_lock)
        except Exception as exc:
            self.wt_state.last_error = str(exc)
            try:
                self._send_json(conn, {"type": "status", "state": "ERROR", "session_id": session.session_id}, send_lock)
                self._send_json(conn, {"type": "error", "message": str(exc)}, send_lock)
            finally:
                session.close()
            return

        def backend_to_browser() -> None:
            assert session.backend is not None
            while not stop.is_set() and not session.closed:
                try:
                    data = session.backend.recv(_BACKEND_READ_SIZE)
                    if not data:
                        session.state_name = "DISCONNECTED"
                        session.closed = True
                        break
                    session.bytes_out += len(data)
                    session.last_output = time.time()
                    # Preserve terminal bytes as text. The frontend terminal handles CR/LF and ANSI.
                    text = data.decode("utf-8", errors="ignore")
                    self._send_json(conn, {"type": "output", "data": text}, send_lock)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not session.closed:
                        session.state_name = "ERROR"
                        session.last_error = str(exc)
                    break
                except Exception as exc:
                    session.state_name = "ERROR"
                    session.last_error = f"Backend stream failed: {type(exc).__name__}: {exc}"
                    break
            stop.set()
            try:
                self._send_json(conn, {"type": "status", "state": session.state_name, "session_id": session.session_id}, send_lock)
            except Exception:
                pass

        reader = threading.Thread(target=backend_to_browser, daemon=True, name=f"WebTermBackendPump-{session.session_id[:8]}")
        reader.start()
        try:
            for raw in conn:
                if stop.is_set() or session.closed:
                    break
                if isinstance(raw, bytes):
                    payload = raw.decode("utf-8", errors="ignore")
                else:
                    payload = raw
                if len(payload) > _MAX_MESSAGE:
                    self._send_json(conn, {"type": "error", "message": "WebSocket message too large"}, send_lock)
                    continue
                try:
                    msg = json.loads(payload)
                except Exception:
                    self._send_json(conn, {"type": "error", "message": "Invalid JSON message"}, send_lock)
                    continue
                mtype = str(msg.get("type") or "")
                try:
                    if mtype == "input":
                        data = str(msg.get("data") or "")
                        session.send_backend(data.encode("utf-8", errors="ignore"))
                    elif mtype == "key":
                        session.send_key(str(msg.get("key") or ""))
                    elif mtype == "resize":
                        # Accepted for protocol compatibility. Raw backend remains authoritative.
                        continue
                    elif mtype == "ping":
                        self._send_json(conn, {"type": "pong"}, send_lock)
                    elif mtype == "diagnostics":
                        self._send_json(conn, {"type": "diagnostics", "data": session.to_diag()}, send_lock)
                    else:
                        self._send_json(conn, {"type": "error", "message": f"Unknown message type: {mtype}"}, send_lock)
                except Exception as exc:
                    session.state_name = "ERROR"
                    session.last_error = str(exc)
                    self._send_json(conn, {"type": "error", "message": str(exc)}, send_lock)
        except ConnectionClosed:
            pass
        except Exception as exc:
            self.wt_state.last_error = f"WebSocket session failed: {type(exc).__name__}: {exc}"
        finally:
            stop.set()
            self.wt_state.remove(session)

    def _client_ip(self, conn: ServerConnection) -> str:
        try:
            return str(conn.remote_address[0]) if conn.remote_address else "unknown"
        except Exception:
            return "unknown"

    def _page(self) -> str:
        buttons = "".join(f"<button type='button' onclick=\"sendKey('{b}')\">{b}</button>" for b in ["PF3", "PF7", "PF8", "TAB", "ENTER", "CLEAR", "PA1", "PA2"])
        port = html.escape(str(self.port))
        return f"""<!doctype html><html><head><meta charset='utf-8'><title>Gibson Browser Terminal</title>
<style>
html,body{{height:100%;margin:0;background:#010501;color:#00ff66;font-family:ui-monospace,Consolas,monospace}}
body{{display:flex;flex-direction:column}}
header{{padding:10px;border-bottom:1px solid #0b5;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
#status{{color:#9ff;font-weight:bold}} #status.error{{color:#ff9f9f}}
#term{{flex:1;min-height:420px;margin:12px;padding:12px;border:1px solid #0b5;background:#000;color:#4dff8a;white-space:pre-wrap;overflow:auto;outline:none;font-size:15px;line-height:1.25}}
.keys,.inputbar{{padding:8px 12px;border-top:1px solid #063;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
button{{margin:2px;padding:8px 12px;background:#031;color:#bfffcf;border:1px solid #0b5;cursor:pointer}}
button:hover,button:focus{{background:#062}}
#cmd{{flex:1;min-width:280px;background:#000;color:#bfffcf;border:1px solid #0b5;padding:8px;font-family:inherit}}
small{{color:#9c9}} .error{{color:#ffb0b0}}
</style></head><body>
<header><b>Gibson Browser Terminal</b><span>Port {port}</span><span>Mode xtermjs-websocket-bridge</span><span id='status'>CONNECTING</span><button onclick='connect()'>Reconnect</button><button onclick='diagnostics()'>Diagnostics</button></header>
<div id='term' tabindex='0' aria-label='Gibson browser terminal output'>Connecting to Gibson backend...\n</div>
<div class='inputbar'><label for='cmd'>Command/input ===&gt;</label><input id='cmd' autocomplete='off' spellcheck='false' autofocus><button onclick='sendCommand()'>Send</button><small>Terminal area also accepts keyboard input. Type L TSO (or L CICS, L DB2, L IMS, L ZVM) to begin.</small></div>
<div class='keys'>{buttons}<small>PF buttons send panel-key events over WebSocket.</small></div>
<script>
let ws=null; const term=document.getElementById('term'); const statusEl=document.getElementById('status'); const cmd=document.getElementById('cmd');
function append(s){{ if(!s) return; term.textContent += s; term.scrollTop=term.scrollHeight; }}
function setStatus(s, err=false){{ statusEl.textContent=s; statusEl.className=err?'error':''; }}
function showError(s){{ append('\n[WEBTERM] '+s+'\n'); setStatus('ERROR', true); }}
function wsUrl(){{ return (location.protocol==='https:'?'wss://':'ws://') + location.host + '/ws/terminal'; }}
function connect(){{
  try{{ if(ws) ws.close(); }}catch(e){{}}
  setStatus('CONNECTING'); term.textContent='Connecting to Gibson backend...\n';
  ws = new WebSocket(wsUrl());
  ws.onopen = () => {{ cmd.focus(); }};
  ws.onclose = () => {{ if(statusEl.textContent!=='ERROR') setStatus('DISCONNECTED', true); append('\n[WEBTERM] disconnected\n'); }};
  ws.onerror = () => {{ showError('WebSocket connection failed'); }};
  ws.onmessage = (ev) => {{
    let m; try{{ m=JSON.parse(ev.data); }}catch(e){{ append(ev.data); return; }}
    if(m.type==='status'){{ setStatus(m.state || 'CONNECTED', (m.state==='ERROR'||m.state==='DISCONNECTED')); }}
    else if(m.type==='output'){{ append(m.data || ''); }}
    else if(m.type==='error'){{ showError(m.message || 'unknown error'); }}
    else if(m.type==='diagnostics'){{ console.log('Gibson diagnostics', m.data); }}
    else if(m.type==='pong'){{}}
  }};
}}
function send(obj){{ if(!ws || ws.readyState!==WebSocket.OPEN){{ showError('terminal is not connected'); return; }} ws.send(JSON.stringify(obj)); }}
function sendKey(k){{ send({{type:'key',key:k}}); term.focus(); }}
function sendCommand(){{ const v=cmd.value; cmd.value=''; send({{type:'input',data:v+'\r'}}); term.focus(); }}
function diagnostics(){{ send({{type:'diagnostics'}}); fetch('/api/diagnostics').then(r=>r.json()).then(j=>append('\n[DIAG] '+JSON.stringify(j)+'\n')).catch(e=>showError(e)); }}
cmd.addEventListener('keydown',e=>{{
  if(e.key==='Enter'){{e.preventDefault(); sendCommand(); return;}}
  if(e.key==='F3'){{e.preventDefault(); sendKey('PF3'); return;}}
  if(e.key==='F7'){{e.preventDefault(); sendKey('PF7'); return;}}
  if(e.key==='F8'){{e.preventDefault(); sendKey('PF8'); return;}}
  if(e.key==='Tab'){{e.preventDefault(); sendKey('TAB'); return;}}
}});
term.addEventListener('keydown',e=>{{
  if(e.ctrlKey || e.metaKey) return;
  if(e.key==='F3'){{e.preventDefault(); sendKey('PF3'); return;}}
  if(e.key==='F7'){{e.preventDefault(); sendKey('PF7'); return;}}
  if(e.key==='F8'){{e.preventDefault(); sendKey('PF8'); return;}}
  if(e.key==='Tab'){{e.preventDefault(); sendKey('TAB'); return;}}
  if(e.key==='Enter'){{e.preventDefault(); send({{type:'input',data:'\r'}}); return;}}
  if(e.key==='Backspace'){{e.preventDefault(); send({{type:'input',data:'\b'}}); return;}}
  if(e.key.length===1){{e.preventDefault(); send({{type:'input',data:e.key}}); return;}}
}});
term.addEventListener('paste',e=>{{ e.preventDefault(); const text=(e.clipboardData||window.clipboardData).getData('text'); send({{type:'input',data:text}}); }});
window.addEventListener('beforeunload',()=>{{ try{{ if(ws) ws.close(); }}catch(e){{}} }});
connect();
</script></body></html>"""


def serve_web_terminal(state: GibsonState) -> WebTerminalServerWrapper:
    return WebTerminalServerWrapper(state).start()
