from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional
import fnmatch
import json
import re

_ACCESS_ORDER = ["NONE", "READ", "UPDATE", "CONTROL", "ALTER"]
_GROUP_ORDER = ["USE", "CREATE", "CONNECT", "JOIN"]


def _normal_access(value: str) -> str:
    v = (value or "NONE").strip().upper()
    return v if v in _ACCESS_ORDER else "NONE"


@dataclass
class AccessDecision:
    allowed: bool
    effective: str
    required: str
    reason: str
    warning: bool = False
    profile: Optional["RacfProfile"] = None
    user_permit_used: str = ""
    group_permit_used: str = ""
    special_bypass_used: bool = False
    owner_bypass_used: bool = False
    message: str = ""


def _access_at_least(have: str, want: str) -> bool:
    try:
        return _ACCESS_ORDER.index(have.upper()) >= _ACCESS_ORDER.index(want.upper())
    except ValueError:
        return have.upper() not in ("", "NONE")


@dataclass
class RacfGroup:
    name: str
    owner: str = "#SYSPROG"
    supgroup: str = "SYS1"
    users: Dict[str, str] = field(default_factory=dict)  # userid -> authority


@dataclass
class RacfProfile:
    class_name: str
    name: str
    owner: str = "#SYSPROG"
    uacc: str = "NONE"
    permits: Dict[str, str] = field(default_factory=dict)
    attrs: Dict[str, str] = field(default_factory=dict)
    warning: bool = False
    audit: str = "FAILURES(READ)"
    volume: str = "SBSYS1"
    resource_type: str = "NON-VSAM"


