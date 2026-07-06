from __future__ import annotations

from pathlib import Path

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.omvs import OmvsShellSession


def make_omvs(tmp_path: Path) -> OmvsShellSession:
    cfg = GibsonConfig(sim_root=tmp_path / "sim", files_root=tmp_path / "sim" / "f", commands_dir=tmp_path / "sim" / "f" / "commands", transfer_root=tmp_path / "sim" / "transfers", gacf_path=tmp_path / "sim" / "GACF.DB")
    state = GibsonState.create(cfg)
    return OmvsShellSession(state, "IBMUSER")


def test_canonical_target_resolution_and_netstat_help(tmp_path):
    omvs = make_omvs(tmp_path)
    assert "mainframe -> 127.0.0.1" in omvs.execute("hosts resolve mainframe")
    assert "Canonical IP:   127.0.0.1" in omvs.execute("netstat -h")
    home = omvs.execute("netstat HOME")
    assert "127.0.0.1" in home
    assert "192.168.0.254" not in home


def test_nmap_tso_enum_and_port_mapping(tmp_path):
    omvs = make_omvs(tmp_path)
    out = omvs.execute('nmap mainframe -p23 --script=tso-enum --script-args tso-enum.commands="L TSO"')
    assert "Starting Nmap" in out
    assert "Gibson compatibility: requested 23, mapped to 2023" in out
    assert "IBMUSER" in out and "CONFIRMED" in out
    assert "RUARIV" in out and "DENIED" in out
    assert "nmap-sim" not in out.splitlines()[0]


def test_msfconsole_tomcat_flow_and_session(tmp_path):
    omvs = make_omvs(tmp_path)
    out = omvs.execute('msfconsole -x "search tomcat; use 0; show options; set RHOST mainframe; set USERNAME tomcat; set PASSWORD tomcat; run; sessions; sessions -i 1; id"')
    assert "exploit/multi/http/tomcat_mgr_upload" in out
    assert "Command shell session 1 opened" in out
    assert "127.0.0.1:31337" in out
    assert "uid=12345(tomcat) gid=1000(tomcat)" in out
    assert "TOMCATSH" in omvs.state.network.format("PORTLIST")


def test_msfconsole_denies_external_targets(tmp_path):
    omvs = make_omvs(tmp_path)
    out = omvs.execute('msfconsole -x "use 0; set RHOSTS evil.example; set USERNAME tomcat; set PASSWORD tomcat; run"')
    assert "outside Gibson training scope" in out


def test_cicspwn_professional_output_and_scope(tmp_path):
    omvs = make_omvs(tmp_path)
    out = omvs.execute("CICSPWN mainframe")
    assert "CICSPWN Gibson Safe CICS Assessment" in out
    assert "Target: mainframe (127.0.0.1)" in out
    assert "[2] Transaction access" in out
    assert "CEMT" in out and "SECURITY_PROTECTED" in out
    denied = omvs.execute("CICSPWN evil.example")
    assert "target denied" in denied.lower()


def test_nmap_31337_opens_after_msfconsole(tmp_path):
    omvs = make_omvs(tmp_path)
    before = omvs.execute("nmap mainframe -p31337")
    assert "closed" in before
    omvs.execute('msfconsole -x "use 0; set RHOSTS mainframe; set HttpUsername tomcat; set HttpPassword tomcat; run"')
    after = omvs.execute("nmap mainframe -p31337")
    assert "open" in after
    assert "tomcat-bind-safe" in after
