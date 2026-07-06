from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import socketserver
import threading
from pathlib import Path
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from gibson.apps.cbsa.services import CbsaService
from gibson.apps.cbsa.teller_search import teller_search
from gibson.apps.cbsa.store import get_cbsa_store
from gibson.core.security_mode import SECURE
from gibson.core.security_event_bus import clear_trace_events, get_trace_events, create_trace_session, emit_smf80, emit_smf110, emit_trace_event
from gibson.apps.fibs_identity import discovery, jwks, authorize as oauth_authorize, token as oauth_token, introspect as oauth_introspect, revoke as oauth_revoke, lab_jwt_forge, lab_oauth_authorize, lab_oauth_token, lab_oauth_refresh
from gibson.apps.fibs_training.lab_catalog import get_lab, list_labs
from gibson.apps.fibs_training.lab_rendering import render_lab_index, render_lab_detail
from gibson.apps.fibs_training.lab_runner import run_lab, secure_compare, reset_lab, export_evidence
from gibson.core.state import GibsonState


BRAND = "FIBS BANK"
FULL_BRAND = "FIBS BANK - First International Bank of Scotland"


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _money(value: Any) -> str:
    try:
        return f"£{Decimal(str(value or '0')).quantize(Decimal('0.01'))}"
    except Exception:
        return "£0.00"


def _body(handler: BaseHTTPRequestHandler) -> bytes:
    try:
        n = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        n = 0
    return handler.rfile.read(min(n, 1024 * 1024)) if n > 0 else b""


