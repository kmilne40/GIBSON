from __future__ import annotations
import http.cookiejar, subprocess, tempfile, threading, urllib.request
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.fibs_web9080 import FibsWeb9080Handler, ThreadedHTTPServer


def _server():
    cfg = GibsonConfig(host='127.0.0.1', fibs_web_port=0, sim_root=Path(tempfile.mkdtemp()), security_mode='vuln')
    state = GibsonState.create(cfg)
    FibsWeb9080Handler.state = state
    srv = ThreadedHTTPServer(('127.0.0.1',0), FibsWeb9080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state, srv, f'http://127.0.0.1:{srv.server_address[1]}'


def test_static_js_served_from_asset_file_and_not_inline_blob():
    state, srv, base = _server()
    try:
        r = urllib.request.urlopen(base+'/static/js/fibs.js')
        body = r.read().decode()
        assert r.headers.get_content_type() in {'application/javascript', 'text/javascript'}
        assert 'addEventListener' in body
        assert 'form.lab-action-form' in body
        assert Path('gibson/assets/fibs9080/fibs.js').exists()
        service = Path('gibson/services/fibs_web9080.py').read_text()
        assert 'async function runLabAction' not in service
    finally:
        srv.shutdown()


def test_static_missing_returns_404():
    state, srv, base = _server()
    try:
        try:
            urllib.request.urlopen(base+'/static/js/missing.js')
            assert False, 'expected 404'
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()


def test_js_syntax_if_node_available():
    js = Path('gibson/assets/fibs9080/fibs.js')
    try:
        result = subprocess.run(['node', '--check', str(js)], text=True, capture_output=True, timeout=20)
    except FileNotFoundError:
        text = js.read_text()
        assert text.count('{') == text.count('}')
        return
    assert result.returncode == 0, result.stderr
