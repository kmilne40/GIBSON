from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid
from urllib.parse import parse_qs

from gibson.core.security_mode import SECURE
from gibson.core.security_event_bus import (
    clear_trace_events,
    emit_trace_event,
    emit_smf80,
    emit_smf101,
    emit_smf102,
    emit_smf110,
    get_trace_events,
)
from gibson.apps.cbsa.services import CbsaService
from gibson.apps.cbsa.store import get_cbsa_store
from gibson.apps.cbsa.teller_search import teller_search
from gibson.apps.fibs_identity import lab_jwt_forge, lab_oauth_authorize
from .lab_catalog import get_lab
from gibson.core.passticket import get_passticket_service
from gibson.core.identity_events import emit_identity_event


def _mode(state: Any) -> str:
    return "SECURE" if getattr(state.config, "security_mode", "vulnerable") == SECURE else "VULNERABLE"


def _corr(prefix: str = "LAB") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _clip(value: Any, limit: int = 500) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _parse_payload(payload: str) -> dict[str, str]:
    if not payload:
        return {}
    parsed = parse_qs(payload, keep_blank_values=True)
    if parsed:
        return {k: v[-1] if v else "" for k, v in parsed.items()}
    return {"payload": payload}


def _audit(store: Any, user: str, slug: str, payload: str, result: str, scenario: str, corr: str) -> dict[str, str]:
    ev = {
        "EVENT_ID": _corr("EV"),
        "TIMESTAMP": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "CHANNEL": "WEB9080",
        "USER": user.upper(),
        "ACTION": f"LAB_{slug.upper().replace('-', '_')}",
        "PAYLOAD": _clip(payload, 240),
        "RESULT": result,
        "SCENARIO": scenario,
        "CORRELATION_ID": corr,
    }
    try:
        store.web_audit.append(ev)
        store.web_lab_events.append(ev.copy())
        if scenario:
            store.vuln_events.append(ev.copy())
            if slug == "sqli":
                store.sqli_events.append(ev.copy())
    except Exception:
        pass
    return ev


def _base_result(slug: str, user: str, payload: str, action: str, trace_id: str = "") -> dict[str, Any]:
    corr = trace_id or _corr("CORR")
    return {
        "lab": slug,
        "mode": action,
        "payload": _clip(payload, 500),
        "request": {},
        "response": {},
        "trace_id": corr,
        "correlation_id": corr,
        "evidence_id": "",
        "backend_mapping": {},
        "trace_events": [],
        "events": [],
        "timeline": [],
        "simulated_sql": "",
        "cics_transaction": "",
        "cics_program": "",
        "db2_tables": [],
        "smf_events": [],
        "console_alerts": [],
        "secure_comparison": "",
        "teaching_notes": [],
        "knowledge_check_context": {},
        "user": user,
    }


def _lab_meta(result: dict[str, Any], slug: str) -> None:
    lab = get_lab(slug)
    if not lab:
        return
    result["backend_mapping"] = lab.backend_mapping
    result["cics_transaction"] = lab.backend_mapping.get("CICS transaction", "CBSA")
    result["cics_program"] = lab.backend_mapping.get("Program", "LABSIM")
    tables = lab.backend_mapping.get("Db2 tables", "CBSA.WEB_AUDIT")
    result["db2_tables"] = [x.strip() for x in tables.split(",") if x.strip()]
    result["simulated_sql"] = lab.backend_mapping.get("SQL", result.get("simulated_sql", ""))


def _emit_path(state: Any, result: dict[str, Any], slug: str, user: str, components: list[str], *, rows: int = 0, sql: str = "", table: str = "", message: str = "") -> None:
    trace_id = result["trace_id"]
    corr = result["correlation_id"]
    for component in components:
        ev = emit_trace_event(
            state,
            component=component,
            action=f"LAB_{slug.upper().replace('-', '_')}",
            user=user,
            channel="WEB9080",
            route=f"/webapi/labs/{slug}/{result['mode']}",
            result=result["response"].get("result", "OK"),
            rows_returned=rows,
            message=message or f"FIBS Security Academy lab {slug}",
            correlation_id=corr,
            trace_id=trace_id,
            cics_transaction=result.get("cics_transaction", ""),
            cics_program=result.get("cics_program", ""),
            sql=sql or result.get("simulated_sql", ""),
            table=table or ",".join(result.get("db2_tables", [])[:2]),
        )
        row = ev.row()
        result["trace_events"].append(row)
        result["events"].append(row)
        result["timeline"].append(row)


def _smf80(state: Any, result: dict[str, Any], slug: str, user: str, status: str, resource: str, detail: str = "") -> None:
    ev = emit_smf80(state, event=f"LAB_{slug.upper()}", user=user, channel="WEB9080", result=status, resource=resource, endpoint=f"/webapi/labs/{slug}/{result['mode']}", correlation_id=result["correlation_id"], detail=detail)
    result["smf_events"].append(ev.row())


def _smf102(state: Any, result: dict[str, Any], slug: str, user: str, status: str, table: str, detail: str = "") -> None:
    ev = emit_smf102(state, event=f"LAB_{slug.upper()}", user=user, channel="WEB9080", result=status, resource=table, table=table, endpoint=f"/webapi/labs/{slug}/{result['mode']}", correlation_id=result["correlation_id"], detail=detail)
    result["smf_events"].append(ev.row())


