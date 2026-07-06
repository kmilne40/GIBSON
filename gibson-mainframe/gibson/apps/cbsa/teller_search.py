from __future__ import annotations

from typing import Any
import uuid

from gibson.apps.cbsa.vuln_sql import sqli_search
from gibson.core.security_event_bus import (
    emit_smf101,
    emit_smf102,
    emit_smf110,
    emit_trace_event,
)


def _corr() -> str:
    return "TELLER-" + uuid.uuid4().hex[:8].upper()


def _clip(value: Any, limit: int = 220) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _q(query: str) -> str:
    return str(query or "").strip()


def _matches(*values: Any, query: str) -> bool:
    q = _q(query).upper()
    if not q:
        return False
    return any(q in str(v or "").upper() for v in values)


def _transaction_id(row: dict[str, Any]) -> str:
    return str(row.get("TRANSACTION_ID") or row.get("EVENT_ID") or row.get("CORRELATION_ID") or "")


def _safe_rows(store: Any, query: str, search_type: str, include_transactions: bool = True) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, Any]]]:
    st = (search_type or "all").lower()
    customers: list[dict[str, str]] = []
    accounts: list[dict[str, str]] = []
    txns: list[dict[str, Any]] = []
    for c in store.customers.values():
        if st in {"all", "customer", "customer_id", "customer_name"} and _matches(c.customer_id, c.name, c.address1, getattr(c, "postcode", ""), query=query):
            customers.append(c.row())
    for a in store.accounts.values():
        if st in {"all", "account", "account_number", "sort_code"} and _matches(a.account_number, a.customer_id, a.sort_code, a.account_type, query=query):
            accounts.append(a.row())
    if include_transactions:
        for row in store.proctran:
            if st in {"all", "transaction", "transaction_ref"} and _matches(_transaction_id(row), row.get("FROM_ACCOUNT"), row.get("TO_ACCOUNT"), row.get("ACCOUNT_NUMBER"), row.get("REFERENCE"), query=query):
                txns.append({k: str(v) for k, v in row.items()})
    return customers, accounts, txns


def _sql_for(search_type: str, query: str) -> str:
    st = (search_type or "all").lower()
    q = _clip(query, 120).replace("\n", " ")
    if st.startswith("customer"):
        return "SELECT * FROM CBSA.CUSTOMER WHERE CUSTOMER_ID = '%s' OR NAME LIKE '%%%s%%'" % (q, q)
    if st.startswith("transaction"):
        return "SELECT * FROM CBSA.PROCTRAN WHERE TRANSACTION_ID = '%s' OR FROM_ACCOUNT = '%s' OR TO_ACCOUNT = '%s'" % (q, q, q)
    return "SELECT * FROM CBSA.ACCOUNT WHERE ACCOUNT_NUMBER = '%s' OR CUSTOMER_ID = '%s' OR SORT_CODE = '%s'" % (q, q, q)


