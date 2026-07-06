from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import base64, hashlib, hmac, json, os, re, secrets
from typing import Dict, List, Optional, Tuple


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')

@dataclass
class PasswordPolicy:
    algorithm: str = "MD5"
    minlength: int = 8
    history: int = 5
    revoke: int = 5
    interval: int = 90
    mixedcase: bool = False
    specialchars: bool = False
    # When False (default), ADDUSER/ALTUSER do NOT force a password change on
    # first logon - the user logs on directly with the password that was set.
    initial_password_change: bool = False
    newuser_change: bool = True
    mfa_active: bool = False
    mlactive: bool = False
    mfa_policy: str = "USER-CONTROLLED"
    inactive_days: int = 0
    pending_refresh: bool = False
    classact: List[str] = field(default_factory=lambda: ["DATASET", "FACILITY", "OPERCMDS", "JESSPOOL", "SURROGAT", "TCICSTRN", "CCICSCMD", "FCICSFCT", "PCICSPSB"])
    raclist: List[str] = field(default_factory=lambda: ["FACILITY", "OPERCMDS", "TCICSTRN", "CCICSCMD"])
    generic: List[str] = field(default_factory=lambda: ["DATASET", "FACILITY", "OPERCMDS"])
    audit: List[str] = field(default_factory=lambda: ["DATASET", "USER"])
    warning: bool = False
    last_updated: str = field(default_factory=_now)
    last_updated_by: str = "SYSTEM"
    rules: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "PasswordPolicy":
        defaults = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                kwargs = {}
                for k in cls.__dataclass_fields__:
                    kwargs[k] = data.get(k, getattr(defaults, k))
                # v30.287 accidentally defaulted mixedcase to True.  If the field is
                # absent, keep the corrected inactive default.  If the operator has
                # explicitly enabled it in saved state, honour that saved value.
                if "mixedcase" not in data:
                    kwargs["mixedcase"] = False
                return cls(**kwargs)
            except Exception:
                pass
        return defaults

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding='utf-8')

    @staticmethod
    def help_text(topic: str = "SETROPTS") -> str:
        t = (topic or "SETROPTS").upper()
        if "PASSWORD" in t:
            return "\n".join([
                "SETROPTS PASSWORD HELP",
                "  Syntax:",
                "    SETROPTS PASSWORD(ALGORITHM(KDFAES|DES|NONE))",
                "    SETROPTS PASSWORD(MINLENGTH(n))",
                "    SETROPTS PASSWORD(HISTORY(n))",
                "    SETROPTS PASSWORD(REVOKE(n))",
                "    SETROPTS PASSWORD(INTERVAL(n))",
                "    SETROPTS PASSWORD(MIXEDCASE|NOMIXEDCASE)",
                "    SETROPTS PASSWORD(SPECIALCHARS|NOSPECIALCHARS)",
                "    SETROPTS PASSWORD(RULE1(...)) | SETROPTS PASSWORD(NORULE1)",
                "  Examples:",
                "    SETROPTS PASSWORD(ALGORITHM(KDFAES))",
                "    SETROPTS PASSWORD(MINLENGTH(12))",
                "    SETROPTS PASSWORD(NOMIXEDCASE)",
                "    SETROPTS LIST",
                "  Gibson note: this is a training simulation of RACF SETROPTS.",
            ])
        return "\n".join([
            "SETROPTS HELP",
            "  Display:",
            "    SETROPTS LIST",
            "  Password policy:",
            "    SETROPTS PASSWORD(ALGORITHM(KDFAES|DES|NONE))",
            "    SETROPTS PASSWORD(MINLENGTH(n)|HISTORY(n)|REVOKE(n)|INTERVAL(n))",
            "    SETROPTS PASSWORD(MIXEDCASE|NOMIXEDCASE|SPECIALCHARS|NOSPECIALCHARS)",
            "  Class and profile processing:",
            "    SETROPTS CLASSACT(class-list) | NOCLASSACT(class-list)",
            "    SETROPTS RACLIST(class-list) | NORACLIST(class-list)",
            "    SETROPTS RACLIST(class-list) REFRESH",
            "    SETROPTS GENERIC(class-list) | NOGENERIC(class-list)",
            "    SETROPTS REFRESH",
            "  MFA:",
            "    SETROPTS MFA | NOMFA | MLACTIVE | NOMLACTIVE",
            "  Audit/warning simulation:",
            "    SETROPTS AUDIT(class-list) | NOAUDIT(class-list)",
            "    SETROPTS WARNING | NOWARNING",
        ])

    def _fmt_list(self, title: str, values: List[str]) -> List[str]:
        vals = sorted({str(v).upper() for v in values})
        return [f"  {v:<16}: ACTIVE" for v in vals] if vals else ["  NONE            : ACTIVE"]

    def list_lines(self) -> List[str]:
        lines: List[str] = [
            "ICH31005I SETROPTS LIST",
            "",
            "RACF OPTIONS",
            "  RACF MODE        : SECURE",
            f"  GENERIC DATASET  : {'ACTIVE' if 'DATASET' in {x.upper() for x in self.generic} else 'INACTIVE'}",
            f"  GLOBAL ACCESS    : INACTIVE",
            f"  WARNING MODE     : {'GLOBAL' if self.warning else 'PROFILE-CONTROLLED'}",
            "  ERASE            : SIMULATED",
            f"  AUDIT            : {'ACTIVE' if self.audit else 'INACTIVE'}",
            "",
            "CLASSACT",
        ]
        lines.extend(self._fmt_list("CLASSACT", self.classact))
        lines.extend(["", "RACLIST"])
        lines.extend(self._fmt_list("RACLIST", self.raclist))
        lines.extend(["", "GENERIC"])
        lines.extend(self._fmt_list("GENERIC", self.generic))
        lines.extend([
            "",
            "PASSWORD OPTIONS",
            "PASSWORD PROCESSING OPTIONS",
            f"  ALGORITHM        : {self.algorithm}",
            f"  MINLENGTH        : {self.minlength}",
            f"  HISTORY          : {self.history}",
            f"  INTERVAL         : {self.interval}",
            f"  REVOKE           : {self.revoke}",
            f"  MIXEDCASE        : {'ACTIVE' if self.mixedcase else 'INACTIVE'}",
            f"  SPECIALCHARS     : {'ACTIVE' if self.specialchars else 'INACTIVE'}",
            f"  NEWUSER-CHANGE   : {'ACTIVE' if self.newuser_change else 'INACTIVE'}",
            f"  INACTIVE         : {'NOINACTIVE' if int(self.inactive_days or 0) <= 0 else str(self.inactive_days)}",
            "  -- legacy-compatible summary --",
            f"  ALGORITHM       {self.algorithm}",
            f"  MINLENGTH       {self.minlength}",
            f"  HISTORY         {self.history}",
            f"  INTERVAL        {self.interval}",
            f"  REVOKE          {self.revoke}",
            f"  MIXEDCASE       {'ACTIVE' if self.mixedcase else 'INACTIVE'}",
            f"  SPECIALCHARS    {'ACTIVE' if self.specialchars else 'INACTIVE'}",
        ])
        for k in sorted(self.rules):
            lines.append(f"  {k:<16}: {self.rules[k]}")
        lines.extend([
            "",
            "MFA OPTIONS",
            f"  MFA              : {'ACTIVE' if self.mfa_active else 'INACTIVE'}",
            f"  MLACTIVE         : {'ACTIVE' if self.mlactive else 'INACTIVE'}",
            f"  POLICY           : {self.mfa_policy}",
            f"  INACTIVE         : {'NOINACTIVE' if int(self.inactive_days or 0) <= 0 else str(self.inactive_days)}",
            "",
            "CICS SECURITY SUMMARY",
            "  SEC              : YES",
            "  XTRAN            : YES",
            "  XCMD             : YES",
            "  XPCT             : YES",
            "  XFCT             : YES",
            "  DFLTUSER         : CICSUSER",
            "",
            "LAST REFRESH",
            f"  STATUS           : {'PENDING' if self.pending_refresh else 'CURRENT'}",
            f"  LAST UPDATED BY  : {self.last_updated_by}",
            f"  LAST UPDATED     : {self.last_updated}",
            "",
            "GIBSON NOTE: OUTPUT IS A TRAINING SIMULATION OF RACF SETROPTS.",
        ])
        return lines

    def _extract_list(self, u: str, name: str) -> List[str]:
        m = re.search(name + r"\s*\(([^)]*)\)", u)
        if not m:
            return []
        return [x.upper() for x in re.split(r"[\s,]+", m.group(1).strip()) if x]

    def _set_values(self, attr: str, classes: List[str], active: bool) -> List[str]:
        cur = {x.upper() for x in getattr(self, attr)}
        changed = []
        for cls in classes:
            if active:
                cur.add(cls); changed.append(cls)
            else:
                cur.discard(cls); changed.append("NO" + cls)
        setattr(self, attr, sorted(cur))
        return changed

    def set_from_command(self, cmd: str, *, secure_mode: bool = False, userid: str = "SYSTEM") -> str:
        u = re.sub(r"\s+", " ", cmd.upper()).strip()
        changed: List[str] = []
        if u in {"SETROPTS ?", "SETROPTS HELP", "HELP SETROPTS"}:
            return self.help_text("SETROPTS")
        if u in {"SETROPTS PASSWORD ?", "SETROPTS PASSWORD HELP", "HELP SETROPTS PASSWORD"}:
            return self.help_text("PASSWORD")
        if u == "SETROPTS" or u == "SETROPTS PASSWORD":
            return "\n".join(self.list_lines()) if u == "SETROPTS" else self.help_text("PASSWORD")
        if u in {"SETROPTS LIST", "SETROPTS LIST ALL"}:
            return "\n".join(self.list_lines())

        mi = re.search(r"\bINACTIVE\s*\(\s*(\d+)\s*\)", u)
        if mi:
            self.inactive_days = int(mi.group(1)); changed.append(f"INACTIVE INTERVAL IS NOW {self.inactive_days} DAYS")
        if re.search(r"\bNOINACTIVE\b", u):
            self.inactive_days = 0; changed.append("INACTIVE PROCESSING IS NOW DISABLED")

        # Password sub-operands.  Accept compact or spaced parenthesized form.
        m = re.search(r"ALGO(?:RITHM)?\s*\(\s*([^)\s]+)\s*\)", u)
        if m:
            alg = m.group(1).strip().upper()
            if alg not in {"KDFAES", "DES", "NONE", "LEGACY", "MD5", "MD5CRYPT"}:
                return f"ICH14002I INVALID PASSWORD ALGORITHM {alg}"
            if alg == "NONE" and secure_mode:
                return "ICH14003I PASSWORD(ALGORITHM(NONE)) NOT ALLOWED IN SECURE MODE"
            self.algorithm = alg; changed.append(f"PASSWORD ALGORITHM IS NOW {alg}")
        for name, attr in [("MINLENGTH", "minlength"), ("HISTORY", "history"), ("REVOKE", "revoke"), ("INTERVAL", "interval")]:
            m = re.search(name + r"\s*\(\s*(\d+)\s*\)", u)
            if m:
                val = int(m.group(1)); setattr(self, attr, val); changed.append(f"PASSWORD {name} IS NOW {val}")
        if "NOMIXEDCASE" in u:
            self.mixedcase = False; changed.append("PASSWORD MIXEDCASE IS NOW INACTIVE")
        elif "MIXEDCASE" in u:
            self.mixedcase = True; changed.append("PASSWORD MIXEDCASE IS NOW ACTIVE")
        if "NOSPECIALCHARS" in u:
            self.specialchars = False; changed.append("PASSWORD SPECIALCHARS IS NOW INACTIVE")
        elif "SPECIALCHARS" in u:
            self.specialchars = True; changed.append("PASSWORD SPECIALCHARS IS NOW ACTIVE")
        for n in range(1,5):
            m = re.search(rf"RULE{n}\s*\((.*?)\)", u)
            if m:
                self.rules[f"RULE{n}"] = m.group(1).strip(); changed.append(f"PASSWORD RULE{n} UPDATED")
            if re.search(rf"NORULE{n}\b", u):
                self.rules.pop(f"RULE{n}", None); changed.append(f"PASSWORD RULE{n} REMOVED")

        # MFA and multi-level authentication flags.
        if re.search(r"\bNOMFA\b", u):
            self.mfa_active = False; changed.append("MFA IS NOW INACTIVE")
        elif re.search(r"\bMFA\b", u):
            self.mfa_active = True; changed.append("MFA IS NOW ACTIVE")
        if re.search(r"\bNOMLACTIVE\b", u):
            self.mlactive = False; changed.append("MLACTIVE IS NOW INACTIVE")
        elif re.search(r"\bMLACTIVE\b", u):
            self.mlactive = True; changed.append("MLACTIVE IS NOW ACTIVE")
        m = re.search(r"MFA\s*\(\s*(REQUIRED|OPTIONAL)\s*\)", u)
        if m:
            self.mfa_policy = m.group(1); self.mfa_active = True; changed.append(f"MFA POLICY IS NOW {self.mfa_policy}")

        # Class, RACLIST, and generic profile options.
        for name, attr, active, msg in [
            ("NOCLASSACT", "classact", False, "DEACTIVATED"), ("CLASSACT", "classact", True, "ACTIVATED"),
            ("NORACLIST", "raclist", False, "RACLIST DISABLED"), ("RACLIST", "raclist", True, "RACLISTED"),
            ("NOGENERIC", "generic", False, "GENERIC DISABLED"), ("GENERIC", "generic", True, "GENERIC ACTIVE"),
            ("NOAUDIT", "audit", False, "AUDIT DISABLED"), ("AUDIT", "audit", True, "AUDIT ACTIVE"),
        ]:
            if name in u:
                vals = self._extract_list(u, name)
                if vals:
                    self._set_values(attr, vals, active)
                    changed.extend([f"{v} {msg}" for v in vals])
        if re.search(r"\bNOWARNING\b", u):
            self.warning = False; changed.append("WARNING IS NOW INACTIVE")
        elif re.search(r"\bWARNING\b", u):
            self.warning = True; changed.append("WARNING IS NOW ACTIVE")
        if "REFRESH" in u:
            self.pending_refresh = False
            if not changed:
                return "ICH14070I SETROPTS REFRESH COMPLETE"
            changed.append("SETROPTS REFRESH COMPLETE")

        if not changed:
            return "ICH70002I SETROPTS OPTION NOT SUPPORTED IN GIBSON SIMULATION"
        self.last_updated = _now(); self.last_updated_by = userid.upper(); self.pending_refresh = False
        return "ICH70001I SETROPTS OPTION(S) UPDATED\n" + "\n".join(f"  {c}" for c in changed)


    def validate_new_password(self, userid: str, password: str, history: List[str] | None = None, verify_func=None) -> Tuple[bool, str]:
        # An empty / not-yet-entered new password must prompt for one, never be
        # reported as "MINIMUM LENGTH IS 8" (len("")==0 < 8).  This is what made
        # the EBCDIC LOGON panel reject an initial logon before any new password
        # was typed.
        if not (password or "").strip():
            return False, "ICH70008I PASSWORD EXPIRED OR INITIAL - ENTER A NEW PASSWORD"
        if len(password) < int(self.minlength):
            return False, f"ICH70002I PASSWORD REJECTED - MINIMUM LENGTH IS {self.minlength}"
        if self.mixedcase and (password.upper() == password or password.lower() == password):
            return False, "ICH70003I PASSWORD REJECTED - MIXED CASE REQUIRED"
        if self.specialchars and re.fullmatch(r"[A-Za-z0-9]+", password or ""):
            return False, "ICH70004I PASSWORD REJECTED - SPECIAL CHARACTER REQUIRED"
        if history and verify_func:
            for old in history[-int(self.history):]:
                try:
                    if verify_func(password, old):
                        return False, "ICH70005I PASSWORD REJECTED - PASSWORD HISTORY VIOLATION"
                except Exception:
                    pass
        return True, "ICH70000I PASSWORD ACCEPTED"


