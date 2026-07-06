from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import fnmatch
import hashlib
import json
import re
from typing import Optional

from gibson.core.racf import RacfRepository
from gibson.core.racf_dynamic import DynamicRacfStore, RacfGroup


_ACCESS_TO_SERVICE = {
    "NONE": "",
    "READ": "READ",
    "UPDATE": "READ,UPDATE",
    "CONTROL": "READ,UPDATE,DELETE",
    "ALTER": "READ,UPDATE,DELETE",
    "EXECUTE": "EXECUTE",
}

_SERVICE_TO_ACCESS = {
    "": "NONE",
    "READ": "READ",
    "UPDATE": "UPDATE",
    "READ,UPDATE": "UPDATE",
    "READ,UPDATE,DELETE": "ALTER",
    "ADD": "UPDATE",
    "DELETE": "CONTROL",
    "EXEC": "EXECUTE",
    "EXECUTE": "EXECUTE",
}

_RESOURCE_TYPE_TO_CLASS = {
    "FAC": "FACILITY",
    "SUR": "SURROGAT",
    "OPR": "OPERCMDS",
    "APL": "APPL",
    "VAR": "RACFVARS",
}

_CLASS_TO_RESOURCE_TYPE = {v: k for k, v in _RESOURCE_TYPE_TO_CLASS.items()}


@dataclass
class Acf2Context:
    setting: str = "LID"
    division: str = ""
    profile_type: str = ""
    resource_type: str = ""


@dataclass
class Acf2MetaStore:
    path: Path
    users: dict[str, dict[str, object]] = field(default_factory=dict)
    groups: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Acf2MetaStore":
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return cls(p, {k.upper(): v for k, v in (data.get("users") or {}).items()}, {k.upper(): v for k, v in (data.get("groups") or {}).items()})
            except Exception:
                pass
        return cls(p)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"users": self.users, "groups": self.groups}, indent=2, sort_keys=True), encoding="utf-8")

    def _stable_num(self, seed: str, base: int = 10000, mod: int = 50000) -> int:
        digest = hashlib.sha1(seed.upper().encode("utf-8")).hexdigest()[:8]
        return base + (int(digest, 16) % mod)

    def uid_for(self, userid: str, users_repo: RacfRepository) -> int:
        uid = self.users.get(userid.upper(), {}).get("uid")
        if isinstance(uid, int):
            return uid
        user = users_repo.get(userid)
        if user and user.special and user.has_omvs:
            return 0
        return self._stable_num(userid, base=1000, mod=60000)

    def gid_for(self, group: str) -> int:
        gid = self.groups.get(group.upper(), {}).get("gid")
        if isinstance(gid, int):
            return gid
        if group.upper() == "SYS1":
            return 0
        return self._stable_num(group, base=2000, mod=60000)

    def ensure_user(self, userid: str, *, uid: int | None = None, home: str | None = None, program: str | None = None, no_omvs: bool | None = None, group: str | None = None) -> None:
        rec = dict(self.users.get(userid.upper(), {}))
        if uid is not None:
            rec["uid"] = int(uid)
        if home is not None:
            rec["home"] = home
        if program is not None:
            rec["program"] = program
        if no_omvs is not None:
            rec["no_omvs"] = bool(no_omvs)
        if group is not None:
            rec["group"] = group.upper()
        self.users[userid.upper()] = rec
        self.save()

    def ensure_group(self, group: str, *, gid: int | None = None) -> None:
        rec = dict(self.groups.get(group.upper(), {}))
        if gid is not None:
            rec["gid"] = int(gid)
        self.groups[group.upper()] = rec
        self.save()

    def user_home(self, userid: str) -> str:
        return str(self.users.get(userid.upper(), {}).get("home") or f"/u/{userid.lower()}")

    def user_program(self, userid: str) -> str:
        return str(self.users.get(userid.upper(), {}).get("program") or "/bin/sh")

    def user_group(self, userid: str, users_repo: RacfRepository) -> str:
        group = self.users.get(userid.upper(), {}).get("group")
        if group:
            return str(group).upper()
        user = users_repo.get(userid)
        return (user.default_group if user and user.default_group else "SYS1").upper()

    def user_no_omvs(self, userid: str, users_repo: RacfRepository) -> bool:
        if userid.upper() in self.users and "no_omvs" in self.users[userid.upper()]:
            return bool(self.users[userid.upper()]["no_omvs"])
        user = users_repo.get(userid)
        return not bool(user and user.has_omvs)


