from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver, threading
from urllib.parse import urlparse, unquote
from gibson.apps.welcome import render_page

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class WelcomeHandler(BaseHTTPRequestHandler):
    state = None
    server_version = "GibsonWelcome"
    sys_version = ""

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        try:
            self.state.note_port_touch(self.client_address[0], int(getattr(self.state.config, "welcome_port", 80)), service="WELCOME80")
        except Exception:
            pass
        path = unquote(urlparse(self.path or "/").path or "/")
        code, ctype, body = render_page(self.path or path, state=self.state, headers=self.headers)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        if code == 401:
            self.send_header("WWW-Authenticate", "Basic realm=\"Gibson Sentry\"")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        path = unquote(urlparse(self.path or "/").path or "/")
        code, ctype, body = render_page(self.path or path, state=self.state, headers=self.headers)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        if code == 401:
            self.send_header("WWW-Authenticate", "Basic realm=\"Gibson Sentry\"")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

def serve_welcome(state):
    WelcomeHandler.state = state
    port = int(getattr(state.config, "welcome_port", 80))
    srv = ThreadedHTTPServer((state.config.host, port), WelcomeHandler)
    th = threading.Thread(target=srv.serve_forever, name="GibsonWelcome80", daemon=True)
    th.start()
    return srv
