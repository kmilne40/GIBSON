from __future__ import annotations
# Compatibility shim for older imports. The Welcome service now uses port 80
# by default; this module no longer implies or starts port 8000.
from gibson.services.welcome80 import ThreadedHTTPServer, WelcomeHandler, serve_welcome

Welcome8000Handler = WelcomeHandler

def serve_welcome8000(state):
    return serve_welcome(state)
