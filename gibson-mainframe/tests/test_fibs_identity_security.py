from __future__ import annotations

import http.cookiejar
import json
import tempfile
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.fibs_web9080 import FibsWeb9080Handler, ThreadedHTTPServer


def _server(secure: bool = False):
    cfg = GibsonConfig(host="127.0.0.1", fibs_web_port=0, sim_root=Path(tempfile.mkdtemp()), security_mode="secure" if secure else "vuln")
    state = GibsonState.create(cfg)
    FibsWeb9080Handler.state = state
    srv = ThreadedHTTPServer(("127.0.0.1", 0), FibsWeb9080Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return state, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _post(opener, url, data):
    return json.loads(opener.open(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")).read().decode())


def test_oidc_discovery_and_jwks():
    state, srv, base = _server(False)
    try:
        disc = json.loads(urllib.request.urlopen(base + "/.well-known/openid-configuration").read().decode())
        assert disc["issuer"] == "http://127.0.0.1:9080"
        assert disc["token_endpoint"].endswith("/oauth/token")
        jwks = json.loads(urllib.request.urlopen(base + "/oauth/jwks").read().decode())
        assert jwks["keys"][0]["kid"] == "fibs-hs256-1"
    finally:
        srv.shutdown()


def test_jwt_alg_none_vulnerable_and_secure():
    state, srv, base = _server(False)
    try:
        op = _opener()
        res = _post(op, base + "/webapi/labs/jwt/forge", {"lab": "alg_none", "sub": "alice", "role": "admin"})
        assert res["accepted"] is True
        assert res["claims"]["role"] == "admin"
        assert "SIMULATED SMF80" in "\n".join(m for _s, m in state.console_events)
    finally:
        srv.shutdown()
    state, srv, base = _server(True)
    try:
        op = _opener()
        res = _post(op, base + "/webapi/labs/jwt/forge", {"lab": "alg_none", "sub": "alice", "role": "admin"})
        assert res["accepted"] is False
        assert "algorithm rejected" in res["error"]
    finally:
        srv.shutdown()


def test_oauth_pkce_state_secure_mode_and_vulnerable_redirect_lab():
    state, srv, base = _server(True)
    try:
        op = _opener()
        blocked = _post(op, base + "/webapi/labs/oauth/authorize", {"client_id": "fibs-web", "redirect_uri": "http://evil.example/callback"})
        assert "error" in blocked
        assert blocked["error"] in {"invalid_redirect_uri", "state_required", "pkce_required"}
    finally:
        srv.shutdown()
    state, srv, base = _server(False)
    try:
        op = _opener()
        res = _post(op, base + "/webapi/labs/oauth/authorize", {"client_id": "fibs-web", "redirect_uri": "http://evil.example/callback", "scope": "openid admin"})
        assert "code" in res
        tok = _post(op, base + "/webapi/labs/oauth/token", {"code": res["code"]})
        assert "access_token" in tok
    finally:
        srv.shutdown()


def test_identity_trace_has_no_password_or_cookie():
    state, srv, base = _server(False)
    try:
        op = _opener()
        _post(op, base + "/webapi/labs/jwt/forge", {"lab": "role_tamper", "sub": "bob", "role": "admin", "password": "notlogged"})
        trace = json.loads(op.open(base + "/webapi/teller/events").read().decode())["events"]
        joined = json.dumps(trace)
        assert "notlogged" not in joined
        assert "Cookie" not in joined and "FIBSSESS" not in joined
        assert any(e["component"] == "AUTH" for e in trace)
    finally:
        srv.shutdown()


def test_secure_authorization_code_pkce_flow_works():
    import hashlib, base64
    state, srv, base = _server(True)
    try:
        verifier = "correct-horse-battery-staple"
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = urllib.parse.urlencode({
            "client_id": "fibs-web",
            "redirect_uri": "http://127.0.0.1:9080/oauth/callback",
            "state": "STATE123",
            "nonce": "NONCE123",
            "code_challenge": challenge,
            "scope": "openid profile accounts",
        })
        auth = json.loads(urllib.request.urlopen(base + "/oauth/authorize?" + params).read().decode())
        assert "code" in auth
        tok = _post(_opener(), base + "/oauth/token", {"code": auth["code"], "code_verifier": verifier})
        assert "access_token" in tok and "id_token" in tok
    finally:
        srv.shutdown()
