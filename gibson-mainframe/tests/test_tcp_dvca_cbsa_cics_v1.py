from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.omvs import OmvsShellSession


def make_state(tmp_path):
    cfg = GibsonConfig(sim_root=tmp_path / "sim", host="127.0.0.1")
    st = GibsonState.create(cfg)
    st.config.cbsa_vuln = True
    return st


def test_tcpfix_ping_tracerte_external_not_loopback(tmp_path):
    st = make_state(tmp_path)
    out = st.network.ping("8.8.8.8")
    assert "PING 8.8.8.8 (8.8.8.8)" in out
    assert "PING 8.8.8.8 (127.0.0.1)" not in out
    tr = st.network.traceroute("8.8.8.8")
    assert "8.8.8.8" in tr
    assert "mainframe (127.0.0.1)" in tr


def test_tcpfix_mainframe_still_loopback_and_netstat(tmp_path):
    st = make_state(tmp_path)
    assert "PING mainframe (127.0.0.1)" in st.network.ping("mainframe")
    ns = st.network.format("HOME")
    assert "127.0.0.1" in ns
    assert "EZZ2500I NETSTAT command complete" in ns


def test_omvs_ping_and_netstat_help_are_simulated(tmp_path):
    st = make_state(tmp_path)
    sh = OmvsShellSession(st, "IBMUSER")
    assert "Usage: netstat" in sh.execute("netstat -h")
    out = sh.execute("ping 8.8.8.8")
    assert "PING 8.8.8.8 (8.8.8.8)" in out


def test_dvca_hack_on_buy_price_redraws_immediately(tmp_path):
    st = make_state(tmp_path)
    execute_dvca(st, "IBMUSER", "DVCA")
    execute_dvca(st, "IBMUSER", "MCOR")
    normal = execute_dvca(st, "IBMUSER", "PRICE=1.00 CANBUY=Y")
    assert "PROTECTED FIELD" in normal or "3.99" in normal
    execute_dvca(st, "IBMUSER", "HACK ON")
    out = execute_dvca(st, "IBMUSER", "BUY=Y PRICE=1.00 CANBUY=Y")
    assert "Price             :1.00" in out
    assert "Buy item (Y/N)    Y" in out
    assert "ORDER ACCEPTED" in out


def test_dvca_pf10_instructions(tmp_path):
    st = make_state(tmp_path)
    execute_dvca(st, "IBMUSER", "DVCA")
    out = execute_dvca(st, "IBMUSER", "PF10")
    assert "CICS / DVCA / CBSA INSTRUCTIONS" in out
    assert "HACK ON" in out


def test_cbpp_valid_login_and_vulnerability_panel(tmp_path):
    st = make_state(tmp_path)
    c = CicsSimulator(st, "IBMUSER")
    first = c.execute("CBSA")
    assert "CBPP - CBSA PRE-AUTHENTICATION" in first
    logged = c.execute("IBMUSER SYS1")
    assert "CBSA MAIN MENU" in logged
    vuln = c.execute("V BUFFER")
    assert "CBSA BUFFER OVERFLOW SIMULATION" in vuln
    assert "ASRA SIMULATED" in vuln


def test_cbpp_pa3_escape_vulnerable_and_cemt_route(tmp_path):
    st = make_state(tmp_path)
    c = CicsSimulator(st, "GUEST")
    assert "CBPP" in c.execute("CBSA")
    pa = c.execute("PA3")
    assert "ATTENTION KEY NOT VALID" in pa
    menu = c.execute("ENTER")
    assert "CBSA MAIN MENU" in menu
    c2 = CicsSimulator(st, "IBMUSER")
    c2.execute("CBSA")
    c2.execute("PA1")
    routed = c2.execute("CEMT")
    assert "STATUS:  ENTER ONE OF THE FOLLOWING" in routed or "CEMT" in routed


def test_cbpp_pa_key_escape_secure_blocks(tmp_path):
    st = make_state(tmp_path)
    st.config.cbpp_secure_mode = True
    c = CicsSimulator(st, "GUEST")
    c.execute("CBSA")
    assert "ATTENTION KEY NOT VALID" in c.execute("PA1")
    out = c.execute("ENTER")
    assert "CBPP - CBSA PRE-AUTHENTICATION" in out
    assert "CBSA MAIN MENU" not in out


def test_cics_pf10_instructions(tmp_path):
    st = make_state(tmp_path)
    c = CicsSimulator(st, "IBMUSER")
    out = c.execute("PF10")
    assert "CICS INSTRUCTIONS" in out
    assert "DVCA" in out and "CBSA" in out
