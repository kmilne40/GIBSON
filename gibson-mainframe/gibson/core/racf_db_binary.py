"""Snapshot the live RACF state into a binary SYS1.RACFDS.BACKUP (Scope A).

Triggered on a backup action (COPYRACF.JCL, RVARY, or an explicit backup
command). Builds the binary image from current users + recorded password
material, writes the raw bytes to a file the FTP listener can serve in binary
mode, stores a base64 copy in the catalogued dataset for visibility, and records
the SMF/HMS evidence a defender would see for a RACF-DB copy.
"""
from __future__ import annotations

import base64
import os
from typing import List, Optional, Tuple

from gibson.core.racf_db_image import RacfDbImage, ALG_DES, parse as _parse
from gibson.core.racf_legacy_des import generate_legacy_racf_des_hash

# A binary RACF DB cannot live verbatim in Gibson's text dataset store, so it is
# held as a marker line + base64. Retrieval paths (OMVS cp / OPUT, FTP binary)
# detect the marker and reconstitute the raw bytes, so the bytes that leave the
# system are the real binary image (not the base64 text).
BINARY_MARKER = "*RACFDS-BINARY-BASE64*"


def encode_for_dataset(data: bytes) -> str:
    return BINARY_MARKER + "\n" + base64.b64encode(data).decode("ascii") + "\n"


def is_binary_dataset(text: str) -> bool:
    return bool(text) and text.lstrip().startswith(BINARY_MARKER)


def decode_from_dataset(text: str) -> Optional[bytes]:
    """Return the raw binary bytes if `text` is a marker-wrapped binary dataset,
    else None."""
    if not is_binary_dataset(text):
        return None
    body = text.split("\n", 1)[1] if "\n" in text else ""
    try:
        return base64.b64decode("".join(body.split()))
    except Exception:
        return None

try:
    from gibson.core.racf_database import (
        _cred_store, LEGACY_LAB_PASSWORDS, legacy_seed_enabled)
except Exception:  # pragma: no cover
    LEGACY_LAB_PASSWORDS = {}

    def _cred_store(state):
        return {}

    def legacy_seed_enabled(state):
        return False


def _gather_users(state) -> List[Tuple[str, str, dict]]:
    """Return [(userid, des_hash_hex, attrs)] for the snapshot."""
    out: dict = {}
    # 1) any password material already recorded (set via ADDUSER/ALTUSER/PASSWORD)
    for uid, cred in (_cred_store(state) or {}).items():
        hx = cred.get("hash_hex") if isinstance(cred, dict) else getattr(cred, "hash_hex", "")
        if hx:
            out[uid.upper()] = (hx.upper(), {})
    # 2) the seeded legacy lab passwords (the intended crackable users)
    if legacy_seed_enabled(state):
        for uid, pw in LEGACY_LAB_PASSWORDS.items():
            out.setdefault(uid.upper(), (generate_legacy_racf_des_hash(uid, pw).upper(), {}))
    # 3) every current user; derive from cleartext where we have it
    for uid, user in (getattr(state.racf, "users", {}) or {}).items():
        u = uid.upper()
        attrs = {"default_group": getattr(user, "default_group", "SYS1"),
                 "name": getattr(user, "name", "") or "",
                 "special": bool(getattr(user, "special", False)),
                 "operations": bool(getattr(user, "operations", False))}
        if u in out:
            out[u] = (out[u][0], attrs)
            continue
        pw = getattr(user, "password", "") or ""
        # only treat as cleartext if short/plain (a sim stores cleartext for labs)
        if pw and not pw.startswith(("$", "*")) and len(pw) <= 8:
            out[u] = (generate_legacy_racf_des_hash(u, pw).upper(), attrs)
        else:
            out[u] = ("0000000000000000", attrs)  # password-protected / unknown
    return [(uid, hx, attrs) for uid, (hx, attrs) in sorted(out.items())]


def build_racfds_binary(state) -> bytes:
    """Build the binary RACF DB image from current Gibson RACF state."""
    img = RacfDbImage()
    for uid, hx, attrs in _gather_users(state):
        img.add_user(uid, hx, algorithm=ALG_DES,
                     default_group=attrs.get("default_group", "SYS1"),
                     name=attrs.get("name", ""),
                     special=attrs.get("special", False),
                     operations=attrs.get("operations", False))
    return img.to_bytes()


def _binary_path(state) -> str:
    root = getattr(state.config, "sim_root", None) or "/tmp"
    d = os.path.join(str(root), "racfds")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = "/tmp"
    return os.path.join(d, "SYS1.RACFDS.BACKUP")


def materialise_racfds_binary(state, *, trigger: str = "BACKUP",
                              src_ip: str = "", userid: str = "IBMUSER") -> Tuple[str, bytes]:
    """Produce the binary backup; write the file, catalogue it, log evidence.
    Returns (operator_message, raw_bytes)."""
    data = build_racfds_binary(state)
    path = _binary_path(state)
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except Exception:
        pass
    # store a base64 copy in the catalogued dataset; retrieval paths decode it
    try:
        state.datasets.write(userid, "SYS1.RACFDS.BACKUP", encode_for_dataset(data))
    except Exception:
        pass
    setattr(state, "racfds_backup_stale", False)
    n = len(_gather_users(state))
    try:
        state.record_security_event(
            src_ip or "INTERNAL", "RACFDS BACKUP",
            f"BINARY SYS1.RACFDS.BACKUP WRITTEN ({len(data)} bytes, {n} users) TRIGGER={trigger}",
            service="RACF", result="SUCCESS", addr=src_ip or "INTERNAL", terminal="BATCH")
    except Exception:
        pass
    try:
        from gibson.apps.cti_hms import trigger_ttp
        trigger_ttp(state, "racfds_john", src_ip=src_ip or "10.4.22.17", userid=userid,
                    detail=f"binary SYS1.RACFDS.BACKUP created ({n} users) via {trigger}")
    except Exception:
        pass
    msg = (f"IRRDBK00I SYS1.RACFDS.BACKUP CREATED - {len(data)} BYTES, "
           f"{n} USERS, FORMAT=BINARY (racf2john)")
    return msg, data


def verify_roundtrip(state) -> bool:
    """Build then parse the image, confirming users + hashes survive."""
    data = build_racfds_binary(state)
    built = {(u, h) for u, h, _ in _gather_users(state)}
    parsed = {(e.userid, e.password_hex) for e in _parse(data)}
    return built == parsed
