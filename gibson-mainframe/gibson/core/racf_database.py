from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import re

from gibson.core.security_mode import is_vuln_mode, is_secure_mode
from gibson.core.racf_legacy_des import (
    generate_legacy_racf_des_hash,
    format_john_racf_hash,
    crypto_available,
)
from gibson.core.smf.records.type80 import racf_event

LEGACY_LAB_PASSWORDS = {
    "FIREID1": "VIPER1",
    "FIREID2": "VIPER1",
    "DUMONT": "SWIM",
}

POLICY_PROTECTED = "protected"
POLICY_LEGACY_LAB = "legacy-lab"
POLICY_LEGACY_ALL = "legacy-all-vuln"


@dataclass
class RacfCredentialMaterial:
    userid: str
    algorithm: str
    hash_hex: str
    john_format: str
    created_by: str = "GIBSON"
    changed_at: str = ""
    source_command: str = ""
    crackable: bool = False
    simulator_only: bool = False
    crypto_provider: str = "REAL-DES"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm_user(userid: str) -> str:
    return (userid or "").strip().upper()[:8]


def _cred_store(state: Any) -> dict[str, dict[str, Any]]:
    store = getattr(state, "racfds_credentials", None)
    if not isinstance(store, dict):
        store = {}
        setattr(state, "racfds_credentials", store)
    return store


def _marked_store(state: Any) -> set[str]:
    marks = getattr(state, "racfds_legacy_marked", None)
    if not isinstance(marks, set):
        marks = set(marks or [])
        setattr(state, "racfds_legacy_marked", marks)
    return marks


def get_policy(state: Any) -> str:
    policy = str(getattr(state, "racfds_policy", "") or "").strip().lower()
    if policy in {POLICY_PROTECTED, POLICY_LEGACY_LAB, POLICY_LEGACY_ALL}:
        return policy
    if is_secure_mode(state):
        return POLICY_PROTECTED
    # Keep historical classroom behaviour: vulnerable mode exposes seeded lab
    # users, but only explicit LEGACY ALL makes every new password crackable.
    if is_vuln_mode(state) or bool(getattr(state, "racfds_legacy_seed", False)):
        return POLICY_LEGACY_LAB
    return POLICY_PROTECTED


def set_policy(state: Any, policy: str) -> str:
    p = (policy or "").strip().lower().replace("_", "-")
    aliases = {
        "protected": POLICY_PROTECTED,
        "secure": POLICY_PROTECTED,
        "legacy-lab": POLICY_LEGACY_LAB,
        "lab": POLICY_LEGACY_LAB,
        "legacy": POLICY_LEGACY_LAB,
        "legacy-all": POLICY_LEGACY_ALL,
        "legacy-all-vuln": POLICY_LEGACY_ALL,
        "all": POLICY_LEGACY_ALL,
    }
    if p not in aliases:
        raise ValueError("policy must be PROTECTED, LEGACY LAB or LEGACY ALL")
    setattr(state, "racfds_policy", aliases[p])
    materialise_racfds(state)
    return aliases[p]


def _provider_name(simulator_only: bool = False) -> str:
    if simulator_only:
        return "SIMULATOR"
    return "REAL-DES" if crypto_available() else "SIMULATOR"


def _hash_algorithm() -> tuple[str, bool, str]:
    if crypto_available():
        return "LEGACY-DES", False, "REAL-DES"
    return "LEGACY-DES-SIM", True, "SIMULATOR"


def _make_credential(userid: str, password: str, *, created_by: str = "GIBSON", source_command: str = "") -> dict[str, Any]:
    uid = _norm_user(userid)
    alg, sim_only, provider = _hash_algorithm()
    hx = generate_legacy_racf_des_hash(uid, password or "")
    mat = RacfCredentialMaterial(
        userid=uid,
        algorithm=alg,
        hash_hex=hx,
        john_format=format_john_racf_hash(uid, hx),
        created_by=(created_by or "GIBSON").upper(),
        changed_at=_now(),
        source_command=source_command or "PASSWORD-SET",
        crackable=True,
        simulator_only=sim_only,
        crypto_provider=provider,
    )
    return asdict(mat)


def should_legacy_for_password(state: Any, userid: str) -> bool:
    uid = _norm_user(userid)
    policy = get_policy(state)
    if policy == POLICY_PROTECTED:
        return False
    if policy == POLICY_LEGACY_ALL:
        return True
    if uid in LEGACY_LAB_PASSWORDS:
        return True
    if uid in _marked_store(state):
        return True
    return False


def record_password_material(state: Any, userid: str, plaintext: str | None, *, source_command: str = "PASSWORD-SET", actor: str = "IBMUSER") -> None:
    uid = _norm_user(userid)
    if not uid:
        return
    store = _cred_store(state)
    if plaintext and should_legacy_for_password(state, uid):
        store[uid] = _make_credential(uid, plaintext, created_by=actor, source_command=source_command)
    else:
        store.pop(uid, None)