def _smf110(state: Any, result: dict[str, Any], slug: str, user: str, status: str, tran: str, prog: str, detail: str = "") -> None:
    ev = emit_smf110(state, event=f"LAB_{slug.upper()}", user=user, channel="WEB9080", result=status, resource=f"CICS.{tran}", transaction=tran, program=prog, endpoint=f"/webapi/labs/{slug}/{result['mode']}", correlation_id=result["correlation_id"], detail=detail)
    result["smf_events"].append(ev.row())


def _finish(state: Any, result: dict[str, Any], slug: str, user: str, status: str, scenario: str, payload: str, components: list[str], rows: int = 0, table: str = "") -> dict[str, Any]:
    store = get_cbsa_store(state)
    ev = _audit(store, user, slug, payload, status, scenario, result["correlation_id"])
    result["evidence_id"] = ev["EVENT_ID"]
    result["response"].setdefault("evidence_id", ev["EVENT_ID"])
    _emit_path(state, result, slug, user, components, rows=rows, table=table, message=f"{slug} {status}")
    return result


def _sqli_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "sqli"
    result = _base_result(slug, user, payload, "secure-compare" if secure else "run", trace_id)
    vulnerable = (_mode(state) != "SECURE") and not secure
    search = teller_search(state, store, payload or "1001", "all", user, vulnerable)
    scenario = "SQLI" if vulnerable and "'" in payload else ""
    status = search.get("result", "OK")
    result["request"] = {"method": "GET", "endpoint": "/webapi/teller/search", "query": {"type": "all", "q": payload}}
    result["response"] = {"status": 200, "result": status, "rows_returned": search.get("rows_returned", 0), "customers": search.get("customers", [])[:5], "accounts": search.get("accounts", [])[:5]}
    _lab_meta(result, slug)
    result["simulated_sql"] = search.get("simulated_sql", result.get("simulated_sql", ""))
    result["cics_transaction"] = "OMEN / INQCUST / INQACC"
    result["cics_program"] = "TELLER_SEARCH / INQCUST / INQACC"
    result["db2_tables"] = ["CBSA.CUSTOMER", "CBSA.ACCOUNT", "CBSA.SQLI_EVENTS", "CBSA.VULN_EVENTS", "CBSA.WEB_AUDIT"]
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "SQL", "DB2", "SMF", "CONSOLE"], int(search.get("rows_returned", 0) or 0), "CBSA.ACCOUNT")
    if scenario:
        _smf102(state, result, slug, user, "SUCCESS", "CBSA.ACCOUNT", f"rows_returned={result['response']['rows_returned']}")
        result["console_alerts"].append(f"GIBSQLI01W SQLI TRAINING PAYLOAD DETECTED CHANNEL=WEB9080 CORRID={result['correlation_id']}")
    else:
        _smf101 = emit_smf101(state, event="TELLER_SEARCH", user=user, channel="WEB9080", result="SUCCESS", resource="CBSA.ACCOUNT", table="CBSA.ACCOUNT", endpoint="/webapi/labs/sqli/run", correlation_id=result["correlation_id"])
        result["smf_events"].append(_smf101.row())
    result["secure_comparison"] = "Secure mode treats the payload as literal data; no rowset expansion or metadata extraction occurs." if secure else "Vulnerable mode shows the unsafe query path; use secure comparison to validate the fix."
    result["teaching_notes"] = ["Db2 can return rows correctly while the API layer remains vulnerable.", "Trace ID binds the browser action to CBSA, CICS, SQL and SMF-style evidence."]
    return result