@dataclass
class DynamicRacfStore:
    groups: Dict[str, RacfGroup] = field(default_factory=dict)
    profiles: Dict[str, Dict[str, RacfProfile]] = field(default_factory=dict)
    raclist_active: Dict[str, bool] = field(default_factory=dict)
    global_access: Dict[str, str] = field(default_factory=dict)
    path: Optional[str] = None

    @classmethod
    def seeded(cls) -> "DynamicRacfStore":
        s = cls()
        s.groups = {
            "SYS1": RacfGroup("SYS1", "IBMUSER", "SYS1", {"IBMUSER": "JOIN", "RUARIV": "USE"}),
            "STUDENT": RacfGroup("STUDENT", "IBMUSER", "SYS1", {"GUEST": "USE", "ENLIMV": "USE"}),
            "#SYSPROG": RacfGroup("#SYSPROG", "IBMUSER", "SYS1", {"IBMUSER": "JOIN", "RUARIV": "CONNECT"}),
        }
        # v26.1: protect SYS1 by default. GUEST receives explicit ACCESS(NONE).
        s.define("DATASET", "SYS1.**", "IBMUSER", "NONE", warning=False, volume="SBSYS1")
        for admin in ("IBMUSER", "RUARIV"):
            s.permit("DATASET", "SYS1.**", admin, "ALTER", save=False)
        s.permit("DATASET", "SYS1.**", "GUEST", "NONE", save=False)
        s.define("DATASET", "SYS1.PARMLIB", "IBMUSER", "READ", warning=False, volume="SBSYS1")
        s.permit("DATASET", "SYS1.PARMLIB", "IBMUSER", "ALTER", save=False)
        s.permit("DATASET", "SYS1.PARMLIB", "GUEST", "NONE", save=False)
        s.define("DATASET", "SYS1.RACFDS", "IBMUSER", "NONE", volume="SBSYS1")
        s.define("DATASET", "SYS1.RACFDS.BACKUP", "IBMUSER", "NONE", volume="SBRES1")
        s.define("DATASET", "SYS1.CKDS", "IBMUSER", "NONE", volume="SBSYS1")
        s.define("DATASET", "SYS1.PKDS", "IBMUSER", "NONE", volume="SBSYS1")
        s.define("DATASET", "SYS1.TKDS", "IBMUSER", "NONE", volume="SBSYS1")
        s.define("DATASET", "SYS1.PROCLIB", "IBMUSER", "READ", volume="SBSYS1")
        s.permit("DATASET", "SYS1.PROCLIB", "IBMUSER", "ALTER", save=False)
        s.permit("DATASET", "SYS1.PROCLIB", "GUEST", "NONE", save=False)
        s.define("DATASET", "SYS1.LINKLIB", "IBMUSER", "READ", volume="SBSYS1")
        s.permit("DATASET", "SYS1.LINKLIB", "IBMUSER", "ALTER", save=False)
        s.permit("DATASET", "SYS1.LINKLIB", "GUEST", "NONE", save=False)
        s.define("DATASET", "SYS1.VULNAPF.LIB", "RUARIV", "NONE", volume="TK5RES")
        s.permit("DATASET", "SYS1.VULNAPF.LIB", "RUARIV", "ALTER", save=False)
        s.permit("DATASET", "SYS1.RACFDS", "RUARIV", "ALTER", save=False)
        s.permit("DATASET", "SYS1.RACFDS.BACKUP", "RUARIV", "ALTER", save=False)
        for n, uacc in {
            "BPX.SUPERUSER": "READ",
            "BPX.FILEATTR.APF": "READ",
            "BPX.CONSOLE": "NONE",
            "BPX.SERVER": "NONE",
            "IRR.PASSWORD.RESET": "NONE",
            "IRR.DIGTCERT.ADD": "NONE",
            "IRR.DIGTCERT.LISTRING": "READ",
            "CSF.STATUS": "NONE",
            "CSF.REFRESH": "NONE",
            "CSF.REFRESH.MASTERKEY": "NONE",
            "CSF.REFRESH.CKDS": "NONE",
            "CSF.REFRESH.PKDS": "NONE",
            "CSF.REFRESH.TKDS": "NONE",
            "CSF.ADMIN": "NONE",
            "CSF.KEYGEN": "NONE",
        }.items():
            s.define("FACILITY", n, "IBMUSER", uacc)
        for n in ["IBMUSER.SUBMIT", "RUARIV.SUBMIT", "*.SUBMIT"]:
            s.define("SURROGAT", n, "IBMUSER", "NONE")
        s.permit("SURROGAT", "IBMUSER.SUBMIT", "SARCHER", "READ", save=False)
        s.permit("SURROGAT", "IBMUSER.SUBMIT", "RUARIV", "READ", save=False)
        for n in ["MVS.DISPLAY", "MVS.SETPROG", "MVS.START", "MVS.STOP", "MVS.CANCEL"]:
            s.define("OPERCMDS", n, "IBMUSER", "NONE")
            s.permit("OPERCMDS", n, "RUARIV", "READ", save=False)
        for n in ["GIB1.*.*.SYSOUT", "MVSC.*.*.SYSOUT"]:
            s.define("JESSPOOL", n, "IBMUSER", "READ")
        for n in ["FTPD1.*", "DB2A.*", "CICS.*", "TCPIP.*"]:
            s.define("STARTED", n, "IBMUSER", "NONE")
        for n in ["TSO", "TSOGIBS", "CICS", "DB2"]:
            s.define("APPL", n, "IBMUSER", "READ")
        for n in ["CEMT", "CEDA", "CECI", "CESN", "CESF", "CEBR", "CECS"]:
            s.define("TCICSTRN", n, "IBMUSER", "READ")
        for n in ["FILEA", "FILEB", "CICS560.FILEA"]:
            s.define("FCICSFCT", n, "IBMUSER", "READ")
        prof = s.define("RACFVARS", "&RACLNDE", "IBMUSER", "NONE")
        prof.permits["HAL"] = "MEMBER"
        prof.permits["ORAC"] = "MEMBER"
        for n in ["TSO", "CICS"]:
            s.define("PTKTDATA", n, "IBMUSER", "NONE")
        s.raclist_active = {"FACILITY": True, "SURROGAT": True, "OPERCMDS": True, "RACFVARS": True}
        return s

    @classmethod
    def load_or_seed(cls, path: Path) -> "DynamicRacfStore":
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return cls.from_dict(data, path=p)
            except Exception:
                pass
        s = cls.seeded()
        s.path = str(p)
        s.save()
        return s

    @classmethod
    def from_dict(cls, data: dict, *, path: Optional[Path] = None) -> "DynamicRacfStore":
        store = cls(path=str(path) if path else None)
        for name, raw in (data.get("groups") or {}).items():
            store.groups[name.upper()] = RacfGroup(
                raw.get("name", name).upper(),
                raw.get("owner", "#SYSPROG").upper(),
                raw.get("supgroup", "SYS1").upper(),
                {k.upper(): v.upper() for k, v in (raw.get("users") or {}).items()},
            )
        for clsname, entries in (data.get("profiles") or {}).items():
            store.profiles[clsname.upper()] = {}
            for profname, raw in entries.items():
                store.profiles[clsname.upper()][profname.upper()] = RacfProfile(
                    raw.get("class_name", clsname).upper(),
                    raw.get("name", profname).upper(),
                    raw.get("owner", "#SYSPROG").upper(),
                    raw.get("uacc", "NONE").upper(),
                    {k.upper(): v.upper() for k, v in (raw.get("permits") or {}).items()},
                    {k.upper(): str(v) for k, v in (raw.get("attrs") or {}).items()},
                    bool(raw.get("warning", False)),
                    raw.get("audit", "FAILURES(READ)"),
                    raw.get("volume", "SBSYS1").upper(),
                    raw.get("resource_type", "NON-VSAM").upper(),
                )
        store.raclist_active = {k.upper(): bool(v) for k, v in (data.get("raclist_active") or {}).items()}
        store.global_access = {k.upper(): str(v).upper() for k, v in (data.get("global_access") or {}).items()}
        return store

    def to_dict(self) -> dict:
        return {
            "groups": {name: asdict(group) for name, group in self.groups.items()},
            "profiles": {clsname: {name: asdict(prof) for name, prof in entries.items()} for clsname, entries in self.profiles.items()},
            "raclist_active": self.raclist_active,
            "global_access": self.global_access,
        }

    def save(self) -> None:
        if not self.path:
            return
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def define(self, clsname: str, name: str, owner: str = "#SYSPROG", uacc: str = "NONE", *, warning: bool = False, volume: str = "SBSYS1", resource_type: str = "NON-VSAM", attrs: Optional[dict[str, str]] = None) -> RacfProfile:
        c = clsname.upper(); p = name.upper()
        prof = RacfProfile(c, p, owner.upper(), uacc.upper(), attrs={k.upper(): str(v) for k, v in (attrs or {}).items()}, warning=warning, volume=volume.upper(), resource_type=resource_type.upper())
        self.profiles.setdefault(c, {})[p] = prof
        return prof

    def _find_profile(self, clsname: str, profile: str) -> Optional[RacfProfile]:
        c = clsname.upper(); p = profile.upper()
        profs = self.profiles.get(c, {})
        if p in profs:
            return profs[p]
        matches = []
        for name, prof in profs.items():
            pattern = name.replace("**", "*")
            if fnmatch.fnmatch(p, pattern):
                matches.append((len(name.replace("*", "")), prof))
        if matches:
            return sorted(matches, key=lambda x: x[0], reverse=True)[0][1]
        return None

    def connected_groups(self, userid: str, users_repo=None) -> list[str]:
        u = userid.upper()
        groups = set()
        if users_repo is not None:
            rec = users_repo.get(u)
            if rec and rec.default_group:
                groups.add(rec.default_group.upper())
        for name, group in self.groups.items():
            if u in group.users:
                groups.add(name.upper())
        return sorted(groups)

    def access_decision(self, clsname: str, profile: str, userid: str, access: str = "READ", users_repo=None) -> AccessDecision:
        c = clsname.upper(); p = profile.upper(); u = userid.upper()
        required = _normal_access(access)
        prof = self._find_profile(c, p)
        rec = users_repo.get(u) if users_repo is not None else None
        if rec and rec.special and c == "DATASET":
            return AccessDecision(True, "ALTER", required, "SPECIAL", False, prof, special_bypass_used=True, message="SPECIAL bypass")
        if prof is None:
            # Gibson default for unprofiled data sets: readable by non-owners, not writable.
            if c == "DATASET":
                eff = "ALTER" if p.split(".", 1)[0] == u else "READ"
                return AccessDecision(_access_at_least(eff, required), eff, required, "OWNER" if eff == "ALTER" else "DEFAULT_READ", False, None, owner_bypass_used=(eff == "ALTER"), message="unprofiled dataset default")
            return AccessDecision(False, "NONE", required, "NO_PROFILE", False, None, message="no matching profile")
        if rec and rec.special and c != "DATASET":
            return AccessDecision(True, "ALTER", required, "SPECIAL", False, prof, special_bypass_used=True, message="SPECIAL bypass")
        if u == prof.owner.upper():
            return AccessDecision(True, "ALTER", required, "OWNER", False, prof, owner_bypass_used=True, message="profile owner")
        explicit_user_permit = u in prof.permits
        best = _normal_access(prof.permits.get(u, "NONE"))
        reason = "USER_PERMIT" if explicit_user_permit else "NONE"
        user_permit = u if explicit_user_permit else ""
        group_permit = ""
        for group in self.connected_groups(u, users_repo):
            if group == prof.owner.upper():
                best, reason = "ALTER", "GROUP_OWNER"
                group_permit = group
            gacc = _normal_access(prof.permits.get(group, "NONE"))
            if _access_at_least(gacc, best) and gacc != best:
                best, reason = gacc, f"GROUP_PERMIT({group})"
                group_permit = group
        uacc = _normal_access(prof.uacc)
        # v26.1: an explicit ACCESS(NONE) on the access list is a deny override
        # for this training simulator and must not be raised by UACC. This is
        # critical for GUEST against SYS1.*.
        if not (explicit_user_permit and best == "NONE") and _access_at_least(uacc, best):
            best, reason = uacc, "UACC"
        allowed = _access_at_least(best, required)
        if allowed:
            return AccessDecision(True, best, required, reason, False, prof, user_permit_used=user_permit, group_permit_used=group_permit, message=f"effective {best} via {reason}")
        if prof.warning:
            return AccessDecision(True, best, required, "WARNING", True, prof, user_permit_used=user_permit, group_permit_used=group_permit, message=f"WARNING MODE allowed request requiring {required}; effective access was {best}")
        return AccessDecision(False, best, required, "DENIED", False, prof, user_permit_used=user_permit, group_permit_used=group_permit, message=f"insufficient access: effective {best}, required {required}")

    def effective_access(self, clsname: str, profile: str, userid: str, users_repo=None) -> str:
        return self.access_decision(clsname, profile, userid, "READ", users_repo).effective

    def has_access(self, clsname: str, profile: str, userid: str, access: str = "READ", users_repo=None) -> bool:
        return self.access_decision(clsname, profile, userid, access, users_repo).allowed

    def permit(self, clsname: str, profile: str, identity: str, access: str, *, save: bool = True) -> str:
        c = clsname.upper(); p = profile.upper(); ident = identity.upper()
        prof = self._find_profile(c, p) or self.define(c, p)
        prof.permits[ident] = _normal_access(access)
        if save:
            self.save()
        return f"ICH06011I PERMIT SUCCESSFUL FOR {p} CLASS({c}) ID({ident}) ACCESS({_normal_access(access)})"

    def revoke(self, clsname: str, profile: str, identity: str, *, save: bool = True) -> str:
        c = clsname.upper(); p = profile.upper(); ident = identity.upper()
        prof = self._find_profile(c, p)
        if prof is None:
            return f"ICH06012I PROFILE {p} NOT FOUND IN CLASS({c})"
        existed = ident in prof.permits
        prof.permits.pop(ident, None)
        if save:
            self.save()
        return f"ICH06013I PERMIT DELETED FOR {prof.name} CLASS({c}) ID({ident})" if existed else f"ICH06014I NO ACCESS LIST ENTRY FOR {ident} ON {prof.name}"

    def cleanup_deleted_user(self, userid: str, *, save: bool = True) -> None:
        u = userid.upper()
        for group in self.groups.values():
            group.users.pop(u, None)
        for entries in self.profiles.values():
            for prof in entries.values():
                prof.permits.pop(u, None)
        if save:
            self.save()

    def refresh(self, clsname: str | None = None) -> str:
        if clsname:
            self.raclist_active[clsname.upper()] = True
        self.save()
        return f"ICH14070I RACLIST REFRESH COMPLETE FOR CLASS {clsname.upper()}" if clsname else "ICH14070I SETROPTS REFRESH COMPLETE"

    def connect_user(self, userid: str, group: str, authority: str = "USE") -> None:
        auth = (authority or "USE").upper()
        if auth not in _GROUP_ORDER:
            auth = "USE"
        self.groups.setdefault(group.upper(), RacfGroup(group.upper())).users[userid.upper()] = auth
        self.save()

    def _extract_attrs(self, clsname: str, raw: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        c = clsname.upper()
        if c == "STARTED":
            m = re.search(r"STDATA\((.*)\)", raw, re.I)
            if m:
                st = m.group(1)
                for key in ("USER", "GROUP", "TRUSTED", "PRIVILEGED", "TRACE"):
                    km = re.search(rf"{key}\(([^)]+)\)", st, re.I)
                    if km:
                        attrs[key] = km.group(1).strip().upper()
            return attrs
        if c in {"DSNR", "TSOAUTH", "SERVAUTH", "CSFKEYS", "CSFSERV", "TCICSTRN", "CCICSCMD", "FCICSFCT", "DCICSDCT", "SCICSTST", "PCICSPSB", "MCICSPPT", "JESSPOOL", "JESJOBS", "SURROGAT", "MFADEF"}:
            for key in ("DATA", "APPLDATA", "OWNERDATA"):
                m = re.search(rf"{key}\((['\"]?)(.*?)\1\)", raw, re.I)
                if m:
                    attrs[key] = m.group(2).strip()
            return attrs
        if c != "PTKTDATA":
            return attrs
        for key in ("KEYMASKED", "KEYENCRYPTED", "LABTRUST", "LABAPPLMISMATCH", "LABLEAK", "VALIDSECS"):
            m = re.search(rf"{key}\(([^)]+)\)", raw, re.I)
            if m:
                attrs[key] = m.group(1).strip().strip("'\"")
        m = re.search(r"SSIGNON\(([^)]*)\)", raw, re.I)
        if m:
            attrs["SSIGNON"] = m.group(1).strip()
            for key in ("KEYMASKED", "KEYENCRYPTED"):
                km = re.search(rf"{key}\(([^)]+)\)", m.group(1), re.I)
                if km:
                    attrs[key] = km.group(1).strip().strip("'\"")
            if "KEYENCRYPTED" in m.group(1).upper() and "KEYENCRYPTED" not in attrs:
                attrs["KEYENCRYPTED"] = "YES"
            if "KEYMASKED" in m.group(1).upper() and "KEYMASKED" not in attrs:
                attrs["KEYMASKED"] = "YES"
        m = re.search(r"APPLDATA\((['\"])(.*?)\1\)", raw, re.I)
        if m:
            attrs["APPLDATA"] = m.group(2)
        m = re.search(r"DATA\((['\"])(.*?)\1\)", raw, re.I)
        if m:
            attrs["DATA"] = m.group(2)
        return attrs

    def command(self, cmd: str, userid: str, users_repo=None) -> Optional[str]:
        raw = cmd.strip(); u = raw.upper()
        if u.startswith("ADDGROUP"):
            parts = raw.split()
            if len(parts) < 2:
                return "ICH01050I ADDGROUP REQUIRES A GROUP NAME"
            name = parts[1].upper()
            self.groups[name] = RacfGroup(name, userid.upper(), "SYS1")
            self.save()
            return f"ICH01051I GROUP {name} DEFINED"
        if u.startswith("ALTGROUP"):
            parts = raw.split()
            if len(parts) < 2:
                return "ICH01056I ALTGROUP REQUIRES A GROUP NAME"
            name = parts[1].upper(); g = self.groups.get(name)
            if not g:
                return f"ICH30001I GROUP {name} NOT FOUND"
            m = re.search(r"OWNER\(([^)]+)\)", raw, re.I)
            if m:
                g.owner = m.group(1).upper()
            self.save()
            return f"ICH01057I GROUP {name} ALTERED"
        if u.startswith("DELGROUP"):
            parts = raw.split()
            if len(parts) < 2:
                return "ICH01058I DELGROUP REQUIRES A GROUP NAME"
            name = parts[1].upper()
            self.groups.pop(name, None)
            self.save()
            return f"ICH01059I GROUP {name} DELETED"
        if u.startswith("LISTGRP"):
            parts = raw.split()
            if len(parts) < 2 or parts[1] == "*":
                return "\n\n".join(self._format_group(g) for g in self.groups.values())
            g = self.groups.get(parts[1].upper())
            return self._format_group(g) if g else f"ICH30001I GROUP {parts[1].upper()} NOT FOUND"
        if u.startswith("CONNECT"):
            m = re.search(r"CONNECT\s+(\S+)\s+GROUP\(([^)]+)\)(?:\s+AUTHORITY\(([^)]+)\))?", raw, re.I)
            if not m:
                return "ICH01052I CONNECT SYNTAX: CONNECT userid GROUP(group) [AUTHORITY(USE)]"
            user, group, auth = m.group(1).upper(), m.group(2).upper(), (m.group(3) or "USE").upper()
            self.connect_user(user, group, auth)
            return f"ICH01053I USER {user} CONNECTED TO GROUP {group} WITH AUTHORITY {auth}"
        if u.startswith("REMOVE"):
            m = re.search(r"REMOVE\s+(\S+)\s+GROUP\(([^)]+)\)", raw, re.I)
            if not m:
                return "ICH01054I REMOVE SYNTAX: REMOVE userid GROUP(group)"
            user, group = m.group(1).upper(), m.group(2).upper()
            if group in self.groups:
                self.groups[group].users.pop(user, None)
            self.save()
            return f"ICH01055I USER {user} REMOVED FROM GROUP {group}"
        if u.startswith("RDEFINE"):
            m = re.search(r"RDEFINE\s+(\S+)\s+(.+?)(?:\s+UACC\(([^)]+)\))?(?:\s+|$)", raw, re.I)
            if not m:
                return "ICH10001I RDEFINE SYNTAX: RDEFINE class profile [UACC(access)]"
            clsname, profile, uacc = m.group(1), m.group(2).strip(), m.group(3) or "NONE"
            profile = re.split(r"\s+", profile)[0]
            prof = self.define(clsname, profile, userid, uacc, attrs=self._extract_attrs(clsname, raw))
            self.save()
            return f"ICH10002I PROFILE {prof.name} DEFINED IN CLASS {prof.class_name}"
        if u.startswith("RALTER") or u.startswith("ALTDSD"):
            if u.startswith("ALTDSD"):
                m = re.search(r"ALTDSD\s+'?([^'\s]+)'?\s*(.*)$", raw, re.I)
                if not m:
                    return "ICH10005I ALTDSD SYNTAX: ALTDSD dataset [WARNING|NOWARNING|UACC(access)]"
                c, p = "DATASET", m.group(1).upper()
            else:
                m = re.search(r"RALTER\s+(\S+)\s+(.+)", raw, re.I)
                if not m:
                    return "ICH10005I RALTER SYNTAX: RALTER class profile ..."
                c, p = m.group(1).upper(), m.group(2).split()[0].upper()
            prof = self._find_profile(c, p)
            if not prof:
                return f"ICH10004I PROFILE {p} NOT FOUND IN CLASS {c}"
            if "NOWARNING" in u:
                prof.warning = False
            if "WARNING" in u and "NOWARNING" not in u:
                prof.warning = True
            um = re.search(r"UACC\(([^)]+)\)", raw, re.I)
            if um:
                prof.uacc = um.group(1).upper()
            prof.attrs.update(self._extract_attrs(c, raw))
            self.save()
            return f"ICH10006I PROFILE {p} ALTERED IN CLASS {c}"
        if u.startswith("RDELETE") or u.startswith("DELDSD"):
            if u.startswith("DELDSD"):
                m = re.search(r"DELDSD\s+'?([^'\s]+)'?", raw, re.I)
                if not m:
                    return "ICH10007I DELDSD SYNTAX: DELDSD dataset"
                c, p = "DATASET", m.group(1).upper()
            else:
                m = re.search(r"RDELETE\s+(\S+)\s+(\S+)", raw, re.I)
                if not m:
                    return "ICH10007I RDELETE SYNTAX: RDELETE class profile"
                c, p = m.group(1).upper(), m.group(2).upper()
            self.profiles.get(c, {}).pop(p, None)
            self.save()
            return f"ICH10008I PROFILE {p} DELETED FROM CLASS {c}"
        if u.startswith("ADDSD"):
            m = re.search(r"ADDSD\s+'?([^'\s]+)'?(?:\s+UACC\(([^)]+)\))?", raw, re.I)
            if not m:
                return "ICH10009I ADDSD SYNTAX: ADDSD 'dataset' [UACC(access)]"
            prof = self.define("DATASET", m.group(1), userid, _normal_access(m.group(2) or "NONE"), warning=("WARNING" in u and "NOWARNING" not in u))
            self.save()
            return f"ICH10010I DATASET PROFILE {prof.name} ADDED"
        if u.startswith("LISTDSD"):
            return self.listdsd(raw, userid, users_repo)
        if u.startswith("RLIST"):
            m = re.search(r"RLIST\s+(\S+)\s+(.+?)(?:\s+(ALL|AUTH|STDATA))?$", raw, re.I)
            if not m:
                return "ICH10003I RLIST SYNTAX: RLIST class profile [ALL|AUTH]"
            c, p = m.group(1).upper(), m.group(2).split()[0].upper()
            if p == "*":
                rows = [self._format_profile(x, requester=userid, users_repo=users_repo) for x in self.profiles.get(c, {}).values()]
                return "\n\n".join(rows) if rows else f"ICH10004I NO PROFILES FOUND IN CLASS {c}"
            prof = self._find_profile(c, p)
            return self._format_profile(prof, requester=userid, users_repo=users_repo) if prof else f"ICH10004I PROFILE {p} NOT FOUND IN CLASS {c}"
        if u.startswith("PERMIT"):
            md = re.search(r"PERMIT\s+(.+?)\s+CLASS\(([^)]+)\)\s+ID\(([^)]+)\)\s+DELETE", raw, re.I)
            if md:
                return self.revoke(md.group(2), md.group(1).strip(), md.group(3))
            m = re.search(r"PERMIT\s+(.+?)\s+CLASS\(([^)]+)\)\s+ID\(([^)]+)\)\s+ACCESS\(([^)]+)\)", raw, re.I)
            if not m:
                return "ICH06010I PERMIT SYNTAX: PERMIT profile CLASS(class) ID(userid) ACCESS(access) | DELETE"
            return self.permit(m.group(2), m.group(1).strip(), m.group(3), m.group(4))
        if u.startswith("REVOKE"):
            m = re.search(r"REVOKE\s+(.+?)\s+CLASS\(([^)]+)\)\s+ID\(([^)]+)\)", raw, re.I)
            if not m:
                return "ICH06015I REVOKE SYNTAX: REVOKE profile CLASS(class) ID(userid)"
            return self.revoke(m.group(2), m.group(1).strip(), m.group(3))
        if u.startswith("SEARCH"):
            return self.search(raw, users_repo)
        if u.startswith("SETROPTS"):
            return self.setropts(raw)
        return None

    def setropts(self, raw: str) -> str:
        u = raw.upper()
        if u == "SETROPTS LIST":
            active = " ".join(sorted(k for k, v in self.raclist_active.items() if v)) or "NONE"
            return "\n".join([
                "PASSWORD PROCESSING OPTIONS:",
                "  PASSWORD CHANGE INTERVAL IS  90 DAYS.",
                "  PASSWORD MINIMUM CHANGE INTERVAL IS   1 DAYS.",
                "  MIXED CASE PASSWORD SUPPORT IS IN EFFECT",
                "  AFTER   6 CONSECUTIVE UNSUCCESSFUL PASSWORD ATTEMPTS,",
                "      A USERID WILL BE REVOKED.",
                "  PASSWORD EXPIRATION WARNING LEVEL IS   5 DAYS.",
                "SETROPTS RACLIST CLASSES: " + active,
                "SETROPTS CACHE SIMULATION: ACTIVE" if active != "NONE" else "SETROPTS CACHE SIMULATION: NOT ACTIVE",
                "ATTRIBUTES = INITSTATS WHEN(PROGRAM) SAUDIT CMDVIOL OPERAUDIT TERMINAL(NONE)",
                "PROTECT-ALL IS ACTIVE, CURRENT OPTIONS:",
                "  PROTECT-ALL FAIL OPTION IS IN EFFECT",
                "SPECIAL USERS ARE AUDITED",
                "OPERATIONS USERS ARE AUDITED",
            ])
        m = re.search(r"CLASSACT\(([^)]+)\)", u)
        if m:
            self.raclist_active[m.group(1).upper()] = True
            self.save()
            return f"ICH14064I CLASS {m.group(1).upper()} ACTIVATED"
        if u == "SETROPTS REFRESH":
            return self.refresh()
        m = re.search(r"RACLIST\(([^)]+)\)\s+REFRESH", u)
        if m:
            return self.refresh(m.group(1).upper())
        m = re.search(r"RACLIST\(([^)]+)\)", u)
        if m:
            clsname = m.group(1).upper(); self.raclist_active[clsname] = True
            self.save()
            return f"ICH14070I RACLIST PROCESSING COMPLETE FOR CLASS {clsname}"
        return "ICH14001I SETROPTS OPTION ACCEPTED BY GIBSON"

    def listdsd(self, raw: str, userid: str, users_repo=None) -> str:
        m = re.search(r"DATASET\('([^']+)'\)", raw, re.I) or re.search(r"LISTDSD\s+'?([^'\s]+)'?", raw, re.I)
        if not m:
            return "ICH13001I LISTDSD SYNTAX: LISTDSD DATASET('dataset') ALL"
        dsn = m.group(1).upper()
        prof = self._find_profile("DATASET", dsn) or self.define("DATASET", dsn, userid, "NONE")
        access = self.effective_access("DATASET", dsn, userid, users_repo)
        warn = "YES" if prof.warning else "NO"
        lines = [
            f"INFORMATION FOR DATASET {dsn}",
            "",
            "LEVEL  OWNER    UNIVERSAL ACCESS   WARNING   ERASE",
            "-----  -------- ----------------   -------   -----",
            f" 00    {prof.owner:<8} {prof.uacc:<16} {warn:<7} NO",
            "",
            "AUDITING",
            "--------",
            f"{prof.audit}",
            "",
            "NOTIFY",
            "--------",
            "NO USER TO BE NOTIFIED",
            "",
            "YOUR ACCESS  CREATION GROUP  DATASET TYPE",
            "-----------  --------------  ------------",
            f"{access:>8}        {getattr(users_repo.get(userid), 'default_group', 'SYS1') if users_repo and users_repo.get(userid) else 'SYS1':<8}   {prof.resource_type}",
            "",
            "ACCESS LIST",
            "-----------",
        ]
        if prof.permits:
            for ident, acc in sorted(prof.permits.items()):
                lines.append(f"{ident:<8} {acc}")
        else:
            lines.append("NO ENTRIES")
        lines.extend(["", "VOLUMES ON WHICH DATASET RESIDES", "--------------------------------", prof.volume])
        return "\n".join(lines)

    def search(self, raw: str, users_repo=None) -> str:
        u = raw.upper()
        if "ALL WARNING NOMASK" in u:
            rows = [p.name for profiles in self.profiles.values() for p in profiles.values() if p.warning]
            return "\n".join(sorted(rows)) if rows else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
        cm = re.search(r"CLASS\(([^)]+)\)", u)
        if cm:
            clsname = cm.group(1).upper()
            if clsname == "USER" and users_repo:
                if "UID(0)" in u:
                    rows = [x.userid for x in users_repo.users.values() if x.has_omvs and x.special]
                    return "\n".join(sorted(rows)) if rows else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
                return "\n".join(sorted(users_repo.users)) or "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
            filt = None
            fm = re.search(r"(?:FILTER|MASK)\(([^)]+)\)", u)
            if fm:
                filt = fm.group(1).upper()
            entries = self.profiles.get(clsname, {})
            rows = sorted(entries)
            if "WARNING" in u:
                rows = [r for r in rows if entries[r].warning]
            if filt:
                pat = filt.replace("**", "*")
                rows = [r for r in rows if fnmatch.fnmatch(r, pat)]
            return "\n".join(rows) if rows else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
        gm = re.search(r"GROUP\(([^)]+)\)", u)
        if gm:
            prefix = gm.group(1).upper()
            rows = [g for g in sorted(self.groups) if g.startswith(prefix)]
            return "\n".join(rows) if rows else "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"
        return "ICH31005I NO ENTRIES MEET SEARCH CRITERIA"

    def _format_group(self, group: RacfGroup | None) -> str:
        if not group:
            return "ICH30001I GROUP NOT FOUND"
        lines = [f"GROUP={group.name}  OWNER={group.owner} SUPGROUP={group.supgroup}", " CONNECTED USERS:"]
        for user, auth in sorted(group.users.items()):
            lines.append(f"  {user:<8} AUTHORITY={auth}")
        return "\n".join(lines)

    def _format_profile(self, prof: RacfProfile | None, requester: str = "", users_repo=None) -> str:
        if not prof:
            return "ICH10004I PROFILE NOT FOUND"
        your = self.effective_access(prof.class_name, prof.name, requester, users_repo)
        lines = [
            "CLASS      NAME",
            "-----      ----",
            f"{prof.class_name:<10} {prof.name}",
            "",
            "LEVEL  OWNER      UNIVERSAL ACCESS  YOUR ACCESS  WARNING",
            "-----  --------   ----------------  -----------  -------",
            f" 00    {prof.owner:<8}     {prof.uacc:<8}       {your:<8} {'YES' if prof.warning else 'NO'}",
            "",
            "AUDITING",
            "--------",
            prof.audit,
            "",
            "USER      ACCESS   ACCESS COUNT",
            "----      ------   ------------",
        ]
        if prof.permits:
            for ident, acc in sorted(prof.permits.items()):
                lines.append(f"{ident:<8}  {acc:<7} 000000")
        else:
            lines.append("NO USER TO BE NOTIFIED")
        if prof.class_name.upper() == "STARTED" and prof.attrs:
            lines.extend(["", "STDATA INFORMATION", "------------------"])
            lines.append(f"USER={prof.attrs.get('USER','')}".rstrip())
            lines.append(f"GROUP={prof.attrs.get('GROUP','')}".rstrip())
            lines.append(f"TRUSTED={prof.attrs.get('TRUSTED','NO')}".rstrip())
        if prof.attrs:
            lines.extend(["", "PROFILE ATTRIBUTES", "------------------"])
            for key, value in sorted(prof.attrs.items()):
                display = value
                if "KEY" in key.upper() and len(str(display)) > 4:
                    display = str(display)[:4] + "...MASKED"
                lines.append(f"{key:<14} {display}")
        return "\n".join(lines)