def hash_password(password: str, algorithm: str = "MD5") -> str:
    alg = (algorithm or "MD5").upper()
    # RACF folds passwords to upper case before hashing (unless MIXEDCASE is set);
    # the 3270 logon panel also sends upper case, so we fold here for a consistent
    # match between ADDUSER and logon.
    pw = (password or "").upper()
    if alg in {"MD5", "MD5CRYPT", "LEGACY", "DES", "DES-SIM"}:
        # Real crypt(3) md5 ($1$salt$hash) - matches the existing GACF.DB format.
        try:
            from gibson.core.racf import _md5crypt_hash
            return _md5crypt_hash(pw, secrets.token_hex(4))
        except Exception:
            pass
    if alg in {"KDFAES", "PBKDF2"}:
        salt = secrets.token_bytes(16)
        rounds = 150000
        digest = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, rounds)
        return "{KDFAES}" + base64.b64encode(salt).decode() + f"${rounds}$" + base64.b64encode(digest).decode()
    if alg == "NONE":
        return "{NONE}" + pw
    # fallback: md5crypt
    try:
        from gibson.core.racf import _md5crypt_hash
        return _md5crypt_hash(pw, secrets.token_hex(4))
    except Exception:
        salt = secrets.token_hex(4)
        digest = hashlib.sha256((salt + pw).encode()).hexdigest()
        return f"{{LEGACY-SHA256}}{salt}${digest}"