def _idor_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "idor"
    result = _base_result(slug, user, payload or "00000103", "secure-compare" if secure else "run", trace_id)
    svc = CbsaService(state)
    account_id = (payload or "00000103").strip().zfill(8)
    sess_user = store.web_users.get(user.upper(), {})
    allowed_customer = sess_user.get("CUSTOMER_ID") or "1001"
    vulnerable = (_mode(state) != "SECURE") and not secure
    try:
        acct = svc.account(account_id)
        authorized = acct.customer_id == allowed_customer or not allowed_customer
        if vulnerable or authorized:
            body = acct.row()
            status = "VULNERABLE_OBJECT_RETURNED" if not authorized else "AUTHORIZED"
            code = 200
        else:
            body = {"error": "account access denied", "account": account_id}
            status = "DENIED_SECURE"
            code = 403
    except Exception as e:
        body = {"error": str(e)}; status = "NOT_FOUND"; code = 404; authorized = False
    scenario = "IDOR" if vulnerable and not authorized and code == 200 else ""
    result["request"] = {"method": "GET", "endpoint": f"/accounts/{account_id}", "object_id": account_id, "acting_customer": allowed_customer}
    result["response"] = {"status": code, "result": status, "account": body, "authorization": {"authorized": authorized, "enforced": not vulnerable}}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "DB2", "SMF", "CONSOLE"], 1 if code == 200 else 0, "CBSA.ACCOUNT")
    _smf80(state, result, slug, user, status, f"CBSA.ACCOUNT.{account_id}", "object ownership check")
    result["console_alerts"].append(f"GIBAPI401W API AUTHZ TRAINING EVENT TYPE=BOLA USER={user.upper()} OBJECT={account_id} RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour enforces customer-account ownership and returns 403 for cross-customer objects." if secure else "Vulnerable behaviour returns a valid Db2 account row without object-level authorization."
    return result


def _mass_assignment_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "mass-assignment"
    result = _base_result(slug, user, payload or "name=Alice&role=admin&isAdmin=true", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    svc = CbsaService(state)
    target = store.web_users.get(user.upper(), {}).get("CUSTOMER_ID") or "1001"
    before = svc.customer(target).row().copy()
    vulnerable = (_mode(state) != "SECURE") and not secure
    allowed = {k: v for k, v in data.items() if k in {"name", "address1", "address2", "date_of_birth"}}
    applied = data if vulnerable else allowed
    svc.update_customer(target, applied, channel="WEB9080", vulnerable=vulnerable)
    after = svc.customer(target).row().copy()
    restricted = sorted(set(data) - set(allowed))
    status = "VULNERABLE_PRIVILEGED_FIELDS_APPLIED" if vulnerable and restricted else "BLOCKED_SECURE" if restricted else "UPDATED"
    scenario = "MASS_ASSIGNMENT" if vulnerable and restricted else ""
    result["request"] = {"method": "POST", "endpoint": "/profile", "body": data}
    result["response"] = {"status": 200, "result": status, "restricted_fields": restricted, "before": before, "after": after, "allowlist_enforced": not vulnerable}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "DB2", "SMF", "CONSOLE"], 1, "CBSA.CUSTOMER")
    _smf80(state, result, slug, user, status, f"CBSA.CUSTOMER.{target}", "property authorization")
    result["console_alerts"].append(f"GIBAPI403I MASS ASSIGNMENT {'DETECTED' if scenario else 'BLOCKED'} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour allowlists profile fields and ignores privileged properties." if secure else "Vulnerable behaviour binds unexpected request properties into sensitive customer fields."
    return result


def _weak_auth_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "weak-auth"
    result = _base_result(slug, user, payload or "username=alice&weak_auth=1", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    username = data.get("username", "alice")
    weak = data.get("weak_auth") == "1"
    vulnerable = (_mode(state) != "SECURE") and not secure
    accepted = bool(vulnerable and weak) or bool(store.verify_web_user(username, data.get("password", "")))
    status = "WEAK_AUTH_ACCEPTED" if vulnerable and weak else "AUTHENTICATED" if accepted else "REJECTED_SECURE"
    scenario = "WEAK_AUTH" if vulnerable and weak else ""
    result["request"] = {"method": "POST", "endpoint": "/login", "body": {k: ('***' if k == 'password' else v) for k, v in data.items()}}
    result["response"] = {"status": 200 if accepted else 401, "result": status, "accepted": accepted, "mfa_required": not vulnerable, "gacf_user": username.upper()}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "GACF", "SMF", "CONSOLE"], 1 if accepted else 0, "CBSA.WEB_USERS")
    _smf80(state, result, slug, user, status, f"GACF.USER.{username.upper()}", "authentication decision")
    result["console_alerts"].append(f"GIBAUTH02W WEAK AUTH TRAINING EVENT USER={username.upper()} RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour ignores weak-auth flags and requires verified credentials/MFA policy." if secure else "Vulnerable behaviour accepts a controlled weak-auth training flag."
    return result


def _verbose_errors_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "verbose-errors"
    result = _base_result(slug, user, payload or "'", "secure-compare" if secure else "run", trace_id)
    vulnerable = (_mode(state) != "SECURE") and not secure
    detail = "SQLCODE=-104 SQLSTATE=42601 PLAN=FIBSWEB TABLE=CBSA.ACCOUNT TRAN=INQCUST PROGRAM=TELLER_SEARCH"
    status = "VERBOSE_ERROR_LEAKED" if vulnerable else "GENERIC_ERROR_WITH_CORRELATION"
    user_error = detail if vulnerable else f"Request failed. Reference correlation ID {result['correlation_id']}."
    scenario = "VERBOSE_ERRORS" if vulnerable else ""
    result["request"] = {"method": "GET", "endpoint": "/webapi/teller/search", "query": {"q": result["payload"]}}
    result["response"] = {"status": 500 if vulnerable else 400, "result": status, "user_message": user_error, "backend_detail_logged": detail}
    _lab_meta(result, slug)
    result["simulated_sql"] = "SELECT * FROM CBSA.ACCOUNT WHERE CUSTOMER_ID = '<payload>'"
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "SQL", "DB2", "SMF", "CONSOLE"], 0, "CBSA.ACCOUNT")
    _smf102(state, result, slug, user, status, "CBSA.ACCOUNT", detail)
    _smf110(state, result, slug, user, status, "INQC", "INQCUST", detail)
    result["console_alerts"].append(f"GIBERR01W VERBOSE ERROR TRAINING EVENT DETAIL_REDACTED={'NO' if vulnerable else 'YES'} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour keeps SQLCODE/CICS detail in backend trace and returns only a correlation ID." if secure else "Vulnerable behaviour exposes SQLCODE, plan, table, transaction and program details to the browser."
    return result


def _business_logic_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "business-logic"
    result = _base_result(slug, user, payload or "from=00000101&to=00000103&amount=-25.00", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    svc = CbsaService(state)
    from_acc = data.get("from", data.get("from_account", "00000101"))
    to_acc = data.get("to", data.get("to_account", "00000103"))
    amount = data.get("amount", "-25.00")
    vulnerable = (_mode(state) != "SECURE") and not secure
    try:
        if Decimal(str(amount)) <= 0 and not vulnerable:
            raise ValueError("AMOUNT MUST BE POSITIVE")
        src, dst = svc.transfer(from_acc, to_acc, amount, channel="WEB9080", vulnerable=vulnerable)
        status = "VULNERABLE_RULE_BYPASS" if vulnerable and Decimal(str(amount)) <= 0 else "TRANSFER_ACCEPTED"
        body = {"from": src.row(), "to": dst.row()}
        code = 200
    except Exception as e:
        status = "BLOCKED_SECURE"; body = {"error": str(e)}; code = 422
    scenario = "BUSINESS_LOGIC" if status == "VULNERABLE_RULE_BYPASS" else ""
    result["request"] = {"method": "POST", "endpoint": "/transfer", "body": {"from_account": from_acc, "to_account": to_acc, "amount": amount}}
    result["response"] = {"status": code, "result": status, "ledger": body, "rule": "amount must be positive and transfer sequence must be valid"}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "DB2", "SMF", "CONSOLE"], 1 if code == 200 else 0, "CBSA.PROCTRAN")
    ev101 = emit_smf101(state, event="LAB_BUSINESS_LOGIC", user=user, channel="WEB9080", result=status, resource="CBSA.PROCTRAN", table="CBSA.PROCTRAN", endpoint="/webapi/labs/business-logic/run", correlation_id=result["correlation_id"], detail="business rule decision")
    result["smf_events"].append(ev101.row())
    _smf110(state, result, slug, user, status, "PAYM", "PAYMENT", "payment sequence")
    result["console_alerts"].append(f"GIBPAY01W BUSINESS LOGIC TRAINING EVENT RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour enforces amount bounds, sequence and idempotency." if secure else "Vulnerable behaviour demonstrates a controlled transfer rule bypass."
    return result


def _method_override_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "method-override"
    result = _base_result(slug, user, payload or "_method=DELETE&account=00000103", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    override = data.get("_method") or data.get("X-HTTP-Method-Override") or "DELETE"
    vulnerable = (_mode(state) != "SECURE") and not secure
    accepted = vulnerable and override.upper() in {"DELETE", "PUT", "PATCH"}
    status = "METHOD_OVERRIDE_ACCEPTED" if accepted else "OVERRIDE_REJECTED_SECURE"
    scenario = "METHOD_OVERRIDE" if accepted else ""
    result["request"] = {"method": "POST", "endpoint": "/webapi/accounts", "headers": {"X-HTTP-Method-Override": override}, "body": data}
    result["response"] = {"status": 202 if accepted else 405, "result": status, "effective_method": override.upper() if accepted else "POST", "policy": "method override disabled" if not accepted else "unsafe override honoured"}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "CBSA", "CICS", "DB2", "SMF", "CONSOLE"], 1 if accepted else 0, "CBSA.API_AUDIT")
    _smf102(state, result, slug, user, status, "CBSA.API_AUDIT", "method normalisation")
    result["console_alerts"].append(f"GIBAPI405W UNSAFE METHOD OVERRIDE TRAINING EVENT RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour rejects method override headers/parameters unless explicitly allowed." if secure else "Vulnerable behaviour honours method override and bypasses route restrictions."
    return result


def _excessive_data_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "excessive-data"
    cid = (payload or "1001").strip() or "1001"
    result = _base_result(slug, user, cid, "secure-compare" if secure else "run", trace_id)
    c = store.customers.get(cid)
    vulnerable = (_mode(state) != "SECURE") and not secure
    if not c:
        row = {"error": "not found"}; status = "NOT_FOUND"; code = 404
    else:
        row = c.row()
        if not vulnerable:
            row = {k: v for k, v in row.items() if k not in {"RISK_SCORE", "ISADMIN", "CREDITLIMIT", "CREDIT_SCORE", "DATE_OF_BIRTH"}}
        status = "EXCESSIVE_DATA_RETURNED" if vulnerable else "MINIMAL_DATA_RETURNED"
        code = 200
    scenario = "EXCESSIVE_DATA" if vulnerable and code == 200 else ""
    result["request"] = {"method": "GET", "endpoint": f"/webapi/debug/customer/{cid}", "object_id": cid}
    result["response"] = {"status": code, "result": status, "customer": row, "field_count": len(row)}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, cid, ["WEB9080", "CBSA", "CICS", "DB2", "SMF", "CONSOLE"], 1 if code == 200 else 0, "CBSA.CUSTOMER")
    _smf102(state, result, slug, user, status, "CBSA.CUSTOMER", "debug customer exposure")
    result["console_alerts"].append(f"GIBDATA01W EXCESSIVE DATA TRAINING EVENT FIELDS={len(row)} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour returns only fields required by the user story." if secure else "Vulnerable behaviour returns internal customer, risk and credit fields."
    return result


def _jwt_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "jwt"
    result = _base_result(slug, user, payload or "lab=alg_none&sub=alice&role=admin", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    data.setdefault("lab", "role_tamper" if "role_tamper" in result["payload"] else "alg_none")
    data.setdefault("sub", "alice")
    data.setdefault("role", "admin")
    vulnerable = (_mode(state) != "SECURE") and not secure
    identity_result = lab_jwt_forge(state, data) if vulnerable else {"accepted": False, "result": "REJECTED_SECURE", "reason": "strict JWT validation"}
    status = "JWT_ACCEPTED_VULN" if vulnerable and identity_result.get("accepted") else "JWT_REJECTED_SECURE"
    scenario = "JWT" if vulnerable else ""
    result["request"] = {"method": "POST", "endpoint": "/webapi/labs/jwt/forge", "body": data}
    result["response"] = {"status": 200, "result": status, "identity_result": identity_result}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, result["payload"], ["WEB9080", "IDENTITY", "GACF", "SMF", "CONSOLE"], 1, "CBSA.WEB_USERS")
    _smf80(state, result, slug, user, status, "JWT.FIBS", "token validation")
    result["console_alerts"].append(f"GIBJWT01W JWT TRAINING EVENT RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour enforces signature, algorithm and role claims." if secure else "Vulnerable behaviour demonstrates a forged/tampered JWT training path."
    return result


def _oauth_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "oauth"
    result = _base_result(slug, user, payload or "redirect_uri=http://evil.example/callback&scope=openid admin", "secure-compare" if secure else "run", trace_id)
    data = _parse_payload(result["payload"])
    data.setdefault("client_id", "fibs-web")
    data.setdefault("redirect_uri", "http://evil.example/callback")
    data.setdefault("scope", "openid admin")
    vulnerable = (_mode(state) != "SECURE") and not secure
    identity_result = lab_oauth_authorize(state, data, user) if vulnerable else {"accepted": False, "result": "REJECTED_SECURE", "reason": "exact redirect/state/PKCE required"}
    status = "OAUTH_ACCEPTED_VULN" if vulnerable and identity_result.get("accepted") else "OAUTH_REJECTED_SECURE"
    scenario = "OAUTH" if vulnerable else ""
    result["request"] = {"method": "POST", "endpoint": "/webapi/labs/oauth/authorize", "body": data}
    result["response"] = {"status": 200, "result": status, "identity_result": identity_result}
    _lab_meta(result, slug)
    _finish(state, result, slug, user, status, scenario, result["payload"], ["WEB9080", "IDENTITY", "GACF", "SMF", "CONSOLE"], 1, "CBSA.WEB_USERS")
    _smf80(state, result, slug, user, status, "OAUTH.FIBS", "redirect/scope decision")
    result["console_alerts"].append(f"GIBOAUTH01W OAUTH TRAINING EVENT RESULT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure behaviour requires exact redirect, state and PKCE-style checks." if secure else "Vulnerable behaviour demonstrates unsafe redirect/scope handling."
    return result


def _cobol_bo_lab(state: Any, store: Any, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    slug = "cobol-buffer-overflow"
    p = payload or "ALICE-TRANSFER-0001"
    result = _base_result(slug, user, p, "secure-compare" if secure else "run", trace_id)
    _lab_meta(result, slug)
    vulnerable = (_mode(state) != "SECURE") and not secure
    crash = len(p) > 12 and ("1234567890" in p or len(p) > 140)
    auth_overwrite = p.endswith("Y") and len(p) >= 30
    channel_overflow = "USERDATA=" in p or len(p) > 120
    scenario = "COBOL_BUFFER_OVERFLOW" if vulnerable and (crash or auth_overwrite or channel_overflow) else ""
    status = "BLOCKED_SECURE" if secure or not vulnerable else ("SIMULATED_ABEND" if crash else ("AUTH_FLAG_OVERWRITE" if auth_overwrite else ("CHANNEL_OVERFLOW" if channel_overflow else "NORMAL")))
    result["request"] = {"method": "POST", "endpoint": "/webapi/labs/cobol-buffer-overflow/run", "body": {"payload": _clip(p, 240)}}
    result["response"] = {"status": 200, "result": status, "rows_returned": 1, "authenticated_flag": "Y" if vulnerable and auth_overwrite else "N", "abend": "ASRA/S0C4" if vulnerable and crash else ""}
    result["cics_transaction"] = "BOFL / BANKBO"
    result["cics_program"] = "VULNERABLE-BANK-UPDATE / VULNBO"
    result["db2_tables"] = ["CBSA.WEB_AUDIT", "CBSA.VULN_EVENTS", "CBSA.PROCTRAN"]
    result["simulated_sql"] = "INSERT INTO CBSA.VULN_EVENTS(EVENT_ID, SCENARIO, RESULT) VALUES (?, 'COBOL_BUFFER_OVERFLOW', ?)"
    _finish(state, result, slug, user, status, scenario, p, ["WEB9080", "CICS", "COBOL", "AUDIT", "SMF", "CONSOLE"], 1, "CBSA.VULN_EVENTS")
    _smf110(state, result, slug, user, status, "BOFL", "VULNBO", "ABEND=ASRA/S0C4" if crash else "COBOL channel validation")
    _smf80(state, result, slug, user, status, "CICS.BOFL", "COBOL buffer-overflow training event")
    result["console_alerts"].append(f"DFHAC2206W GIBCICS TRAN=BOFL PROGRAM=VULNBO EVENT={status} CORRID={result['correlation_id']}")
    result["secure_comparison"] = "Secure mode rejects oversized input and records only defensive evidence." if secure else "Vulnerable mode simulates flag overwrite or abend based on payload length/content."
    return result


# --- Identity Academy runners (PassTicket + MFA) -------------------------
def _identity_result(state: Any, store: Any, slug: str, payload: str, user: str, secure: bool, trace_id: str = "") -> dict[str, Any]:
    result = _base_result(slug, user, payload, "secure-compare" if secure else "run", trace_id)
    _lab_meta(result, slug)
    pt = get_passticket_service(state)
    status = "OK"
    scenario = slug.upper().replace('-', '_')
    response: dict[str, Any] = {"result": status, "identity_result": scenario, "secure_mode": secure}
    extra_events: list[dict[str, str]] = []
    user_u = (user or "WEBUSER").upper()
    if slug.startswith("passticket"):
        if slug == "passticket-concepts":
            response.update({"profiles": pt.profile_rows(), "issued": pt.issued_rows(), "audit": pt.audit_rows(), "terminal_equivalent": "PTKTSTAT; RLIST PTKTDATA CICS"})
        elif slug == "passticket-generate-validate":
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-LAB")
            val = pt.validate("IBMUSER", "CICS", gen.get("ticket", ""), consumer="WEB9080-LAB") if gen.get("ok") else {"ok": False, "message": gen.get("message", "generate failed")}
            response.update({"generate": gen, "validate": val, "terminal_equivalent": "PTKTGEN USER(IBMUSER) APPL(CICS); PTKTUSE USER(IBMUSER) APPL(CICS) TICKET(token)"})
        elif slug == "passticket-cics-cesn":
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-CESN")
            val = pt.validate("IBMUSER", "CICS", gen.get("ticket", ""), consumer="CESN") if gen.get("ok") else {"ok": False}
            response.update({"generate": gen, "cesn": val, "terminal_equivalent": "CESN USER(IBMUSER) PTKT(token) APPL(CICS)"})
        elif slug == "passticket-gmvb-banking":
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-GMVB")
            val = pt.validate("IBMUSER", "CICS", gen.get("ticket", ""), consumer="GMVB") if gen.get("ok") else {"ok": False}
            response.update({"generate": gen, "gmvb": val, "terminal_equivalent": "GMVB LOGN IBMUSER PTKT token CICS"})
        elif slug == "passticket-tso-logon":
            appl = "TSOGIBS" if getattr(state.config, "strict_tso_ptkt", False) else "TSO"
            gen = pt.generate("IBMUSER", appl, "IBMUSER", source="WEB9080-TSO")
            response.update({"generate": gen, "terminal_equivalent": f"USERID IBMUSER PASSWORD PTKT({gen.get('ticket','TOKEN')})", "applid": appl})
        elif slug == "passticket-db2-evidence":
            response.update({"profiles": pt.profile_rows(), "issued": pt.issued_rows(), "audit": pt.audit_rows(), "terminal_equivalent": "RUN SQL SELECT * FROM GIBSON.PTKT_AUDIT"})
        elif slug == "passticket-replay-protection":
            pt.set_profile_flags("CICS", replay_protection=True)
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-REPLAY")
            first = pt.validate("IBMUSER", "CICS", gen.get("ticket", ""), consumer="FIRST") if gen.get("ok") else {"ok": False}
            second = pt.validate("IBMUSER", "CICS", gen.get("ticket", ""), consumer="SECOND") if gen.get("ok") else {"ok": False}
            response.update({"generate": gen, "first_use": first, "second_use": second, "replay_blocked": not second.get("ok", True)})
            extra_events.append(emit_identity_event(state, event_type="PTKT_REPLAY_DENIED", user=user_u, service="PTKT", result="DENIED", resource="CICS", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="PassTicket replay attempt rejected"))
        elif slug == "passticket-applid-mismatch":
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-MISMATCH")
            mismatch = pt.validate("IBMUSER", "DB2", gen.get("ticket", ""), consumer="DB2") if gen.get("ok") else {"ok": False}
            response.update({"generate": gen, "mismatch_attempt": mismatch, "mismatch_blocked": not mismatch.get("ok", True)})
            extra_events.append(emit_identity_event(state, event_type="PTKT_APPL_MISMATCH", user=user_u, service="PTKT", result="DENIED", resource="CICS->DB2", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="PassTicket APPLID mismatch rejected"))
        elif slug == "passticket-overbroad-irrptauth":
            gen = pt.generate("IBMUSER", "CICS", "WEBBANK", source="WEB9080-IRRPTAUTH")
            response.update({"generate_by_webbank": gen, "risk": "WEBBANK can request CICS PassTickets through IRRPTAUTH.CICS.*", "secure_fix": "Narrow IRRPTAUTH to specific users and services"})
            extra_events.append(emit_identity_event(state, event_type="PTKT_IRRPTAUTH_OVERBROAD", user="WEBBANK", service="PTKT", result="WARNING", resource="IRRPTAUTH.CICS.*", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="Overbroad PassTicket generation authority"))
        elif slug == "passticket-debug-leakage":
            pt.set_profile_flags("CICS", leak=not secure)
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-LEAK")
            response.update({"generate": gen, "controlled_lab_evidence_leak": gen.get("ticket") if gen.get("ok") and not secure else "<redacted>", "contained": True, "secure_fix": "Disable LABLEAK and redact tokens from logs"})
            if not secure:
                extra_events.append(emit_identity_event(state, event_type="PTKT_DEBUG_LEAK", user=user_u, service="PTKT", result="WARNING", resource="CICS", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="Lab-only PassTicket debug leakage"))
        elif slug == "passticket-expiry":
            pt.set_profile_flags("CICS", valid_secs=1)
            gen = pt.generate("IBMUSER", "CICS", "IBMUSER", source="WEB9080-EXPIRY")
            token = gen.get("ticket", "")
            if token in pt.issued:
                pt.issued[token].expires_at = "2000-01-01T00:00:00+00:00"
            val = pt.validate("IBMUSER", "CICS", token, consumer="EXPIRY") if token else {"ok": False}
            response.update({"generate": gen, "expired_validate": val, "expired": not val.get("ok", True)})
            pt.set_profile_flags("CICS", valid_secs=600)
            extra_events.append(emit_identity_event(state, event_type="PTKT_EXPIRED", user=user_u, service="PTKT", result="DENIED", resource="CICS", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="INFO", detail="Expired PassTicket rejected"))
        elif slug == "passticket-hardening":
            for a in ["TSO","TSOGIBS","CICS","DB2","WEBBANK"]:
                pt.set_profile_flags(a, replay_protection=True, appl_mismatch=False, leak=False, valid_secs=300 if secure else 600)
            response.update({"hardened_profiles": pt.profile_rows(), "controls": ["replay protection", "strict APPL binding", "narrow IRRPTAUTH", "no debug leakage", "short lifetime"]})
            extra_events.append(emit_identity_event(state, event_type="IDENTITY_HARDENING_APPLIED", user=user_u, service="PTKT", result="SUCCESS", resource="PTKTDATA", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="INFO", detail="PassTicket hardening applied"))
    else:
        policy = getattr(state, "mfa_policy", None)
        if policy is None:
            from gibson.core.mfa import MfaPolicyStore
            policy = MfaPolicyStore.seeded(); state.mfa_policy = policy
        if slug == "mfa-concepts-zos":
            response.update({"required_services": policy.required_services, "users": {k: v.factors for k,v in policy.users.items()}, "terminal_equivalent": "RACFADMIN MFA IBMUSER"})
        elif slug == "mfa-tso-enforcement":
            policy.set_required("TSO", True); no = policy.validate("RUARIV", "TSO", ""); yes = policy.validate("RUARIV", "TSO", "222222")
            response.update({"without_factor": no.__dict__, "with_factor": yes.__dict__, "expected_token": "222222"})
        elif slug == "mfa-cics-step-up":
            no = policy.validate("TELLER", "CICS", "", stepup="GMVB.ADMIN"); yes = policy.validate("TELLER", "CICS", "333333", stepup="GMVB.ADMIN")
            response.update({"without_stepup": no.__dict__, "with_stepup": yes.__dict__, "transaction": "GMVB.ADMIN"})
        elif slug == "mfa-service-gap-ftp":
            policy.set_required("TSO", True); policy.set_required("FTP", False); dec = policy.validate("RUARIV", "FTP", "")
            response.update({"ftp_decision": dec.__dict__, "risk": "TSO requires MFA but FTP remains password-only"})
            extra_events.append(emit_identity_event(state, event_type="MFA_SERVICE_GAP", user="RUARIV", service="MFA", result="WARNING", resource="FTP", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="MFA not enforced consistently across services"))
        elif slug == "mfa-fallback-breakglass":
            dec = policy.validate("IBMUSER", "TSO", "")
            response.update({"breakglass_decision": dec.__dict__, "risk": "Break-glass account used; monitor and restrict"})
            extra_events.append(emit_identity_event(state, event_type="MFA_BREAKGLASS_USED", user="IBMUSER", service="MFA", result="WARNING", resource="TSO", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="Break-glass MFA exemption"))
        elif slug == "mfa-shared-factor-seed":
            policy.enrolled("TELLER").seed = policy.enrolled("RUARIV").seed
            response.update({"shared_seed_users": ["RUARIV", "TELLER"], "seed": policy.enrolled("RUARIV").seed, "secure_fix": "Assign unique factor seeds"})
            extra_events.append(emit_identity_event(state, event_type="MFA_SHARED_FACTOR", user="SYSTEM", service="MFA", result="WARNING", resource="RUARIV,TELLER", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="Shared MFA factor seed detected"))
        elif slug == "mfa-passticket-bypass":
            gen = pt.generate("RUARIV", "CICS", "WEBBANK", source="WEB9080-MFA-BYPASS")
            response.update({"passticket_generated_without_mfa_context": gen, "risk": "Trusted middle tier can create a PassTicket before MFA context is proven", "secure_fix": "Require MFA context for PassTicket generation"})
            extra_events.append(emit_identity_event(state, event_type="MFA_PASSTICKET_BYPASS", user="WEBBANK", service="MFA/PTKT", result="WARNING", resource="CICS", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="ALERT", detail="PassTicket issued without MFA context"))
        elif slug == "mfa-fatigue-concept":
            response.update({"simulated_prompts": 5, "risk": "Repeated prompts can condition users to approve requests", "safe": True})
            extra_events.append(emit_identity_event(state, event_type="MFA_FAILURE", user="RUARIV", service="MFA", result="WARNING", resource="PUSH", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="INFO", detail="Safe conceptual MFA fatigue simulation"))
        elif slug == "mfa-audit-review":
            response.update({"mfa_audit": policy.audit, "identity_events": getattr(state, "identity_events", [])[-10:]})
        elif slug == "mfa-hardening":
            for svc in ["TSO","CICS","FTP","ZOSMF"]: policy.set_required(svc, True)
            state.config.mfa_require_context_for_passticket = True
            response.update({"required_services": policy.required_services, "mfa_context_for_passticket": True, "fallback_review": "restricted"})
            extra_events.append(emit_identity_event(state, event_type="IDENTITY_HARDENING_APPLIED", user=user_u, service="MFA", result="SUCCESS", resource="MFA_POLICY", correlation_id=result["correlation_id"], trace_id=result["trace_id"], severity="INFO", detail="MFA hardening applied"))
    result["request"] = {"method": "POST", "endpoint": f"/webapi/labs/{slug}/{result['mode']}", "payload": payload}
    result["response"] = {"status": 200, **response}
    _finish(state, result, slug, user, status, scenario, payload, ["WEB9080", "RACF", "IDENTITY", "SMF", "SDSF", "ZSECURE"], 1, "IDENTITY.EVIDENCE")
    _smf80(state, result, slug, user, status, "IDENTITY.EVIDENCE", "Identity Academy lab event")
    for ev in extra_events:
        result["trace_events"].append(ev); result["events"].append(ev); result["timeline"].append(ev)
    result["secure_comparison"] = "Secure comparison enforces the recommended control and records identity evidence." if secure else "Vulnerable path demonstrates the identity risk; use secure comparison to view the fix."
    result["teaching_notes"] = ["This is a safe Gibson simulation.", "Terminal equivalents are provided for TSO/CICS reinforcement.", "Review SMF80/SDSF/zSecure/dashboard evidence after the run."]
    return result

_RUNNERS = {
    "sqli": _sqli_lab,
    "idor": _idor_lab,
    "mass-assignment": _mass_assignment_lab,
    "weak-auth": _weak_auth_lab,
    "verbose-errors": _verbose_errors_lab,
    "business-logic": _business_logic_lab,
    "method-override": _method_override_lab,
    "excessive-data": _excessive_data_lab,
    "jwt": _jwt_lab,
    "oauth": _oauth_lab,
    "cobol-buffer-overflow": _cobol_bo_lab,
}

_IDENTITY_SLUGS = [s for s in get_lab.__globals__.get("LABS", {}) if s.startswith("passticket-") or s.startswith("mfa-")]
for _slug in _IDENTITY_SLUGS:
    _RUNNERS[_slug] = (lambda state, store, payload, user, secure, trace_id, slug=_slug: _identity_result(state, store, slug, payload, user, secure, trace_id))


def run_lab(state: Any, slug: str, payload: str, user: str = "WEBUSER", trace_id: str = "") -> dict[str, Any]:
    store = get_cbsa_store(state)
    runner = _RUNNERS.get(slug)
    if not runner:
        raise KeyError(f"Unknown lab slug: {slug}")
    return runner(state, store, payload, user, False, trace_id)


def secure_compare(state: Any, slug: str, payload: str, user: str = "WEBUSER", trace_id: str = "") -> dict[str, Any]:
    store = get_cbsa_store(state)
    runner = _RUNNERS.get(slug)
    if not runner:
        raise KeyError(f"Unknown lab slug: {slug}")
    return runner(state, store, payload, user, True, trace_id)


def reset_lab(state: Any, slug: str, user: str = "WEBUSER", trace_id: str = "") -> dict[str, Any]:
    if not get_lab(slug):
        raise KeyError(f"Unknown lab slug: {slug}")
    corr = trace_id or _corr("RESET")
    if slug.startswith("passticket-"):
        try:
            pt = get_passticket_service(state)
            for a in ["TSO", "TSOGIBS", "CICS", "DB2", "WEBBANK"]:
                pt.set_profile_flags(a, replay_protection=True, appl_mismatch=False, leak=False, valid_secs=600)
            pt.issued.clear()
        except Exception:
            pass
    if slug.startswith("mfa-"):
        try:
            from gibson.core.mfa import MfaPolicyStore
            state.mfa_policy = MfaPolicyStore.seeded()
        except Exception:
            pass
    clear_trace_events(state, corr)
    ev = emit_trace_event(state, component="WEB9080", action=f"RESET_{slug.upper().replace('-', '_')}", user=user, route=f"/webapi/labs/{slug}/reset", result="OK", correlation_id=corr, trace_id=corr, message="Lab reset completed")
    return {"lab": slug, "mode": "reset", "status": "reset", "result": "reset", "trace_id": corr, "correlation_id": corr, "evidence_id": "", "request": {"method": "POST", "endpoint": f"/webapi/labs/{slug}/reset"}, "response": {"status": 200, "result": "RESET", "message": "Lab reset complete"}, "trace_events": [ev.row()], "events": [ev.row()], "timeline": [ev.row()], "smf_events": [], "console_alerts": [], "secure_comparison": "Lab state reset; run the vulnerable or secure path again."}


def export_evidence(state: Any, slug: str, evidence_id: str = "", user: str = "WEBUSER", trace_id: str = "") -> dict[str, Any]:
    store = get_cbsa_store(state)
    events: list[dict[str, Any]] = []
    for group in (store.web_audit, store.vuln_events, store.sqli_events, store.api_audit, store.cics_audit, store.web_lab_events):
        events.extend([e for e in group if (not evidence_id or e.get("EVENT_ID") == evidence_id) and (not trace_id or e.get("CORRELATION_ID") == trace_id)])
    return {
        "lab": slug,
        "evidence_id": evidence_id,
        "trace_id": trace_id,
        "user": user,
        "events": events[-50:],
        "trace_events": get_trace_events(state, trace_id=trace_id) if trace_id else getattr(state, "backend_trace_events", [])[-50:],
        "security_training_events": [e for e in getattr(state, "security_training_events", [])[-100:] if not trace_id or e.get("correlation_id") == trace_id],
        "note": "Training evidence export; secrets, cookies and passwords are not included.",
    }