def legacy_seed_enabled(state: Any) -> bool:
    return bool(getattr(state, "racfds_legacy_seed", False)) or is_vuln_mode(state) or get_policy(state) in {POLICY_LEGACY_LAB, POLICY_LEGACY_ALL}


def _user_line(state: Any, userid: str, plaintext: str | None = None, *, source_command: str = "") -> str:
    uid = _norm_user(userid)
    rec = state.racf.get(uid)
    dflt = getattr(rec, "default_group", "SYS1") if rec else "SYS1"
    attrs = ",".join(sorted(getattr(rec, "attributes", []) or [])) or "NONE"
    omvs = "YES" if getattr(rec, "omvs", "NOOMVS") == "OMVS" or getattr(rec, "has_omvs", False) else "NO"
    store = _cred_store(state)
    if plaintext is not None:
        record_password_material(state, uid, plaintext, source_command=source_command or "PASSWORD-SET")
    if uid in store:
        mat = store[uid]
        alg = str(mat.get("algorithm", "LEGACY-DES"))
        hx = str(mat.get("hash_hex", "*UNKNOWN*"))
        provider = str(mat.get("crypto_provider", _provider_name()))
        john = "YES" if provider == "REAL-DES" and alg == "LEGACY-DES" else "SIM-ONLY"
        return f"USER USERID={uid} DFLTGRP={dflt} ATTR={attrs} OMVS={omvs} ALG={alg} HASH={hx} JOHN={john} PROVIDER={provider}"
    # Deterministic vulnerable seed users are generated on demand.
    if legacy_seed_enabled(state) and uid in LEGACY_LAB_PASSWORDS:
        store[uid] = _make_credential(uid, LEGACY_LAB_PASSWORDS[uid], created_by="GIBSON", source_command="RACFDB-SEED")
        return _user_line(state, uid)
    return f"USER USERID={uid} DFLTGRP={dflt} ATTR={attrs} OMVS={omvs} ALG=KDFAES HASH=*PROTECTED* JOHN=NO PROVIDER=PROTECTED"


def _write_system_dataset(state: Any, dsname: str, text: str) -> None:
    try:
        state.datasets.write("IBMUSER", dsname, text)
        return
    except Exception:
        pass
    try:
        p = state.datasets.ds_path("IBMUSER", dsname)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            # SYS1.RACFDS is catalogued as a PDS in older Gibson packages.
            p = p / "DATABASE"
        p.write_text(text, encoding="utf-8")
        base = p.parent if "(" in dsname else p
        try:
            state.datasets._write_meta(base, org="PO" if p.name == "DATABASE" else "PS", volume="SBSYS1", owner="IBMUSER", recfm="VB", lrecl=4096)
        except Exception:
            pass
    except Exception:
        pass


def materialise_racfds(state: Any, *, changed_user: str = "", plaintext_password: str | None = None, source_command: str = "") -> str:
    """Write SYS1.RACFDS from current Gibson RACF state."""
    changed = _norm_user(changed_user)
    if changed and plaintext_password is not None:
        record_password_material(state, changed, plaintext_password, source_command=source_command or "PASSWORD-SET")
        setattr(state, "racfds_backup_stale", True)
    lines = [
        "RDBU HEADER SYSTEM=GIBSON1 DATABASE=SYS1.RACFDS VERSION=GIBSON-RACFDS-2",
        f"RDBU GENERATED={_now()} MODE={'VULN' if is_vuln_mode(state) else 'SECURE' if is_secure_mode(state) else 'TRAINING'} POLICY={get_policy(state).upper()} CRYPTO={'YES' if crypto_available() else 'NO'}",
    ]
    seen = set()
    for uid in sorted(getattr(state.racf, "users", {})):
        pw = plaintext_password if uid == changed else None
        lines.append(_user_line(state, uid, pw, source_command=source_command))
        seen.add(uid)
    if legacy_seed_enabled(state):
        for uid in sorted(LEGACY_LAB_PASSWORDS):
            if uid not in seen:
                lines.append(_user_line(state, uid))
                seen.add(uid)
    groups = getattr(getattr(state, "dynamic_racf", None), "groups", {}) or {}
    for g, data in sorted(groups.items()):
        lines.append(f"GRP GROUP={g.upper()} OWNER=IBMUSER SUPGROUP=SYS1")
        for u in sorted(getattr(data, "users", {}) or []):
            lines.append(f"CONN USERID={u.upper()} GROUP={g.upper()} AUTH=USE")
    lines.extend([
        "DATA PROFILE=SYS1.RACFDS UACC=NONE OWNER=IBMUSER AUDIT=ALL(READ)",
        "DATA PROFILE=SYS1.RACFDS.BACKUP UACC=NONE OWNER=IBMUSER AUDIT=ALL(READ)",
        "DATA PROFILE=SYS1.MAN* UACC=NONE OWNER=IBMUSER AUDIT=ALL(READ UPDATE)",
        "GENR CLASS=PTKTDATA PROFILE=TSO UACC=NONE OWNER=IBMUSER",
    ])
    text = "\n".join(lines) + "\n"
    _write_system_dataset(state, "SYS1.RACFDS(DATABASE)", text)
    # If the catalog has SYS1.RACFDS as a sequential file in a future package,
    # this writes it. If it is a PDS, the helper safely leaves DATABASE current.
    _write_system_dataset(state, "SYS1.RACFDS", text)
    return text


