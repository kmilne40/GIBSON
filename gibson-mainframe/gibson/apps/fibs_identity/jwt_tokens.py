from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

ISSUER = "http://127.0.0.1:9080"
AUDIENCE = "fibs-web"
LAB_SECRET = b"fibs-training-lab-secret"
STRONG_SECRET = b"gibson-fibs-local-secure-mode-secret-v1"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text or "") + pad)


def _json(data: dict[str, Any]) -> str:
    return b64url(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def sign_hs256(message: str, secret: bytes = STRONG_SECRET) -> str:
    return b64url(hmac.new(secret, message.encode("ascii"), hashlib.sha256).digest())


def make_token(subject: str, role: str = "customer", *, secret: bytes = STRONG_SECRET, alg: str = "HS256", audience: str = AUDIENCE, issuer: str = ISSUER, lifetime: int = 900, kid: str = "fibs-hs256-1", scopes: list[str] | None = None) -> str:
    now = int(time.time())
    header = {"typ": "JWT", "alg": alg, "kid": kid}
    payload = {"iss": issuer, "aud": audience, "sub": subject, "role": role, "scope": " ".join(scopes or ["openid", "profile", "accounts"]), "iat": now, "exp": now + lifetime}
    head = _json(header)
    body = _json(payload)
    signing_input = f"{head}.{body}"
    if alg.lower() == "none":
        return signing_input + "."
    return signing_input + "." + sign_hs256(signing_input, secret)


def parse_token(token: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        raise ValueError("invalid token shape")
    header = json.loads(b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
    return header, payload, parts[2]


def validate_token(token: str, *, secure: bool = True, allow_lab_weak: bool = False) -> dict[str, Any]:
    header, payload, sig = parse_token(token)
    alg = str(header.get("alg", ""))
    signing_input = ".".join(token.split(".")[:2])
    if secure:
        if alg != "HS256":
            raise ValueError("algorithm rejected")
        expected = sign_hs256(signing_input, STRONG_SECRET)
        if not hmac.compare_digest(sig or "", expected):
            raise ValueError("signature rejected")
        if payload.get("iss") != ISSUER:
            raise ValueError("issuer rejected")
        if payload.get("aud") != AUDIENCE:
            raise ValueError("audience rejected")
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
    else:
        if alg.lower() == "none":
            payload["_lab"] = "ALG_NONE_ACCEPTED"
        elif allow_lab_weak:
            expected = sign_hs256(signing_input, LAB_SECRET)
            if sig and hmac.compare_digest(sig, expected):
                payload["_lab"] = "WEAK_HMAC_ACCEPTED"
    return {"header": header, "claims": payload, "active": True}