def _parse_form(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    raw = _body(handler).decode("utf-8", errors="replace")
    ctype = handler.headers.get("Content-Type", "")
    if "application/json" in ctype:
        try:
            data = json.loads(raw or "{}")
            return {str(k): str(v) for k, v in data.items()}
        except Exception:
            return {}
    values = parse_qs(raw, keep_blank_values=True)
    return {k: v[-1] if v else "" for k, v in values.items()}


def _cookie(handler: BaseHTTPRequestHandler, name: str) -> str:
    raw = handler.headers.get("Cookie", "") or ""
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            if k == name:
                return v
    return ""


def _send(handler: BaseHTTPRequestHandler, code: int, body: str, ctype: str = "text/html; charset=utf-8", headers: dict[str, str] | None = None) -> None:
    data = body.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    for k, v in (headers or {}).items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(data)


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    _send(handler, code, json.dumps(payload, indent=2, sort_keys=True), "application/json; charset=utf-8")


def _redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _mode(state: GibsonState) -> str:
    return "secure" if getattr(state.config, "security_mode", "vuln") == SECURE else "vulnerable"


def _is_secure(state: GibsonState) -> bool:
    return _mode(state) == "secure"


class FibsBankApp:
    def __init__(self, state: GibsonState):
        self.state = state
        self.store = get_cbsa_store(state)
        self.svc = CbsaService(state)

    def session(self, handler: BaseHTTPRequestHandler) -> dict[str, str] | None:
        return self.store.get_web_session(_cookie(handler, "FIBSSESS"))

    def require_session(self, handler: BaseHTTPRequestHandler) -> dict[str, str] | None:
        sess = self.session(handler)
        if not sess:
            _redirect(handler, "/login")
            return None
        return sess

    def is_staff(self, sess: dict[str, str]) -> bool:
        return sess.get("ROLE") in {"teller", "admin", "instructor"}

    def audit(self, sess: dict[str, str] | None, action: str, payload: str, result: str = "OK", scenario: str = "") -> dict[str, str]:
        user = (sess or {}).get("USERNAME") or "ANON"
        return self.store.audit("WEB9080", action, payload, result=result, user=user, scenario=scenario)

    def layout(self, title: str, content: str, sess: dict[str, str] | None = None, message: str = "") -> str:
        mode = _mode(self.state)
        banner = "SECURE MODE" if mode == "secure" else "VULNERABLE TRAINING MODE"
        nav_auth = ""
        if sess:
            staff = '<a href="/teller">Teller portal</a>' if self.is_staff(sess) else ""
            nav_auth = f"""
            <a href="/dashboard">Dashboard</a><a href="/accounts">Accounts</a><a href="/transfer">Transfer</a>
            <a href="/labs">Security labs</a><a href="/audit">Audit</a>{staff}<a href="/logout">Logout</a>
            """
        else:
            nav_auth = '<a href="/login">Login</a><a href="/training">Training</a>'
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)} | {FULL_BRAND}</title><link rel="stylesheet" href="/static/css/fibs.css"><script defer src="/static/js/fibs.js"></script></head>
<body class="fibs-scotland"><header class="topbar"><div class="brand"><div class="crest">✦</div><div><strong>{BRAND}</strong><span>First International Bank of Scotland</span></div></div><nav>{nav_auth}</nav></header>
<section class="mode {mode}">{banner}</section>{f'<div class="notice">{_esc(message)}</div>' if message else ''}
<main class="container">{content}</main><footer>FIBS BANK training simulator · CBSA-backed Gibson subsystem · No real banking system</footer></body></html>"""

    def landing(self, handler: BaseHTTPRequestHandler) -> None:
        body = """<section class="hero"><div><p class="eyebrow">Scottish mainframe banking lab</p><h1>FIBS BANK</h1><h2>First International Bank of Scotland</h2><p>Professional CBSA-backed online banking with controlled security training labs.</p><a class="button" href="/login">Sign in to online banking</a></div><div class="hero-card"><h3>Training systems</h3><p>Customer banking, teller portal, Db2 evidence, CICS visibility and OWASP-style labs.</p></div></section>"""
        _send(handler, 200, self.layout("Welcome", body))

    def login_get(self, handler: BaseHTTPRequestHandler, msg: str = "") -> None:
        body = """<section class="login-card"><h1>Sign in</h1><p>Use a seeded customer or teller training account.</p><form method="post" action="/login"><label>Username<input required name="username" autocomplete="username"></label><label>Password<input required type="password" name="password" autocomplete="current-password"></label><button class="button" type="submit">Sign in</button></form><details><summary>Training credentials</summary><p>alice/training1 · bob/training1 · carol/training1 · teller/cics · admin/sys1</p></details></section>"""
        _send(handler, 200, self.layout("Login", body, message=msg))

    def login_post(self, handler: BaseHTTPRequestHandler) -> None:
        data = _parse_form(handler)
        username, password = data.get("username", ""), data.get("password", "")
        allow_weak = (not _is_secure(self.state)) and data.get("weak_auth") == "1"
        rec = self.store.verify_web_user(username, password, allow_weak=allow_weak)
        if not rec:
            self.audit(None, "LOGIN", username, "DENIED")
            return self.login_get(handler, "Login failed. Check the username and password.")
        sid = self.store.create_web_session(rec)
        self.audit(rec, "LOGIN", username, "OK")
        _redirect(handler, "/dashboard")
        # Python's BaseHTTPRequestHandler cannot add headers after _redirect; custom response needed.

    def login_post_fixed(self, handler: BaseHTTPRequestHandler) -> None:
        data = _parse_form(handler)
        username, password = data.get("username", ""), data.get("password", "")
        allow_weak = (not _is_secure(self.state)) and data.get("weak_auth") == "1"
        rec = self.store.verify_web_user(username, password, allow_weak=allow_weak)
        if not rec:
            self.audit(None, "LOGIN", username, "DENIED")
            return self.login_get(handler, "Login failed. Check the username and password.")
        sid = self.store.create_web_session(rec)
        self.audit(rec, "LOGIN", username, "OK")
        try:
            emit_trace_event(self.state, component="WEB9080", action="LOGIN", user=username, route="/login", result="OK", message="FIBS teller/customer login")
            emit_smf80(self.state, event="LOGIN", user=username, channel="WEB9080", result="SUCCESS", resource="FIBS.LOGIN", endpoint="/login")
        except Exception:
            pass
        handler.send_response(303)
        handler.send_header("Location", "/dashboard")
        handler.send_header("Set-Cookie", f"FIBSSESS={sid}; Path=/; HttpOnly; SameSite=Lax")
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    def logout(self, handler: BaseHTTPRequestHandler) -> None:
        sid = _cookie(handler, "FIBSSESS")
        if sid in self.store.web_sessions:
            self.store.web_sessions[sid]["STATUS"] = "LOGGED_OUT"
        handler.send_response(303)
        handler.send_header("Location", "/")
        handler.send_header("Set-Cookie", "FIBSSESS=; Path=/; Max-Age=0")
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    def dashboard(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        cust_id = sess.get("CUSTOMER_ID", "")
        accounts = self.svc.list_accounts(cust_id) if cust_id else list(self.store.accounts.values())
        total = sum(Decimal(a.available_balance) for a in accounts) if accounts else Decimal("0")
        cards = "".join(f"<article class='account-card'><h3>{_esc(a.account_type)}</h3><p class='big'>{_money(a.available_balance)}</p><p>{_esc(a.sort_code)} · <a href='/accounts/{_esc(a.account_number)}'>{_esc(a.account_number)}</a></p></article>" for a in accounts)
        tx = "".join(f"<tr><td>{_esc(r.get('TIMESTAMP'))}</td><td>{_esc(r.get('TRANSACTION_TYPE'))}</td><td>{_esc(r.get('ACCOUNT_NUMBER') or r.get('FROM_ACCOUNT'))}</td><td>{_money(r.get('AMOUNT'))}</td><td>{_esc(r.get('CHANNEL'))}</td></tr>" for r in self.store.proctran[-8:])
        body = f"""<h1>Welcome back, {_esc(sess.get('USERNAME'))}</h1><section class='summary'><div><span>Total available</span><strong>{_money(total)}</strong></div><div><span>Backend</span><strong>CICS · COBOL · Db2 · CBSA</strong></div></section><section class='grid'>{cards}</section><section class='panel'><h2>Recent transactions</h2><table><tr><th>Time</th><th>Type</th><th>Account</th><th>Amount</th><th>Channel</th></tr>{tx}</table></section><section class='quick'><a class='button' href='/transfer'>Make a transfer</a><a class='button secondary' href='/labs'>Open security labs</a></section>"""
        _send(handler, 200, self.layout("Dashboard", body, sess))

    def accounts(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        parts = urlparse(handler.path).path.strip('/').split('/')
        cust_id = sess.get("CUSTOMER_ID", "")
        if len(parts) == 2:
            acc_id = parts[1].zfill(8)
            try: acc = self.svc.account(acc_id)
            except Exception: return _send(handler, 404, self.layout("Not found", "<h1>Account not found</h1>", sess))
            if _is_secure(self.state) and sess.get("ROLE") == "customer" and acc.customer_id != cust_id:
                ev = self.audit(sess, "IDOR", acc_id, "BLOCKED", "IDOR")
                return _send(handler, 403, self.layout("Access denied", f"<h1>Access denied</h1><p>Evidence {_esc(ev['EVENT_ID'])}</p>", sess))
            if (not _is_secure(self.state)) and sess.get("ROLE") == "customer" and acc.customer_id != cust_id:
                self.audit(sess, "IDOR", acc_id, "ALLOWED", "IDOR")
            rows = "".join(f"<tr><td>{_esc(r.get('TIMESTAMP'))}</td><td>{_esc(r.get('TRANSACTION_TYPE'))}</td><td>{_money(r.get('AMOUNT'))}</td><td>{_esc(r.get('RESULT'))}</td></tr>" for r in self.store.proctran if acc.account_number in (r.get('ACCOUNT_NUMBER'), r.get('FROM_ACCOUNT'), r.get('TO_ACCOUNT')))
            body=f"<h1>Account {_esc(acc.account_number)}</h1><div class='account-card'><p>{_esc(acc.account_type)} · {_esc(acc.sort_code)}</p><p class='big'>{_money(acc.available_balance)}</p><p>Status {_esc(acc.status)}</p></div><h2>Transactions</h2><table><tr><th>Time</th><th>Type</th><th>Amount</th><th>Result</th></tr>{rows}</table>"
            return _send(handler, 200, self.layout("Account", body, sess))
        accounts = self.svc.list_accounts(cust_id) if cust_id and sess.get("ROLE") == "customer" else list(self.store.accounts.values())
        cards = "".join(f"<article class='account-card'><h3>{_esc(a.account_type)}</h3><p class='big'>{_money(a.available_balance)}</p><a href='/accounts/{_esc(a.account_number)}'>View account {_esc(a.account_number)}</a></article>" for a in accounts)
        _send(handler, 200, self.layout("Accounts", f"<h1>Your accounts</h1><section class='grid'>{cards}</section>", sess))

    def transfer_get(self, handler: BaseHTTPRequestHandler, msg: str = "") -> None:
        sess = self.require_session(handler)
        if not sess: return
        accounts = self.svc.list_accounts(sess.get("CUSTOMER_ID", "")) if sess.get("ROLE") == "customer" else list(self.store.accounts.values())
        opts = "".join(f"<option value='{_esc(a.account_number)}'>{_esc(a.account_number)} {_esc(a.account_type)} {_money(a.available_balance)}</option>" for a in accounts)
        body = f"""<h1>Transfer money</h1><form method='post' action='/transfer' class='form-grid'><label>From account<select name='from_account'>{opts}</select></label><label>To account<input name='to_account' required value='00000103'></label><label>Amount<input name='amount' required type='number' step='0.01' value='10.00'></label><label>Reference<input name='reference' value='FIBS TRANSFER'></label><button class='button'>Submit transfer</button></form>"""
        _send(handler, 200, self.layout("Transfer", body, sess, msg))

    def transfer_post(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        data = _parse_form(handler)
        vulnerable = (not _is_secure(self.state)) and data.get("lab_business_logic") == "1"
        try:
            src = self.svc.account(data.get("from_account", ""))
            if _is_secure(self.state) and sess.get("ROLE") == "customer" and src.customer_id != sess.get("CUSTOMER_ID"):
                raise PermissionError("Source account ownership check failed")
            self.svc.transfer(data.get("from_account"), data.get("to_account"), data.get("amount"), channel="WEB9080", vulnerable=vulnerable)
            ev = self.audit(sess, "TRANSFER", str(data), "OK", "BUSINESS_LOGIC" if vulnerable else "")
            return self.transfer_get(handler, f"Transfer completed. Evidence {ev['EVENT_ID']}.")
        except Exception as e:
            self.audit(sess, "TRANSFER", str(data), "ERROR")
            return self.transfer_get(handler, f"Transfer failed: {e}")

    def profile(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        if handler.command == "POST":
            data = _parse_form(handler)
            vuln = not _is_secure(self.state)
            if sess.get("CUSTOMER_ID"):
                self.svc.update_customer(sess.get("CUSTOMER_ID"), data, channel="WEB9080", vulnerable=vuln)
                self.audit(sess, "PROFILE", str(data), "OK", "MASS_ASSIGNMENT" if vuln and any(k in data for k in ("role","isAdmin","creditLimit")) else "")
        c = self.store.customers.get(sess.get("CUSTOMER_ID", ""))
        name = c.name if c else sess.get("USERNAME")
        body = f"""<h1>Profile</h1><form method='post' class='form-grid'><label>Name<input name='name' value='{_esc(name)}'></label><label>Address<input name='address1' value='{_esc(getattr(c,'address1',''))}'></label><label class='lab-only'>Mass assignment field<input name='isAdmin' value='true'></label><button class='button'>Update profile</button></form>"""
        _send(handler, 200, self.layout("Profile", body, sess))

    def trace_panel(self) -> str:
        return """
