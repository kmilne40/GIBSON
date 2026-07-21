from __future__ import annotations
import re

def sqli_search(store, customer_input:str, channel="REST"):
    inp=str(customer_input or "")
    q=f"SELECT * FROM CBSA.ACCOUNT WHERE CUSTOMER_ID = '{inp}'"
    rows=[]; scenario="CBSA_VULN_SQLI"; result="NORMAL"
    u=inp.upper()
    if "OR" in u and "1" in u and "=" in u:
        rows=[a.row() for a in store.accounts.values()]; result="ROWSET_EXPANDED"
    elif "AND" in u and ("1'='2" in u or "1=2" in u or "'2'" in u):
        rows=[]; result="BOOLEAN_FALSE"
    elif "UNION" in u:
        rows=[{"TABLE_SCHEMA":"CBSA","TABLE_NAME":k.split('.',1)[1]} for k in store.tables().keys()]; result="UNION_METADATA"
        scenario="CBSA_VULN_UNION_SQLI"
    else:
        rows=[a.row() for a in store.accounts.values() if a.customer_id==inp]
    ev=store.audit(channel,"SQLI_LOOKUP",inp,result, len(rows), scenario=scenario)
    store.sqli_events.append({**ev,"SIMULATED_SQL":q,"ROWS_RETURNED":str(len(rows))})
    return {"input":inp,"simulated_sql":q,"rows_returned":len(rows),"result":result,"correlation_id":ev["CORRELATION_ID"],"rows":rows}
