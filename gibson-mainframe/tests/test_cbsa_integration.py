import json, socket, time, urllib.request, urllib.error
from types import SimpleNamespace
from pathlib import Path

from gibson.cli import build_state
from gibson.apps.cics import CicsSimulator
from gibson.apps.db2_sim import Db2Simulator
from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080
from gibson.apps.omvs import OmvsShellSession


def state(tmp_path, cbsa_vuln=False):
    args=SimpleNamespace(gacf=None, sim_root=str(tmp_path), secure=False, vuln=False, cbsa_vuln=cbsa_vuln, split_console=False, logon_panel=False, host='127.0.0.1', port=None, ftp_port=None, uss_port=None, tn3270_port=None, db2_tcp_port=None, db2_ws_port=None, no_web_terminal=False, with_web_terminal=False, web_terminal_port=None, cbsa_api_port=18080)
    return build_state(args)


def test_cbsa_cics_omen_and_removed_apps(tmp_path):
    st=state(tmp_path, cbsa_vuln=True); c=CicsSimulator(st,'IBMUSER')
    out=c.execute('OMEN')
    assert 'CBPP SIGNON REQUIRED' in out
    out=c.execute('IBMUSER SYS1')
    assert 'PIN REQUIRED' in out
    out=c.execute('PIN 1234')
    assert 'CBSA MAIN MENU' in out
    assert 'FIBS' not in out
    assert 'DFHCE3551' in c.execute('FIBS')
    assert 'DAMN VULNERABLE CICS APPLICATION' in c.execute('DVCA')
    assert 'DFHCE3551' in c.execute('CICSLAB1')
    assert 'CBSA DISPLAY CUSTOMER' in c.execute('OMEN 1 1001')
    c.execute('OMEN')
    assert 'CBSA DISPLAY ACCOUNT' in c.execute('2 00000101')
    assert 'CBSA CREATE ACCOUNT' in c.execute('OMEN 4 CUSTOMER=1001 BALANCE=77.77')
    assert 'CBSA SQL TRAINING RESULT' in c.execute("OMEN V SQLI 1001' OR '1'='1")


def test_cbsa_db2_bridge_and_sqli(tmp_path):
    st=state(tmp_path); db=Db2Simulator(st)
    rows=db.run_sql("SELECT * FROM CBSA.ACCOUNT WHERE CUSTOMER_ID = '1001'")
    assert len(rows)>=2
    rows2=db.run_sql("SELECT * FROM CBSA.VULN_ACCOUNT_LOOKUP WHERE CUSTOMER_INPUT = '1001'' OR ''1''=''1'")
    assert len(rows2)>=4
    ev=db.run_sql('SELECT * FROM CBSA.SQLI_EVENTS')
    assert ev


def test_cbsa_vuln_endpoints_disabled_by_default(tmp_path):
    st=state(tmp_path); st.config.cbsa_api_port=18082
    srv=serve_cbsa_rest8080(st)
    try:
        time.sleep(.1)
        req=urllib.request.Request("http://127.0.0.1:18082/api/v1/cbsa/vuln/accounts?customer=1001")
        try:
            urllib.request.urlopen(req, timeout=3)
            assert False, "vulnerable endpoint should be disabled by default"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
            body=exc.read().decode()
            assert "Security Training Mode is disabled" in body
    finally:
        srv.shutdown(); srv.server_close()


def test_cbsa_rest_8080(tmp_path):
    st=state(tmp_path, cbsa_vuln=True); st.config.cbsa_api_port=18080
    srv=serve_cbsa_rest8080(st)
    try:
        time.sleep(.1)
        def req(path, method='GET', data=None, headers=None):
            body=json.dumps(data).encode() if data is not None else None
            h={'Content-Type':'application/json'} if data is not None else {}
            if headers: h.update(headers)
            r=urllib.request.Request('http://127.0.0.1:18080'+path, data=body, method=method, headers=h)
            with urllib.request.urlopen(r, timeout=3) as resp:
                return json.loads(resp.read().decode())
        assert req('/health')['service']=='CBSA8080'
        assert req('/inqcustz/enquiry/1001')['INQCUST']['COMM_SUCCESS']=='Y'
        pay=req('/makepayment/dbcr','PUT', {'PAYDBCR': {'COMM_ACCNO':'00000101','COMM_AMT':'10.00'}})
        assert pay['PAYDBCR']['COMM_SUCCESS']=='Y'
        vuln=req("/api/v1/cbsa/vuln/accounts?customer=1001'%20OR%20'1'%3D'1")
        assert vuln['rows_returned']>=4
        mass=req('/api/v1/cbsa/vuln/customers/1001','PUT', {'name':'ALICE','isAdmin':'true','creditLimit':'999999'})
        assert mass['ISADMIN']=='true'
        over=req('/api/v1/cbsa/vuln/account/00000101','POST', headers={'X-HTTP-Method-Override':'DELETE'})
        assert over['result']=='SIMULATED_DELETE'
    finally:
        srv.shutdown(); srv.server_close()


def test_cbsa_omvs_curl(tmp_path):
    st=state(tmp_path, cbsa_vuln=True); st.config.cbsa_api_port=18081
    srv=serve_cbsa_rest8080(st)
    try:
        shell=OmvsShellSession(st, 'IBMUSER')
        out=shell.execute('curl http://127.0.0.1:18081/api/v1/cbsa/health')
        assert 'CBSA8080' in out
        out=shell.execute("curl http://127.0.0.1:18081/api/v1/cbsa/vuln/accounts?customer=1001%27%20OR%20%271%27%3D%271")
        assert 'ROWSET_EXPANDED' in out
    finally:
        srv.shutdown(); srv.server_close()
