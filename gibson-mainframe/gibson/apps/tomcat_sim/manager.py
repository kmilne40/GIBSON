from __future__ import annotations
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Any
import json
import re

from .auth import authenticate, REALM
from .state import get_state, deploy_war, undeploy, safe_context, create_session
from . import rendering
from .events import record_login, record_upload, record_deploy, record_payload_trigger
from .session import start_listener
from .config import get_config


def is_tomcat_route(path: str) -> bool:
    if path in {"/", "/tomcat", "/docs", "/examples", "/manager", "/manager/html", "/manager/status"}:
        return True
    if path.startswith("/manager/"):
        return True
    if path.startswith("/shell_exploit") or path.startswith("/ws_shell_exploit"):
        return True
    return False


def send_bytes(h: BaseHTTPRequestHandler, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8", headers: dict[str, str] | None = None) -> None:
    h.send_response(code)
    h.send_header("Server", "Apache-Coyote/1.1")
    h.send_header("X-Gibson-Simulator", "safe-tomcat")
    h.send_header("Content-Type", ctype)
    h.send_header("Cache-Control", "no-store")
    if headers:
        for k, v in headers.items():
            h.send_header(k, v)
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    if getattr(h, "command", "GET") != "HEAD":
        h.wfile.write(body)


def send_text(h: BaseHTTPRequestHandler, code: int, text: str, ctype: str = "text/plain; charset=utf-8", headers: dict[str, str] | None = None) -> None:
    send_bytes(h, code, text.encode("utf-8"), ctype, headers)


def require(h: BaseHTTPRequestHandler, state: Any, role: str) -> tuple[bool, str, set[str]]:
    ok, user, roles, reason = authenticate(state, h.headers.get("Authorization"), role)
    if ok:
        # Tomcat normally doesn't emit a new console event for every authenticated hit, but Gibson training wants clear evidence.
        if not getattr(h, "_tomcat_login_recorded", False):
            record_login(state, user, getattr(h, "client_address", [""])[0])
            h._tomcat_login_recorded = True  # type: ignore[attr-defined]
        return True, user, roles
    send_text(h, 401, "Authentication required", headers={"WWW-Authenticate": f'Basic realm="{REALM}"'})
    return False, user, roles


def _body(h: BaseHTTPRequestHandler) -> bytes:
    try:
        length = int(h.headers.get("Content-Length", "0") or "0")
    except ValueError:
        length = 0
    if length <= 0:
        return b""
    return h.rfile.read(min(length, 3 * 1024 * 1024))


def _filename_from_multipart(data: bytes) -> str:
    m = re.search(br'filename="([^"\\/]+)"', data[:4096])
    if m:
        return m.group(1).decode("utf-8", errors="ignore")
    return "ws_shell_exploit.war"


def _file_bytes_from_multipart(data: bytes) -> bytes:
    # Minimal bounded parser good enough for browser tests. It does not execute or extract content.
    if b"\r\n\r\n" in data:
        parts = data.split(b"\r\n\r\n", 1)[1]
        # Trim the trailing multipart boundary if present.
        if b"\r\n--" in parts:
            parts = parts.rsplit(b"\r\n--", 1)[0]
        return parts
    return data


def _text_list(state: Any) -> str:
    sim = get_state(state)
    lines = ["OK - Listed applications for virtual host [localhost]"]
    for ctx, dep in sorted(sim.deployments.items()):
        lines.append(f"{ctx}:{dep.status}:0:{dep.display_name or dep.filename or 'ROOT'}")
    return "\n".join(lines) + "\n"


def handle(handler: BaseHTTPRequestHandler, state: Any) -> bool:
    cfg = get_config(state)
    parsed = urlparse(handler.path)
    path = parsed.path or "/"
    method = getattr(handler, "command", "GET").upper()
    if not is_tomcat_route(path):
        return False
    if not cfg.enabled:
        send_text(handler, 404, "Tomcat simulator disabled")
        return True
    try:
        state.note_port_touch(handler.client_address[0], int(getattr(state.config, "cbsa_api_port", 8080)), service="TOMCAT")
    except Exception:
        pass
    if path in {"/", "/tomcat"}:
        return send_text(handler, 200, rendering.landing(), "text/html; charset=utf-8") or True
    if path == "/docs":
        return send_text(handler, 200, rendering.docs(), "text/html; charset=utf-8") or True
    if path == "/examples":
        return send_text(handler, 200, rendering.examples(), "text/html; charset=utf-8") or True
    if path in {"/manager", "/manager/"}:
        send_text(handler, 302, "", headers={"Location": "/manager/html"})
        return True
    if path == "/manager/html":
        ok, user, _roles = require(handler, state, "manager-gui")
        if not ok: return True
        return send_text(handler, 200, rendering.manager_html(state, user), "text/html; charset=utf-8") or True
    if path == "/manager/status":
        ok, user, _roles = require(handler, state, "manager-status")
        if not ok: return True
        return send_text(handler, 200, rendering.status(state, user), "text/html; charset=utf-8") or True
    if path == "/manager/html/upload":
        ok, user, _roles = require(handler, state, "manager-gui")
        if not ok: return True
        data = _body(handler)
        qs = parse_qs(parsed.query)
        context = qs.get("path", [None])[0]
        if not context and b'name="path"' in data:
            m = re.search(br'name="path"\r\n\r\n([^\r\n]+)', data)
            context = m.group(1).decode("utf-8", errors="ignore") if m else "/shell_exploit"
        context = context or "/shell_exploit"
        filename = _filename_from_multipart(data)
        body = _file_bytes_from_multipart(data)
        ok2, msg, dep = deploy_war(state, context, filename, body, user, update=True)
        if dep:
            record_upload(state, dep, handler.client_address[0]); record_deploy(state, dep, handler.client_address[0])
        code = 200 if ok2 else 400
        return send_text(handler, code, rendering.manager_html(state, user, msg), "text/html; charset=utf-8") or True
    if path.startswith("/manager/text/"):
        ok, user, _roles = require(handler, state, "manager-script")
        if not ok: return True
        if path == "/manager/text/list":
            return send_text(handler, 200, _text_list(state)) or True
        if path == "/manager/text/serverinfo":
            info = "OK - Server info\nTomcat Version: Apache Tomcat/9.0.x Gibson safe simulator\nOS Name: z/OS UNIX Gibson USS\nConnector: HTTP/1.1-8080\n"
            return send_text(handler, 200, info) or True
        if path == "/manager/text/deploy":
            qs = parse_qs(parsed.query)
            context = qs.get("path", ["/shell_exploit"])[0]
            update = (qs.get("update", ["false"])[0] or "").lower() == "true"
            data = _body(handler)
            filename = qs.get("war", ["ws_shell_exploit.war"])[0]
            ok2, msg, dep = deploy_war(state, context, filename, data, user, update=update)
            if dep:
                record_upload(state, dep, handler.client_address[0]); record_deploy(state, dep, handler.client_address[0])
            return send_text(handler, 200 if ok2 else 400, msg + "\n") or True
        if path == "/manager/text/undeploy":
            qs = parse_qs(parsed.query)
            ok2, msg = undeploy(state, qs.get("path", [""])[0])
            return send_text(handler, 200 if ok2 else 400, msg + "\n") or True
        send_text(handler, 404, "FAIL - Unknown command\n")
        return True
    ctx = safe_context(path)
    sim = get_state(state)
    if ctx and ctx in sim.deployments and ctx not in {"/", "/docs", "/examples"}:
        dep = sim.deployments[ctx]
        sess = create_session(state, ctx, dep.uploaded_by or "tomcat")
        if cfg.allow_pseudo_bind_listener:
            start_listener(state, cfg.pseudo_bind_port)
        try:
            state.allowed_high_ports.add(int(cfg.pseudo_bind_port))
            # still emit explicit requested alert even though allowed high port avoids generic unknown-port noise
        except Exception:
            pass
        record_payload_trigger(state, sess, handler.client_address[0])
        body = f"<html><head><title>{ctx}</title></head><body><h1>Gibson Tomcat Training Payload</h1><p>Simulated bind session {sess.session_id} active on port {sess.port}.</p><p>Connect with ncat mainframe {sess.port} or use msfconsole-sim sessions -i {sess.session_id}.</p></body></html>"
        return send_text(handler, 200, body, "text/html; charset=utf-8") or True
    send_text(handler, 404, "Tomcat route not found")
    return True
