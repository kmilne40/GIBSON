from __future__ import annotations
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tomcat_sim.config import TomcatSimConfig, get_config


def test_feature_flags_defaults_and_secure(tmp_path):
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    cfg=get_config(state)
    assert cfg.enabled and cfg.vulnerable_defaults_enabled
    state.tomcat_sim_config=TomcatSimConfig(secure_mode=True, vulnerable_defaults_enabled=False)
    cfg=get_config(state)
    assert cfg.secure_mode and not cfg.vulnerable_defaults_enabled
