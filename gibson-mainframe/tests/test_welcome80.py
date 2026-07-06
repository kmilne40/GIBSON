from __future__ import annotations
import tempfile, threading, urllib.request, urllib.error
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.welcome80 import WelcomeHandler, ThreadedHTTPServer


def _server():
    cfg = GibsonConfig(host='127.0.0.1', welcome_port=0, sim_root=Path(tempfile.mkdtemp()))
    state = GibsonState.create(cfg)
    WelcomeHandler.state = state
    srv = ThreadedHTTPServer(('127.0.0.1', 0), WelcomeHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def test_welcome80_health_and_core_pages():
    srv, base = _server()
    try:
        assert urllib.request.urlopen(base + '/health').read().decode().strip() == 'OK'
        for path in ['/', '/welcome', '/gibson', '/apps', '/ports', '/getting-started', '/safety', '/labs', '/labs/identity', '/links']:
            body = urllib.request.urlopen(base + path).read().decode()
            assert 'Gibson' in body
            assert '80' in body and '2023' in body and '8080' in body and '9080' in body
            assert 'safe' in body.lower() or 'Safety' in body
            assert 'TFTP' not in body
    finally:
        srv.shutdown()


def test_ttp_routes_are_not_served_by_welcome_site():
    srv, base = _server()
    try:
        for path in ['/ttp', '/ttp/mainframe', '/ttp/passtickets', '/ttp/mfa']:
            try:
                urllib.request.urlopen(base + path)
                assert False, path
            except urllib.error.HTTPError as e:
                assert e.code == 404
    finally:
        srv.shutdown()