def verify_password_hash(password: str, stored: str) -> bool:
    # Try the password as entered and folded to upper case (RACF default), so
    # both legacy mixed-case hashes and new upper-case hashes verify.
    for password in {password, (password or "").upper()}:
        if _verify_one(password, stored):
            return True
    return False


def _verify_one(password: str, stored: str) -> bool:
    if stored.startswith("$1$"):
        try:
            from gibson.core.racf import verify_md5crypt
            return verify_md5crypt(password, stored)
        except Exception:
            return False
    if stored.startswith("{KDFAES}"):
        try:
            rest = stored[len("{KDFAES}"):]
            salt_b64, rounds_s, digest_b64 = rest.split("$", 2)
            salt = base64.b64decode(salt_b64.encode())
            rounds = int(rounds_s)
            expected = base64.b64decode(digest_b64.encode())
            actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False
    if stored.startswith("{DES-SIM}"):
        try:
            rest = stored[len("{DES-SIM}"):]
            salt, digest = rest.split("$", 1)
            return hmac.compare_digest(hashlib.sha256((salt + password).encode()).hexdigest()[:32], digest)
        except Exception:
            return False
    if stored.startswith("{NONE}"):
        return stored[len("{NONE}"):] == password
    if stored.startswith("{LEGACY-SHA256}"):
        try:
            rest = stored[len("{LEGACY-SHA256}"):]
            salt, digest = rest.split("$", 1)
            return hmac.compare_digest(hashlib.sha256((salt + password).encode()).hexdigest(), digest)
        except Exception:
            return False
    return False