class Acf2Bridge:
    def __init__(self, state, requester: str):
        self.state = state
        self.requester = requester.upper()
        self.context = Acf2Context()
        self.meta = Acf2MetaStore.load(Path(state.config.sim_root) / "acf2_meta.json")

    def activate(self) -> str:
        self.context = Acf2Context()
        return (
            "ACF2 MODE ACTIVE\n"
            "CURRENT SETTING: LID\n"
            "USE SET LID, SET RULE, SET RESOURCE(type), SET CONTROL(GSO), OR SET PROFILE(GROUP) DIV(OMVS)."
        )

    def banner_racf(self) -> str:
        return "RACF MODE ACTIVE"

    def help_text(self) -> str:
        return "\n".join([
            "ACF2 COMMANDS AVAILABLE IN GIBSON",
            " SET LID                              Logonid processing",
            " SET PROFILE(GROUP) DIV(OMVS)         OMVS group profiles",
            " SET RULE                             Data set access rules",
            " SET RESOURCE(FAC|SUR|OPR|APL|VAR)    Resource rules",
            " SET CONTROL(GSO)                     GSO/SHOW commands",
            " LIST userid | LIST LIKE(-)           List current setting entries",
            " INSERT userid PASSWORD(pw) ...       Insert logonid in LID mode",
            " CHANGE userid ...                    Change logonid in LID mode",
            " DELETE userid                        Delete current setting entry",
            " RECKEY key ADD( ... )                Add rule lines in RULE/RESOURCE mode",
            " SHOW ACF2 | SHOW TSO | SHOW PSWD     Display ACF2 options",
            " SHOW DDSN                            Show active ACF2 data sets",
            " ACCESS DSNAME('dsn')                 Show matching data set rule access",
            " ACCESS RESOURCE(name) TYPE(type)     Show matching resource rule access",
            " TEST DSNAME('dsn') LID(userid) SERVICE(READ)      Test a data set access",
            " TEST key RSRCNAME('name') LID(userid) SERVICE(READ)  Test a resource access",
            " END | QUIT                           Reset ACF2 setting to LID",
            " RACF                                 Return to RACF command mode",
        ])

    def command(self, raw: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> Optional[str]:
        cmd = (raw or "").strip()
        if not cmd:
            return None
        upper = cmd.upper()
        first = upper.split()[0]
        if first not in {"SET", "SHOW", "LIST", "INSERT", "CHANGE", "DELETE", "ACCESS", "TEST", "RECKEY", "END", "QUIT", "HELP", "?", "ROLES"}:
            return None
        if upper in {"HELP", "?"}:
            return self.help_text()
        if first in {"END", "QUIT"}:
            self.context = Acf2Context()
            return "ACF2 COMMAND SETTING RESET TO LID"
        if first == "SET":
            return self._set(cmd)
        if first == "SHOW":
            return self._show(cmd, users_repo)
        if first == "LIST":
            return self._list(cmd, users_repo, dynamic_racf)
        if first == "INSERT":
            return self._insert(cmd, users_repo, dynamic_racf)
        if first == "CHANGE":
            return self._change(cmd, users_repo, dynamic_racf)
        if first == "DELETE":
            return self._delete(cmd, users_repo, dynamic_racf)
        if first == "ACCESS":
            return self._access(cmd, users_repo, dynamic_racf)
        if first == "TEST":
            return self._test(cmd, users_repo, dynamic_racf)
        if first == "RECKEY":
            return self._reckey(cmd, users_repo, dynamic_racf)
        if first == "ROLES":
            return self._roles(cmd, dynamic_racf)
        return None

    def _is_security_admin(self, users_repo: RacfRepository) -> bool:
        user = users_repo.get(self.requester)
        return bool(user and user.special)

    def _deny_field(self, field: str = "COMMAND") -> str:
        return f"ACF00103 NOT AUTHORIZED TO CHANGE FIELD {field.upper()}"

    def _deny_function(self) -> str:
        return "ACF04017 NOT AUTHORIZED FOR REQUESTED FUNCTION"

    def _set(self, cmd: str) -> str:
        upper = cmd.upper()
        if re.fullmatch(r"SET\s+(ACF|LID)", upper):
            self.context = Acf2Context(setting="LID")
            return "LID SETTING ACTIVE"
        m = re.fullmatch(r"SET\s+(?:CONTROL|C)\(([^)]+)\)", upper)
        if m:
            self.context = Acf2Context(setting="CONTROL", profile_type=m.group(1).upper())
            return f"CONTROL({self.context.profile_type}) SETTING ACTIVE"
        m = re.fullmatch(r"SET\s+(?:PROFILE|P)\(([^)]+)\)(?:\s+DIV\(([^)]+)\))?", upper)
        if m:
            self.context = Acf2Context(setting="PROFILE", profile_type=m.group(1).upper(), division=(m.group(2) or "").upper())
            div = f" DIV({self.context.division})" if self.context.division else ""
            return f"PROFILE({self.context.profile_type}){div} SETTING ACTIVE"
        m = re.fullmatch(r"SET\s+(?:RESOURCE|R)\(([^)]+)\)", upper)
        if m:
            self.context = Acf2Context(setting="RESOURCE", resource_type=m.group(1).upper())
            return f"RESOURCE({self.context.resource_type}) SETTING ACTIVE"
        if upper == "SET RULE":
            self.context = Acf2Context(setting="RULE")
            return "RULE SETTING ACTIVE"
        if upper == "SET XREF(ROL)":
            self.context = Acf2Context(setting="XREF", profile_type="ROL")
            return "XREF(ROL) SETTING ACTIVE"
        return "INVALID SET SUBCOMMAND"

    def _show(self, cmd: str, users_repo: RacfRepository) -> str:
        upper = cmd.upper().strip()
        if not self._is_security_admin(users_repo) and upper not in {"SHOW MODE", "SHOW OMVS"} and not upper.startswith("SHOW OMVS"):
            return self._deny_function()
        if upper in {"SHOW MODE", "SHOW MOD"}:
            parts = [self.context.setting]
            if self.context.profile_type:
                parts.append(self.context.profile_type)
            if self.context.division:
                parts.append(self.context.division)
            if self.context.resource_type:
                parts.append(self.context.resource_type)
            return "ACF2 CURRENT SETTING: " + " ".join(parts)
        if upper in {"SHOW ACF2", "SHOW ALL"}:
            return "\n".join([
                "-- ACF2 SYSTEM PARAMETERS ACTIVE --",
                f"LOGONIDS={len(users_repo.users):04d}  GROUPS={len(self.state.dynamic_racf.groups):04d}",
                f"RULE SETS={sum(len(v) for v in self.state.dynamic_racf.profiles.values()):04d}",
                "DEFAULT MODE=ABORT  UID STRING PROCESSING=ACTIVE",
                "COMMAND PROPAGATION=SIMULATED  INFOSTG=ACTIVE",
                "SHOW TSO, SHOW PSWD, SHOW DDSN AVAILABLE",
            ])
        if upper == "SHOW TSO":
            return "\n".join([
                "-- TSO RELATED DEFAULTS ACTIVE --",
                "LOGON ACCOUNT STRING=NONE  CMD LIST BYPASS CHAR=#     CHAR DELETE CHAR=NO",
                "TSO CMD LIST=NONE          COMMAND SMF RECORDS=YES    TSOGNAME=NONE",
                "LINE DELETE CHAR=NONE      LOGON CHECK=YES           PERFORMANCE GROUP=NONE",
                "TSO LOGON PROC=IKJACCNT    QUICK LOGON=YES           TSO REGION SIZE=NONE",
                "SUBMIT CLASS=NONE          SUBMIT HOLD CLASS=NONE    SUBMIT MESSAGE CLASS=NONE",
            ])
        if upper in {"SHOW PSWD", "SHOW PSWDOPTS"}:
            return "\n".join([
                "PASSWORD (PSWD) OPTIONS IN EFFECT:",
                "  PSWDLMT=005   PSWDMAX=090   MINDAYS=001",
                "  MIXED CASE PASSWORDS=YES   PASSWORD HISTORY=SIMULATED",
                "  PASSWORD PHRASE LOGON=YES  PASSWORD PHRASE SUPPORT=YES",
                "  REVOKE ON EXCESSIVE FAILURES=YES",
            ])
        if upper == "SHOW DDSN":
            return "\n".join([
                "ACF2 DATABASE DATA SET NAMES IN EFFECT",
                f" LOGONID DB  : {self.state.config.gacf_path}",
                f" RULE DB     : {Path(self.state.config.sim_root) / 'racf_dynamic.json'}",
                f" INFOSTG DB  : {Path(self.state.config.sim_root) / 'acf2_meta.json'}",
            ])
        if upper.startswith("SHOW OMVS"):
            return self._show_omvs(cmd, users_repo)
        return "SHOW SUBCOMMAND NOT IMPLEMENTED"

    def _show_omvs(self, cmd: str, users_repo: RacfRepository) -> str:
        upper = cmd.upper()
        m = re.search(r"USER\(([^)]+)\)", upper)
        if m:
            userid = m.group(1).upper()
            if not users_repo.exists(userid):
                return f"LOGONID {userid} NOT FOUND"
            return self._format_lid(users_repo.get(userid), users_repo, short=False, omvs_only=True)
        m = re.search(r"GROUP\(([^)]+)\)", upper)
        if m:
            gid = m.group(1)
            try:
                gid_num = int(gid)
            except ValueError:
                gid_num = -1
            rows = [g for g in sorted(self.state.dynamic_racf.groups) if self.meta.gid_for(g) == gid_num]
            return "\n".join(rows) if rows else f"NO GROUP FOR GID {gid}"
        rows = []
        for user in sorted(users_repo.users):
            if self.meta.user_no_omvs(user, users_repo):
                continue
            rows.append(f"{user:<8} UID({self.meta.uid_for(user, users_repo)}) GROUP({self.meta.user_group(user, users_repo)}) HOME({self.meta.user_home(user)})")
        return "\n".join(rows) if rows else "NO OMVS USERS FOUND"

    def _list(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        arg = cmd[4:].strip()
        if self.context.setting == "LID":
            return self._list_lid(arg, users_repo, dynamic_racf)
        if self.context.setting == "PROFILE" and self.context.profile_type == "GROUP":
            return self._list_group(arg, users_repo, dynamic_racf)
        if self.context.setting == "RULE":
            return self._list_rules(arg, dynamic_racf, dataset_mode=True)
        if self.context.setting == "RESOURCE":
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(self.context.resource_type, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {self.context.resource_type}"
            return self._list_rules(arg, dynamic_racf, dataset_mode=False, racf_class=racf_class)
        if self.context.setting == "XREF" and self.context.profile_type == "ROL":
            return self._list_roles(arg, dynamic_racf)
        return "LIST NOT VALID UNDER CURRENT SETTING"

    def _list_lid(self, arg: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        upper = arg.upper()
        section_m = re.search(r"SECTION\(([^)]+)\)", upper)
        section = section_m.group(1).upper() if section_m else ""
        if upper.startswith("UID("):
            uid_val = upper[4:-1] if upper.endswith(")") else upper[4:upper.find(")")]
            rows = []
            for user in sorted(users_repo.users):
                user_uid = str(self.meta.uid_for(user, users_repo))
                if uid_val == "0" and user_uid == "0":
                    rows.append(user)
                elif fnmatch.fnmatch(user_uid, uid_val.replace("-", "*")):
                    rows.append(user)
            return "\n".join(rows) if rows else "NO LOGONIDS MATCH CRITERIA"
        if upper.startswith("LIKE("):
            mask = arg[arg.find("(") + 1: arg.find(")")].strip().upper().replace("-", "*")
            rows = [u for u in sorted(users_repo.users) if fnmatch.fnmatch(u, mask)]
            if section == "PASSWORD":
                return "\n".join(self._format_password_section(users_repo.get(u)) for u in rows if users_repo.get(u)) or "NO LOGONIDS MATCH CRITERIA"
            return "\n".join(self._format_lid(users_repo.get(u), users_repo, short=True) for u in rows if users_repo.get(u)) or "NO LOGONIDS MATCH CRITERIA"
        if upper in {"*", ""}:
            rows = [self._format_lid(users_repo.get(u), users_repo, short=True) for u in sorted(users_repo.users)]
            return "\n".join(rows)
        target = arg.split()[0].upper()
        user = users_repo.get(target)
        if not user:
            return f"LOGONID {target} NOT FOUND"
        if section == "PASSWORD":
            return self._format_password_section(user)
        return self._format_lid(user, users_repo, short=False)

    def _list_group(self, arg: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        upper = arg.upper().strip()
        if not upper or upper == "*" or upper.startswith("LIKE("):
            if upper.startswith("LIKE("):
                mask = upper[5:upper.find(")")].replace("-", "*")
                names = [g for g in sorted(dynamic_racf.groups) if fnmatch.fnmatch(g, mask)]
            else:
                names = sorted(dynamic_racf.groups)
            return "\n\n".join(self._format_group(n, users_repo, dynamic_racf) for n in names) if names else "NO GROUP PROFILES MATCH CRITERIA"
        return self._format_group(upper.split()[0], users_repo, dynamic_racf)

    def _list_roles(self, arg: str, dynamic_racf: DynamicRacfStore) -> str:
        target = (arg or "").strip().upper()
        if not target:
            return "ROLES userid"
        groups = dynamic_racf.connected_groups(target)
        if not groups:
            return f"NO ROLES FOUND FOR {target}"
        return "\n".join(f"{target} ROLE({g})" for g in groups)

    def _insert(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if self.context.setting == "LID":
            return self._insert_lid(cmd, users_repo, dynamic_racf)
        if self.context.setting == "PROFILE" and self.context.profile_type == "GROUP":
            return self._insert_group(cmd, dynamic_racf)
        if self.context.setting == "RULE":
            return self._insert_rule(cmd, dynamic_racf, dataset_mode=True)
        if self.context.setting == "RESOURCE":
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(self.context.resource_type, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {self.context.resource_type}"
            return self._insert_rule(cmd, dynamic_racf, dataset_mode=False, racf_class=racf_class)
        return "INSERT NOT VALID UNDER CURRENT SETTING"

    def _change(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if self.context.setting == "LID":
            return self._change_lid(cmd, users_repo, dynamic_racf)
        if self.context.setting == "PROFILE" and self.context.profile_type == "GROUP":
            return self._change_group(cmd, dynamic_racf)
        if self.context.setting in {"RULE", "RESOURCE"}:
            return self._change_rule(cmd, dynamic_racf)
        return "CHANGE NOT VALID UNDER CURRENT SETTING"

    def _delete(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if not self._is_security_admin(users_repo):
            return self._deny_function()
        arg = cmd[6:].strip()
        target = arg.split()[0].upper() if arg else ""
        if self.context.setting == "LID":
            if not target:
                return "DELETE logonid"
            if target == self.requester:
                return "DELETE OF CURRENT LOGONID NOT PERMITTED"
            if not users_repo.exists(target):
                return f"LOGONID {target} NOT FOUND"
            users_repo.deleteuser(target)
            for group in dynamic_racf.groups.values():
                group.users.pop(target, None)
            dynamic_racf.save()
            self.meta.users.pop(target, None)
            self.meta.save()
            return f"LOGONID {target} DELETED"
        if self.context.setting == "PROFILE" and self.context.profile_type == "GROUP":
            if not target:
                return "DELETE group"
            dynamic_racf.groups.pop(target, None)
            dynamic_racf.save()
            self.meta.groups.pop(target, None)
            self.meta.save()
            return f"GROUP PROFILE {target} DELETED"
        if self.context.setting == "RULE":
            dsn = self._dataset_name(target)
            dynamic_racf.profiles.get("DATASET", {}).pop(dsn, None)
            dynamic_racf.save()
            return f"RULE SET {dsn} DELETED"
        if self.context.setting == "RESOURCE":
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(self.context.resource_type, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {self.context.resource_type}"
            profile = target
            dynamic_racf.profiles.get(racf_class, {}).pop(profile, None)
            dynamic_racf.save()
            return f"RESOURCE RULE {profile} TYPE({self.context.resource_type}) DELETED"
        return "DELETE NOT VALID UNDER CURRENT SETTING"

    def _access(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        upper = cmd.upper()
        m = re.search(r"DSNAME\('([^']+)'\)", cmd, re.I)
        if m:
            dsn = self._dataset_name(m.group(1))
            prof = dynamic_racf._find_profile("DATASET", dsn)
            return self._format_access_result(dsn, prof, users_repo, dynamic_racf, dataset_mode=True)
        m = re.search(r"RESOURCE\(([^)]+)\)\s+TYPE\(([^)]+)\)", upper)
        if m:
            name, typ = m.group(1).upper(), m.group(2).upper()
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(typ, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {typ}"
            prof = dynamic_racf._find_profile(racf_class, name)
            return self._format_access_result(name, prof, users_repo, dynamic_racf, dataset_mode=False, typecode=typ)
        return "ACCESS DSNAME('dataset') OR ACCESS RESOURCE(name) TYPE(type)"

    def _test(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        upper = cmd.upper()
        lid_m = re.search(r"LID\(([^)]+)\)", upper)
        svc_m = re.search(r"SERVICE\(([^)]+)\)", upper)
        ident = lid_m.group(1).upper() if lid_m else self.requester
        service = self._service_to_access(svc_m.group(1) if svc_m else "READ")
        ds_m = re.search(r"DSNAME\('([^']+)'\)", cmd, re.I)
        if ds_m:
            dsn = self._dataset_name(ds_m.group(1))
            ok = dynamic_racf.has_access("DATASET", dsn, ident, service, users_repo)
            return f"TEST DSNAME('{dsn}') LID({ident}) SERVICE({service}) {'ALLOW' if ok else 'PREVENT'}"
        rsrc_m = re.search(r"RSRCNAME\('([^']+)'\)", cmd, re.I)
        if rsrc_m and self.context.setting == "RESOURCE":
            typ = self.context.resource_type
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(typ, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {typ}"
            name = rsrc_m.group(1).upper()
            ok = dynamic_racf.has_access(racf_class, name, ident, service, users_repo)
            return f"TEST TYPE({typ}) RSRCNAME('{name}') LID({ident}) SERVICE({service}) {'ALLOW' if ok else 'PREVENT'}"
        return "TEST DSNAME('dataset') LID(userid) SERVICE(READ) OR SET RESOURCE(type) + TEST ... RSRCNAME('resource')"

    def _reckey(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if not self._is_security_admin(users_repo):
            return self._deny_function()
        if self.context.setting not in {"RULE", "RESOURCE"}:
            return "RECKEY VALID ONLY IN RULE OR RESOURCE SETTINGS"
        m = re.match(r"RECKEY\s+([^\s]+)\s+ADD\((.+)\)\s*$", cmd, re.I)
        if not m:
            return "RECKEY key ADD( resource UID(id) SERVICE(READ) ALLOW )"
        key = m.group(1).strip("'\"").upper()
        body = m.group(2)
        uid_m = re.search(r"UID\(([^)]+)\)", body, re.I)
        svc_m = re.search(r"SERVICE\(([^)]+)\)", body, re.I)
        action = "ALLOW"
        if re.search(r"\bPREVENT\b", body, re.I):
            action = "PREVENT"
        elif re.search(r"\bLOG\b", body, re.I):
            action = "LOG"
        ident = uid_m.group(1).strip().upper() if uid_m else "*"
        access = self._service_to_access(svc_m.group(1) if svc_m else "READ")
        body2 = re.sub(r"UID\([^)]+\)", "", body, flags=re.I)
        body2 = re.sub(r"SERVICE\([^)]+\)", "", body2, flags=re.I)
        body2 = re.sub(r"\b(ALLOW|LOG|PREVENT)\b", "", body2, flags=re.I).strip()
        resource = body2.split()[0].strip("'\"") if body2 else ""
        if self.context.setting == "RULE":
            profile = self._compose_dataset_from_key_resource(key, resource)
            prof = dynamic_racf._find_profile("DATASET", profile) or dynamic_racf.define("DATASET", profile, self.requester, "NONE")
        else:
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(self.context.resource_type, "")
            if not racf_class:
                return f"UNKNOWN RESOURCE TYPE {self.context.resource_type}"
            profile = resource.upper() if resource else key
            prof = dynamic_racf._find_profile(racf_class, profile) or dynamic_racf.define(racf_class, profile, self.requester, "NONE")
        if ident == "*":
            prof.uacc = access if action != "PREVENT" else "NONE"
        else:
            prof.permits[ident] = access if action != "PREVENT" else "NONE"
        dynamic_racf.save()
        mode = "DATA SET" if self.context.setting == "RULE" else f"RESOURCE {self.context.resource_type}"
        return f"RECKEY {key} {mode} RULE LINE STORED FOR {profile} UID({ident}) {action}"

    def _roles(self, cmd: str, dynamic_racf: DynamicRacfStore) -> str:
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "ROLES userid"
        user = parts[1].strip().upper()
        groups = dynamic_racf.connected_groups(user)
        return "\n".join(f"{user} ROLE({group})" for group in groups) if groups else f"NO ROLES FOR {user}"

    def _insert_lid(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if not self._is_security_admin(users_repo):
            return self._deny_field("LOGONID")
        parts = cmd.split()
        if len(parts) < 2:
            return "INSERT logonid PASSWORD(pw) [SECURITY] [GROUP(group)] [UID(uid)]"
        userid = parts[1].upper()
        pw_m = re.search(r"PASSWORD\(([^)]*)\)", cmd, re.I)
        password = pw_m.group(1) if pw_m else userid
        special = bool(re.search(r"(?:^|\s)SECURITY(?:\s|$)", cmd.upper()))
        no_special = bool(re.search(r"(?:^|\s)NOSECURITY(?:\s|$)", cmd.upper()))
        if no_special:
            special = False
        group_m = re.search(r"GROUP\(([^)]+)\)", cmd, re.I)
        group = group_m.group(1).upper() if group_m else "SYS1"
        uid_m = re.search(r"UID\(([^)]+)\)", cmd, re.I)
        uid = int(uid_m.group(1)) if uid_m and uid_m.group(1).isdigit() else None
        home_m = re.search(r"HOME\(([^)]+)\)", cmd, re.I)
        home = home_m.group(1).strip("'\"") if home_m else f"/u/{userid.lower()}"
        prog_m = re.search(r"(?:OMVSPGM|PROGRAM)\(([^)]+)\)", cmd, re.I)
        program = prog_m.group(1).strip("'\"") if prog_m else "/bin/sh"
        no_omvs = bool(re.search(r"NO-OMVS|NONO-OMVS|NOOMVS", cmd.upper()))
        omvs = not no_omvs and (uid is not None or home_m is not None or prog_m is not None or bool(re.search(r"\bOMVS\b", cmd.upper())))
        if group not in dynamic_racf.groups:
            dynamic_racf.groups.setdefault(group, RacfGroup(group, self.requester, 'SYS1'))
        out = users_repo.adduser(userid, password, special=special, omvs=omvs, default_group=group)
        dynamic_racf.connect_user(userid, group, "USE")
        self.meta.ensure_user(userid, uid=uid, home=home, program=program, no_omvs=not omvs, group=group)
        self.meta.ensure_group(group)
        return out.replace("ICH01003I USERID", "LOGONID") if out.startswith("ICH01003I") else out

    def _change_lid(self, cmd: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        if not self._is_security_admin(users_repo):
            return self._deny_field("LOGONID")
        parts = cmd.split()
        if len(parts) < 2:
            return "CHANGE logonid PASSWORD(pw) [SECURITY|NOSECURITY] [GROUP(group)] [UID(uid)]"
        userid = parts[1].upper()
        if not users_repo.exists(userid):
            return f"LOGONID {userid} NOT FOUND"
        pw_m = re.search(r"PASSWORD\(([^)]*)\)", cmd, re.I)
        password = pw_m.group(1) if pw_m else None
        text_u = " " + cmd.upper() + " "
        special = True if " SECURITY " in text_u and " NOSECURITY " not in text_u else False if " NOSECURITY " in text_u else None
        group_m = re.search(r"GROUP\(([^)]+)\)", cmd, re.I)
        group = group_m.group(1).upper() if group_m else None
        uid_m = re.search(r"UID\(([^)]+)\)", cmd, re.I)
        uid = int(uid_m.group(1)) if uid_m and uid_m.group(1).isdigit() else None
        home_m = re.search(r"HOME\(([^)]+)\)", cmd, re.I)
        home = home_m.group(1).strip("'\"") if home_m else None
        prog_m = re.search(r"(?:OMVSPGM|PROGRAM)\(([^)]+)\)", cmd, re.I)
        program = prog_m.group(1).strip("'\"") if prog_m else None
        if re.search(r"NO-OMVS|NONO-OMVS|NOOMVS", cmd.upper()):
            omvs = False
        elif uid_m or home_m or prog_m or re.search(r"\bOMVS\b", cmd.upper()):
            omvs = True
        else:
            omvs = None
        no_group_m = re.search(r"NOGROUP\(([^)]+)\)", cmd, re.I)
        no_group = no_group_m.group(1).upper() if no_group_m else None
        out = users_repo.altuser(userid, password=password, special=special, omvs=omvs, default_group=group)
        if group:
            dynamic_racf.connect_user(userid, group, "USE")
            self.meta.ensure_group(group)
        if no_group and no_group in dynamic_racf.groups:
            dynamic_racf.groups[no_group].users.pop(userid, None)
            dynamic_racf.save()
        self.meta.ensure_user(userid, uid=uid, home=home, program=program, no_omvs=(False if omvs else True) if omvs is not None else None, group=group)
        return out.replace("ICH01006I USERID", "LOGONID") if out.startswith("ICH01006I") else out

    def _insert_group(self, cmd: str, dynamic_racf: DynamicRacfStore) -> str:
        user = self.state.racf.get(self.requester)
        if not (user and user.special):
            return self._deny_field("GROUP")
        parts = cmd.split()
        if len(parts) < 2:
            return "INSERT group GID(n)"
        group = parts[1].upper()
        gid_m = re.search(r"(?:GID|AUTOGID)\(([^)]+)\)", cmd, re.I)
        gid = int(gid_m.group(1)) if gid_m and gid_m.group(1).isdigit() else None
        dynamic_racf.groups.setdefault(group, RacfGroup(group, self.requester, 'SYS1'))
        dynamic_racf.save()
        self.meta.ensure_group(group, gid=gid)
        return f"GROUP PROFILE {group} STORED"

    def _change_group(self, cmd: str, dynamic_racf: DynamicRacfStore) -> str:
        user = self.state.racf.get(self.requester)
        if not (user and user.special):
            return self._deny_field("GROUP")
        parts = cmd.split()
        if len(parts) < 2:
            return "CHANGE group GID(n)"
        group = parts[1].upper()
        if group not in dynamic_racf.groups:
            return f"GROUP PROFILE {group} NOT FOUND"
        gid_m = re.search(r"GID\(([^)]+)\)", cmd, re.I)
        gid = int(gid_m.group(1)) if gid_m and gid_m.group(1).isdigit() else None
        self.meta.ensure_group(group, gid=gid)
        return f"GROUP PROFILE {group} CHANGED"

    def _insert_rule(self, cmd: str, dynamic_racf: DynamicRacfStore, *, dataset_mode: bool, racf_class: str = "") -> str:
        user = self.state.racf.get(self.requester)
        if not (user and user.special):
            return self._deny_function()
        parts = cmd.split()
        if len(parts) < 2:
            return "INSERT profile-name"
        profile = parts[1].strip("'\"").upper()
        if dataset_mode:
            dsn = self._dataset_name(profile)
            dynamic_racf.define("DATASET", dsn, self.requester, "NONE")
            dynamic_racf.save()
            return f"RULE SET {dsn} STORED"
        dynamic_racf.define(racf_class, profile, self.requester, "NONE")
        dynamic_racf.save()
        return f"RESOURCE RULE {profile} TYPE({self.context.resource_type}) STORED"

    def _change_rule(self, cmd: str, dynamic_racf: DynamicRacfStore) -> str:
        user = self.state.racf.get(self.requester)
        if not (user and user.special):
            return self._deny_function()
        parts = cmd.split()
        if len(parts) < 2:
            return "CHANGE profile [ALLOW|LOG|PREVENT] ..."
        target = parts[1].strip("'\"").upper()
        warning = None
        if re.search(r"\bLOG\b", cmd.upper()):
            warning = True
        if re.search(r"\bNOLOG\b", cmd.upper()):
            warning = False
        if self.context.setting == "RULE":
            dsn = self._dataset_name(target)
            prof = dynamic_racf._find_profile("DATASET", dsn)
            if not prof:
                return f"RULE SET {dsn} NOT FOUND"
        else:
            racf_class = _RESOURCE_TYPE_TO_CLASS.get(self.context.resource_type, "")
            prof = dynamic_racf._find_profile(racf_class, target)
            if not prof:
                return f"RESOURCE RULE {target} NOT FOUND"
        uacc_m = re.search(r"UACC\(([^)]+)\)", cmd, re.I)
        if uacc_m:
            prof.uacc = uacc_m.group(1).upper()
        if warning is not None:
            prof.warning = warning
        dynamic_racf.save()
        return f"RULE {prof.name} CHANGED"

    def _format_password_section(self, user) -> str:
        if not user:
            return ""
        masked = "ENCRYPTED" if str(user.password).startswith("$1$") else "CLEAR"
        return f"{user.userid:<8} PASSWORD({masked}) PASSDATE(25.020) MAXDAYS(090)"

    def _format_lid(self, user, users_repo: RacfRepository, *, short: bool = False, omvs_only: bool = False) -> str:
        if not user:
            return ""
        attrs = {a.upper() for a in user.attributes}
        flags = []
        if "SPECIAL" in attrs:
            flags.append("SECURITY")
        else:
            flags.append("NOSECURITY")
        flags.append("TSO")
        flags.append("NON-CNCL")
        no_omvs = self.meta.user_no_omvs(user.userid, users_repo)
        if no_omvs:
            flags.append("NO-OMVS")
        group = self.meta.user_group(user.userid, users_repo)
        uid = self.meta.uid_for(user.userid, users_repo)
        home = self.meta.user_home(user.userid)
        program = self.meta.user_program(user.userid)
        if short:
            base = f"{user.userid:<8} NAME({user.userid}) GROUP({group}) {' '.join(flags)}"
            if not no_omvs:
                base += f" UID({uid})"
            return base
        lines = [
            f"{user.userid} NAME({user.userid}) GROUP({group}) {' '.join(flags)}",
        ]
        if not no_omvs:
            lines.append(f"{user.userid} UID({uid}) HOME({home}) OMVSPGM({program})")
        if omvs_only:
            return "\n".join(lines[1:] if len(lines) > 1 else lines)
        return "\n".join(lines)

    def _format_group(self, group: str, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore) -> str:
        g = dynamic_racf.groups.get(group.upper())
        if not g:
            return f"GROUP PROFILE {group.upper()} NOT FOUND"
        lines = [f"{g.name} GID({self.meta.gid_for(g.name)}) OWNER({g.owner}) SUPGROUP({g.supgroup})"]
        members = sorted(g.users)
        if members:
            lines.append("MEMBERS")
            for user in members:
                lines.append(f"  {user} AUTH({g.users[user]})")
        return "\n".join(lines)

    def _list_rules(self, arg: str, dynamic_racf: DynamicRacfStore, *, dataset_mode: bool, racf_class: str = "") -> str:
        upper = (arg or "").upper().strip()
        if dataset_mode:
            clsname = "DATASET"
            typecode = "DSN"
        else:
            clsname = racf_class
            typecode = self.context.resource_type
        profiles = dynamic_racf.profiles.get(clsname, {})
        if not upper or upper == "*" or upper == "LIKE(-)":
            names = sorted(profiles)
        elif upper.startswith("LIKE("):
            mask = upper[5:upper.find(")")].replace("-", "*")
            names = [n for n in sorted(profiles) if fnmatch.fnmatch(n, mask)]
        else:
            target = upper.split()[0].strip("'\"")
            if dataset_mode:
                target = self._dataset_name(target)
            names = [n for n in sorted(profiles) if n == target or fnmatch.fnmatch(n, target.replace("-", "*"))]
        if not names:
            return "NO RULES MATCH CRITERIA"
        return "\n\n".join(self._format_rule_set(profiles[n], dataset_mode=dataset_mode, typecode=typecode) for n in names)

    def _format_rule_set(self, prof, *, dataset_mode: bool, typecode: str) -> str:
        name = prof.name.upper()
        if dataset_mode:
            key, _, remainder = name.partition('.')
            resource = remainder or name
        else:
            key = name.split('.', 1)[0]
            resource = name
        lines = [f"$KEY({key})" + ("" if dataset_mode else f" TYPE({typecode})")]
        if prof.permits:
            for ident, access in sorted(prof.permits.items()):
                service = _ACCESS_TO_SERVICE.get(access.upper(), "READ")
                if service:
                    lines.append(f"{resource} UID({ident}) SERVICE({service}) ALLOW")
                else:
                    lines.append(f"{resource} UID({ident}) PREVENT")
        if prof.uacc != "NONE":
            service = _ACCESS_TO_SERVICE.get(prof.uacc.upper(), "READ")
            lines.append(f"{resource} UID(*) SERVICE({service}) ALLOW")
        else:
            lines.append(f"{resource} UID(*) PREVENT")
        return "\n".join(lines)

    def _format_access_result(self, name: str, prof, users_repo: RacfRepository, dynamic_racf: DynamicRacfStore, *, dataset_mode: bool, typecode: str = "") -> str:
        title = name.upper()
        if not prof:
            return f"ACCESS SUBCOMMAND RESULTS FOR: {title}\n\nNO MATCHING RULES"
        lines = [f"ACCESS SUBCOMMAND RESULTS FOR: {title}", ""]
        if dataset_mode:
            key = title.split('.', 1)[0]
        else:
            key = title.split('.', 1)[0]
        lines.append(f"Key: {key}")
        for ident, access in sorted(prof.permits.items()):
            service = _ACCESS_TO_SERVICE.get(access.upper(), "READ")
            lines.append(f" {title} UID({ident}) SERVICE({service}) ALLOW")
        if prof.uacc != "NONE":
            service = _ACCESS_TO_SERVICE.get(prof.uacc.upper(), "READ")
            lines.append(f" {title} UID(*) SERVICE({service}) ALLOW")
        else:
            lines.append(f" {title} UID(*) PREVENT")
        return "\n".join(lines)

    def _dataset_name(self, value: str) -> str:
        name = value.strip().strip("'\"").upper()
        return name

    def _compose_dataset_from_key_resource(self, key: str, resource: str) -> str:
        key = key.upper().strip("'\"")
        resource = resource.upper().strip("'\"")
        if not resource:
            return key
        if resource.startswith(key + "."):
            return resource
        if key in {"*", "**"}:
            return resource
        return f"{key}.{resource}"

    def _service_to_access(self, text: str) -> str:
        services = ",".join(part.strip().upper() for part in (text or "").replace(" ", "").split(",") if part.strip())
        if services in _SERVICE_TO_ACCESS:
            return _SERVICE_TO_ACCESS[services]
        if "DELETE" in services:
            return "ALTER"
        if "UPDATE" in services or "ADD" in services:
            return "UPDATE"
        if "EXEC" in services:
            return "EXECUTE"
        return "READ"