def backup_racfds(state: Any) -> str:
    # Produce a real binary SYS1.RACFDS.BACKUP (the racf2john-crackable image),
    # not a text copy. The primary SYS1.RACFDS(DATABASE) stays text for the
    # in-sim tooling; the .BACKUP is the binary you FTP/cp off and crack.
    # We also refresh the realistic IRRDBU00 database unload (the RACFHound /
    # pyracf input) so a single BACKUP yields both the crackable image and the
    # parseable unload with profiles, access lists, SURROGAT, etc.
    try:
        unload_msg = export_irrdbu00_full(state)
        unload_tail = "\n" + unload_msg.splitlines()[1]  # RECORDS=... (counts) line
    except Exception:
        unload_tail = ""
    try:
        from gibson.core.racf_db_binary import materialise_racfds_binary
        msg, _data = materialise_racfds_binary(state, trigger="BACKUP")
        setattr(state, "racfds_backup_at", _now())
        return msg + unload_tail
    except Exception as exc:  # pragma: no cover - fall back to text copy
        text = state.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
        _write_system_dataset(state, "SYS1.RACFDS.BACKUP", text)
        setattr(state, "racfds_backup_stale", False)
        setattr(state, "racfds_backup_at", _now())
        return f"IRRDBK00I SYS1.RACFDS.BACKUP UPDATED FROM SYS1.RACFDS (text fallback: {exc})" + unload_tail


def _counts(text: str) -> tuple[int, int, int, int]:
    users = sum(1 for l in text.splitlines() if l.startswith("USER "))
    legacy = sum(1 for l in text.splitlines() if "ALG=LEGACY-DES" in l)
    sim = sum(1 for l in text.splitlines() if "ALG=LEGACY-DES-SIM" in l)
    kdfa = sum(1 for l in text.splitlines() if "ALG=KDFAES" in l or "*PROTECTED*" in l)
    return users, legacy, sim, kdfa


def status(state: Any) -> str:
    materialise_racfds(state)
    text = state.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
    users, legacy, sim, kdfa = _counts(text)
    try:
        btxt = state.datasets.read("IBMUSER", "SYS1.RACFDS.BACKUP")
        from gibson.core.racf_db_binary import decode_from_dataset
        raw = decode_from_dataset(btxt)
        if raw is not None:
            from gibson.core.racf_db_image import parse as _parse_img
            busers = len(_parse_img(raw))
            blegacy = bsim = 0
            backup_fmt = "BINARY"
        else:
            busers, blegacy, bsim, _ = _counts(btxt)
            backup_fmt = "TEXT"
    except Exception:
        busers = blegacy = bsim = 0
        backup_fmt = "NONE"
    stale = bool(getattr(state, "racfds_backup_stale", False))
    return "\n".join([
        "RACFDB STATUS",
        f"PRIMARY  SYS1.RACFDS        USERS={users} LEGACY-DES={legacy + sim} KDFAES={kdfa}",
        f"BACKUP   SYS1.RACFDS.BACKUP USERS={busers} FORMAT={backup_fmt} STALE={'YES' if stale else 'NO'}",
        f"POLICY   {get_policy(state).upper()}",
        f"LEGACY-DES RECORDS          {legacy + sim}",
        f"REAL-DES RECORDS            {legacy}",
        f"SIMULATOR-DES RECORDS       {sim}",
        f"KDFAES/PROTECTED RECORDS    {kdfa}",
        f"JOHN-COMPATIBLE EXPORT      {'YES' if legacy else 'NO'}",
        f"SIMULATOR-ONLY EXPORT       {'YES' if sim else 'NO'}",
        f"LAST SYNC                   {_now()}",
    ])


