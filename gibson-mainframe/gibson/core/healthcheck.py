from __future__ import annotations

from typing import Any

from gibson.core.state import GibsonState


class HealthChecker:
    def __init__(self, state: GibsonState):
        self.state = state
        self.state.seed_health_checks()
        self.state.refresh_health_checks()

    def rows(self) -> list[dict[str, str]]:
        self.state.refresh_health_checks()
        out = []
        for check_id, item in sorted(self.state.health_checks.items()):
            out.append(
                {
                    "CHECK": check_id,
                    "NAME": str(item.get("NAME", check_id)),
                    "SEV": str(item.get("SEVERITY", "LOW")),
                    "STATUS": str(item.get("STATUS", "ACTIVE")),
                    "FINDING": str(item.get("FINDING", item.get("DETAIL", ""))),
                }
            )
        return out

    def command(self, text: str) -> str:
        self.state.refresh_health_checks()
        t = (text or "").strip().upper()
        if not t or t in {"REFRESH", "R"}:
            return "HZS0001I HEALTH CHECK DATA REFRESHED"
        if t.startswith("START "):
            cid = t.split(None, 1)[1].strip().upper()
            if cid in self.state.health_checks:
                self.state.health_checks[cid]["STATUS"] = "ACTIVE"
                return f"HZS0002I CHECK {cid} STARTED"
        if t.startswith("STOP "):
            cid = t.split(None, 1)[1].strip().upper()
            if cid in self.state.health_checks:
                self.state.health_checks[cid]["STATUS"] = "STOPPED"
                return f"HZS0003I CHECK {cid} STOPPED"
        if t.startswith("DISPLAY "):
            cid = t.split(None, 1)[1].strip().upper()
            item = self.state.health_checks.get(cid)
            if item:
                return f"{cid} {item.get('NAME','')}\nSTATUS={item.get('STATUS','ACTIVE')}\nSEVERITY={item.get('SEVERITY','LOW')}\nDETAIL={item.get('DETAIL','')}\nFINDING={item.get('FINDING','')}"
        return "HZS0004I HEALTH CHECK COMMAND ACCEPTED"


def get_healthchecker(state: GibsonState) -> HealthChecker:
    hc = getattr(state, "healthchecker_service", None)
    if hc is None:
        hc = HealthChecker(state)
        setattr(state, "healthchecker_service", hc)
    return hc
