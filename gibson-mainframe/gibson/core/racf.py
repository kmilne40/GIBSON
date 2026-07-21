from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import base64
import hashlib
import re
import json
from .security_freeze import hash_password as freeze_hash_password, verify_password_hash as freeze_verify_password_hash

try:
    from passlib.hash import md5_crypt  # type: ignore
    HAS_PASSLIB = True
except Exception:  # pragma: no cover - optional dependency in source tree
    md5_crypt = None
    HAS_PASSLIB = False

MD5CRYPT_RE = re.compile(r"^\$1\$([^$]+)\$([./A-Za-z0-9]+)$")
ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _to64(value: int, length: int) -> str:
    out = ""
    for _ in range(length):
        out += ITOA64[value & 0x3F]
        value >>= 6
    return out


def _md5crypt_hash(password: str, salt: str, magic: str = "$1$") -> str:
    pw = password.encode("utf-8")
    salt = salt.split("$")[0][:8].encode("utf-8")
    magic_b = magic.encode("ascii")

    ctx = hashlib.md5()
    ctx.update(pw)
    ctx.update(magic_b)
    ctx.update(salt)

    alt = hashlib.md5()
    alt.update(pw)
    alt.update(salt)
    alt.update(pw)
    final = alt.digest()

    plen = len(pw)
    while plen > 0:
        ctx.update(final[: min(16, plen)])
        plen -= 16

    i = len(pw)
    while i > 0:
        if i & 1:
            ctx.update(b"\x00")
        else:
            ctx.update(pw[:1])
        i >>= 1

    final = ctx.digest()
    for i in range(1000):
        ctx = hashlib.md5()
        if i & 1:
            ctx.update(pw)
        else:
            ctx.update(final)
        if i % 3:
            ctx.update(salt)
        if i % 7:
            ctx.update(pw)
        if i & 1:
            ctx.update(final)
        else:
            ctx.update(pw)
        final = ctx.digest()

    encoded = ""
    encoded += _to64((final[0] << 16) | (final[6] << 8) | final[12], 4)
    encoded += _to64((final[1] << 16) | (final[7] << 8) | final[13], 4)
    encoded += _to64((final[2] << 16) | (final[8] << 8) | final[14], 4)
    encoded += _to64((final[3] << 16) | (final[9] << 8) | final[15], 4)
    encoded += _to64((final[4] << 16) | (final[10] << 8) | final[5], 4)
    encoded += _to64(final[11], 2)
    return f"{magic}{salt.decode('ascii')}${encoded}"


def verify_md5crypt(password: str, stored: str) -> bool:
    m = MD5CRYPT_RE.match(stored)
    if not m:
        return False
    salt = m.group(1)
    try:
        if md5_crypt is not None:
            return bool(md5_crypt.verify(password, stored))
    except Exception:
        pass
    try:
        return _md5crypt_hash(password, salt) == stored
    except Exception:
        return False


@dataclass
class RacfUser:
    userid: str
    password: str
    attributes: List[str] = field(default_factory=list)
    omvs: str = "NOOMVS"
    owner: str = "#SYSPROG"
    default_group: str = "SYS1"
    revoked: bool = False
    name: str = ""
    uacc: str = "NONE"
    data: str = ""
    model: str = ""
    seclabel: str = ""
    tso: dict = field(default_factory=dict)
    omvs_segment: dict = field(default_factory=dict)
    dfp: dict = field(default_factory=dict)
    mfa: dict = field(default_factory=dict)
    protected: bool = False
    password_change_required: bool = False
    phrase: bool = False
    nooidcard: bool = False

    @property
    def special(self) -> bool:
        return "SPECIAL" in {a.upper() for a in self.attributes}

    @property
    def has_omvs(self) -> bool:
        return bool(self.omvs_segment) or self.omvs.upper() == "OMVS" or "OMVS" in {a.upper() for a in self.attributes}

    def to_legacy_line(self) -> str:
        attrs = sorted({a.upper() for a in self.attributes if a})
        attr = ",".join(attrs) if attrs else "NONE"
        omvs = "OMVS" if self.has_omvs else "NOOMVS"
        extra = {
            "name": self.name,
            "uacc": self.uacc,
            "data": self.data,
            "model": self.model,
            "seclabel": self.seclabel,
            "owner": self.owner,
            "tso": self.tso,
            "omvs_segment": self.omvs_segment,
            "dfp": self.dfp,
            "mfa": self.mfa,
            "protected": self.protected,
            "password_change_required": self.password_change_required,
            "phrase": self.phrase,
            "nooidcard": self.nooidcard,
        }
        blob = base64.b64encode(json.dumps(extra, sort_keys=True).encode("utf-8")).decode("ascii")
        return f"{self.userid}:{self.password}:{attr}:{omvs}:{self.default_group}:V30289={blob}"


