from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from gibson.apps.fibs_identity.jwt_tokens import AUDIENCE, ISSUER, LAB_SECRET, make_token, validate_token
from gibson.core.security_event_bus import emit_smf80, emit_trace_event

CLIENTS = {
    "fibs-web": {
        "client_id": "fibs-web",
        "redirect_uri": "http://127.0.0.1:9080/oauth/callback",
        "scopes": ["openid", "profile", "accounts", "teller"],
        "public": True,
    },
    "fibs-lab": {
        "client_id": "fibs-lab",
        "redirect_uri": "http://127.0.0.1:9080/oauth/callback",
        "scopes": ["openid", "profile", "accounts", "teller", "admin"],
        "public": True,
    },
}


def _secure(state: Any) -> bool:
    return getattr(getattr(state, "config", object()), "security_mode", "vuln") == "secure"


def _corr() -> str:
    return "AUTH-" + secrets.token_hex(4).upper()


def _trace(state: Any, action: str, user: str, result: str, corr: str, message: str = "") -> None:
    emit_trace_event(state, component="AUTH", action=action, user=user, channel="WEB9080", route="/oauth", result=result, correlation_id=corr, message=message)
    emit_smf80(state, event=action, user=user, channel="WEB9080", result=result, resource="FIBS.IDENTITY", endpoint="/oauth", correlation_id=corr, detail=message)


def discovery(base: str = ISSUER) -> dict[str, Any]:
    return {
        "issuer": base,
        "authorization_endpoint": base + "/oauth/authorize",
        "token_endpoint": base + "/oauth/token",
        "jwks_uri": base + "/oauth/jwks",
        "introspection_endpoint": base + "/oauth/introspect",
        "revocation_endpoint": base + "/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "id_token_signing_alg_values_supported": ["HS256"],
        "scopes_supported": ["openid", "profile", "accounts", "teller"],
    }


def jwks() -> dict[str, Any]:
    return {"keys": [{"kty": "oct", "kid": "fibs-hs256-1", "alg": "HS256", "use": "sig", "k": "<redacted-training-key>"}]}


def _store(state: Any) -> dict[str, Any]:
    data = getattr(state, "fibs_identity_store", None)
    if data is None:
        data = {"codes": {}, "refresh": {}, "revoked": set()}
        setattr(state, "fibs_identity_store", data)
    return data


