from pathlib import Path
import argparse
from gibson.cli import build_state
from gibson.apps.ispf import IspfApp
from gibson.apps.editor import InteractiveEditor
from gibson.apps.cics import CicsSimulator
from gibson.apps.dvca.store import DvcaStore
from gibson.apps.dvca.screen_model import menu
from gibson.apps.cbsa.bms_screens import main_menu_screenbuffer

def state(tmp_path: Path):
    ns=argparse.Namespace(sim_root=str(tmp_path), host='127.0.0.1', port=0, ftp_port=None, uss_port=None, tn3270_port=None, rest_port=None, db2_tcp_port=None, db2_ws_port=None, secure=False, vuln=True, gacf=None)
    return build_state(ns)

def test_ispf_34_panel_registry(tmp_path):
    app=IspfApp(state(tmp_path),'IBMUSER', lambda cmd: '')
    s=app.build_dsliste_panel('IBMUSER')
    assert s.get_field('OPTION') and s.get_field('DSNAME_LEVEL')
    assert 'Data Set List Utility' in s.render_plain()

def test_editor_fielded_panel_and_aid(tmp_path):
    ed=InteractiveEditor('IBMUSER.TEST', 'LINE1\nLINE2')
    s=ed.build_fielded_screen()
    assert s.get_field('COMMAND') and s.get_field('SCROLL')
    assert any(f.name.startswith('LINECMD.') for f in s.fields)
    top=ed.top_line_index
    class Ev:
        fields_by_name={}
        def is_pf(self,n): return n==8
    ed.apply_terminal_event(Ev())
    assert ed.top_line_index >= top

def test_operation_cics_fielded_panel(tmp_path):
    c=CicsSimulator(state(tmp_path),'IBMUSER'); c.panel_state='CEMT_INQUIRE'
    s=c.build_fielded_panel()
    assert s.get_field('OPTION')
    assert 'CONNECTION' in s.render_plain()

def test_dvca_and_cbsa_registries(tmp_path):
    st=state(tmp_path); store=DvcaStore(st); sess=store.session(user='IBMUSER')
    scr=menu(sess,store).to_screenbuffer(reveal_hidden=True)
    assert scr.get_field('SELECT')
    cbsa=main_menu_screenbuffer()
    assert cbsa.get_field('OPTION')
