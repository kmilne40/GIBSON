from argparse import Namespace

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.cli import _register_services


def test_port_3270_removed_from_config_and_service_registry():
    cfg = GibsonConfig()
    assert cfg.tn3270_port == 0
    st = GibsonState.create(cfg)
    args = Namespace(no_uss=True, no_dashboard=True, with_ftp=False, no_db2=True, with_cbsa_api=False, with_app8080=False, with_dvca_web=False)
    _register_services(st, [], args)
    svc = st.service_manager.get('TN3270')
    assert svc.state == 'REMOVED'
    assert svc.port is None
    assert svc.starter is None