def _pkce_s256(verifier: str) -> str:
    import base64
    digest = hashlib.sha256((verifier or "").encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize(state: Any, params: dict[str, str], user: str = "alice") -> dict[str, Any]:
    secure = _secure(state)
    corr = _corr()
    client = CLIENTS.get(params.get("client_id", ""))
    if not client:
        _trace(state, "OAUTH_AUTHORIZE", user, "DENIED", corr, "unknown client")
        return {"error": "invalid_client", "correlation_id": corr}
    redirect_uri = params.get("redirect_uri", "")
    if secure and redirect_uri != client["redirect_uri"]:
        _trace(state, "OAUTH_REDIRECT", user, "BLOCKED", corr, "redirect mismatch")
        return {"error": "invalid_redirect_uri", "correlation_id": corr}
    if secure and not params.get("state"):
        _trace(state, "OAUTH_STATE", user, "BLOCKED", corr, "missing state")
        return {"error": "state_required", "correlation_id": corr}
    if secure and not params.get("code_challenge"):
        _trace(state, "OAUTH_PKCE", user, "BLOCKED", corr, "missing PKCE challenge")
        return {"error": "pkce_required", "correlation_id": corr}
    code = "CODE-" + secrets.token_urlsafe(10)
    _store(state)["codes"][code] = {"client_id": client["client_id"], "redirect_uri": redirect_uri or client["redirect_uri"], "user": user, "scope": params.get("scope", "openid profile accounts"), "code_challenge": params.get("code_challenge", ""), "state": params.get("state", ""), "nonce": params.get("nonce", ""), "iat": time.time(), "used": False}
    result = "OK" if secure else "ALLOWED-VULN"
    _trace(state, "OAUTH_AUTHORIZE", user, result, corr, "authorization code issued")
    return {"code": code, "state": params.get("state", ""), "redirect_uri": redirect_uri or client["redirect_uri"], "correlation_id": corr, "mode": "secure" if secure else "vulnerable"}


def token(state: Any, data: dict[str, str]) -> dict[str, Any]:
    secure = _secure(state)
    corr = _corr()
    grant = data.get("grant_type", "authorization_code")
    if grant == "refresh_token":
        rt = data.get("refresh_token", "")
        item = _store(state)["refresh"].get(rt)
        if secure and (not item or item.get("used")):
            _trace(state, "OAUTH_REFRESH_REUSE", "UNKNOWN", "BLOCKED", corr, "refresh reuse")
            return {"error": "invalid_grant", "correlation_id": corr}
        if item:
            item["used"] = True
        user = (item or {}).get("user", "alice")
    else:
        code = data.get("code", "")
        item = _store(state)["codes"].get(code)
        if not item:
            _trace(state, "OAUTH_TOKEN", "UNKNOWN", "DENIED", corr, "unknown code")
            return {"error": "invalid_grant", "correlation_id": corr}
        user = item.get("user", "alice")
        if secure and item.get("used"):
            _trace(state, "OAUTH_CODE_REUSE", user, "BLOCKED", corr, "code reuse")
            return {"error": "invalid_grant", "correlation_id": corr}
        if secure and item.get("code_challenge") and _pkce_s256(data.get("code_verifier", "")) != item.get("code_challenge"):
            _trace(state, "OAUTH_PKCE", user, "BLOCKED", corr, "PKCE verification failed")
            return {"error": "invalid_grant", "correlation_id": corr}
        item["used"] = True
    role = data.get("role", "customer") if not secure else "customer"
    access = make_token(user, role=role, scopes=["openid", "profile", "accounts"])
    ident = make_token(user, role=role, scopes=["openid", "profile"])
    refresh = "RT-" + secrets.token_urlsafe(18)
    _store(state)["refresh"][refresh] = {"user": user, "used": False}
    _trace(state, "TOKEN_ISSUED", user, "OK", corr, "OAuth token issued")
    return {"access_token": access, "id_token": ident, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 900, "correlation_id": corr}


def introspect(state: Any, data: dict[str, str]) -> dict[str, Any]:
    corr = _corr()
    try:
        out = validate_token(data.get("token", ""), secure=_secure(state), allow_lab_weak=not _secure(state))
        sub = out["claims"].get("sub", "UNKNOWN")
        _trace(state, "TOKEN_INTROSPECT", sub, "ACTIVE", corr, "token active")
        return {"active": True, **out["claims"], "correlation_id": corr}
    except Exception as e:
        _trace(state, "TOKEN_INTROSPECT", "UNKNOWN", "INACTIVE", corr, str(e))
        return {"active": False, "error": str(e), "correlation_id": corr}


def revoke(state: Any, data: dict[str, str]) -> dict[str, Any]:
    token_value = data.get("token", "")
    _store(state)["revoked"].add(token_value[:64])
    corr = _corr()
    _trace(state, "TOKEN_REVOKE", "UNKNOWN", "OK", corr, "token revoked")
    return {"revoked": True, "correlation_id": corr}


def lab_jwt_forge(state: Any, data: dict[str, str]) -> dict[str, Any]:
    secure = _secure(state)
    lab = data.get("lab", "alg_none")
    user = data.get("sub", "alice")
    corr = _corr()
    if lab == "alg_none":
        forged = make_token(user, role=data.get("role", "admin"), alg="none")
        if secure:
            _trace(state, "JWT_ALG_NONE", user, "BLOCKED", corr, "alg none rejected")
            return {"accepted": False, "error": "algorithm rejected", "token": forged, "correlation_id": corr}
        _trace(state, "JWT_ALG_NONE", user, "ALLOWED-VULN", corr, "alg none accepted in vulnerable lab")
        return {"accepted": True, "token": forged, "claims": validate_token(forged, secure=False)["claims"], "correlation_id": corr}
    if lab == "weak_hmac":
        forged = make_token(user, role=data.get("role", "admin"), secret=LAB_SECRET)
        if secure:
            _trace(state, "JWT_WEAK_HMAC", user, "BLOCKED", corr, "weak HMAC rejected")
            return {"accepted": False, "token": forged, "correlation_id": corr}
        _trace(state, "JWT_WEAK_HMAC", user, "ALLOWED-VULN", corr, "weak HMAC accepted")
        return {"accepted": True, "token": forged, "correlation_id": corr}
    if lab == "expired":
        forged = make_token(user, lifetime=-5)
        if secure:
            _trace(state, "JWT_EXPIRED", user, "BLOCKED", corr, "expired token rejected")
            return {"accepted": False, "token": forged, "correlation_id": corr}
        _trace(state, "JWT_EXPIRED", user, "ALLOWED-VULN", corr, "expired token accepted")
        return {"accepted": True, "token": forged, "correlation_id": corr}
    if lab == "wrong_audience":
        forged = make_token(user, audience="other-api")
        if secure:
            _trace(state, "JWT_AUDIENCE", user, "BLOCKED", corr, "audience rejected")
            return {"accepted": False, "token": forged, "correlation_id": corr}
        _trace(state, "JWT_AUDIENCE", user, "ALLOWED-VULN", corr, "audience ignored")
        return {"accepted": True, "token": forged, "correlation_id": corr}
    if lab == "wrong_issuer":
        forged = make_token(user, issuer="http://evil.example")
        if secure:
            _trace(state, "JWT_ISSUER", user, "BLOCKED", corr, "issuer rejected")
            return {"accepted": False, "token": forged, "correlation_id": corr}
        _trace(state, "JWT_ISSUER", user, "ALLOWED-VULN", corr, "issuer ignored")
        return {"accepted": True, "token": forged, "correlation_id": corr}
    if lab == "role_tamper":
        forged = make_token(user, role="admin")
        if secure:
            _trace(state, "JWT_ROLE_TAMPER", user, "BLOCKED", corr, "server-side role used")
            return {"accepted": False, "token": forged, "correlation_id": corr}
        _trace(state, "JWT_ROLE_TAMPER", user, "ALLOWED-VULN", corr, "role claim trusted")
        return {"accepted": True, "token": forged, "correlation_id": corr}
    if lab == "kid_confusion":
        if secure:
            _trace(state, "JWT_KID_CONFUSION", user, "BLOCKED", corr, "kid allowlist enforced")
            return {"accepted": False, "error": "kid rejected", "correlation_id": corr}
        _trace(state, "JWT_KID_CONFUSION", user, "ALLOWED-VULN", corr, "controlled kid confusion accepted")
        return {"accepted": True, "kid": "lab-weak-key", "correlation_id": corr}
    return {"accepted": False, "error": "unknown lab", "correlation_id": corr}


def lab_oauth_authorize(state: Any, data: dict[str, str], user: str = "alice") -> dict[str, Any]:
    return authorize(state, data, user=user)


def lab_oauth_token(state: Any, data: dict[str, str]) -> dict[str, Any]:
    return token(state, data)


def lab_oauth_refresh(state: Any, data: dict[str, str]) -> dict[str, Any]:
    return token(state, {**data, "grant_type": "refresh_token"})