def export_irradu00(state: Any, outdsn: str = "IBMUSER.IRRADU00.UNLOAD") -> str:
    """IRRADU00 - unload RACF SMF type-80/81/83 audit records to a flat file.

    Distinct from IRRDBU00 (which unloads the RACF *database*): IRRADU00 unloads
    the *audit trail* SMF cut by RACF, the data auditors and SIEM pipelines
    consume. Here it reads Gibson's recorded SMF-80 security events and writes
    the documented record-type layout (ACCESS / SETROPTS / DEFINE / ...).
    """
    host = str(getattr(getattr(state, "network", None), "hostname", "GIBSON") or "GIBSON").upper()
    audit = getattr(state, "audit", None)
    events = list(getattr(audit, "events", []) or []) if audit else []
    # Map a Gibson audit event to an IRRADU00 event type + numeric record type.
    def _evtype(ev_name: str) -> tuple[str, str]:
        e = (ev_name or "").upper()
        if "LOGON" in e or "JOB" in e or "INIT" in e:
            return ("JOBINIT", "ACCESS")
        if "SETROPTS" in e:
            return ("ACCESS", "SETROPTS")
        if any(k in e for k in ("PERMIT", "RDEFINE", "RALTER", "ADDSD", "ALTDSD", "DELDSD", "PROFILE", "DEFINE")):
            return ("DEFINE", "RACINIT")
        if "DATASET" in e or "ACCESS" in e:
            return ("ACCESS", "DSACC")
        return ("ACCESS", "GENERAL")
    rows = [
        "** IRRADU00 RACF SMF DATA UNLOAD UTILITY - GIBSON SIMULATION **",
        "** RECORD TYPES: ACCESS(80) JOBINIT(80-1) DEFINE(80) COMMAND(80) **",
        "EVENTTYPE QUAL USERID   --DATE-- --TIME-- SYSTEM   RESULT   RESOURCE/DETAIL",
    ]
    n = 0
    for ev in events:
        try:
            r = audit.smf80_row(ev, system=host)
        except Exception:
            continue
        etype, qual = _evtype(r.get("EVENT", ""))
        res = (r.get("RESULT", "") or "").upper()[:8] or "SUCCESS"
        detail = (r.get("RESOURCE") or r.get("PROFILE") or r.get("DETAIL") or r.get("EVENT") or "")[:40]
        rows.append(
            f"{etype:<9} {qual:<4} {r.get('USERID',''):<8} {r.get('DATE',''):<8} "
            f"{r.get('TIME',''):<8} {host:<8} {res:<8} {detail}"
        )
        n += 1
    if n == 0:
        rows.append("(no SMF type-80 audit records have been cut yet - run some "
                    "security-relevant commands first, e.g. LOGON, PERMIT, SETROPTS)")
    try:
        state.datasets.write("IBMUSER", outdsn, "\n".join(rows) + "\n")
    except Exception:
        pass
    return (f"IRRADU00I RACF SMF AUDIT UNLOAD WRITTEN TO {outdsn.upper()}\n"
            f"AUDIT RECORDS UNLOADED={n}\n"
            f"SOURCE=SMF TYPE 80 (RACF PROCESSING RECORDS)")


# ===========================================================================
# Realistic IRRDBU00 database unload - RACFHound / pyracf / mfpandas compatible
#
# pyracf parses each line as: record-type = line[:4]; each field =
# line[start-1:end].strip(), using 1-based inclusive columns from IBM's
# IRRDBU00 record-format spec (icha300/format.htm). We emit the same fixed
# positions so the unload parses byte-for-byte into pyracf DataFrames (and so
# RACFHound can turn it into a BloodHound graph) without needing a real RACF DB.
# Columns below are the exact (start, end) from that spec for the record types
# RACFHound consumes. Password/phrase hash material is never emitted.
# ===========================================================================

