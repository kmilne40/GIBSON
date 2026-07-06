from pathlib import Path
from types import SimpleNamespace

from gibson.apps.welcome.routes import render_page
from gibson.cli import build_state
from gibson.apps.cics import CicsSimulator
from gibson.apps.master_console import MasterConsoleController
from gibson.core import nje


def make_state(tmp_path):
    args=SimpleNamespace(gacf='',sim_root=str(tmp_path),secure=False,vuln=True,cbsa_vuln=False,dvca_vuln=True,split_console=False,logon_panel=False,host='127.0.0.1',ipl_hostname=None,port=2023,ftp_port=None,uss_port=None,db2_tcp_port=None,db2_ws_port=None,no_web_terminal=False,with_web_terminal=False,web_terminal_port=None,cbsa_api_port=None,fibs_web_port=None,welcome_port=None,welcome8000_port=None,no_welcome=False,no_welcome8000=False,with_welcome=False,with_welcome8000=False,dashboard_port=None,rest_port=None,app8080_port=None,no_ftp=False,no_rest=False,with_ftp=True,with_rest=True,with_cbsa_api=True,with_dvca=True,with_dvca_web=True,with_fibs_web=True,with_app8080=True,no_master=True,demo_events=False)
    return build_state(args)


def test_welcome_manual_and_features_render():
    code, _, body = render_page('/welcome')
    assert code == 200 and 'Top 20 Gibson realism features' in body and '/manual' in body
    code, _, body = render_page('/manual')
    assert code == 200 and 'Gibson Technical Manual' in body and 'Open full extracted manual' in body


def test_dvca_hack_on_colours(tmp_path):
    st=make_state(tmp_path)
    c=CicsSimulator(st,'IBMUSER')
    c.execute('DVCA'); c.execute('PF5'); c.execute('1')
    out=c.execute('HACK ON')
    assert '\x1b[31m' in out or '\x1b[94m' in out
    assert 'TRAINING LEGEND HACK ON' in out


def test_master_console_metrics_and_registers(tmp_path):
    st=make_state(tmp_path)
    mc=MasterConsoleController(st)
    assert 'HOST CPU ACTIVITY' in mc.execute('CPU').text
    regs = mc.execute('REGS').text
    for r in '0123456789ABCDEF':
        assert f'R{r}=' in regs


def test_nje_chapter10_helpers():
    assert 'NODE(GIBSON)' in nje.display_nodes()
    assert 'SOCKET(GIBSOCK)' in nje.display_sockets()
    assert 'ACK' in nje.handshake('GIBSON','HAL','GIBSONPW')
