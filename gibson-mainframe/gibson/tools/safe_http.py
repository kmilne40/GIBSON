from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import ssl

MAX_BYTES = 1024 * 1024
DEFAULT_TIMEOUT = 12
USER_AGENT = "Gibson-OMVS-HTTP/1.0"

@dataclass
class HttpResult:
    ok: bool
    status: int = 0
    reason: str = ""
    headers: dict[str, str] | None = None
    body: bytes = b""
    url: str = ""
    error: str = ""


def validate_url(url: str) -> tuple[bool, str]:
    try:
        p = urlparse(url)
    except Exception as exc:
        return False, f"invalid URL: {exc}"
    if p.scheme not in {"http", "https"}:
        return False, "unsupported URL scheme; only http and https are allowed"
    if not p.netloc:
        return False, "URL host is required"
    return True, ""


def fetch(url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None,
          data: bytes | None = None, timeout: float = DEFAULT_TIMEOUT,
          max_bytes: int = MAX_BYTES, head: bool = False) -> HttpResult:
    ok, msg = validate_url(url)
    if not ok:
        return HttpResult(False, url=url, error=msg)
    p = urlparse(url)
    if (p.hostname or "").lower() == "mainframe":
        netloc = "127.0.0.1" + ((":" + str(p.port)) if p.port else "")
        url = urlunparse((p.scheme, netloc, p.path or "/", p.params, p.query, p.fragment))
    method = "HEAD" if head else (method or "GET").upper()
    hdrs = {"User-Agent": USER_AGENT}
    for k, v in (headers or {}).items():
        if "\n" in k or "\r" in k or "\n" in v or "\r" in v:
            return HttpResult(False, url=url, error="invalid header")
        hdrs[str(k)] = str(v)
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=max(1, min(float(timeout), 30.0)), context=ctx) as r:  # nosec - constrained schemes only
            raw = r.read(max_bytes + 1) if not head else b""
            if len(raw) > max_bytes:
                return HttpResult(False, status=getattr(r, 'status', 0), reason=getattr(r, 'reason', ''), headers=dict(r.headers.items()), body=raw[:max_bytes], url=url, error="response too large")
            return HttpResult(True, status=getattr(r, 'status', 0), reason=getattr(r, 'reason', ''), headers=dict(r.headers.items()), body=raw, url=url)
    except HTTPError as exc:
        body = exc.read(min(max_bytes, 8192)) if not head else b""
        return HttpResult(False, status=exc.code, reason=str(exc.reason), headers=dict(exc.headers.items()) if exc.headers else {}, body=body, url=url, error=f"HTTP {exc.code}: {exc.reason}")
    except URLError as exc:
        return HttpResult(False, url=url, error=str(exc.reason))
    except Exception as exc:
        return HttpResult(False, url=url, error=f"{type(exc).__name__}: {exc}")


def safe_workspace_path(env, cwd: str, operand: str) -> str:
    if not operand or operand.startswith('-'):
        raise ValueError('invalid output path')
    if any(tok in operand for tok in ['\x00', '|', ';', '&', '`', '$(', '>', '<']):
        raise ValueError('unsafe output path')
    vp = env.resolve(cwd, operand)
    home = cwd.rstrip('/') or '/'
    if not (vp == home or vp.startswith(home + '/')):
        raise ValueError('output path escapes OMVS workspace')
    real = env.real_path(vp)
    root = env.root.resolve()
    rr = real.resolve() if real.exists() else real.parent.resolve() / real.name
    if root not in rr.parents and rr != root:
        raise ValueError('output path escapes OMVS workspace')
    real.parent.mkdir(parents=True, exist_ok=True)
    return str(real)


def render_headers(res: HttpResult) -> str:
    lines = [f"HTTP {res.status} {res.reason}".rstrip()]
    for k, v in (res.headers or {}).items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def render_body(res: HttpResult) -> str:
    try:
        return res.body.decode('utf-8', errors='replace')
    except Exception:
        return repr(res.body)
