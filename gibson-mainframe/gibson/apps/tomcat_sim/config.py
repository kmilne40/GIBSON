from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class TomcatSimConfig:
    enabled: bool = True
    vulnerable_defaults_enabled: bool = True
    secure_mode: bool = False
    allow_pseudo_bind_listener: bool = True
    pseudo_bind_port: int = 31337
    max_war_size: int = 2 * 1024 * 1024
    allow_raw_war_readback: bool = False
    evidence_enabled: bool = True
    dashboard_alerts_enabled: bool = True


def get_config(state: Any) -> TomcatSimConfig:
    cfg = getattr(state, "tomcat_sim_config", None)
    if cfg is None:
        cfg = TomcatSimConfig(
            enabled=bool(getattr(getattr(state, "config", object()), "tomcat_sim_enabled", True)),
            vulnerable_defaults_enabled=bool(getattr(getattr(state, "config", object()), "tomcat_vulnerable_defaults_enabled", True)),
            secure_mode=bool(getattr(getattr(state, "config", object()), "tomcat_secure_mode", False)),
            allow_pseudo_bind_listener=bool(getattr(getattr(state, "config", object()), "tomcat_allow_pseudo_bind_listener", True)),
            pseudo_bind_port=int(getattr(getattr(state, "config", object()), "tomcat_pseudo_bind_port", 31337)),
            max_war_size=int(getattr(getattr(state, "config", object()), "tomcat_max_war_size", 2 * 1024 * 1024)),
            allow_raw_war_readback=bool(getattr(getattr(state, "config", object()), "tomcat_allow_raw_war_readback", False)),
            evidence_enabled=bool(getattr(getattr(state, "config", object()), "tomcat_evidence_enabled", True)),
            dashboard_alerts_enabled=bool(getattr(getattr(state, "config", object()), "tomcat_dashboard_alerts_enabled", True)),
        )
        state.tomcat_sim_config = cfg
    return cfg