@dataclass
class RacfLoadIssue:
    line_no: int
    code: str
    detail: str


class RacfRepository:
    """Single RACF/GACF authority for Gibson.

    Legacy GACF.DB lines remain supported as USERID:PASSWORD:PRIVILEGE:OMVSFLAG.
    Gibson now also preserves an optional fifth field for DFLTGRP to support
    group-based access without breaking existing archives.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.users: Dict[str, RacfUser] = {}
        self.issues: List[RacfLoadIssue] = []
        # Optional callback fired with the userid after a NEW user is defined,
        # so the owner (GibsonState) can provision the default training datasets
        # exactly like the seeded users get them. Set by GibsonState after init.
        self.on_user_added = None

    def load(self, merge: bool = False) -> None:
        # merge=True keeps users already in memory (e.g. just created by ADDUSER
        # in this shared-state process) and layers the on-disk records on top,
        # so a reload at logon can never erase a real, in-memory user before the
        # exists()/verify checks.  merge=False is a clean reload (default).
        if not merge:
            self.users.clear()
        self.issues.clear()
        if not self.path.exists():
            self.issues.append(RacfLoadIssue(0, "GACF_NOT_FOUND", str(self.path)))
            return
        for line_no, raw in enumerate(self.path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            line = raw.strip("\n")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 2:
                self.issues.append(RacfLoadIssue(line_no, "BAD_FORMAT", raw))
                continue
            userid = parts[0].strip().upper()
            password = parts[1].strip()
            attr = parts[2].strip().upper() if len(parts) >= 3 and parts[2].strip() else "NONE"
            omvs = parts[3].strip().upper() if len(parts) >= 4 and parts[3].strip() else "NOOMVS"
            default_group = parts[4].strip().upper() if len(parts) >= 5 and parts[4].strip() else "SYS1"
            revoked = any(p.strip().upper() == "REVOKED" for p in parts[5:])
            extra = {}
            for pextra in parts[5:]:
                if pextra.startswith("V30289="):
                    try:
                        extra = json.loads(base64.b64decode(pextra.split("=",1)[1]).decode("utf-8"))
                    except Exception:
                        extra = {}
            if not userid or userid in {"''", '""'}:
                self.issues.append(RacfLoadIssue(line_no, "EMPTY_USERID", raw))
                userid = f"__EMPTY_{line_no}__"
            if any(ord(c) < 32 for c in password):
                self.issues.append(RacfLoadIssue(line_no, "CONTROL_CHARS", userid))
            if not MD5CRYPT_RE.match(password):
                self.issues.append(RacfLoadIssue(line_no, "PLAINTEXT_OR_NON_MD5CRYPT", userid))
            attrs: List[str] = [] if attr in ("", "NONE") else [a for a in attr.split(",") if a]
            self.users[userid] = RacfUser(
                userid, password, attrs, omvs,
                owner=extra.get("owner", "#SYSPROG"), default_group=default_group, revoked=revoked,
                name=extra.get("name", ""), uacc=extra.get("uacc", "NONE"), data=extra.get("data", ""),
                model=extra.get("model", ""), seclabel=extra.get("seclabel", ""),
                tso=extra.get("tso", {}) or {}, omvs_segment=extra.get("omvs_segment", {}) or {},
                dfp=extra.get("dfp", {}) or {}, mfa=extra.get("mfa", {}) or {},
                protected=bool(extra.get("protected", False)), password_change_required=bool(extra.get("password_change_required", False)),
                phrase=bool(extra.get("phrase", False)), nooidcard=bool(extra.get("nooidcard", False)),
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for u in self.users.values():
            line = u.to_legacy_line()
            if u.revoked:
                line += ":REVOKED"
            lines.append(line)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def ensure_user_dir(self, files_root: Path, userid: str) -> Path:
        p = Path(files_root) / userid.upper()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def exists(self, userid: str) -> bool:
        return userid.upper() in self.users

    def get(self, userid: str) -> Optional[RacfUser]:
        return self.users.get(userid.upper())

    def verify_password(self, userid: str, supplied: str) -> bool:
        user = self.get(userid)
        if not user or user.revoked:
            return False
        stored = user.password
        # Try the supplied value as entered and folded to upper case (RACF folds
        # passwords to upper case, and the 3270 panel sends upper case).
        candidates = []
        for base in (supplied, supplied.strip()):
            for c in (base, base.upper()):
                if c not in candidates:
                    candidates.append(c)
        for candidate in candidates:
            if stored == candidate or (not stored.startswith(("{", "$")) and stored.upper() == candidate.upper()):
                return True
            try:
                if base64.b64decode(stored.encode("ascii")).decode("utf-8") == candidate:
                    return True
            except Exception:
                pass
            try:
                if base64.b64encode(candidate.encode("utf-8")).decode("ascii") == stored:
                    return True
            except Exception:
                pass
            if stored.startswith("{") and freeze_verify_password_hash(candidate, stored):
                return True
            if MD5CRYPT_RE.match(stored) and verify_md5crypt(candidate, stored):
                return True
        return False

    def adduser(self, userid: str, password: str = "", special: bool = False, omvs: bool = False, default_group: str = "SYS1", **kwargs) -> str:
        userid = userid.upper()
        default_group = (default_group or "SYS1").upper()
        if len(userid) > 8:
            return "IKJ56701I USERID MUST NOT EXCEED 8 CHARACTERS"
        if self.exists(userid):
            return f"ICH01004I USERID {userid} ALREADY DEFINED"
        alg = getattr(getattr(self, "password_policy", None), "algorithm", "KDFAES")
        h = "*NOPASSWORD*" if kwargs.get("protected") or kwargs.get("nopassword") else freeze_hash_password(password or "", alg)
        attrs = set()
        if special:
            attrs.add("SPECIAL")
        for a in kwargs.get("attributes", []) or []:
            aa = str(a).upper()
            if aa and not aa.startswith("NO"):
                attrs.add(aa)
        omvs_segment = kwargs.get("omvs_segment", {}) or {}
        self.users[userid] = RacfUser(
            userid, h, sorted(attrs), "OMVS" if (omvs or omvs_segment) else "NOOMVS",
            owner=(kwargs.get("owner") or "#SYSPROG").upper(), default_group=default_group,
            name=kwargs.get("name", "") or userid, uacc=(kwargs.get("uacc") or "NONE").upper(),
            data=kwargs.get("data", ""), model=(kwargs.get("model") or "").upper(), seclabel=(kwargs.get("seclabel") or "").upper(),
            tso=kwargs.get("tso", {}) or {}, omvs_segment=omvs_segment,
            dfp=kwargs.get("dfp", {}) or {}, mfa=kwargs.get("mfa", {}) or {},
            protected=bool(kwargs.get("protected", False)), revoked=bool(kwargs.get("revoked", False)),
            password_change_required=bool(password and not kwargs.get("protected") and getattr(getattr(self, "password_policy", None), "initial_password_change", False)),
            phrase=bool(kwargs.get("phrase", False)), nooidcard=bool(kwargs.get("nooidcard", False)),
        )
        self.save()
        if self.on_user_added:
            try:
                self.on_user_added(userid)
            except Exception:
                pass
        return f"ICH01003I USERID {userid} DEFINED"


    def deleteuser(self, userid: str) -> str:
        user = self.get(userid)
        if not user:
            return f"ICH01005I USERID {userid.upper()} NOT FOUND"
        self.users.pop(userid.upper(), None)
        self.save()
        return f"ICH01007I USERID {userid.upper()} DELETED"

    def altuser(
        self,
        userid: str,
        password: Optional[str] = None,
        special: Optional[bool] = None,
        omvs: Optional[bool] = None,
        default_group: Optional[str] = None,
        revoked: Optional[bool] = None,
        **kwargs,
    ) -> str:
        user = self.get(userid)
        if not user:
            return f"ICH01005I USERID {userid.upper()} NOT FOUND"
        if password is not None:
            alg = getattr(getattr(self, "password_policy", None), "algorithm", "KDFAES")
            user.password = freeze_hash_password(password, alg)
            user.protected = False
            user.password_change_required = False
        attrs = {a.upper() for a in user.attributes}
        if special is not None:
            if special: attrs.add("SPECIAL")
            else: attrs.discard("SPECIAL")
        for a, enabled in (kwargs.get("attr_changes", {}) or {}).items():
            aa = a.upper()
            if enabled: attrs.add(aa)
            else: attrs.discard(aa)
        user.attributes = sorted(attrs)
        if omvs is not None:
            user.omvs = "OMVS" if omvs else "NOOMVS"
            if not omvs: user.omvs_segment = {}
        if default_group is not None:
            user.default_group = default_group.upper()
        if revoked is not None:
            user.revoked = bool(revoked)
        for field_name in ["name", "uacc", "data", "model", "seclabel", "owner"]:
            if field_name in kwargs and kwargs[field_name] is not None:
                setattr(user, field_name, str(kwargs[field_name]).upper() if field_name != "data" else str(kwargs[field_name]))
        if "tso" in kwargs:
            user.tso = kwargs["tso"] or {}; 
        if kwargs.get("notso"):
            user.tso = {}
        if "omvs_segment" in kwargs:
            seg = dict(user.omvs_segment or {})
            seg.update(kwargs["omvs_segment"] or {})
            user.omvs_segment = seg
            user.omvs = "OMVS" if seg else "NOOMVS"
        if kwargs.get("noomvs"):
            user.omvs_segment = {}; user.omvs = "NOOMVS"
        if "dfp" in kwargs:
            user.dfp = kwargs["dfp"] or {}
        if kwargs.get("nodfp"):
            user.dfp = {}
        if "mfa" in kwargs:
            user.mfa = kwargs["mfa"] or {}
        if kwargs.get("nomfa"):
            user.mfa = {}
        if "phrase" in kwargs:
            user.phrase = bool(kwargs.get("phrase"))
        if kwargs.get("nophrase"):
            user.phrase = False
        if "nooidcard" in kwargs:
            user.nooidcard = bool(kwargs.get("nooidcard"))
        if kwargs.get("protected"):
            user.protected = True; user.password = "*NOPASSWORD*"
        self.save()
        return f"ICH01006I USERID {user.userid} ALTERED"


    def listuser(self, userid: str, segment: str = "") -> str:
        user = self.get(userid)
        if not user:
            return f"ICH30001I USER {userid.upper()} NOT FOUND"
        seg = (segment or "").upper()
        attr_list = list(user.attributes)
        if user.revoked and "REVOKED" not in {a.upper() for a in attr_list}:
            attr_list.append("REVOKED")
        if user.protected and "PROTECTED" not in {a.upper() for a in attr_list}:
            attr_list.append("PROTECTED")
        attr = " ".join(sorted({a.upper() for a in attr_list})) if attr_list else "NONE"
        def tso_lines():
            if not user.tso: return ["NO TSO SEGMENT"]
            return ["TSO INFORMATION"] + [f" {k.upper()}={v}" for k, v in user.tso.items()]
        def omvs_lines():
            if not user.omvs_segment: return ["NO OMVS SEGMENT"]
            uid = int(user.omvs_segment.get("UID", user.omvs_segment.get("uid", 1)))
            home = user.omvs_segment.get("HOME") or user.omvs_segment.get("home") or f"/u/{user.userid.lower()}"
            prog = user.omvs_segment.get("PROGRAM") or user.omvs_segment.get("program") or "/bin/sh"
            return ["OMVS INFORMATION", f" UID={uid:010d} HOME={home} PROGRAM={prog}"]
        def dfp_lines():
            if not user.dfp: return ["NO DFP SEGMENT"]
            return ["DFP INFORMATION"] + [f" {k.upper()}={v}" for k, v in user.dfp.items()]
        def mfa_lines():
            if not user.mfa: return ["NO MFA SEGMENT"]
            return ["MFA INFORMATION"] + [f" {k.upper()}={v}" for k, v in user.mfa.items()]
        if seg == "TSO": return "\n".join(tso_lines())
        if seg == "OMVS": return "\n".join(omvs_lines())
        if seg == "DFP": return "\n".join(dfp_lines())
        if seg == "MFA": return "\n".join(mfa_lines())
        base = [
            f"USER={user.userid}  NAME={user.name or user.userid:<20} OWNER={user.owner}  CREATED=24.271",
            f" DEFAULT-GROUP={user.default_group:<8} PASSDATE=25.020 PASS-INTERVAL= 30",
            f" ATTRIBUTES={attr}",
            f" UACC={user.uacc or 'NONE'} MODEL={user.model or 'NONE'} SECLABEL={user.seclabel or 'NONE'}",
            f" REVOKE DATE={'YES' if user.revoked else 'NONE'}   RESUME DATE=NONE",
            f" PASSWORD CHANGE REQUIRED={'YES' if user.password_change_required else 'NO'}",
            f" PHRASE={'DEFINED' if getattr(user, 'phrase', False) else 'NONE'} NOOIDCARD={'YES' if getattr(user, 'nooidcard', False) else 'NO'}",
            " LOGON ALLOWED   (DAYS)          (TIME)",
            "  ANYDAY                          ANYTIME",
        ]
        if seg == "ALL":
            base += tso_lines() + omvs_lines() + dfp_lines() + mfa_lines()
        else:
            base += omvs_lines()
        return "\n".join(base)


    def search_special(self) -> str:
        names = [u.userid for u in self.users.values() if u.special]
        return "\n".join(names) if names else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"

# v30.289 compatibility method injected for older source trees that may have
# loaded before the class body gained the method in packaged updates.
def _racf_search_uid0(self):
    names=[]
    for u in self.users.values():
        try:
            if getattr(u, "omvs_segment", {}) and int(u.omvs_segment.get("UID", u.omvs_segment.get("uid", -1))) == 0:
                names.append(u.userid)
        except Exception:
            pass
    return "\n".join(sorted(names)) if names else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
RacfRepository.search_uid0 = _racf_search_uid0
