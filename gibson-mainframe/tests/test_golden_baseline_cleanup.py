from __future__ import annotations

import subprocess
import sys

from gibson.cli import build_state
from gibson.apps.cics import CicsSimulator
from gibson.apps.omvs import OmvsShellSession


def _state(tmp_path):
    class Args:
        gacf=None; sim_root=str(tmp_path); secure=False; vuln=False; split_console=False; logon_panel=False
        host=None; port=None; ftp_port=None; uss_port=None; tn3270_port=None; db2_tcp_port=None; db2_ws_port=None
        no_web_terminal=True; with_web_terminal=False; web_terminal_port=None
    return build_state(Args())


def test_removed_cli_flags_absent():
    out = subprocess.run([sys.executable, '-m', 'gibson.cli', '--help'], text=True, capture_output=True, check=True).stdout
    assert '--with-rest' not in out
    assert '--rest-port' not in out
    assert '--with-react8999' not in out
    assert '--react8999-port' not in out


def test_cics_removed_transactions_are_not_live(tmp_path):
    state = _state(tmp_path)
    cics = CicsSimulator(state, 'IBMUSER')
    for tx in ['FIBS','CICSLAB1','BLAB','HACK3270']:
        assert 'COMMAND NOT RECOGNIZED' in cics.execute(tx)
    assert cics.execute('CEMT').strip()


def test_omvs_nmap_rss_curl_wget_commands_exist(tmp_path):
    state = _state(tmp_path)
    sh = OmvsShellSession(state, 'IBMUSER')
    assert 'nmap-sim' in sh.execute('nmap --version')
    assert 'CTI RSS' in sh.execute('rss --list-feeds')
    assert 'KREBSONSECURITY' in sh.execute('cti-rss --list-feeds').upper()
    assert 'output path escapes' in sh.execute('curl -o ../../escape https://example.com')
    assert 'output path escapes' in sh.execute('wget -O ../../escape https://example.com')
