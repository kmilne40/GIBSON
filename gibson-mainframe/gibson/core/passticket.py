from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict

from gibson.core.state import GibsonState

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@dataclass
class IssuedPassTicket:
    ticket: str
    userid: str
    applid: str
    requester: str
    source: str
    created_at: str
    expires_at: str
    used: bool = False
    uses: int = 0
    replay_allowed: bool = False
    appl_mismatch_allowed: bool = False
    leaked: bool = False


class PassTicketService:
    def __init__(self, state: GibsonState):
        self.state = state
        if not hasattr(state, "issued_passtickets"):
            setattr(state, "issued_passtickets", {})
        if not hasattr(state, "passticket_audit"):
            setattr(state, "passticket_audit", [])
        self.ensure_seeded_profiles()

    @property
    def issued(self) -> Dict[str, IssuedPassTicket]:
        return getattr(self.state, "issued_passtickets")

    @property
    def audit(self) -> list[dict[str, str]]:
        return getattr(self.state, "passticket_audit")

    def _record_audit(self, stage: str, detail: str, *, severity: str = "INFO") -> None:
        self.audit.append(
            {
                "TIME": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "STAGE": stage,
                "SEVERITY": severity.upper(),
                "DETAIL": detail,
            }
        )
        del self.audit[:-40]


    def _record_smf_passticket(self, kind: str, *, userid: str, applid: str, actor: str, result: str, reason: str = "OK", detail: str = "", consumer: str = "") -> None:
        try:
            if kind.upper().startswith("GEN"):
                from gibson.core.smf.records.type80 import passticket_generate
                passticket_generate(self.state, userid=userid, requester=actor, applid=applid, result=result, reason_code=reason, detail=detail)
            else:
                from gibson.core.smf.records.type80 import passticket_evaluate
                passticket_evaluate(self.state, userid=userid, consumer=consumer or actor, applid=applid, result=result, reason_code=reason, detail=detail)
        except Exception:
            pass

    def ensure_seeded_profiles(self) -> None:
        store = self.state.dynamic_racf
        store.raclist_active.setdefault("PTKTDATA", True)
        defaults = {
            "TSO": {"KEYMASKED": "A1B2C3D4E5F60718", "APPLDATA": "GIBSON PTKT TSO", "VALIDSECS": "600"},
            "TSOGIBS": {"KEYMASKED": "B1C2D3E4F5061728", "APPLDATA": "GIBSON PTKT TSO STRICT", "VALIDSECS": "600"},
            "CICS": {"KEYMASKED": "1A2B3C4D5E6F7081", "APPLDATA": "GIBSON PTKT CICS", "VALIDSECS": "600"},
            "DB2": {"KEYMASKED": "1122334455667788", "APPLDATA": "GIBSON PTKT DB2", "VALIDSECS": "600"},
            "WEBBANK": {"KEYMASKED": "89ABCDEF01234567", "APPLDATA": "GIBSON PTKT WEBBANK", "VALIDSECS": "600"},
        }
        for appl, attrs in defaults.items():
            prof = store._find_profile("PTKTDATA", appl) or store.define("PTKTDATA", appl, "IBMUSER", "NONE", attrs=attrs)
            for key, value in attrs.items():
                prof.attrs.setdefault(key, value)
            prof.attrs.setdefault("DATA", f"Gibson PassTicket lab for {appl}")
        auth_profiles = {
            "IRRPTAUTH.CICS.*": {"WEBBANK": "UPDATE", "IBMUSER": "UPDATE"},
            "IRRPTAUTH.TSO.*": {"IBMUSER": "UPDATE"},
            "IRRPTAUTH.DB2.*": {"WEBBANK": "UPDATE", "IBMUSER": "UPDATE"},
        }
        for name, permits in auth_profiles.items():
            prof = store._find_profile("PTKTDATA", name) or store.define("PTKTDATA", name, "IBMUSER", "NONE", attrs={"DATA": "Generation authorization"})
            for ident, access in permits.items():
                prof.permits.setdefault(ident, access)
        store.save()

    def _profile(self, applid: str):
        return self.state.dynamic_racf._find_profile("PTKTDATA", applid.upper())

    def _valid_secs(self, applid: str) -> int:
        prof = self._profile(applid)
        if not prof:
            return 600
        try:
            value = int(str(prof.attrs.get("VALIDSECS", "600")))
        except Exception:
            value = 600
        return max(1, min(600, value))

    def _replay_allowed(self, applid: str) -> bool:
        prof = self._profile(applid)
        if not prof:
            return False
        return "NO REPLAY PROTECTION" in str(prof.attrs.get("APPLDATA", "")).upper()

    def _appl_mismatch_allowed(self, applid: str) -> bool:
        prof = self._profile(applid)
        if not prof:
            return False
        return str(prof.attrs.get("LABAPPLMISMATCH", "NO")).upper() in {"Y", "YES", "TRUE", "1"}

    def _leak_enabled(self, applid: str) -> bool:
        prof = self._profile(applid)
        if not prof:
            return False
        return str(prof.attrs.get("LABLEAK", "NO")).upper() in {"Y", "YES", "TRUE", "1"}

    def _ticket_from_material(self, material: bytes) -> str:
        raw = hashlib.sha256(material).digest()
        chars = []
        for byte in raw[:8]:
            chars.append(ALPHABET[byte % len(ALPHABET)])
        return "".join(chars)

    def _authorized_requester(self, requester: str, applid: str, userid: str) -> tuple[bool, str]:
        req = (requester or "").upper()
        user = (userid or "").upper()
        appl = (applid or "").upper()
        rec = self.state.racf.get(req)
        if req == user:
            return True, "SELF"
        if rec and rec.special:
            return True, "SPECIAL"
        if self.state.dynamic_racf.has_access("PTKTDATA", f"IRRPTAUTH.{appl}.{user}", req, "UPDATE", self.state.racf):
            return True, "IRRPTAUTH"
        if self.state.dynamic_racf.has_access("PTKTDATA", f"IRRPTAUTH.{appl}.*", req, "UPDATE", self.state.racf):
            return True, "IRRPTAUTH-GENERIC"
        return False, "NO IRRPTAUTH UPDATE ACCESS"

    def generate(self, userid: str, applid: str, requester: str, *, source: str = "WEB") -> dict[str, Any]:
        self.ensure_seeded_profiles()
        user = (userid or "").upper().strip()
        appl = (applid or "CICS").upper().strip() or "CICS"
        req = (requester or user or "IBMUSER").upper().strip() or "IBMUSER"
        if not self.state.racf.exists(user):
            detail = f"IRRPT001I USERID {user or 'BLANK'} NOT FOUND"
            self._record_audit("GENERATE", detail, severity="ERROR")
            self._record_smf_passticket("GENERATE", userid=user or "UNKNOWN", applid=appl, actor=req, result="FAILURE", reason="USER_NOT_FOUND", detail=detail)
            return {"ok": False, "message": detail}
        prof = self._profile(appl)
        if not prof:
            detail = f"IRRPT002I PTKTDATA PROFILE {appl} NOT FOUND"
            self._record_audit("GENERATE", detail, severity="ERROR")
            self._record_smf_passticket("GENERATE", userid=user, applid=appl, actor=req, result="FAILURE", reason="PTKTDATA_PROFILE_NOT_FOUND", detail=detail)
            return {"ok": False, "message": detail}
        allowed, reason = self._authorized_requester(req, appl, user)
        if not allowed:
            detail = f"IRRPT003I {req} NOT AUTHORIZED TO REQUEST PASSTICKET FOR {user} APPL {appl} ({reason})"
            self._record_audit("GENERATE", detail, severity="ERROR")
            self._record_smf_passticket("GENERATE", userid=user, applid=appl, actor=req, result="FAILURE", reason="NOT_AUTHORIZED", detail=detail)
            return {"ok": False, "message": detail}
        if not self.state.dynamic_racf.has_access("APPL", appl, user, "READ", self.state.racf):
            detail = f"IRRPT004I {user} NOT AUTHORIZED TO APPL {appl}"
            self._record_audit("GENERATE", detail, severity="ERROR")
            self._record_smf_passticket("GENERATE", userid=user, applid=appl, actor=req, result="FAILURE", reason="APPL_ACCESS", detail=detail)
            return {"ok": False, "message": detail}
        secret = str(prof.attrs.get("KEYMASKED", "0000000000000000"))
        created = datetime.now(timezone.utc)
        expires = created + timedelta(seconds=self._valid_secs(appl))
        nonce = secrets.token_hex(4)
        material = f"{user}|{appl}|{req}|{source}|{created.isoformat()}|{nonce}".encode("utf-8")
        ticket = self._ticket_from_material(hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest())
        while ticket in self.issued:
            nonce = secrets.token_hex(4)
            material = f"{user}|{appl}|{req}|{source}|{created.isoformat()}|{nonce}".encode("utf-8")
            ticket = self._ticket_from_material(hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest())
        entry = IssuedPassTicket(
            ticket=ticket,
            userid=user,
            applid=appl,
            requester=req,
            source=source,
            created_at=created.isoformat(timespec="seconds"),
            expires_at=expires.isoformat(timespec="seconds"),
            replay_allowed=self._replay_allowed(appl),
            appl_mismatch_allowed=self._appl_mismatch_allowed(appl),
            leaked=self._leak_enabled(appl),
        )
        self.issued[ticket] = entry
        detail = f"IRRPT100I PASSTICKET {ticket} GENERATED FOR {user} APPL {appl} BY {req} SOURCE={source} EXPIRES={entry.expires_at}"
        self._record_audit("GENERATE", detail)
        self._record_smf_passticket("GENERATE", userid=user, applid=appl, actor=req, result="SUCCESS", reason="OK", detail=detail)
        self.state.record_security_event(req, "PASSTICKET GENERATE", f"USER={user} APPL={appl}", service="PTKT")
        return {
            "ok": True,
            "ticket": ticket,
            "userid": user,
            "applid": appl,
            "requester": req,
            "source": source,
            "expires_at": entry.expires_at,
            "replay_allowed": entry.replay_allowed,
            "appl_mismatch_allowed": entry.appl_mismatch_allowed,
            "leaked": entry.leaked,
            "message": detail,
        }

    def validate(self, userid: str, applid: str, ticket: str, *, consumer: str = "CICS") -> dict[str, Any]:
        user = (userid or "").upper().strip()
        appl = (applid or "CICS").upper().strip() or "CICS"
        token = (ticket or "").upper().strip()
        entry = self.issued.get(token)
        if not entry:
            detail = f"IRRPT200I PASSTICKET {token or 'BLANK'} NOT FOUND"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=user or "UNKNOWN", applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="NOT_FOUND", detail=detail)
            self.state.record_security_event(user or entry.userid if entry else "UNKNOWN", "PASSTICKET VALIDATE", detail, result="FAILURE", service="PTKT")
            return {"ok": False, "message": detail}
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(entry.expires_at)
        if now > expires:
            detail = f"IRRPT201I PASSTICKET {token} EXPIRED FOR {entry.userid} APPL {entry.applid}"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=entry.userid, applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="EXPIRED", detail=detail)
            return {"ok": False, "message": detail, "reason": "EXPIRED"}
        if entry.userid != user:
            detail = f"IRRPT202I PASSTICKET {token} USERID MISMATCH EXPECTED {entry.userid} RECEIVED {user}"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=user or entry.userid, applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="USERID_MISMATCH", detail=detail)
            return {"ok": False, "message": detail, "reason": "USERID_MISMATCH"}
        if entry.applid != appl and not entry.appl_mismatch_allowed:
            detail = f"IRRPT203I PASSTICKET {token} APPLID MISMATCH EXPECTED {entry.applid} RECEIVED {appl}"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=user, applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="APPLID_MISMATCH", detail=detail)
            return {"ok": False, "message": detail, "reason": "APPLID_MISMATCH"}
        if entry.used and not entry.replay_allowed:
            detail = f"IRRPT204I PASSTICKET {token} REPLAY DETECTED FOR {user} APPL {entry.applid}"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=user, applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="REPLAY", detail=detail)
            return {"ok": False, "message": detail, "reason": "REPLAY"}
        if not self.state.dynamic_racf.has_access("APPL", appl, user, "READ", self.state.racf):
            detail = f"IRRPT205I {user} NOT AUTHORIZED TO APPL {appl}"
            self._record_audit("VALIDATE", detail, severity="ERROR")
            self._record_smf_passticket("VALIDATE", userid=user, applid=appl, actor=consumer, consumer=consumer, result="FAILURE", reason="APPL_ACCESS", detail=detail)
            return {"ok": False, "message": detail, "reason": "APPL_ACCESS"}
        entry.used = True
        entry.uses += 1
        detail = f"IRRPT299I PASSTICKET {token} ACCEPTED FOR {user} APPL {appl} CONSUMER={consumer} USES={entry.uses}"
        self._record_audit("VALIDATE", detail)
        self._record_smf_passticket("VALIDATE", userid=user, applid=appl, actor=consumer, consumer=consumer, result="SUCCESS", reason="OK", detail=detail)
        self.state.record_security_event(user, "PASSTICKET VALIDATE", f"APPL={appl} CONSUMER={consumer}", service="PTKT")
        return {
            "ok": True,
            "message": detail,
            "userid": user,
            "applid": appl,
            "ticket": token,
            "uses": entry.uses,
            "replay_allowed": entry.replay_allowed,
            "appl_mismatch_allowed": entry.appl_mismatch_allowed,
            "leaked": entry.leaked,
        }

    def set_profile_flags(self, applid: str, *, replay_protection: bool | None = None, appl_mismatch: bool | None = None, leak: bool | None = None, valid_secs: int | None = None) -> dict[str, str]:
        prof = self._profile(applid.upper())
        if not prof:
            prof = self.state.dynamic_racf.define("PTKTDATA", applid.upper(), "IBMUSER", "NONE")
        appldata = str(prof.attrs.get("APPLDATA", "GIBSON PTKT"))
        appldata_up = appldata.upper()
        if replay_protection is not None:
            if replay_protection:
                appldata_up = appldata_up.replace("NO REPLAY PROTECTION", "").strip() or "GIBSON PTKT"
            elif "NO REPLAY PROTECTION" not in appldata_up:
                appldata_up = (appldata_up + " NO REPLAY PROTECTION").strip()
            prof.attrs["APPLDATA"] = appldata_up
        if appl_mismatch is not None:
            prof.attrs["LABAPPLMISMATCH"] = "YES" if appl_mismatch else "NO"
        if leak is not None:
            prof.attrs["LABLEAK"] = "YES" if leak else "NO"
        if valid_secs is not None:
            prof.attrs["VALIDSECS"] = str(max(1, min(600, int(valid_secs))))
        self.state.dynamic_racf.save()
        return {"APPLDATA": str(prof.attrs.get("APPLDATA", "")), "LABAPPLMISMATCH": str(prof.attrs.get("LABAPPLMISMATCH", "NO")), "LABLEAK": str(prof.attrs.get("LABLEAK", "NO")), "VALIDSECS": str(prof.attrs.get("VALIDSECS", "600"))}

    def profile_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for appl in sorted([name for name in self.state.dynamic_racf.profiles.get("PTKTDATA", {}) if not name.startswith("IRRPTAUTH.")]):
            prof = self._profile(appl)
            if not prof:
                continue
            rows.append(
                {
                    "PROFILE": appl,
                    "REPLAY": "OFF" if self._replay_allowed(appl) else "ON",
                    "APPLCHK": "RELAXED" if self._appl_mismatch_allowed(appl) else "STRICT",
                    "LABLEAK": "ON" if self._leak_enabled(appl) else "OFF",
                    "VALIDSECS": str(self._valid_secs(appl)),
                    "KEYMASKED": str(prof.attrs.get("KEYMASKED", "0000"))[:4] + "...",
                }
            )
        return rows

    def issued_rows(self) -> list[dict[str, str]]:
        rows = []
        for entry in sorted(self.issued.values(), key=lambda item: item.created_at, reverse=True):
            rows.append(
                {
                    "TICKET": entry.ticket,
                    "USERID": entry.userid,
                    "APPLID": entry.applid,
                    "REQUESTER": entry.requester,
                    "SOURCE": entry.source,
                    "CREATED": entry.created_at,
                    "EXPIRES": entry.expires_at,
                    "USED": "Y" if entry.used else "N",
                    "USES": str(entry.uses),
                    "REPLAY": "ALLOW" if entry.replay_allowed else "BLOCK",
                }
            )
        return rows[:20]

    def audit_rows(self) -> list[dict[str, str]]:
        return list(reversed(self.audit))[:20]



def get_passticket_service(state: GibsonState) -> PassTicketService:
    svc = getattr(state, "passticket_service", None)
    if svc is None:
        svc = PassTicketService(state)
        setattr(state, "passticket_service", svc)
    return svc