@dataclass
class UadsEntry:
    userid: str
    default_group: str = "SYS1"
    tso_proc: str = "DBSPROCC"
    account: str = "ACCT#"
    region: str = "4096K"
    status: str = "ACTIVE"
    password_change_required: bool = False
    password_hash: str = ""
    password_history: List[str] = field(default_factory=list)
    mfa_required: bool = False
    mfa_type: str = ""
    mfa_secret: str = ""
    created: str = field(default_factory=_now)
    changed: str = field(default_factory=_now)
    creation_source: str = "RACF"

class UadsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: Dict[str, UadsEntry] = {}
        self.load()

    def load(self) -> None:
        self.entries = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                for k, v in data.get('entries', {}).items():
                    self.entries[k.upper()] = UadsEntry(**v)
            except Exception:
                self.entries = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {'format':'GIBSON-SYS1-UADS-JSON', 'changed': _now(), 'entries': {k: asdict(v) for k,v in sorted(self.entries.items())}}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')

    def sync_from_racf(self, racf_repo, policy: PasswordPolicy) -> None:
        """Synchronise SYS1.UADS from the RACF/GACF authority.

        RACF/GACF.DB owns password hashes and the initial/expired password
        state.  UADS is the TSO logon view of that state, so it must not keep a
        stale hash or stale password_change_required flag after a reload.  This
        matters when ASCII and EBCDIC listeners use separate processes.
        """
        for raw_uid, user in getattr(racf_repo, 'users', {}).items():
            uid = (raw_uid or getattr(user, 'userid', '') or '').upper()
            if not uid:
                continue
            racf_hash = getattr(user, 'password', '') or ''
            racf_change_required = bool(getattr(user, 'password_change_required', False))
            default_group = getattr(user, 'default_group', 'SYS1') or 'SYS1'
            entry = self.entries.get(uid)
            if entry is None:
                self.entries[uid] = UadsEntry(
                    userid=uid, default_group=default_group.upper(),
                    password_hash=racf_hash,
                    password_change_required=racf_change_required,
                    creation_source='RACF')
                continue
            entry.default_group = default_group.upper()
            if entry.password_hash != racf_hash:
                if entry.password_hash:
                    if (not entry.password_history or
                            entry.password_history[-1] != entry.password_hash):
                        entry.password_history.append(entry.password_hash)
                        entry.password_history = entry.password_history[-20:]
                entry.password_hash = racf_hash
            entry.password_change_required = racf_change_required
            entry.changed = _now()
        self.save()

    def add_or_update_user(self, userid: str, password_hash: str, default_group: str = "SYS1", *, change_required: bool = True, source: str = "ADDUSER") -> None:
        uid = userid.upper()
        old = self.entries.get(uid)
        hist = list(old.password_history) if old else []
        if old and old.password_hash:
            hist.append(old.password_hash)
        self.entries[uid] = UadsEntry(userid=uid, default_group=default_group.upper(), password_hash=password_hash, password_history=hist[-20:], password_change_required=change_required, creation_source=source)
        self.save()

    def get(self, userid: str) -> Optional[UadsEntry]:
        return self.entries.get((userid or '').upper())

    def set_password(self, userid: str, password_hash: str, *, change_required: bool = False) -> None:
        uid = userid.upper(); ent = self.entries.get(uid)
        if ent is None:
            ent = UadsEntry(userid=uid)
            self.entries[uid] = ent
        if ent.password_hash:
            ent.password_history.append(ent.password_hash)
            ent.password_history = ent.password_history[-20:]
        ent.password_hash = password_hash
        ent.password_change_required = change_required
        ent.changed = _now()
        self.save()

    def set_mfa(self, userid: str, required: bool, mfa_type: str = "TOTP") -> str:
        uid = userid.upper(); ent = self.entries.get(uid)
        if ent is None:
            ent = UadsEntry(userid=uid)
            self.entries[uid] = ent
        ent.mfa_required = required
        ent.mfa_type = mfa_type.upper() if required else ""
        if required and not ent.mfa_secret:
            ent.mfa_secret = base64.b32encode(secrets.token_bytes(10)).decode().rstrip('=')
        ent.changed = _now(); self.save()
        return ent.mfa_secret

    def list_lines(self, reveal_hash: bool = False) -> List[str]:
        lines = ["SYS1.UADS - GIBSON SIMULATED TSO USER ATTRIBUTE DATA SET", "USERID   DFLTGRP  PROC     STATUS   PWCHANGE MFA  HASH"]
        for uid, ent in sorted(self.entries.items()):
            h = ent.password_hash if reveal_hash else (ent.password_hash[:12] + '...' if ent.password_hash else '')
            lines.append(f"{uid:<8} {ent.default_group:<8} {ent.tso_proc:<8} {ent.status:<8} {'YES' if ent.password_change_required else 'NO ':<8} {'YES' if ent.mfa_required else 'NO ':<4} {h}")
        return lines

    def show(self, userid: str) -> str:
        ent = self.get(userid)
        if not ent:
            return f"UADS ENTRY {userid.upper()} NOT FOUND"
        return "\n".join([
            f"SYS1.UADS ENTRY FOR {ent.userid}",
            f"  DEFAULT GROUP . . : {ent.default_group}",
            f"  TSO PROC. . . . . : {ent.tso_proc}",
            f"  ACCOUNT . . . . . : {ent.account}",
            f"  REGION. . . . . . : {ent.region}",
            f"  STATUS. . . . . . : {ent.status}",
            f"  PASSWORD CHANGE . : {'REQUIRED' if ent.password_change_required else 'NOT REQUIRED'}",
            f"  MFA REQUIRED  . . : {'YES' if ent.mfa_required else 'NO'} {ent.mfa_type}",
            f"  PASSWORD HASH . . : {'PRESENT - MASKED' if ent.password_hash else 'MISSING'}",
            f"  CREATED . . . . . : {ent.created}",
            f"  CHANGED . . . . . : {ent.changed}",
        ])

