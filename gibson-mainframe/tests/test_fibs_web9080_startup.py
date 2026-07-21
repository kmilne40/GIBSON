from argparse import Namespace
from pathlib import Path
import tempfile

from gibson.cli import build_state


def _args(**kw):
    base = dict(gacf=None, sim_root=str(Path(tempfile.mkdtemp())), secure=False, vuln=False, cbsa_vuln=False, dvca_vuln=False, split_console=False, logon_panel=False, host=None, port=None, ftp_port=None, uss_port=None, tn3270_port=None, db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False, with_web_terminal=False, web_terminal_port=None, cbsa_api_port=None, fibs_web_port=None, no_fibs_web=False, with_fibs_web=False)
    base.update(kw)
    return Namespace(**base)


def test_build_state_defaults_fibs_web9080_enabled():
    state = build_state(_args())
    assert state.config.with_fibs_web is True
    assert state.config.fibs_web_port == 9080
    assert state.config.security_mode == "vuln"


def test_no_fibs_web_disables_service_flag():
    state = build_state(_args(no_fibs_web=True))
    assert state.config.with_fibs_web is False


def test_fibs_web_port_flag():
    state = build_state(_args(fibs_web_port=19080))
    assert state.config.fibs_web_port == 19080