<section class='trace-shell' id='traceShell'>
  <div class='trace-head'><h2>Live backend trace</h2><span id='traceStatus' class='status-chip'>Trace starting</span><div><button class='button tiny' onclick='pauseTrace()'>Pause</button><button class='button tiny secondary' onclick='resumeTrace()'>Resume</button><button class='button tiny ghost' onclick='clearTrace()'>Clear</button><select id='traceFilter' onchange='renderTrace()'><option value='ALL'>All</option><option>WEB9080</option><option>CBSA</option><option>CICS</option><option>SQL</option><option>DB2</option><option>SMF</option><option>CONSOLE</option></select></div></div>
  <div class='trace-grid'>
    <pre id='traceStream' class='trace-stream'>Waiting for teller activity...</pre>
    <div class='arch-map' id='archMap'>
      <div class='arch-node' data-node='BROWSER'>Browser Teller Portal</div>
      <div class='arch-arrow'>↓</div>
      <div class='arch-node' data-node='WEB9080'>FIBSWEB9080</div>
      <div class='arch-arrow'>↓</div>
      <div class='arch-node' data-node='CBSA'>CBSA Service Layer</div>
      <div class='arch-split'><div class='arch-node' data-node='CICS'>CICS / OMEN</div><div class='arch-node' data-node='DB2'>Db2 / CBSA Tables</div></div>
      <div class='arch-split'><div class='arch-node' data-node='SQL'>SQL</div><div class='arch-node' data-node='SMF'>SMF 80/101/102/110</div></div>
      <div class='arch-node' data-node='CONSOLE'>Master Console / zSecure / SYSVIEW</div>
    </div>
  </div>
