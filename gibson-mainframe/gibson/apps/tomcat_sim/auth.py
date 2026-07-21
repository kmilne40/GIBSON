from __future__ import annotations
import base64
from typing import Any

REALM = "Tomcat Manager Application"

USERS = {
    ("tomcat", "tomcat"): {"manager-gui", "manager-script", "manager-status"},
    ("tomcat", "manager"): {"manager-gui", "manager-script", "manager-status"},
    ("manager", "manager"): {"manager-gui", "manager-script", "manager-status"},
}


def parse_basic(header: str | None) -> tuple[str, str] | None:
    h = (header or "").strip()
    if not h.lower().startswith("basic "):
        return None
    token = h.split(None, 1)[1].strip()
    if len(token) > 4096:
        return None
    try:
        raw = base64.b64decode(token, validate=True).decode("utf-8", errors="ignore")
    except Exception:
        return None
    if ":" not in raw:
        return None
    u, p = raw.split(":", 1)
    if len(u) > 64 or len(p) > 128:
        return None
    return u, p


def authenticate(state: Any, header: str | None, required_role: str) -> tuple[bool, str, set[str], str]:
    from .config import get_config
    cfg = get_config(state)
    if not cfg.enabled:
        return False, "", set(), "disabled"
    pair = parse_basic(header)
    if not pair:
        return False, "", set(), "missing"
    user, password = pair
    roles = USERS.get((user, password), set())
    if cfg.secure_mode or not cfg.vulnerable_defaults_enabled:
        roles = set()
    if not roles:
        return False, user, set(), "bad_credentials"
    if required_role and required_role not in roles:
        return False, user, roles, "missing_role"
    return True, user, set(roles), "ok"