class MfaManager:
    def __init__(self, uads: UadsStore, policy: PasswordPolicy):
        self.uads = uads; self.policy = policy
    def status(self) -> str:
        total = len(self.uads.entries)
        req = sum(1 for e in self.uads.entries.values() if e.mfa_required)
        return f"MFA STATUS\n  GLOBAL: {'ACTIVE' if self.policy.mfa_active else 'INACTIVE'}\n  USERS REQUIRING MFA: {req}/{total}"
    def enroll(self, userid: str, mfa_type: str = "TOTP") -> str:
        secret = self.uads.set_mfa(userid, True, mfa_type)
        token = self.training_token(userid)
        return f"IRR71001I MFA FACTOR {mfa_type.upper()} ENROLLED FOR {userid.upper()}\nTRAINING TOKEN: {token}\nSECRET: ******"
    def remove(self, userid: str) -> str:
        self.uads.set_mfa(userid, False, '')
        return f"IRR71002I MFA FACTOR REMOVED FOR {userid.upper()}"
    def training_token(self, userid: str) -> str:
        ent = self.uads.get(userid)
        base = (ent.mfa_secret if ent and ent.mfa_secret else userid.upper()).encode()
        return str(int(hashlib.sha1(base).hexdigest(),16) % 1000000).zfill(6)
    def verify(self, userid: str, token: str) -> bool:
        return (token or '').strip() == self.training_token(userid)