_IRR_LAYOUT: dict[str, dict[str, tuple[int, int]]] = {
    "0100": {  # group basic data (GPBD)
        "GPBD_NAME": (6, 13), "GPBD_SUPGRP_ID": (15, 22), "GPBD_CREATE_DATE": (24, 33),
        "GPBD_OWNER_ID": (35, 42), "GPBD_UACC": (44, 51), "GPBD_NOTERMUACC": (53, 56),
        "GPBD_UNIVERSAL": (359, 362)},
    "0102": {  # group members (GPMEM) - carries connect (group) authority
        "GPMEM_NAME": (6, 13), "GPMEM_MEMBER_ID": (15, 22), "GPMEM_AUTH": (24, 31)},
    "0200": {  # user basic data (USBD)
        "USBD_NAME": (6, 13), "USBD_CREATE_DATE": (15, 24), "USBD_OWNER_ID": (26, 33),
        "USBD_ADSP": (35, 38), "USBD_SPECIAL": (40, 43), "USBD_OPER": (45, 48),
        "USBD_REVOKE": (50, 53), "USBD_GRPACC": (55, 58), "USBD_PWD_INTERVAL": (60, 62),
        "USBD_PWD_DATE": (64, 73), "USBD_PROGRAMMER": (75, 94), "USBD_DEFGRP_ID": (96, 103),
        "USBD_LASTJOB_DATE": (114, 123), "USBD_UAUDIT": (381, 384), "USBD_AUDITOR": (386, 389)},
    "0205": {  # user connect data (USCON)
        "USCON_NAME": (6, 13), "USCON_GRP_ID": (15, 22), "USCON_CONNECT_DATE": (24, 33),
        "USCON_OWNER_ID": (35, 42), "USCON_UACC": (64, 71), "USCON_GRP_ADSP": (79, 82),
        "USCON_GRP_SPECIAL": (84, 87), "USCON_GRP_OPER": (89, 92), "USCON_REVOKE": (94, 97),
        "USCON_GRP_ACC": (99, 102), "USCON_GRP_AUDIT": (109, 112)},
    "0270": {  # user OMVS data (USOMVS) - UID(0) superuser detection
        "USOMVS_NAME": (6, 13), "USOMVS_UID": (15, 24), "USOMVS_HOME_PATH": (26, 1048)},
    "0400": {  # dataset basic data (DSBD)
        "DSBD_NAME": (6, 49), "DSBD_VOL": (51, 56), "DSBD_GENERIC": (58, 61),
        "DSBD_CREATE_DATE": (63, 72), "DSBD_OWNER_ID": (74, 81), "DSBD_UACC": (129, 136)},
    "0404": {  # dataset access (DSACC)
        "DSACC_NAME": (6, 49), "DSACC_VOL": (51, 56), "DSACC_AUTH_ID": (58, 65),
        "DSACC_ACCESS": (67, 74), "DSACC_ACCESS_CNT": (76, 80)},
    "0500": {  # general resource basic data (GRBD)
        "GRBD_NAME": (6, 251), "GRBD_CLASS_NAME": (253, 260), "GRBD_GENERIC": (262, 265),
        "GRBD_CREATE_DATE": (271, 280), "GRBD_OWNER_ID": (282, 289), "GRBD_UACC": (337, 344)},
    "0505": {  # general resource access (GRACC)
        "GRACC_NAME": (6, 251), "GRACC_CLASS_NAME": (253, 260), "GRACC_AUTH_ID": (262, 269),
        "GRACC_ACCESS": (271, 278), "GRACC_ACCESS_CNT": (280, 284)},
}

_IRR_SEED_DATE = "2024-01-15"


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


def _irr_line(rt: str, values: dict[str, str]) -> str:
    """Render one IRRDBU00 record at fixed columns (record type in cols 1-4)."""
    layout = _IRR_LAYOUT[rt]
    ends = [4] + [layout[k][1] for k, v in values.items()
                  if k in layout and v not in (None, "")]
    buf = [" "] * max(ends)
    for i, ch in enumerate(rt[:4]):
        buf[i] = ch
    for k, v in values.items():
        if k not in layout or v in (None, ""):
            continue
        start, end = layout[k]
        for i, ch in enumerate(str(v)[:end - start + 1]):
            buf[start - 1 + i] = ch
    return "".join(buf).rstrip()


def _seed_realistic_racf(store: Any) -> None:
    """Plant realistic, RACFHound-interesting attack-path objects (idempotent).

    Everything here is synthetic training data on the simulated database; it
    gives the auditing tool genuine escalation paths to surface on a demo:
    SURROGAT submit-as, FACILITY BPX.SUPERUSER, UNIXPRIV, APF/PARMLIB and RACF
    DB dataset exposure, a UID(0) OMVS user, and a group-SPECIAL connect.
    """
    if getattr(store, "_irr_seeded", False):
        return
    store._irr_seeded = True
    store._irr_connect_auth = getattr(store, "_irr_connect_auth", {})
    store._irr_group_priv = getattr(store, "_irr_group_priv", {})

    # Nested groups under SYS1 with members.
    for g in ("PAYROLL", "DEVOPS"):
        store.groups.setdefault(g, set())
    store.groups["DEVOPS"].add("TRAINEE")
    store.groups["PAYROLL"].add("FIBSUSR")
    # A UID(0) OMVS user - direct UNIX superuser (classic finding).
    store.users.setdefault("OMVSROOT", {
        "USERID": "OMVSROOT", "NAME": "UNIX SUPERUSER", "DFLTGRP": "DEVOPS",
        "ATTRS": set(), "OMVS": {"UID": "0"}, "TSO": {}, "CICS": {},
        "MFA": {"ENABLED": "N"}, "REVOKED": "N"})
    store.groups["DEVOPS"].add("OMVSROOT")
    # Group-SPECIAL connect: TRAINEE is SPECIAL within DEVOPS (scoped escalation).
    store._irr_group_priv[("DEVOPS", "TRAINEE")] = {"SPECIAL": True}
    store._irr_connect_auth[("DEVOPS", "TRAINEE")] = "JOIN"
    store._irr_connect_auth[("FIBS", "FIBSADM")] = "JOIN"

    def _prof(cls, name, uacc, permits):
        store.profiles.setdefault(cls, {})
        store.profiles[cls].setdefault(name, {"UACC": uacc, "PERMITS": dict(permits)})

    # UNIX privilege escalation paths.
    _prof("FACILITY", "BPX.SUPERUSER", "NONE", {"TRAINEE": "READ"})
    _prof("FACILITY", "BPX.DAEMON", "NONE", {"FIBSUSR": "READ"})
    _prof("UNIXPRIV", "SUPERUSER.FILESYS", "NONE", {"TRAINEE": "UPDATE"})
    # Submit-as impersonation: anyone with READ can submit jobs AS IBMUSER.
    _prof("SURROGAT", "IBMUSER.SUBMIT", "NONE", {"FIBSUSR": "READ"})
    # APF / PARMLIB / system library tamper paths (privilege escalation).
    _prof("DATASET", "SYS1.PARMLIB", "NONE", {"TRAINEE": "UPDATE"})
    _prof("DATASET", "SYS1.LINKLIB", "NONE", {"FIBSUSR": "ALTER"})
    # Read access to the RACF database itself.
    _prof("DATASET", "SYS1.RACFDS.**", "NONE", {"TRAINEE": "READ"})
    # A started-task profile (common in real unloads).
    _prof("STARTED", "JES2.*", "NONE", {})


