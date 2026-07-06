from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socketserver
import threading
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from gibson.core.state import GibsonState
from gibson.apps.cbsa.rest_api import handle as handle_cbsa
from gibson.apps.dvca.api import handle as handle_dvca
from gibson.apps.tomcat_sim import handle as handle_tomcat, is_tomcat_route


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html(handler: BaseHTTPRequestHandler, code: int, body: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _normalise_path(raw_path: str) -> str:
    """Return a safe path for route matching while preserving API segments.

    Query strings are stripped for dispatch; handlers still receive the original
    path and may parse their own query strings.  Trailing slashes are normalised
    for page-style routes but not collapsed across the middle of the path.
    """
    parsed = urlparse(raw_path or "/")
    path = unquote(parsed.path or "/")
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    if "/../" in path or path.endswith("/..") or "/./" in path:
        return "/__invalid_path__"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def _is_dvca_or_hack3270_route(path: str) -> bool:
    return (
        path == "/dvca"
        or path.startswith("/dvca/")
        or path == "/dvca/hack3270"
        or path.startswith("/api/v1/dvca")
        or path.startswith("/api/v1/hack3270")
        or path.startswith("/ws/dvca")
    )


def _is_probably_browser_path(path: str) -> bool:
    return path in {"/dvca", "/dvca/hack3270"} or path.startswith("/dvca/")


class App8080Router:
    """Unified port-8080 router for CBSA, DVCA and hack3270.

    DVCA/hack3270 routes are intentionally matched before the CBSA handler so
    they cannot fall through to CBSA's JSON route-not-found response.
    """

    def route(self, handler: BaseHTTPRequestHandler, state: GibsonState) -> None:
        path = _normalise_path(handler.path)
        if path == "/__invalid_path__":
            return _json(handler, 400, {"error": "invalid path", "path": urlparse(handler.path).path})

        # Preserve the original handler.path but route based on the normalised
        # path.  DVCA's handler already parses query strings from handler.path.
        if _is_dvca_or_hack3270_route(path):
            original = handler.path
            try:
                # Normalise only the path component for handlers that currently
                # match exact paths, while preserving query strings.
                parsed = urlparse(original)
                query = ("?" + parsed.query) if parsed.query else ""
                handler.path = path + query
                handled = handle_dvca(handler, state)
            finally:
                handler.path = original
            if handled is False:
                if _is_probably_browser_path(path):
                    return _html(handler, 404, f"<html><body><h1>DVCA route not found</h1><p>{path}</p></body></html>")
                return _json(handler, 404, {"error": "DVCA/hack3270 route not found", "path": path})
            return

        if is_tomcat_route(path):
            original = handler.path
            try:
                parsed = urlparse(original)
                query = ("?" + parsed.query) if parsed.query else ""
                handler.path = path + query
                handled = handle_tomcat(handler, state)
            finally:
                handler.path = original
            if handled:
                return

        return handle_cbsa(handler, state)


_ROUTER = App8080Router()


class Cbsa8080Handler(BaseHTTPRequestHandler):
    state: GibsonState
    server_version = "GibsonApp8080"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _dispatch(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], int(getattr(self.state.config, "cbsa_api_port", 8080)), service="APP8080")
        except Exception:
            pass
        return _ROUTER.route(self, self.state)

    def do_GET(self) -> None:
        return self._dispatch()

    def do_POST(self) -> None:
        return self._dispatch()

    def do_PUT(self) -> None:
        return self._dispatch()

    def do_DELETE(self) -> None:
        return self._dispatch()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-HTTP-Method-Override")
        self.end_headers()


def serve_cbsa_rest8080(state: GibsonState):
    Cbsa8080Handler.state = state
    srv = ThreadedHTTPServer((state.config.host, int(getattr(state.config, "cbsa_api_port", 8080))), Cbsa8080Handler)
    th = threading.Thread(target=srv.serve_forever, name="GibsonApp8080", daemon=True)
    th.start()
    return srv
