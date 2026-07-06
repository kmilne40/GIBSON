from types import SimpleNamespace
from gibson.cli import build_state

def test_cli_flags_include_dvca_and_app8080():
    args=SimpleNamespace(gacf=None,sim_root=None,secure=False,vuln=True,cbsa_vuln=False,dvca_vuln=True,split_console=False,logon_panel=False,host=None,port=None,ftp_port=None,uss_port=None,tn3270_port=None,db2_tcp_port=None,db2_ws_port=None,no_web_terminal=False,with_web_terminal=False,web_terminal_port=None,cbsa_api_port=None,with_dvca=True,with_dvca_web=True,with_app8080=True)
    st=build_state(args)
    assert st.config.dvca_vuln is True
    assert st.config.security_mode == 'vuln'
