from __future__ import annotations
from .services import CbsaService
from .vuln_sql import sqli_search

def scenarios(store): return {"scenarios":dict(store.scenarios)}
def set_scenario(store,name,value): store.scenarios[name]=bool(value); return scenarios(store)

def vuln_account_search(state, customer):
    svc=CbsaService(state); return sqli_search(svc.store, customer, "REST")
def vuln_debug_customer(state, cid):
    svc=CbsaService(state); c=svc.customer(cid); svc.store.audit("REST","DEBUG_CUSTOMER",cid,"LEAKED",1,scenario="CBSA_VULN_VERBOSE_ERRORS")
    return {"customer":c.row(),"internal":{"risk_score":c.risk_score,"teller_flags":"OVERRIDE_ALLOWED","control":"CBSA-TRAINING-ONLY"}}
def vuln_mass_assign(state,cid,payload):
    svc=CbsaService(state); c=svc.update_customer(cid,payload,channel="REST",vulnerable=True); svc.store.audit("REST","MASS_ASSIGNMENT",str(payload),"UPDATED",1,scenario="CBSA_VULN_MASS_ASSIGNMENT"); return c.row()
def vuln_transfer(state,payload):
    svc=CbsaService(state); src,dst=svc.transfer(payload.get("from_account"),payload.get("to_account"),payload.get("amount"),channel="REST",vulnerable=True); svc.store.audit("REST","BUSINESS_LOGIC_TRANSFER",str(payload),"UPDATED",2,scenario="CBSA_VULN_BUSINESS_LOGIC"); return {"from":src.row(),"to":dst.row()}
