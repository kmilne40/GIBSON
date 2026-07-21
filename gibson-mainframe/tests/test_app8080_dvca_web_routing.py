from __future__ import annotations

import http.client
import json

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080


def _server():
    cfg = GibsonConfig(host="127.0.0.1", cbsa_api_port=0, security_mode="vuln", cbsa_vuln=True, dvca_vuln=True)
    state = GibsonState.create(cfg)
    srv = serve_cbsa_rest8080(state)
    return srv, srv.server_address[1]


def _request(port: int, method: str, path: str, body: str | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=body, headers=headers)
    res = conn.getresponse()
    data = res.read()
    ctype = res.getheader("Content-Type", "")
    conn.close()
    return res.status, ctype, data


def test_dvca_and_hack3270_html_pages_route_before_cbsa_fallback():
    srv, port = _server()
    try:
        for path, marker in [
            ("/dvca", b"hack3270-gibson"),
            ("/dvca/", b"hack3270-gibson"),
            ("/dvca?x=1", b"hack3270-gibson"),
            ("/dvca/hack3270", b"hack3270-gibson"),
            ("/dvca/hack3270/", b"hack3270-gibson"),
            ("/dvca/hack3270?x=1", b"hack3270-gibson"),
        ]:
            status, ctype, body = _request(port, "GET", path)
            assert status == 200, (path, status, body[:200])
            assert "text/html" in ctype
            assert marker in body
            assert b"CBSA route not found" not in body
    finally:
        srv.shutdown()
        srv.server_close()


def test_dvca_and_hack3270_json_api_routes_are_not_cbsa_fallback():
    srv, port = _server()
    try:
        for path in [
            "/api/v1/dvca/health",
            "/api/v1/dvca/health?verbose=true",
            "/api/v1/hack3270/status",
            "/api/v1/hack3270/status?verbose=true",
        ]:
            status, ctype, body = _request(port, "GET", path)
            assert status == 200, (path, status, body)
            assert "application/json" in ctype
            payload = json.loads(body.decode("utf-8"))
            assert payload["status"] == "UP"
            assert "CBSA route not found" not in body.decode("utf-8")

        status, ctype, body = _request(port, "POST", "/api/v1/dvca/session/start", "{}")
        assert status == 200
        assert "application/json" in ctype
        assert "session_id" in json.loads(body.decode("utf-8"))

        status, ctype, body = _request(port, "POST", "/api/v1/hack3270/session/start", "{}")
        assert status == 200
        assert "application/json" in ctype
        assert "session_id" in json.loads(body.decode("utf-8"))
    finally:
        srv.shutdown()
        srv.server_close()


def test_cbsa_routes_still_work_and_unknown_dvca_routes_are_isolated():
    srv, port = _server()
    try:
        status, ctype, body = _request(port, "GET", "/api/v1/cbsa/health")
        assert status == 200
        assert "application/json" in ctype
        payload = json.loads(body.decode("utf-8"))
        assert payload["service"] == "CBSA8080"

        status, ctype, body = _request(port, "GET", "/dvca/no-such-route")
        assert status == 404
        assert b"CBSA route not found" not in body

        status, ctype, body = _request(port, "GET", "/api/v1/hack3270/nope")
        assert status == 404
        assert b"CBSA route not found" not in body
        assert b"DVCA/hack3270 route not found" in body
    finally:
        srv.shutdown()
        srv.server_close()
