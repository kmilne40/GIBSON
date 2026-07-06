from __future__ import annotations
import json
from urllib.parse import urlparse, parse_qs, unquote
from .services import CbsaService
from .store import get_cbsa_store
from .vuln_api import vuln_account_search, vuln_debug_customer, vuln_mass_assign, vuln_transfer, scenarios, set_scenario

def _body(handler):
    n=int(handler.headers.get('Content-Length','0') or 0)
    raw=handler.rfile.read(n) if n else b''
    try: return json.loads(raw.decode('utf-8')) if raw else {}
    except Exception: return {}

def _json(handler, code, payload):
    b=json.dumps(payload, indent=2, sort_keys=True).encode('utf-8')
    handler.send_response(code); handler.send_header('Content-Type','application/json; charset=utf-8'); handler.send_header('Cache-Control','no-store'); handler.send_header('Content-Length',str(len(b))); handler.end_headers(); handler.wfile.write(b)

def handle(handler, state):
    svc=CbsaService(state); st=svc.store; method=handler.command.upper(); parsed=urlparse(handler.path); path=parsed.path; qs=parse_qs(parsed.query)
    try:
        if path in {'/health','/api/v1/cbsa/health'}: st.audit('REST','HEALTH',path,'OK',1); return _json(handler,200,{"status":"UP","service":"CBSA8080","port":8080,"cbsa_security_training_mode":bool(getattr(state.config,'cbsa_vuln',False))})
        if path=='/api/v1/cbsa/capabilities': return _json(handler,200,{"cics_transaction":"OMEN","rest_port":8080,"security_training_mode":bool(getattr(state.config,'cbsa_vuln',False)),"cbsa_security_training_mode":bool(getattr(state.config,'cbsa_vuln',False)),"schemas":["CBSA"]})
        if path=='/api/v1/cbsa/schema': return _json(handler,200,{"tables":list(st.tables())})
        if path in {'/api/v1/cbsa/reset','/api/v1/cbsa/seed'} and method=='POST': return _json(handler,200,svc.reset())
        if path=='/api/v1/cbsa/audit': return _json(handler,200,{"api_audit":st.api_audit,"cics_audit":st.cics_audit,"sqli_events":st.sqli_events,"vuln_events":st.vuln_events})
        if path.startswith('/api/v1/cbsa/vuln') and not bool(getattr(state.config,'cbsa_vuln',False)):
            return _json(handler,403,{"error":"CBSA Security Training Mode is disabled","enable":"start Gibson with --with-cbsa-api --vuln or --with-cbsa-api --cbsa-vuln","cbsa_security_training_mode":False})
        if path=='/api/v1/cbsa/vuln/events': return _json(handler,200,{"events":st.vuln_events,"sqli_events":st.sqli_events})
        if path=='/api/v1/cbsa/vuln/scenarios' and method=='GET': return _json(handler,200,scenarios(st))
        if path.startswith('/api/v1/cbsa/vuln/scenarios/') and method=='POST':
            name=path.split('/')[-2] if path.endswith('/enable') or path.endswith('/disable') else path.split('/')[-1]; val=path.endswith('/enable'); return _json(handler,200,set_scenario(st,name,val))
        if path=='/api/v1/cbsa/vuln/reset' and method=='POST': return _json(handler,200,{"reset":svc.reset(),"scenarios":st.scenarios})
        if path=='/api/v1/cbsa/vuln/accounts': return _json(handler,200,vuln_account_search(state, qs.get('customer',[''])[0]))
        if path.startswith('/api/v1/cbsa/vuln/debug/customer/'): return _json(handler,200,vuln_debug_customer(state,path.rsplit('/',1)[1]))
        if path.startswith('/api/v1/cbsa/vuln/customers/') and method=='PUT': return _json(handler,200,vuln_mass_assign(state,path.rsplit('/',1)[1],_body(handler)))
        if path=='/api/v1/cbsa/vuln/transfer' and method=='POST': return _json(handler,200,vuln_transfer(state,_body(handler)))
        if path.startswith('/api/v1/cbsa/vuln/account/'):
            acc=path.rsplit('/',1)[1]
            if handler.headers.get('X-HTTP-Method-Override','').upper()=='DELETE': st.audit('REST','METHOD_OVERRIDE_DELETE',acc,'SIMULATED_DELETE',1,scenario='CBSA_VULN_METHOD_OVERRIDE'); return _json(handler,200,{"vulnerable":"method_override","account":acc,"result":"SIMULATED_DELETE"})
            a=svc.account(acc); st.audit('REST','IDOR_ACCOUNT',acc,'RETURNED',1,scenario='CBSA_VULN_IDOR'); return _json(handler,200,{"account":a.row(),"training":"IDOR ownership check bypassed"})
        if path.startswith('/api/v1/cbsa/vuln/sql-error'): inp=qs.get('account',[''])[0]; st.audit('REST','VERBOSE_SQL_ERROR',inp,'ERROR',0,scenario='CBSA_VULN_VERBOSE_ERRORS'); return _json(handler,500,{"SQLCODE":"-104","SQLSTATE":"42601","simulated_sql":f"SELECT * FROM CBSA.ACCOUNT WHERE ACCOUNT_NUMBER = '{inp}'","error":"controlled verbose SQL error"})
        if path=='/api/v1/cbsa/vuln/login' and method=='POST': data=_body(handler); st.audit('REST','WEAK_LOGIN',str(data),'BYPASS',1,scenario='CBSA_VULN_WEAK_AUTH'); return _json(handler,200,{"authenticated":True,"training":"weak auth accepted lab credentials","token":"unsigned-lab-token"})
        if path.startswith('/inqcustz/enquiry/') and method=='GET': c=svc.customer(path.rsplit('/',1)[1]); st.audit('REST','INQCUST',path,'OK',1); return _json(handler,200,{"INQCUST":{"CUSTOMER":c.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path.startswith('/inqaccz/enquiry/') and method=='GET': a=svc.account(path.rsplit('/',1)[1]); st.audit('REST','INQACC',path,'OK',1); return _json(handler,200,{"INQACC":{"ACCOUNT":a.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path.startswith('/inqacccz/list/') and method in {'PUT','GET'}: rows=[a.row() for a in svc.list_accounts(path.rsplit('/',1)[1])]; st.audit('REST','INQACCCU',path,'OK',len(rows)); return _json(handler,200,{"INQACCCU":{"ACCOUNTS":rows,"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path=='/crecust/insert' and method=='POST': c=svc.create_customer(_body(handler), channel='REST'); st.audit('REST','CRECUST',str(c.customer_id),'OK',1); return _json(handler,201,{"CRECUST":{"CUSTOMER":c.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path=='/creacc/insert' and method=='POST': a=svc.create_account(_body(handler), channel='REST'); st.audit('REST','CREACC',str(a.account_number),'OK',1); return _json(handler,201,{"CREACC":{"ACCOUNT":a.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path=='/updcust/update' and method=='PUT': data=_body(handler); c=svc.update_customer(data.get('customer_id') or data.get('CUSTOMER_ID'), data, channel='REST'); st.audit('REST','UPDCUST',str(c.customer_id),'OK',1); return _json(handler,200,{"UPDCUST":{"CUSTOMER":c.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path=='/updacc/update' and method=='PUT': data=_body(handler); a=svc.update_account(data.get('account_number') or data.get('ACCOUNT_NUMBER'), data, channel='REST'); st.audit('REST','UPDACC',str(a.account_number),'OK',1); return _json(handler,200,{"UPDACC":{"ACCOUNT":a.row(),"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path.startswith('/delcus/remove/') and method=='DELETE': c=svc.delete_customer(path.rsplit('/',1)[1], channel='REST'); return _json(handler,200,{"DELCUS":{"CUSTOMER_ID":c.customer_id,"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path.startswith('/delacc/remove/') and method=='DELETE': a=svc.delete_account(path.rsplit('/',1)[1], channel='REST'); return _json(handler,200,{"DELACC":{"ACCOUNT_NUMBER":a.account_number,"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" "}})
        if path=='/makepayment/dbcr' and method=='PUT': return _json(handler,200,svc.payment_envelope(_body(handler), channel='REST'))
        return _json(handler,404,{"error":"CBSA route not found","path":path})
    except Exception as e:
        st.abend('REST','CBSA8080','RESTERR',str(e),path); return _json(handler,400,{"error":str(e),"path":path,"COMM_SUCCESS":"N"})
