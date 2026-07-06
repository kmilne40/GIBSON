from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import uuid
from gibson.apps.dvca.models import Event, now

DEFAULT_PRODUCTS = {
    "00001": {"item":"00001","canbuy":"Y","name":"Bulk Paper Clips","price":"3.99","shipping":"1.25","comments":"Standard office supply"},
    "00002": {"item":"00002","canbuy":"Y","name":"Printer Toner XL","price":"89.50","shipping":"6.95","comments":"Warehouse stock"},
    "00003": {"item":"00003","canbuy":"N","name":"Dom Perignon Rose 1959","price":"9999.99","shipping":"250.00","comments":"BANNED: not office supply"},
    "00004": {"item":"00004","canbuy":"Y","name":"Executive Stapler","price":"18.45","shipping":"3.25","comments":"Approved"},
    "00005": {"item":"00005","canbuy":"N","name":"Ancient Golden Idol","price":"45000.00","shipping":"500.00","comments":"BANNED: controlled artifact"},
}
DEFAULT_SCENARIOS = {"FIELD_PROTECTION_BYPASS": True, "HIDDEN_CANBUY_BYPASS": True, "NUMERIC_ONLY_BYPASS": True, "FSET_MDT_TRUST": True, "HIDDEN_OPTION_99": True, "PA3_SECRET": True, "HARDCODED_PIN": True, "DIRECT_SCRT": True, "API_LEAKAGE": True}
@dataclass
class DvcaSession:
    sid: str
    user: str = "DVCA"
    screen: str = "MCGM"
    fields: dict[str, str] = field(default_factory=dict)
    hack: dict[str, bool] = field(default_factory=lambda: {"enabled": False, "disable_protection": False, "reveal_hidden": False, "remove_numeric": False, "show_start_field": False, "show_sfe": False, "modify_field": False})
    last_message: str = ""
    catalog_index: int = 0

class DvcaStore:
    def __init__(self, state: Any):
        self.state = state
        self.products = {k: dict(v) for k, v in DEFAULT_PRODUCTS.items()}
        self.history = [{"item":"00001","name":"Bulk Paper Clips","price":"3.99","shipping":"1.25","status":"ORDERED"}]
        self.address = {"name":"MEL CARGO", "line1":"1 MAINFRAME WAY", "line2":"CICS CITY", "postcode":"ZOS 3270"}
        self.sessions: dict[str, DvcaSession] = {}
        self.events: list[Event] = []
        self.scenarios = dict(DEFAULT_SCENARIOS)
    def new_sid(self) -> str:
        return "DVCA" + uuid.uuid4().hex[:8].upper()
    def session(self, sid: str | None = None, user: str = "DVCA") -> DvcaSession:
        if not sid or sid not in self.sessions:
            sid = sid or self.new_sid(); self.sessions[sid] = DvcaSession(sid=sid, user=user)
        return self.sessions[sid]
    def reset(self):
        self.__init__(self.state); return {"status":"RESET", "products": len(self.products)}
    def corrid(self, prefix="DVCA"):
        return prefix + "-" + uuid.uuid4().hex[:8].upper()
    def log(self, channel, sid, action, result="OK", field="", payload="", screen="", scenario="", user="DVCA"):
        ev = Event("DVCA-" + str(len(self.events)+1).zfill(5), now(), channel, sid or "", user or "DVCA", "DVCA", screen or "", action, field, str(payload)[:300], result, scenario, self.corrid("DVC"))
        self.events.append(ev)
        try:
            from gibson.core.cics_region import get_cics_region
            level = "INFO" if result in {"OK", "SUCCESS", "FOUND"} else "WARN"
            get_cics_region(self.state).add_log(level, "DVCA", user or "DVCA", f"{action} {result} {field} {str(payload)[:80]}")
        except Exception:
            pass
        try:
            if result in {"OK", "SUCCESS", "FOUND"} and scenario:
                from gibson.core.security_event_bus import emit_smf80, emit_smf110, emit_smf102, emit_training_security_event
                common = dict(user=user or "DVCAUSR", channel=channel or "DVCA", result=result,
                              resource=field or scenario, transaction="DVCA", program=screen or "",
                              payload=str(payload)[:160], correlation_id=ev.correlation_id,
                              detail=f"scenario={scenario} action={action}")
                if "SQL" in scenario.upper() or "SQL" in action.upper():
                    emit_smf102(self.state, event=action, table="CBSA.ACCOUNT", endpoint="/api/v1/dvca", **common)
                elif "PIN" in scenario.upper():
                    emit_smf80(self.state, event=action, **common)
                    emit_smf110(self.state, event=action, **common)
                elif scenario.upper() in {"FIELD_MUTATION", "FIELD_PROTECTION_BYPASS", "HIDDEN_CANBUY_BYPASS", "NUMERIC_ONLY_BYPASS", "HARDCODED_PIN"}:
                    emit_smf80(self.state, event=action, **common)
                    emit_smf110(self.state, event=action, **common)
                else:
                    emit_training_security_event(self.state, event=action, smf_type="110", subsystem="CICS", **common)
        except Exception:
            pass
        return ev

def get_dvca_store(state: Any) -> DvcaStore:
    svc = getattr(state, "dvca_store", None)
    if svc is None:
        svc = DvcaStore(state); setattr(state, "dvca_store", svc)
    return svc
