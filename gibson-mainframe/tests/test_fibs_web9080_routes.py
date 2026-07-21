from __future__ import annotations
import http.cookiejar
import tempfile
import threading
import urllib.error
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
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return state, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _post(opener, url, data):
    return opener.open(urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST"))


def test_landing_login_and_dashboard_branding():
    state, srv, base = _server()
    try:
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "FIBS BANK" in page
        assert "First International Bank of Scotland" in page
        assert "VULNERABLE TRAINING MODE" in page
        assert "fibs.css" in page
        css = urllib.request.urlopen(base + "/static/css/fibs.css").read().decode()
        assert "--saltire" in css and "--heather" in css
        opener = _opener()
        login = _post(opener, base + "/login", {"username": "alice", "password": "training1"})
        assert login.url.endswith("/dashboard")
        dash = opener.open(base + "/dashboard").read().decode()
        assert "Welcome back" in dash
        assert "account-card" in dash
    finally:
        srv.shutdown()


def test_login_required_and_teller_portal_gacf_user_creation():
    state, srv, base = _server()
    try:
        opener = _opener()
        redirected = opener.open(base + "/dashboard")
        assert redirected.url.endswith("/login")
        _post(opener, base + "/login", {"username": "teller", "password": "cics"})
        teller = opener.open(base + "/teller").read().decode()
        assert "Teller portal" in teller
        _post(opener, base + "/teller/customers/new", {"name": "FIONA MACLEOD", "address1": "1 THISTLE WAY"})
        cid = state.cbsa_store.control["LAST_CUSTOMER_NUMBER"]
        _post(opener, base + "/teller/users/new", {"username": "FIONA", "password": "loch", "customer_id": cid, "role": "customer"})
        assert state.racf.get("FIONA") is not None
        assert "FIONA" in state.cbsa_store.web_users
        opener2 = _opener()
        _post(opener2, base + "/login", {"username": "fiona", "password": "loch"})
        assert "Welcome back" in opener2.open(base + "/dashboard").read().decode()
    finally:
        srv.shutdown()


def test_customer_cannot_access_teller_portal():
    _state, srv, base = _server()
    try:
        opener = _opener()
        _post(opener, base + "/login", {"username": "alice", "password": "training1"})
        try:
            opener.open(base + "/teller")
            assert False, "expected forbidden"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()


def test_transfer_updates_cbsa_proctran_and_audit():
    state, srv, base = _server()
    try:
        opener = _opener()
        _post(opener, base + "/login", {"username": "alice", "password": "training1"})
        before = len(state.cbsa_store.proctran)
        _post(opener, base + "/transfer", {"from_account": "00000101", "to_account": "00000103", "amount": "12.34"})
        assert len(state.cbsa_store.proctran) > before
        assert any(e["CHANNEL"] == "WEB9080" for e in state.cbsa_store.web_audit)
        tables = state.cbsa_store.tables()
        assert "CBSA.WEB_USERS" in tables
        assert "CBSA.WEB_AUDIT" in tables
    finally:
        srv.shutdown()


def test_sqli_lab_vulnerable_and_secure_modes():
    state, srv, base = _server(False)
    try:
        opener = _opener(); _post(opener, base + "/login", {"username": "alice", "password": "training1"})
        data = opener.open(base + "/webapi/labs/sqli?customer=1001%27%20OR%20%271%27=%271").read().decode()
        assert "SQLI" in data and "00000103" in data
    finally:
        srv.shutdown()
    state, srv, base = _server(True)
    try:
        opener = _opener(); _post(opener, base + "/login", {"username": "alice", "password": "training1"})
        data = opener.open(base + "/webapi/labs/sqli?customer=1001%27%20OR%20%271%27=%271").read().decode()
        assert "SQLI" not in data
    finally:
        srv.shutdown()

def test_static_path_traversal_rejected():
    _state, srv, base = _server()
    try:
        try:
            urllib.request.urlopen(base + "/static/../gibson/cli.py")
            assert False, "expected bad path or not found"
        except urllib.error.HTTPError as e:
            assert e.code in {400, 404}
    finally:
        srv.shutdown()
