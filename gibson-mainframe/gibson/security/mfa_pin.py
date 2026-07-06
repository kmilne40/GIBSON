from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import time
import os
import secrets
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class MfaPinState:
    pin_hash: str = ""
    salt: str = ""
    pin_set_time: str = ""
    pin_set_by: str = ""
    time_window_minutes: int = 1


def _now(now: Optional[datetime] = None) -> datetime:
    return now or datetime.now()


def validate_pin_format(pin: str) -> bool:
    return isinstance(pin, str) and pin.isdigit() and len(pin) == 4


def _hash_pin(pin: str, salt: str) -> str:
    # stdlib-only simulator storage; no plaintext PIN is retained.
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def _state_path(state) -> Optional[Path]:
    cfg = getattr(state, "config", None)
    root = getattr(cfg, "sim_root", None) if cfg is not None else None
    if root is None:
        return None
    return Path(root) / "mfa_pin_state.json"


def save_pin_state(state) -> None:
    st = getattr(state, "mfa_pin_state", None)
    path = _state_path(state)
    if st is None or path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(st), indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        # MFA must not break simulator startup if the lab filesystem is read-only.
        pass


def load_pin_state(state) -> None:
    path = _state_path(state)
    if path is None or not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        setattr(state, "mfa_pin_state", MfaPinState(
            pin_hash=str(data.get("pin_hash", "")),
            salt=str(data.get("salt", "")),
            pin_set_time=str(data.get("pin_set_time", "")),
            pin_set_by=str(data.get("pin_set_by", "")),
            time_window_minutes=int(data.get("time_window_minutes", 1) or 1),
        ))
    except Exception:
        setattr(state, "mfa_pin_state", MfaPinState())


def set_pin(state, pin: str, actor: str = "CONSOLE", *, now: Optional[datetime] = None) -> str:
    pin = (pin or "").strip()
    if not validate_pin_format(pin):
        raise ValueError("MFA PIN MUST BE EXACTLY 4 NUMERIC DIGITS")
    st = getattr(state, "mfa_pin_state", None)
    if st is None:
        st = MfaPinState()
        setattr(state, "mfa_pin_state", st)
    st.salt = secrets.token_hex(16)
    st.pin_hash = _hash_pin(pin, st.salt)
    st.pin_set_time = _now(now).isoformat(timespec="seconds")
    st.pin_set_by = (actor or "CONSOLE").upper()
    save_pin_state(state)
    try:
        state.record_security_event(st.pin_set_by, "MFA PIN", "PIN SET OR CHANGED - SECRET NOT LOGGED", service="CONSOLE")
    except Exception:
        pass
    try:
        state.notify_console("GIBSON MFA PIN SET OR CHANGED - SECRET NOT LOGGED", severity="INFO")
    except Exception:
        pass
    return "GIBSON MFA PIN ACCEPTED\nMFA TOKEN FORMAT WHEN MFA IS ON: <PIN><HHMM>\nSECURITY EVENT RECORDED"


def is_pin_set(state) -> bool:
    st = getattr(state, "mfa_pin_state", None)
    return bool(st and st.pin_hash and st.salt)


def status_lines(state) -> list[str]:
    st = getattr(state, "mfa_pin_state", None)
    window = getattr(st, "time_window_minutes", 1) if st is not None else 1
    set_time = getattr(st, "pin_set_time", "") if st is not None else ""
    set_by = getattr(st, "pin_set_by", "") if st is not None else ""
    return [
        "MFA STATUS: " + ("ENABLED" if getattr(state, "mfa_enabled", False) else "DISABLED"),
        "MFA PIN STATUS: " + ("SET" if is_pin_set(state) else "NOT SET"),
        "MFA TOKEN FORMAT: PIN + HHMM (8 DIGITS)",
        f"MFA TIME WINDOW: +/- {window} MINUTE(S)",
        "MFA PIN SET TIME: " + (set_time or "NOT SET"),
        "MFA PIN SET BY: " + (set_by or "NOT SET"),
    ]


def _window_times(state, now: Optional[datetime] = None) -> Iterable[datetime]:
    st = getattr(state, "mfa_pin_state", None)
    window = int(getattr(st, "time_window_minutes", 1) if st is not None else 1)
    current = _now(now).replace(second=0, microsecond=0)
    for offset in range(-window, window + 1):
        yield current + timedelta(minutes=offset)


def _pin_matches(state, pin: str) -> bool:
    st = getattr(state, "mfa_pin_state", None)
    if not st or not st.pin_hash or not st.salt:
        return False
    return secrets.compare_digest(_hash_pin(pin, st.salt), st.pin_hash)


def validate_token(state, token: str, *, now: Optional[datetime] = None) -> bool:
    token = (token or "").strip()
    if is_pin_set(state):
        if not (token.isdigit() and len(token) == 8):
            return False
        pin = token[:4]
        hhmm = token[4:]
        if not _pin_matches(state, pin):
            return False
        return any(hhmm == t.strftime("%H%M") for t in _window_times(state, now))
    # Backward-compatible fallback for old tests/installations that have not yet
    # completed the IPL PIN prompt. This preserves existing HHMM-only MFA until a
    # PIN is explicitly configured.
    return token == (now.strftime("%H%M") if now is not None else time.strftime("%H%M"))


def configure_from_environment(state) -> None:
    # Load persisted IPL PIN first so the master-console IPL process and the
    # background service process validate the same PIN+HHMM token.
    load_pin_state(state)
    pin = os.getenv("GIBSON_MFA_PIN", "").strip()
    if pin and not is_pin_set(state):
        set_pin(state, pin, "ENVIRONMENT")