def _irr_group_superior(store: Any, group: str) -> str:
    if group == "SYS1":
        return "SYS1"
    return "SYS1"


def export_irrdbu00_full(state: Any, outdsn: str = "IBMUSER.IRRDBU00.UNLOAD") -> str:
    """Render a realistic, RACFHound/pyracf-parseable IRRDBU00 database unload
    from Gibson's live RACF model (users, groups, connects, dataset and general
    resource profiles with their access lists). No password/phrase hashes."""
    from gibson.apps.racf_admin import get_racf_store
    store = get_racf_store(state)
    _seed_realistic_racf(store)
    date = _IRR_SEED_DATE
    cauth = getattr(store, "_irr_connect_auth", {})
    gpriv = getattr(store, "_irr_group_priv", {})
    rows: list[str] = []

    # Groups (0100) + members/connect-authority (0102).
    for g in sorted(store.groups):
        rows.append(_irr_line("0100", {
            "GPBD_NAME": g, "GPBD_SUPGRP_ID": _irr_group_superior(store, g),
            "GPBD_CREATE_DATE": date, "GPBD_OWNER_ID": "IBMUSER",
            "GPBD_UACC": "NONE", "GPBD_NOTERMUACC": "No", "GPBD_UNIVERSAL": "No"}))
        for m in sorted(store.groups[g]):
            rows.append(_irr_line("0102", {
                "GPMEM_NAME": g, "GPMEM_MEMBER_ID": m,
                "GPMEM_AUTH": cauth.get((g, m), "USE")}))

    # Users (0200) + connects (0205) + OMVS (0270).
    for uid in sorted(store.users):
        u = store.users[uid]
        attrs = u.get("ATTRS", set()) or set()
        dflt = (u.get("DFLTGRP") or "SYS1").upper()
        revoked = str(u.get("REVOKED", "N")).upper() in ("Y", "YES", "TRUE")
        rows.append(_irr_line("0200", {
            "USBD_NAME": uid, "USBD_CREATE_DATE": date, "USBD_OWNER_ID": dflt,
            "USBD_ADSP": "No", "USBD_SPECIAL": _yn("SPECIAL" in attrs),
            "USBD_OPER": _yn("OPERATIONS" in attrs), "USBD_AUDITOR": _yn("AUDITOR" in attrs),
            "USBD_REVOKE": _yn(revoked), "USBD_GRPACC": "No", "USBD_PWD_INTERVAL": "030",
            "USBD_PWD_DATE": date, "USBD_PROGRAMMER": str(u.get("NAME", uid) or uid)[:20],
            "USBD_DEFGRP_ID": dflt, "USBD_LASTJOB_DATE": date}))
        member_of = {g for g in store.groups if uid in store.groups[g]}
        member_of.add(dflt)
        for g in sorted(member_of):
            priv = gpriv.get((g, uid), {})
            rows.append(_irr_line("0205", {
                "USCON_NAME": uid, "USCON_GRP_ID": g, "USCON_CONNECT_DATE": date,
                "USCON_OWNER_ID": "IBMUSER", "USCON_UACC": "NONE", "USCON_GRP_ADSP": "No",
                "USCON_GRP_SPECIAL": _yn(priv.get("SPECIAL", False)),
                "USCON_GRP_OPER": _yn(priv.get("OPER", False)),
                "USCON_GRP_AUDIT": _yn(priv.get("AUDITOR", False)),
                "USCON_REVOKE": _yn(revoked), "USCON_GRP_ACC": "No"}))
        omvs_uid = str((u.get("OMVS") or {}).get("UID", "") or "")
        if omvs_uid != "":
            rows.append(_irr_line("0270", {
                "USOMVS_NAME": uid, "USOMVS_UID": omvs_uid,
                "USOMVS_HOME_PATH": f"/u/{uid.lower()}"}))

    # Dataset profiles (0400) + access lists (0404).
    for prof in sorted(store.profiles.get("DATASET", {})):
        info = store.profiles["DATASET"][prof]
        generic = "Yes" if ("*" in prof or "%" in prof) else "No"
        rows.append(_irr_line("0400", {
            "DSBD_NAME": prof, "DSBD_GENERIC": generic, "DSBD_CREATE_DATE": date,
            "DSBD_OWNER_ID": "IBMUSER", "DSBD_UACC": str(info.get("UACC", "NONE")).upper()}))
        for authid, acc in sorted((info.get("PERMITS") or {}).items()):
            rows.append(_irr_line("0404", {
                "DSACC_NAME": prof, "DSACC_AUTH_ID": authid,
                "DSACC_ACCESS": str(acc).upper(), "DSACC_ACCESS_CNT": "0"}))

    # General resource profiles (0500) + access lists (0505), every non-DATASET class.
    for cls in sorted(c for c in store.profiles if c != "DATASET"):
        for prof in sorted(store.profiles[cls]):
            info = store.profiles[cls][prof]
            generic = "Yes" if ("*" in prof or "%" in prof) else "No"
            rows.append(_irr_line("0500", {
                "GRBD_NAME": prof, "GRBD_CLASS_NAME": cls, "GRBD_GENERIC": generic,
                "GRBD_CREATE_DATE": date, "GRBD_OWNER_ID": "IBMUSER",
                "GRBD_UACC": str(info.get("UACC", "NONE")).upper()}))
            for authid, acc in sorted((info.get("PERMITS") or {}).items()):
                rows.append(_irr_line("0505", {
                    "GRACC_NAME": prof, "GRACC_CLASS_NAME": cls, "GRACC_AUTH_ID": authid,
                    "GRACC_ACCESS": str(acc).upper(), "GRACC_ACCESS_CNT": "0"}))

    state.datasets.write("IBMUSER", outdsn, "\n".join(rows) + "\n")
    from collections import Counter
    counts = Counter(r[:4] for r in rows)
    summary = " ".join(f"{k}:{counts[k]}" for k in sorted(counts))
    return (f"IRRDBU00I RACF DATABASE UNLOAD WRITTEN TO {outdsn.upper()}\n"
            f"RECORDS={len(rows)} ({summary})\n"
            f"PASSWORD HASH MATERIAL SUPPRESSED")