</section>
"""

    def teller_search_page(self, handler: BaseHTTPRequestHandler, msg: str = "", result: dict[str, Any] | None = None) -> None:
        sess = self.require_session(handler)
        if not sess: return
        if not self.is_staff(sess): return _send(handler, 403, self.layout("Forbidden", "<h1>Teller access required</h1>", sess))
        try:
            emit_trace_event(self.state, component="WEB9080", action="OPEN_TELLER_SEARCH", user=sess.get("USERNAME","TELLER"), route="/teller/search", result="OK", message="Teller search workspace opened")
        except Exception:
            pass
        result = result or {}
        customers = "".join(f"<tr><td>{_esc(r.get('CUSTOMER_ID'))}</td><td>{_esc(r.get('NAME'))}</td><td>{_esc(r.get('STATUS'))}</td><td>{_esc(r.get('LINKED_USER',''))}</td><td>{_esc(r.get('ACCOUNT_COUNT',''))}</td></tr>" for r in result.get('customers', []))
        accounts = "".join(f"<tr><td>{_esc(r.get('ACCOUNT_NUMBER'))}</td><td>{_esc(r.get('SORT_CODE'))}</td><td>{_esc(r.get('CUSTOMER_ID'))}</td><td>{_esc(r.get('ACCOUNT_TYPE'))}</td><td>{_money(r.get('AVAILABLE_BALANCE'))}</td><td>{_money(r.get('ACTUAL_BALANCE'))}</td><td>{_esc(r.get('STATUS'))}</td></tr>" for r in result.get('accounts', []))
        txns = "".join(f"<tr><td>{_esc(r.get('TIMESTAMP'))}</td><td>{_esc(r.get('TRANSACTION_ID') or r.get('EVENT_ID'))}</td><td>{_esc(r.get('TRANSACTION_TYPE') or r.get('ACTION'))}</td><td>{_esc(r.get('FROM_ACCOUNT') or r.get('ACCOUNT_NUMBER'))}</td><td>{_esc(r.get('TO_ACCOUNT'))}</td><td>{_money(r.get('AMOUNT'))}</td><td>{_esc(r.get('CORRELATION_ID'))}</td></tr>" for r in result.get('transactions', []))
        sql_panel = ""
        if result:
            sql_panel = f"""<aside class='sql-trace'><h3>Training SQL trace</h3><p><strong>Result:</strong> {_esc(result.get('result'))} · <strong>Rows:</strong> {_esc(result.get('rows_returned'))} · <strong>Correlation:</strong> {_esc(result.get('correlation_id'))}</p><pre>{_esc(result.get('simulated_sql'))}</pre><p>{_esc(result.get('secure_comparison'))}</p></aside>"""
        body = f"""
