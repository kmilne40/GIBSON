from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class MfaDecision:
    allowed: bool
    user: str
    service: str
    reason: str
    event_type: str
    evidence_id: str = ""

@dataclass
class MfaUser:
    user: str
    factors: list[str] = field(default_factory=lambda: ["R04"])
    seed: str = "246810"
    fallback_allowed: bool = False
    break_glass: bool = False

class MfaPolicyStore:
    """Deterministic Gibson MFA policy store.  No external providers."""
    def __init__(self) -> None:
        self.users: dict[str, MfaUser] = {
            "IBMUSER": MfaUser("IBMUSER", ["R04","OTP"], "111111", False, True),
            "RUARIV": MfaUser("RUARIV", ["OTP"], "222222"),
            "TELLER": MfaUser("TELLER", ["OTP"], "333333"),
            "GUEST": MfaUser("GUEST", [], "", True),
        }
        self.required_services: dict[str, bool] = {"TSO": False, "CICS": False, "FTP": False, "ZOSMF": True}
        self.stepup_transactions: set[str] = {"CICS:GMVB.ADMIN", "CICS:CEMT"}
        self.audit: list[dict[str, str]] = []

    @classmethod
    def seeded(cls) -> "MfaPolicyStore":
        return cls()

    def reset(self) -> None:
        fresh = type(self)()
        self.__dict__.update(fresh.__dict__)

    def set_required(self, service: str, required: bool) -> None:
        self.required_services[(service or "").upper()] = bool(required)

    def enrolled(self, user: str) -> MfaUser:
        who=(user or "UNKNOWN").upper()
        if who not in self.users:
            self.users[who]=MfaUser(who, ["OTP"], "123456")
        return self.users[who]

    def expected_token(self, user: str) -> str:
        rec=self.enrolled(user)
        return (rec.seed or "000000")[-6:]

    def validate(self, user: str, service: str, token: str = "", *, stepup: str = "") -> MfaDecision:
        who=(user or "UNKNOWN").upper(); svc=(service or "TSO").upper()
        rec=self.enrolled(who)
        required = bool(self.required_services.get(svc, False) or (stepup and f"{svc}:{stepup.upper()}" in self.stepup_transactions))
        if not required:
            dec=MfaDecision(True, who, svc, "MFA not required by current policy", "MFA_NOT_REQUIRED")
        elif rec.break_glass:
            dec=MfaDecision(True, who, svc, "break-glass exemption used", "MFA_BREAKGLASS_USED")
        elif rec.fallback_allowed and not token:
            dec=MfaDecision(True, who, svc, "fallback allowed", "MFA_FALLBACK_USED")
        elif token and token == self.expected_token(who):
            dec=MfaDecision(True, who, svc, "valid simulator MFA factor", "MFA_SUCCESS")
        else:
            dec=MfaDecision(False, who, svc, "missing or invalid simulator MFA factor", "MFA_FAILURE")
        dec.evidence_id=self.record(dec)
        return dec

    def record(self, dec: MfaDecision) -> str:
        eid=f"MFA-{len(self.audit)+1:05d}"
        self.audit.append({"event_id":eid,"timestamp":datetime.utcnow().replace(microsecond=0).isoformat()+"Z","user":dec.user,"service":dec.service,"event_type":dec.event_type,"result":"ALLOW" if dec.allowed else "DENY","reason":dec.reason})
        return eid