def export_irrdbu00(state: Any, outdsn: str = "IBMUSER.IRRDBU00.UNLOAD") -> str:
    # Full RACFHound/pyracf-compatible unload (record types 0100/0102/0200/0205/
    # 0270/0400/0404/0500/0505) rendered from Gibson's live RACF model.
    return export_irrdbu00_full(state, outdsn)


def seed_legacy(state: Any) -> str:
    setattr(state, "racfds_legacy_seed", True)
    # Keep policy legacy-lab unless instructor explicitly chose legacy-all.
    if get_policy(state) == POLICY_PROTECTED:
        setattr(state, "racfds_policy", POLICY_LEGACY_LAB)
    store = _cred_store(state)
    for uid, pw in LEGACY_LAB_PASSWORDS.items():
        store[uid] = _make_credential(uid, pw, created_by="GIBSON", source_command="RACFDB-SEED")
    materialise_racfds(state)
    setattr(state, "racfds_backup_stale", True)
    return "IRRDBS01I LEGACY-DES RACF HASH LAB USERS SEEDED: " + ",".join(sorted(LEGACY_LAB_PASSWORDS)) + "\n" + status(state)


def verify_hashes(state: Any) -> str:
    materialise_racfds(state)
    text = state.datasets.read("IBMUSER", "SYS1.RACFDS(DATABASE)")
    legacy=[]; sim=[]; protected=0
    for line in text.splitlines():
        if not line.startswith('USER '):
            continue
        m=re.search(r'USERID=([^\s]+)', line)
        uid=m.group(1) if m else 'UNKNOWN'
        if 'ALG=LEGACY-DES-SIM' in line:
            sim.append(uid)
        elif 'ALG=LEGACY-DES' in line:
            legacy.append(uid)
        else:
            protected += 1
    return "\n".join([
        "RACFDB VERIFY HASHES",
        "POLICY: " + get_policy(state).upper(),
        "LEGACY-DES USERS: " + (",".join(sorted(legacy)) if legacy else "NONE"),
        "SIMULATOR-DES USERS: " + (",".join(sorted(sim)) if sim else "NONE"),
        "JOHN-COMPATIBLE EXPORT: " + ("YES" if (legacy or sim) else "NO"),
        "REAL-JOHN-COMPATIBLE EXPORT: " + ("YES" if legacy else "NO"),
        "SIMULATOR-ONLY EXPORT: " + ("YES" if sim else "NO"),
        f"KDFAES/PROTECTED USERS: {protected}",
        "BACKUP STATUS: " + ("STALE" if bool(getattr(state, "racfds_backup_stale", False)) else "CURRENT"),
    ])


