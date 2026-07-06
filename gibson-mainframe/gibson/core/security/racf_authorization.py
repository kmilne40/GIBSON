from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import fnmatch

from gibson.apps.racf_admin import get_racf_store

ACCESS_ORDER = {"NONE": 0, "READ": 1, "UPDATE": 2, "CONTROL": 3, "ALTER": 4}
INTENT_MAP = {"ALLOCATE": "UPDATE", "WRITE": "UPDATE", "EXECUTE": "READ", "INQUIRE": "READ"}
CLASS_ALIASES = {"TCICSTRN": "CICS", "GCICSTRN": "CICS", "DATASET": "DATASET"}

@dataclass(frozen=True)
class RacfDecision:
    allowed: bool
    userid: str
    racf_class: str
    resource: str
    requested: str
    effective: str
    matched_profile: str
    reason: str
    message: str
    evidence_id: str


def _norm_access(access: str) -> str:
    val = INTENT_MAP.get((access or "READ").upper(), (access or "READ").upper())
    return val if val in ACCESS_ORDER else "READ"


def _class_key(racf_class: str) -> str:
    return CLASS_ALIASES.get((racf_class or "DATASET").upper(), (racf_class or "DATASET").upper())


def _profile_matches(profile: str, resource: str) -> bool:
    p = (profile or "").upper().replace("**", "*")
    r = (resource or "").upper()
    return p == r or fnmatch.fnmatchcase(r, p)


def groups_for_user(state: Any, userid: str) -> set[str]:
    st = get_racf_store(state)
    u = (userid or "").upper()
    groups = {g for g, users in st.groups.items() if u in {x.upper() for x in users}}
    rec = st.users.get(u)
    if rec and rec.get("DFLTGRP"):
        groups.add(str(rec.get("DFLTGRP")).upper())
    return groups


def _best_profile(state: Any, racf_class: str, resource: str) -> tuple[str, dict[str, Any]] | tuple[str, None]:
    st = get_racf_store(state)
    profiles = st.profiles.get(_class_key(racf_class), {})
    matches = [(p, v) for p, v in profiles.items() if _profile_matches(p, resource)]
    if not matches:
        return "", None
    matches.sort(key=lambda item: len(item[0].replace("*", "")), reverse=True)
    return matches[0]


def check_access(state: Any, userid: str, racf_class: str, resource: str, requested: str = "READ", *, audit: bool = True) -> RacfDecision:
    user = (userid or "UNKNOWN").upper()
    cls = _class_key(racf_class)
    res = (resource or "").upper()
    req = _norm_access(requested)
    st = get_racf_store(state)
    rec = st.users.get(user, {})
    attrs = {str(a).upper() for a in rec.get("ATTRS", set())}
    prof_name, prof = _best_profile(state, cls, res)
    reason = "NO_PROFILE"
    effective = "NONE"
    if "SPECIAL" in attrs or (cls == "DATASET" and "OPERATIONS" in attrs):
        effective = "ALTER"
        reason = "SPECIAL" if "SPECIAL" in attrs else "OPERATIONS"
    elif prof:
        permits = {str(k).upper(): str(v).upper() for k, v in prof.get("PERMITS", {}).items()}
        candidates = [str(prof.get("UACC", "NONE")).upper()]
        if user in permits:
            candidates.append(permits[user])
        for group in groups_for_user(state, user):
            if group in permits:
                candidates.append(permits[group])
        effective = max((c if c in ACCESS_ORDER else "NONE" for c in candidates), key=lambda x: ACCESS_ORDER[x])
        reason = "PERMIT" if ACCESS_ORDER[effective] > ACCESS_ORDER.get(str(prof.get("UACC", "NONE")).upper(), 0) else "UACC"
    allowed = ACCESS_ORDER[effective] >= ACCESS_ORDER[req]
    evid = f"SMF80-{len(getattr(getattr(state, 'audit', None), 'events', [])) + 1:06d}"
    if allowed:
        msg = f"ICH70001I USER({user}) ACCESS ALLOWED CLASS({cls}) RESOURCE({res}) ACCESS({req}) EFFECTIVE({effective})"
    else:
        msg = f"ICH408I USER({user}) CLASS({cls}) RESOURCE({res}) INSUFFICIENT ACCESS AUTHORITY ACCESS INTENT({req}) ACCESS ALLOWED({effective})"
    dec = RacfDecision(allowed, user, cls, res, req, effective, prof_name or res, reason, msg, evid)
    if audit:
        _audit_decision(state, dec)
    return dec


def _audit_decision(state: Any, dec: RacfDecision) -> None:
    try:
        result = "SUCCESS" if dec.allowed else "FAILURE"
        detail = f"CLASS={dec.racf_class} RESOURCE={dec.resource} ACCESS={dec.requested} EFFECTIVE={dec.effective} PROFILE={dec.matched_profile} REASON={dec.reason}"
        if getattr(state, "audit", None) is not None:
            state.audit.record_smf80(dec.userid, "RACF ACCESS", detail, result=result, extra={
                "CLASS": dec.racf_class, "RESOURCE": dec.resource, "PROFILE": dec.matched_profile,
                "REQUIRED": dec.requested, "EFFECTIVE": dec.effective, "EVENT": "RACF ACCESS", "DETAIL": detail,
            })
        if not dec.allowed and hasattr(state, "notify_console"):
            state.notify_console(dec.message, severity="ALERT")
    except Exception:
        pass


def permit(state: Any, profile: str, racf_class: str, ident: str, access: str = "READ") -> None:
    st = get_racf_store(state)
    cls = _class_key(racf_class)
    st.profiles.setdefault(cls, {}).setdefault(profile.upper(), {"UACC": "NONE", "PERMITS": {}})["PERMITS"][ident.upper()] = _norm_access(access)
