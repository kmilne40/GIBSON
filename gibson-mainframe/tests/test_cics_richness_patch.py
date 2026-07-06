from __future__ import annotations
import subprocess, sys
from argparse import Namespace

import pytest

from gibson.cli import build_state
from gibson.apps.cics import CicsSimulator
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.editor import InteractiveEditor


def _args(**kw):
    base=dict(gacf=None,sim_root=None,secure=False,vuln=False,cbsa_vuln=False,split_console=False,logon_panel=False,host=None,port=None,ftp_port=None,uss_port=None,tn3270_port=None,db2_tcp_port=None,db2_ws_port=None,no_web_terminal=False,with_web_terminal=False,web_terminal_port=None,cbsa_api_port=None)
    base.update(kw)
    return Namespace(**base)


def test_cli_cbsa_vuln_flag_sets_config_and_help_lists_it():
    state = build_state(_args(cbsa_vuln=True))
    assert state.config.cbsa_vuln is True
    cp = subprocess.run([sys.executable, "-m", "gibson.cli", "--help"], text=True, capture_output=True, timeout=20)
    assert cp.returncode == 0
    assert "--cbsa-vuln" in cp.stdout


def test_secure_and_cbsa_vuln_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_state(_args(secure=True, cbsa_vuln=True))


def test_omvs_nmap_menu_and_bad_ping_do_not_exit():
    sh = OmvsShellSession(build_state(_args()), "IBMUSER")
    out = sh.execute("nmap -M")
    assert "Gibson nmap-sim guided menu" in out and "TSO user enumeration" in out
    assert "nmap -M 2" in out
    assert "invalid host" in sh.execute("ping 127.0.0.1;id")


def test_ezedit_accepts_realistic_record_widths():
    ed = InteractiveEditor("IBMUSER.TEST", "", mode="EDIT", recfm="FB", lrecl=80)
    for n in (40, 72, 80):
        ok, msg = ed._validate_line_length("A" * n)
        assert ok, msg
        assert len(ed._normalise_text("A" * n)) == n
    ok, msg = ed._validate_line_length("A" * 100)
    assert not ok
    assert "LINE EXCEEDS LRECL 80" in msg


def test_cics_rich_region_commands_and_removed_transactions_absent():
    c = CicsSimulator(build_state(_args()), "IBMUSER")
    assert "OMEN" in c.transactions
    assert "GMVB" not in c.transactions
    tran = c.execute("CEMT I TRAN")
    assert "Tra(OMEN" in tran
    assert "Tra(GMVB" not in tran
    assert "DFHCE3551" in c.execute("FIBS")
    assert "DFHCE3568" in c.execute("CEDA DEFINE TRANSACTION(FIBS) PROGRAM(TEST) GROUP(GIBLAB)")


def test_cics_ceci_cebr_csmt_cedf_and_omen_disable():
    c = CicsSimulator(build_state(_args()), "IBMUSER")
    out = c.execute("CECI WRITEQ TS QUEUE(TESTQ) FROM('HELLO FROM CICS')")
    assert "WRITEQ TS QUEUE(TESTQ)" in out
    assert "HELLO FROM CICS" in c.execute("CEBR TESTQ")
    assert "CECI" in c.execute("CSMT")
    assert "ENABLED FOR OMEN" in c.execute("CEDF OMEN")
    assert "CBSA MAIN MENU" in c.execute("OMEN")
    assert "BNKMENU" in c.execute("CEDF") or "RECEIVE MAP" in c.execute("CEDF")
    assert "SET DISABLED" in c.execute("CEMT SET TRAN(OMEN) DISABLED")
    assert "TRANSACTION OMEN IS DISABLED" in c.execute("OMEN")
    assert "SET ENABLED" in c.execute("CEMT SET TRAN(OMEN) ENABLED")
    assert "CBSA MAIN MENU" in c.execute("OMEN")

class _KeyReader:
    def __init__(self, keys): self.keys=list(keys)
    def read_key(self):
        class R: pass
        r=R(); k=self.keys.pop(0) if self.keys else 'q'; r.key=k; r.text=''; return r


def test_omvs_more_interactive_pages_and_quits():
    sh = OmvsShellSession(build_state(_args()), "IBMUSER")
    sh.env.write_text('/u/ibmuser/long.txt', '\n'.join(f'line{i:02d}' for i in range(30)))
    out=[]
    handled = sh._handle_interactive_command('more long.txt', _KeyReader(['q']), lambda s: out.append(s))
    assert handled is True
    text=''.join(out)
    assert 'line00' in text and 'line21' in text
    assert 'line29' not in text
    assert '--More--' in text