def teller_search(
    state: Any,
    store: Any,
    query: str,
    search_type: str = "all",
    user: str = "TELLER",
    vulnerable: bool = True,
    include_closed: bool = False,
    include_transactions: bool = True,
) -> dict[str, Any]:
    q = _q(query)
    st = (search_type or "all").lower()
    corr = _corr()
    sql = _sql_for(st, q)
    route = "/webapi/teller/search"

    emit_trace_event(state, component="WEB9080", action="REQUEST", user=user, route=route, result="START", message=f"teller search {st}", correlation_id=corr)
    emit_trace_event(state, component="CBSA", action="TELLER_SEARCH", user=user, route=route, result="START", message=f"query={_clip(q,80)}", correlation_id=corr)
    emit_trace_event(state, component="CICS", action="INQCUST", user=user, cics_transaction="OMEN", cics_program="INQCUST", result="OK", message="simulated customer/account enquiry", correlation_id=corr)
    emit_trace_event(state, component="SQL", action="SELECT", user=user, sql=sql, table="CBSA.CUSTOMER,CBSA.ACCOUNT", result="START", correlation_id=corr)

    mode = "vulnerable" if vulnerable else "secure"
    upper = q.upper()
    sqli = any(tok in upper for tok in ["' OR", " OR ", "UNION", "' AND", "1=1", "1'='1", "1=2", "'1'='2", "--"])
    if vulnerable and sqli:
        if "UNION" in upper:
            rows = sqli_search(store, q, channel="WEB9080")
            customers: list[dict[str, str]] = []
            accounts: list[dict[str, str]] = []
            txns: list[dict[str, Any]] = rows.get("rows", [])
            result = "UNION_METADATA"
        elif "AND" in upper and ("1=2" in upper or "1'='2" in upper or "'2'" in upper):
            customers, accounts, txns = [], [], []
            result = "BOOLEAN_FALSE"
            ev = store.audit("WEB9080", "TELLER_SQLI_SEARCH", q, result, 0, user=user, scenario="SQLI")
            store.sqli_events.append({**ev, "SIMULATED_SQL": sql, "ROWS_RETURNED": "0"})
        else:
            customers = [c.row() for c in store.customers.values()]
            accounts = [a.row() for a in store.accounts.values()]
            txns = [{k: str(v) for k, v in row.items()} for row in store.proctran[-25:]] if include_transactions else []
            result = "ROWSET_EXPANDED"
            ev = store.audit("WEB9080", "TELLER_SQLI_SEARCH", q, result, len(customers)+len(accounts)+len(txns), user=user, scenario="SQLI")
            store.sqli_events.append({**ev, "SIMULATED_SQL": sql, "ROWS_RETURNED": str(len(customers)+len(accounts)+len(txns))})
        rows_returned = len(customers) + len(accounts) + len(txns)
        store.vuln_events.append({"EVENT_ID": corr, "CHANNEL": "WEB9080", "ACTION": "TELLER_SQLI_SEARCH", "RESULT": result, "SCENARIO": "SQLI", "CORRELATION_ID": corr, "ROWS_RETURNED": str(rows_returned)})
        emit_trace_event(state, component="DB2", action="SQLI_PATTERN_DETECTED", user=user, sql=sql, table="CBSA.CUSTOMER,CBSA.ACCOUNT", result=result, rows_returned=rows_returned, correlation_id=corr, severity="WARN")
        emit_smf102(state, event="SQLI_SEARCH", user=user, channel="WEB9080", result="SUCCESS", resource="CBSA.TELLER.SEARCH", table="CBSA.CUSTOMER,CBSA.ACCOUNT", endpoint=route, payload=q, correlation_id=corr, detail=f"rows_returned={rows_returned}")
        emit_trace_event(state, component="SMF", action="SMF102", user=user, smf_type="102", result="SQLI-DETECTED", rows_returned=rows_returned, correlation_id=corr, message="SIMULATED SMF102 DB2 audit event")
        emit_trace_event(state, component="CONSOLE", action="GIBSQLI01W", user=user, result="ALERT", rows_returned=rows_returned, correlation_id=corr, message="SQLI TRAINING PAYLOAD DETECTED")
    else:
        customers, accounts, txns = _safe_rows(store, q, st, include_transactions)
        rows_returned = len(customers) + len(accounts) + len(txns)
        result = "OK" if rows_returned else "NO_ROWS"
        ev = store.audit("WEB9080", "TELLER_SEARCH", q, result, rows_returned, user=user, scenario="")
        if sqli and not vulnerable:
            result = "BLOCKED_SECURE_MODE"
            ev = store.audit("WEB9080", "TELLER_SQLI_BLOCKED", q, result, rows_returned, user=user, scenario="SQLI")
        emit_trace_event(state, component="DB2", action="SELECT", user=user, sql=sql if vulnerable else "PARAMETERIZED SEARCH", table="CBSA.CUSTOMER,CBSA.ACCOUNT", result=result, rows_returned=rows_returned, correlation_id=corr)
        emit_smf101(state, event="TELLER_SEARCH", user=user, channel="WEB9080", result=result, resource="CBSA.TELLER.SEARCH", table="CBSA.CUSTOMER,CBSA.ACCOUNT", endpoint=route, payload=q, correlation_id=corr, detail=f"rows_returned={rows_returned}")
        emit_smf110(state, event="TELLER_SEARCH", user=user, channel="WEB9080", result=result, transaction="OMEN", program="INQCUST", resource="CBSA.TELLER.SEARCH", correlation_id=corr, detail=f"rows_returned={rows_returned}")
        emit_trace_event(state, component="SMF", action="SMF101", user=user, smf_type="101", result=result, rows_returned=rows_returned, correlation_id=corr, message="SIMULATED SMF101 DB2 accounting event")
        emit_trace_event(state, component="SMF", action="SMF110", user=user, smf_type="110", result=result, rows_returned=rows_returned, correlation_id=corr, message="SIMULATED SMF110 CICS monitor event")

    emit_trace_event(state, component="WEB9080", action="RESPONSE", user=user, route=route, result=result, rows_returned=len(customers)+len(accounts)+len(txns), correlation_id=corr)
    return {
        "query": q,
        "search_type": st,
        "mode": mode,
        "customers": customers,
        "accounts": accounts,
        "transactions": txns,
        "simulated_sql": sql if vulnerable else "PARAMETERIZED SEARCH",
        "result": result,
        "rows_returned": len(customers) + len(accounts) + len(txns),
        "evidence": {"correlation_id": corr, "event_id": ev.get("EVENT_ID", corr) if isinstance(ev, dict) else corr},
        "correlation_id": corr,
        "secure_comparison": "secure mode treats the search string as data and does not expand rows",
    }
