from .vuln_sql import sqli_search

def cics_sqli_screen(store, inp):
    res=sqli_search(store, inp, "CICS")
    lines=["CBSA SQL TRAINING RESULT","",f"INPUT CUSTOMER: {res['input']}","QUERY MODE: VULNERABLE CONCATENATION",f"ROWS RETURNED: {res['rows_returned']}","SQLCODE: 000",f"FINDING: CBSA-SQLI-001",f"CORRELATION ID: {res['correlation_id']}","",res['simulated_sql'][:78],"", "ACCOUNTS:"]
    for r in res['rows'][:8]: lines.append(f" {r.get('ACCOUNT_NUMBER',''):<10} CUSTOMER {r.get('CUSTOMER_ID',''):<6} BAL {r.get('ACTUAL_BALANCE','')}")
    return "\n".join(lines)