def export_john(state: Any, outdsn: str = "IBMUSER.RACF.HASHES") -> str:
    from gibson.tools.racf2john_sim import extract_hashes
    return extract_hashes(state, "IBMUSER", "SYS1.RACFDS", outdsn)


def _policy_command(state: Any, parts: list[str]) -> str:
    if len(parts) == 2:
        return "\n".join([
            "RACFDB POLICY",
            f"RACFDS POLICY ===> {get_policy(state).upper()}",
            f"SECURE MODE    ===> {'YES' if is_secure_mode(state) else 'NO'}",
            f"VULN MODE      ===> {'YES' if is_vuln_mode(state) else 'NO'}",
            f"NEW PASSWORDS  ===> {'LEGACY-DES' if get_policy(state)==POLICY_LEGACY_ALL else 'KDFAES/PROTECTED OR MARKED LAB'}",
            "UNKNOWN HASHES ===> KDFAES/PROTECTED",
        ])
    p = " ".join(parts[2:]).replace("-", " ").upper()
    if p in {"PROTECTED", "SECURE"}:
        newp = set_policy(state, POLICY_PROTECTED)
    elif p in {"LEGACY LAB", "LAB", "LEGACY"}:
        newp = set_policy(state, POLICY_LEGACY_LAB)
    elif p in {"LEGACY ALL", "ALL", "LEGACY ALL VULN"}:
        newp = set_policy(state, POLICY_LEGACY_ALL)
    else:
        return "RACFDB POLICY SYNTAX: RACFDB POLICY [PROTECTED|LEGACY LAB|LEGACY ALL]"
    return f"IRRDBP00I RACFDS POLICY SET TO {newp.upper()}\n" + status(state)


def racfdb_command(state: Any, userid: str, cmd: str) -> str | None:
    u = (cmd or "").strip().upper()
    if not (u == "RACFDB" or u.startswith("RACFDB ") or u.startswith("IRRDBU00") or u.startswith("IRRADU00")):
        return None
    if u.startswith("IRRADU00"):
        m = re.search(r"OUTDATASET\(([^)]*)\)", cmd, re.I)
        return export_irradu00(state, m.group(1).strip() if m else "IBMUSER.IRRADU00.UNLOAD")
    if u.startswith("IRRDBU00"):
        m = re.search(r"OUTDATASET\(([^)]*)\)", cmd, re.I)
        return export_irrdbu00(state, m.group(1).strip() if m else "IBMUSER.IRRDBU00.UNLOAD")
    parts = u.split()
    op = parts[1] if len(parts) > 1 else "STATUS"
    if op == "POLICY":
        return _policy_command(state, parts)
    if op == "MARK" and len(parts) >= 4:
        uid = _norm_user(parts[3])
        if parts[2] == "LEGACY":
            _marked_store(state).add(uid)
            materialise_racfds(state)
            return f"IRRDBM00I USER {uid} MARKED FOR LEGACY-DES AT NEXT PASSWORD SET\n" + verify_hashes(state)
        if parts[2] == "PROTECTED":
            _marked_store(state).discard(uid)
            _cred_store(state).pop(uid, None)
            materialise_racfds(state)
            return f"IRRDBM01I USER {uid} MARKED PROTECTED IN SYS1.RACFDS\n" + verify_hashes(state)
    if op in {"STATUS", "LIST"}:
        return status(state)
    if op == "SEED" and len(parts) > 2 and parts[2] == "LEGACY":
        return seed_legacy(state)
    if op == "VERIFY" and "HASHES" in u:
        return verify_hashes(state)
    if op == "SYNC":
        materialise_racfds(state)
        return "IRRDBS00I SYS1.RACFDS SYNCHRONISED FROM GACF.DB AND DYNAMIC RACF STATE\n" + status(state)
    if op == "BACKUP":
        return backup_racfds(state)
    if op == "VERIFY":
        materialise_racfds(state)
        return "IRRDBV00I SYS1.RACFDS VERIFY COMPLETE - SIMULATED DATABASE CONSISTENT"
    if op == "EXPORT" and "JOHN" in u:
        target = parts[-1] if len(parts) > 2 and parts[-1] not in {"EXPORT","JOHN"} else "IBMUSER.RACF.HASHES"
        return export_john(state, target)
    if op == "EXPORT" and "IRRDBU00" in u:
        return export_irrdbu00(state)
    return "RACFDB COMMANDS: STATUS, POLICY, MARK LEGACY <userid>, MARK PROTECTED <userid>, SYNC, SEED LEGACY, BACKUP, VERIFY, VERIFY HASHES, EXPORT IRRDBU00, EXPORT JOHN <DSN>"