<section class='teller-workspace'><h1>Teller customer and account search</h1><div class='tartan-rule'></div><p class='lede'>Search CBSA customers, accounts and transactions. In vulnerable mode this workflow demonstrates SQL injection evidence through WEB9080, CICS, Db2, SMF and the Master Console.</p>
<form method='post' action='/teller/search' class='panel search-panel'><div class='form-row'><label>Search type<select name='type'><option value='all'>All</option><option value='customer'>Customer</option><option value='account'>Account</option><option value='transaction'>Transaction</option></select></label><label>Search value<input name='q' placeholder="1001, ALICE, 00000101, or 1001' OR '1'='1" value='{_esc(result.get('query',''))}'></label><button class='button'>Search</button></div><p class='hint'>Try <code>1001' OR '1'='1</code> in vulnerable mode, then restart with <code>--secure</code> to compare behaviour.</p></form>{sql_panel}
<section class='results-grid'><article class='panel'><h2>Customers</h2><table><tr><th>ID</th><th>Name</th><th>Status</th><th>Linked user</th><th>Accounts</th></tr>{customers or '<tr><td colspan="5">No customer rows yet.</td></tr>'}</table></article><article class='panel'><h2>Accounts</h2><table><tr><th>Account</th><th>Sort code</th><th>Customer</th><th>Type</th><th>Available</th><th>Actual</th><th>Status</th></tr>{accounts or '<tr><td colspan="7">No account rows yet.</td></tr>'}</table></article><article class='panel wide'><h2>Transactions</h2><table><tr><th>Time</th><th>Txn/Evidence</th><th>Type</th><th>From</th><th>To</th><th>Amount</th><th>Correlation</th></tr>{txns or '<tr><td colspan="7">No transaction rows yet.</td></tr>'}</table></article></section></section>{self.trace_panel()}"""
        _send(handler, 200, self.layout("Teller search", body, sess, msg))

    def teller(self, handler: BaseHTTPRequestHandler, msg: str = "") -> None:
        sess = self.require_session(handler)
        if not sess: return
        if not self.is_staff(sess): return _send(handler, 403, self.layout("Forbidden", "<h1>Teller access required</h1>", sess))
        try:
            emit_trace_event(self.state, component="WEB9080", action="OPEN_TELLER", user=sess.get("USERNAME","TELLER"), route="/teller", result="OK", message="Teller portal opened")
        except Exception:
            pass
        users = "".join(f"<tr><td>{_esc(u.get('USERNAME'))}</td><td>{_esc(u.get('ROLE'))}</td><td>{_esc(u.get('CUSTOMER_ID'))}</td><td>{_esc(u.get('STATUS'))}</td></tr>" for u in self.store.web_users.values())
        customers = "".join(f"<tr><td>{_esc(c.customer_id)}</td><td>{_esc(c.name)}</td><td>{_esc(c.status)}</td></tr>" for c in self.store.customers.values())
        body = f"""<h1>Teller portal</h1><p class='lede'>Service FIBS customers, create GACF.DB users and watch every backend interaction in the live trace.</p><div class='quick'><a class='button' href='/teller/search'>Search customers and accounts</a><a class='button secondary' href='/audit'>View audit</a></div><section class='grid'><form method='post' action='/teller/customers/new' class='panel'><h2>Create customer</h2><label>Name<input name='name' required></label><label>Address<input name='address1'></label><button class='button'>Create customer</button></form><form method='post' action='/teller/users/new' class='panel'><h2>Create GACF.DB user</h2><label>Username<input name='username' maxlength='8' required></label><label>Password<input name='password' required></label><label>Customer ID<input name='customer_id'></label><label>Role<select name='role'><option>customer</option><option>teller</option><option>admin</option><option>instructor</option></select></label><button class='button'>Create user</button></form><form method='post' action='/teller/accounts/new' class='panel'><h2>Create account</h2><label>Customer ID<input name='customer_id' required></label><label>Opening balance<input name='balance' value='100.00'></label><button class='button'>Create account</button></form></section><h2>GACF/WEB users</h2><table><tr><th>User</th><th>Role</th><th>Customer</th><th>Status</th></tr>{users}</table><h2>Customers</h2><table><tr><th>ID</th><th>Name</th><th>Status</th></tr>{customers}</table>{self.trace_panel()}"""
        _send(handler, 200, self.layout("Teller portal", body, sess, msg))
    def teller_post(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        sess = self.require_session(handler)
        if not sess: return
        if not self.is_staff(sess): return _send(handler, 403, self.layout("Forbidden", "<h1>Teller access required</h1>", sess))
        data = _parse_form(handler)
        try:
            if path == "/teller/customers/new":
                c = self.svc.create_customer(data, channel="WEB9080")
                self.audit(sess, "TELLER_CREATE_CUSTOMER", c.customer_id, "OK")
                try:
                    emit_trace_event(self.state, component="CBSA", action="CREATE_CUSTOMER", user=sess.get("USERNAME","TELLER"), route=path, result="OK", message=c.customer_id)
                    emit_smf110(self.state, event="CREATE_CUSTOMER", user=sess.get("USERNAME","TELLER"), channel="WEB9080", result="SUCCESS", transaction="OMEN", program="CRECUST", resource=c.customer_id)
                except Exception:
                    pass
                return self.teller(handler, f"Created customer {c.customer_id}.")
            if path == "/teller/users/new":
                username = data.get("username", "").strip().upper()
                if len(username) > 8: raise ValueError("GACF user IDs must not exceed 8 characters")
                self.state.racf.adduser(username, data.get("password", ""), special=data.get("role") in {"admin","instructor"}, omvs=False, name=username)
                self.state.racf.load(merge=True)
                self.store.ensure_web_user(username, data.get("password", ""), data.get("customer_id", ""), data.get("role", "customer"), username)
                self.audit(sess, "TELLER_CREATE_GACF_USER", username, "OK")
                try:
                    emit_trace_event(self.state, component="CBSA", action="CREATE_GACF_USER", user=sess.get("USERNAME","TELLER"), route=path, result="OK", message=username)
                    emit_smf80(self.state, event="CREATE_GACF_USER", user=sess.get("USERNAME","TELLER"), channel="WEB9080", result="SUCCESS", resource="GACF.DB."+username, endpoint=path)
                except Exception:
                    pass
                return self.teller(handler, f"Created GACF.DB/web user {username}.")
            if path == "/teller/accounts/new":
                a = self.svc.create_account(data, channel="WEB9080")
                self.audit(sess, "TELLER_CREATE_ACCOUNT", a.account_number, "OK")
                try:
                    emit_trace_event(self.state, component="CBSA", action="CREATE_ACCOUNT", user=sess.get("USERNAME","TELLER"), route=path, result="OK", message=a.account_number)
                    emit_smf110(self.state, event="CREATE_ACCOUNT", user=sess.get("USERNAME","TELLER"), channel="WEB9080", result="SUCCESS", transaction="OMEN", program="CREACC", resource=a.account_number)
                except Exception:
                    pass
                return self.teller(handler, f"Created account {a.account_number}.")
        except Exception as e:
            self.audit(sess, "TELLER_ACTION", str(data), "ERROR")
            return self.teller(handler, f"Teller action failed: {e}")
        return self.teller(handler)

    def labs(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        _send(handler, 200, self.layout("FIBS Mainframe API Security Academy", render_lab_index(), sess))

    def lab_detail(self, handler: BaseHTTPRequestHandler, slug: str) -> None:
        sess = self.require_session(handler)
        if not sess: return
        lab = get_lab(slug)
        if not lab:
            return _send(handler, 404, self.layout("Lab not found", f"<h1>Lab not found</h1><p>{_esc(slug)}</p>", sess))
        ev = self.audit(sess, f"LAB_{slug.upper().replace('-', '_')}_VIEW", lab.summary, "VIEW", slug.upper())
        try:
            emit_trace_event(self.state, component="WEB9080", action="OPEN_LAB", user=sess.get("USERNAME","WEBUSER"), route=f"/labs/{slug}", result="VIEW", message=lab.title, correlation_id=ev.get("CORRELATION_ID",""))
        except Exception:
            pass
        _send(handler, 200, self.layout(lab.title, render_lab_detail(lab, _mode(self.state)) + self.trace_panel(), sess))

    def lab_action(self, handler: BaseHTTPRequestHandler, slug: str, action: str) -> None:
        sess = self.require_session(handler)
        if not sess:
            return
        lab = get_lab(slug)
        if not lab:
            return _send(handler, 404, self.layout("Lab not found", f"<h1>Lab not found</h1><p>{_esc(slug)}</p>", sess))
        user = sess.get("USERNAME", "WEBUSER")
        data = _parse_form(handler) if handler.command == "POST" else {k: v[-1] for k, v in parse_qs(urlparse(handler.path).query).items()}
        payload = data.get("payload") or data.get("q") or data.get("body") or ""
        trace_id = data.get("trace_id") or ""
        try:
            if action == "run" and handler.command == "POST":
                result = run_lab(self.state, slug, payload, user, trace_id=trace_id)
                return _send(handler, 200, self.layout(lab.title, render_lab_detail(lab, _mode(self.state), result, "Lab action complete.") + self.trace_panel(), sess))
            if action == "secure-compare" and handler.command == "POST":
                result = secure_compare(self.state, slug, payload, user, trace_id=trace_id)
                return _send(handler, 200, self.layout(lab.title, render_lab_detail(lab, _mode(self.state), result, "Secure comparison complete.") + self.trace_panel(), sess))
            if action == "reset" and handler.command == "POST":
                result = reset_lab(self.state, slug, user, trace_id=trace_id)
                return _send(handler, 200, self.layout(lab.title, render_lab_detail(lab, _mode(self.state), result, "Lab reset complete.") + self.trace_panel(), sess))
            if action == "export":
                evidence_id = data.get("evidence_id", "")
                result = export_evidence(self.state, slug, evidence_id, user, trace_id=trace_id)
                body = f"<h1>Evidence export</h1><pre class='sql-trace'>{_esc(json.dumps(result, indent=2, sort_keys=True))}</pre><p><a class='button' href='/labs/{_esc(slug)}'>Back to lab</a></p>"
                return _send(handler, 200, self.layout(f"{lab.title} evidence", body, sess))
        except Exception as e:
            body = render_lab_detail(lab, _mode(self.state), None, f"Lab action failed: {e}") + self.trace_panel()
            return _send(handler, 500, self.layout(lab.title, body, sess))
        return _send(handler, 405, self.layout("Method not allowed", "<h1>Method not allowed</h1>", sess))

    def audit_page(self, handler: BaseHTTPRequestHandler) -> None:
        sess = self.require_session(handler)
        if not sess: return
        events = (self.store.web_audit + self.store.vuln_events + self.store.sqli_events + self.store.api_audit + self.store.cics_audit)[-100:]
        rows = "".join(f"<tr><td>{_esc(e.get('TIMESTAMP'))}</td><td>{_esc(e.get('CHANNEL'))}</td><td>{_esc(e.get('USER'))}</td><td>{_esc(e.get('ACTION'))}</td><td>{_esc(e.get('RESULT'))}</td><td>{_esc(e.get('SCENARIO'))}</td><td>{_esc(e.get('EVENT_ID'))}</td></tr>" for e in events)
        _send(handler, 200, self.layout("Audit", f"<h1>Audit and evidence</h1><table><tr><th>Time</th><th>Channel</th><th>User</th><th>Action</th><th>Result</th><th>Scenario</th><th>Evidence</th></tr>{rows}</table>", sess))

    def webapi(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        sess = self.session(handler)
        if path == "/webapi/session": return _json(handler, 200, {"authenticated": bool(sess), "session": sess or {}, "mode": _mode(self.state)})
        if path == "/webapi/auth/token" and handler.command == "POST": return _json(handler, 200, oauth_token(self.state, _parse_form(handler)))
        if path == "/webapi/auth/introspect" and handler.command == "POST": return _json(handler, 200, oauth_introspect(self.state, _parse_form(handler)))
        if path == "/webapi/labs/jwt/forge" and handler.command == "POST": return _json(handler, 200, lab_jwt_forge(self.state, _parse_form(handler)))
        if path == "/webapi/labs/oauth/authorize" and handler.command == "POST": return _json(handler, 200, lab_oauth_authorize(self.state, _parse_form(handler), (sess or {}).get("USERNAME", "alice")))
        if path == "/webapi/labs/oauth/token" and handler.command == "POST": return _json(handler, 200, lab_oauth_token(self.state, _parse_form(handler)))
        if path == "/webapi/labs/oauth/refresh" and handler.command == "POST": return _json(handler, 200, lab_oauth_refresh(self.state, _parse_form(handler)))
        if path.startswith("/webapi/labs/"):
            parts = path.strip("/").split("/")
            # webapi/labs/{slug}/{action} or evidence/export
            if len(parts) >= 4:
                slug, action = parts[2], parts[3]
                user = (sess or {}).get("USERNAME", "WEBUSER")
                data = _parse_form(handler) if handler.command == "POST" else {k: v[-1] for k, v in parse_qs(urlparse(handler.path).query).items()}
                payload = data.get("payload") or data.get("q") or data.get("body") or ""
                trace_id = data.get("trace_id") or parse_qs(urlparse(handler.path).query).get("trace_id", [""])[0]
                try:
                    if action == "run" and handler.command == "POST":
                        return _json(handler, 200, run_lab(self.state, slug, payload, user, trace_id=trace_id))
                    if action == "secure-compare" and handler.command == "POST":
                        return _json(handler, 200, secure_compare(self.state, slug, payload, user, trace_id=trace_id))
                    if action == "reset" and handler.command == "POST":
                        return _json(handler, 200, reset_lab(self.state, slug, user, trace_id=trace_id))
                    if action in {"evidence", "export"}:
                        evidence_id = parts[4] if len(parts) >= 5 else data.get("evidence_id", "")
                        return _json(handler, 200, export_evidence(self.state, slug, evidence_id, user, trace_id=trace_id))
                except KeyError as e:
                    return _json(handler, 404, {"error": str(e), "lab": slug})
                except Exception as e:
                    return _json(handler, 500, {"error": str(e), "lab": slug, "trace_id": trace_id})
        if path == "/webapi/trace/session" and handler.command == "POST":
            data = _parse_form(handler)
            user = (sess or {}).get("USERNAME", "WEBUSER")
            return _json(handler, 200, create_trace_session(self.state, data.get("page", "/labs"), user, data.get("lab_slug", "")))
        if path.startswith("/webapi/trace/") and path.endswith("/events"):
            qs = parse_qs(urlparse(handler.path).query)
            trace_id = path.split("/")[3]
            return _json(handler, 200, {"events": get_trace_events(self.state, qs.get("since", [""])[0], trace_id=trace_id), "trace_id": trace_id})
        if path.startswith("/webapi/trace/") and path.endswith("/clear") and handler.command == "POST":
            trace_id = path.split("/")[3]
            clear_trace_events(self.state, trace_id)
            return _json(handler, 200, {"status":"cleared", "trace_id": trace_id})
        if path == "/webapi/teller/events":
            qs = parse_qs(urlparse(handler.path).query)
            return _json(handler, 200, {"events": get_trace_events(self.state, qs.get("since", [""])[0])})
        if path == "/webapi/teller/live-events":
            events = get_trace_events(self.state)
            chunks = []
            for ev in events[-50:]:
                chunks.append("event: trace\n")
                chunks.append("data: " + json.dumps(ev, sort_keys=True) + "\n\n")
            if not chunks:
                chunks.append("event: heartbeat\ndata: {}\n\n")
            return _send(handler, 200, "".join(chunks), "text/event-stream; charset=utf-8", {"X-Accel-Buffering":"no"})
        if not sess: return _json(handler, 401, {"error":"login required"})
        if path == "/webapi/teller/trace/clear":
            if not self.is_staff(sess): return _json(handler, 403, {"error":"teller access required"})
            clear_trace_events(self.state)
            return _json(handler, 200, {"status":"cleared"})
        if path == "/webapi/teller/search":
            if not self.is_staff(sess): return _json(handler, 403, {"error":"teller access required"})
            qs = parse_qs(urlparse(handler.path).query)
            result = teller_search(self.state, self.store, qs.get("q", [""])[0], qs.get("type", ["all"])[0], sess.get("USERNAME", "TELLER"), not _is_secure(self.state))
            return _json(handler, 200, result)
        if path == "/webapi/accounts":
            accounts = self.svc.list_accounts(sess.get("CUSTOMER_ID", "")) if sess.get("ROLE") == "customer" else list(self.store.accounts.values())
            return _json(handler, 200, {"accounts":[a.row() for a in accounts]})
        if path == "/webapi/transactions": return _json(handler, 200, {"transactions": self.store.proctran[-50:]})
        if path == "/webapi/audit": return _json(handler, 200, {"events": self.store.web_audit[-100:]})
        if path.startswith("/webapi/debug/customer/"):
            cid = path.rsplit("/",1)[1]
            c = self.store.customers.get(cid)
            if not c: return _json(handler, 404, {"error":"not found"})
            row = c.row()
            if _is_secure(self.state):
                row = {k:v for k,v in row.items() if k not in {"RISK_SCORE","ISADMIN","CREDITLIMIT"}}
            self.audit(sess, "EXCESSIVE_DATA", cid, "OK", "EXCESSIVE_DATA" if not _is_secure(self.state) else "")
            return _json(handler, 200, {"customer": row, "mode": _mode(self.state)})
        if path.startswith("/webapi/labs/sqli"):
            qs = parse_qs(urlparse(handler.path).query); customer = qs.get("customer", ["1001"])[0]
            if _is_secure(self.state) or "'" not in customer:
                rows = [a.row() for a in self.svc.list_accounts(customer)]
                scenario = ""
            else:
                rows = [a.row() for a in self.store.accounts.values()]
                scenario = "SQLI"
            action = "SQLI_SEARCH" if scenario else "ACCOUNT_SEARCH"
            ev = self.audit(sess, action, customer, "OK", scenario)
            if scenario:
                try:
                    from gibson.core.security_event_bus import emit_smf102
                    emit_smf102(self.state, event="SQLI_SEARCH", user=sess.get("USERNAME","WEBUSER"),
                                channel="WEB9080", result="SUCCESS", resource="CBSA.ACCOUNT",
                                table="CBSA.ACCOUNT", endpoint="/webapi/labs/sqli",
                                payload=customer, correlation_id=ev.get("CORRELATION_ID",""),
                                detail=f"rows_returned={len(rows)}")
                except Exception:
                    pass
            return _json(handler, 200, {"rows": rows, "evidence": ev, "mode": _mode(self.state)})
        return _json(handler, 404, {"error":"FIBS web API route not found", "path": path})

    def static(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        if ".." in path or "%2e" in path.lower():
            return _send(handler, 400, "bad path", "text/plain")
        asset_root = Path(__file__).resolve().parents[1] / "assets" / "fibs9080"
        mapping = {
            "/static/js/fibs.js": (asset_root / "fibs.js", "application/javascript; charset=utf-8"),
            "/static/css/fibs.css": (asset_root / "fibs.css", "text/css; charset=utf-8"),
        }
        item = mapping.get(path)
        if not item:
            return _send(handler, 404, "not found", "text/plain")
        file_path, ctype = item
        try:
            return _send(handler, 200, file_path.read_text(encoding="utf-8"), ctype)
        except FileNotFoundError:
            return _send(handler, 404, "not found", "text/plain")


    def route(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        path = unquote(parsed.path or "/")
        if ".." in path: return _send(handler, 400, "bad path", "text/plain")
        if path.startswith("/static/"): return self.static(handler, path)
        if path == "/.well-known/openid-configuration": return _json(handler, 200, discovery("http://127.0.0.1:9080"))
        if path == "/oauth/jwks": return _json(handler, 200, jwks())
        if path == "/oauth/authorize":
            params = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            sess = self.session(handler) or {"USERNAME":"alice"}
            return _json(handler, 200, oauth_authorize(self.state, params, sess.get("USERNAME", "alice")))
        if path == "/oauth/token" and handler.command == "POST": return _json(handler, 200, oauth_token(self.state, _parse_form(handler)))
        if path == "/oauth/introspect" and handler.command == "POST": return _json(handler, 200, oauth_introspect(self.state, _parse_form(handler)))
        if path == "/oauth/revoke" and handler.command == "POST": return _json(handler, 200, oauth_revoke(self.state, _parse_form(handler)))
        if path == "/oauth/logout": return _json(handler, 200, {"status":"logged_out"})
        if path.startswith("/webapi/"): return self.webapi(handler, path)
        if path == "/": return self.landing(handler)
        if path == "/login" and handler.command == "GET": return self.login_get(handler)
        if path == "/login" and handler.command == "POST": return self.login_post_fixed(handler)
        if path == "/logout": return self.logout(handler)
        if path in {"/about","/training"}: return _send(handler, 200, self.layout("Training", "<h1>FIBS BANK training simulator</h1><p>Scottish-themed CBSA-backed vulnerable banking lab.</p>"))
        if path == "/dashboard": return self.dashboard(handler)
        if path == "/accounts" or path.startswith("/accounts/"): return self.accounts(handler)
        if path == "/transactions" or path.startswith("/transactions/"): return self.accounts(handler)
        if path == "/transfer" and handler.command == "GET": return self.transfer_get(handler)
        if path == "/transfer" and handler.command == "POST": return self.transfer_post(handler)
        if path == "/payments" and handler.command == "GET": return self.transfer_get(handler)
        if path == "/payments" and handler.command == "POST": return self.transfer_post(handler)
        if path == "/profile": return self.profile(handler)
        if path in {"/statements","/support"}: return _send(handler, 200, self.layout(path.strip('/').title(), f"<h1>{_esc(path.strip('/').title())}</h1><p>Generated from CBSA transaction state.</p>", self.require_session(handler)))
        if path == "/teller/search" and handler.command == "GET": return self.teller_search_page(handler)
        if path == "/teller/search" and handler.command == "POST":
            sess = self.require_session(handler)
            if not sess: return
            if not self.is_staff(sess): return _send(handler, 403, self.layout("Forbidden", "<h1>Teller access required</h1>", sess))
            data = _parse_form(handler)
            result = teller_search(self.state, self.store, data.get("q", ""), data.get("type", "all"), sess.get("USERNAME", "TELLER"), not _is_secure(self.state))
            return self.teller_search_page(handler, result=result)
        if path == "/teller": return self.teller(handler)
        if path in {"/teller/customers","/teller/customers/new","/teller/users/new","/teller/accounts/new","/teller/audit"} and handler.command == "GET": return self.teller(handler)
        if path in {"/teller/customers/new","/teller/users/new","/teller/accounts/new","/teller/password-reset"} and handler.command == "POST": return self.teller_post(handler, path)
        if path == "/labs": return self.labs(handler)
        if path.startswith("/labs/"):
            parts = [x for x in path.strip("/").split("/") if x]
            if len(parts) >= 3 and parts[2] in {"run", "secure-compare", "reset", "export"}:
                return self.lab_action(handler, parts[1], parts[2])
            return self.lab_detail(handler, parts[1] if len(parts) > 1 else "")
        if path == "/audit": return self.audit_page(handler)
        if path == "/api-docs": return _send(handler, 200, self.layout("API docs", "<h1>API docs</h1><p>Use /webapi/* on 9080 and /api/v1/cbsa/* on 8080.</p>", self.require_session(handler)))
        return _send(handler, 404, self.layout("Not found", f"<h1>Route not found</h1><p>{_esc(path)}</p>", self.session(handler)))


class FibsWeb9080Handler(BaseHTTPRequestHandler):
    state: GibsonState
    server_version = "FIBSWEB9080"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _dispatch(self) -> None:
        try:
            self.state.note_port_touch(self.client_address[0], int(getattr(self.state.config, "fibs_web_port", 9080)), service="FIBS9080")
        except Exception:
            pass
        return FibsBankApp(self.state).route(self)

    def do_GET(self) -> None: return self._dispatch()
    def do_POST(self) -> None: return self._dispatch()
    def do_PUT(self) -> None: return self._dispatch()
    def do_DELETE(self) -> None: return self._dispatch()
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-HTTP-Method-Override")
        self.end_headers()


def serve_fibs_web9080(state: GibsonState):
    FibsWeb9080Handler.state = state
    port = int(getattr(state.config, "fibs_web_port", 9080))
    srv = ThreadedHTTPServer((state.config.host, port), FibsWeb9080Handler)
    th = threading.Thread(target=srv.serve_forever, name="FIBSWEB9080", daemon=True)
    th.start()
    return srv
