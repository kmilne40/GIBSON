from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional
import uuid


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid money amount: {value!r}")


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


class GmvbBankingService:
    """Shared GMVB banking service for React, CICS, REST, TSO DB2 and SPUFI.

    The service is deliberately simulator-only.  It provides a stable banking
    model inspired by the supplied CICS banking sample, but all user-facing
    names and routes remain GMVB.  Data is stored on the shared Gibson state so
    callers in different subsystems see the same rows.
    """

    BATCH_RELEASE_PIN = "0032"

    def __init__(self, state: Any):
        self.state = state
        self._ensure_seed()

    @classmethod
    def get(cls, state: Any) -> "GmvbBankingService":
        svc = getattr(state, "gmvb_banking_service", None)
        if svc is None:
            svc = cls(state)
            setattr(state, "gmvb_banking_service", svc)
        else:
            svc._ensure_seed()
        return svc

    def _ensure_seed(self) -> None:
        if not hasattr(self.state, "gmvb_customers_shared"):
            self.state.gmvb_customers_shared = self._seed_customers()
        if not hasattr(self.state, "gmvb_accounts_shared"):
            self.state.gmvb_accounts_shared = self._seed_accounts()
        if not hasattr(self.state, "gmvb_proctran_shared"):
            self.state.gmvb_proctran_shared = self._seed_transactions()
        if not hasattr(self.state, "gmvb_audit_shared"):
            self.state.gmvb_audit_shared = []
        if not hasattr(self.state, "gmvb_batch_transfer_shared"):
            self.state.gmvb_batch_transfer_shared = self._seed_batches()
        if not hasattr(self.state, "gmvb_swift_message_shared"):
            self.state.gmvb_swift_message_shared = self._seed_swift()
        if not hasattr(self.state, "gmvb_control_shared"):
            self.state.gmvb_control_shared = {
                "CONTROL_KEY": "GMVB",
                "CUSTOMER_COUNT": str(len(self.customers)),
                "CUSTOMER_LAST": max(self.customers) if self.customers else "10000000",
                "ACCOUNT_COUNT": str(len(self.accounts)),
                "ACCOUNT_LAST": max(self.accounts) if self.accounts else "1000000000",
                "PROCTRAN_COUNT": str(len(self.transactions)),
                "BATCH_LAST": "B2026A18",
                "SWIFT_LAST": "SWF000003",
                "UPDATED_TS": _ts(),
            }

    @property
    def customers(self) -> Dict[str, Dict[str, str]]:
        return self.state.gmvb_customers_shared

    @property
    def accounts(self) -> Dict[str, Dict[str, str]]:
        return self.state.gmvb_accounts_shared

    @property
    def transactions(self) -> List[Dict[str, str]]:
        return self.state.gmvb_proctran_shared

    @property
    def audit(self) -> List[Dict[str, str]]:
        return self.state.gmvb_audit_shared

    @property
    def batches(self) -> Dict[str, Dict[str, str]]:
        return self.state.gmvb_batch_transfer_shared

    @property
    def swift(self) -> Dict[str, Dict[str, str]]:
        return self.state.gmvb_swift_message_shared

    @property
    def control(self) -> Dict[str, str]:
        return self.state.gmvb_control_shared

    def _seed_customers(self) -> Dict[str, Dict[str, str]]:
        rows = [
            ("10000001", "JOHN", "SMITH", "12 HIGH STREET", "LONDON", "EC1A1AA", "1965-04-12", "721", "VERIFIED"),
            ("10000002", "MARGARET", "THATCHER", "10 DOWNING STREET", "LONDON", "SW1A2AA", "1925-10-13", "760", "VERIFIED"),
            ("10000003", "ALAN", "TURING", "76 WILMSLOW ROAD", "MANCHESTER", "M200QA", "1912-06-23", "800", "VERIFIED"),
            ("10000004", "GRACE", "HOPPER", "44 COBOL LANE", "ARLINGTON", "VA22201", "1906-12-09", "785", "VERIFIED"),
            ("10000005", "KATHERINE", "JOHNSON", "101 ORBIT WAY", "HAMPTON", "VA23666", "1918-08-26", "790", "VERIFIED"),
            ("10000006", "ADA", "LOVELACE", "1 ANALYTICAL ROW", "LONDON", "W1A1AA", "1815-12-10", "770", "REVIEW"),
            ("10000007", "MARTIN", "FOWLER", "8 REFACTOR CLOSE", "OXFORD", "OX12AB", "1963-12-18", "704", "VERIFIED"),
            ("10000008", "DOROTHY", "VAUGHAN", "22 MAINFRAME AVE", "BIRMINGHAM", "B11AA", "1910-09-20", "735", "VERIFIED"),
        ]
        data: Dict[str, Dict[str, str]] = {}
        for cid, first, last, addr, town, postcode, dob, score, kyc in rows:
            data[cid] = {
                "CUSTOMER_ID": cid,
                "SORT_CODE": "204514",
                "CUSTOMER_NUMBER": cid[-6:],
                "FULL_NAME": f"{first} {last}",
                "FORENAME": first,
                "SURNAME": last,
                "ADDRESS_LINE_1": addr,
                "ADDRESS_LINE_2": "",
                "TOWN": town,
                "POSTCODE": postcode,
                "DATE_OF_BIRTH": dob,
                "CREDIT_SCORE": score,
                "CREDIT_SCORE_REVIEW_DATE": "2026-12-31",
                "STATUS": "A",
                "KYC_STATUS": kyc,
                "CREATED_BY": "SYSTEM",
                "CREATED_TS": _ts(),
                "UPDATED_BY": "SYSTEM",
                "UPDATED_TS": _ts(),
            }
        return data

    def _seed_accounts(self) -> Dict[str, Dict[str, str]]:
        seeds = [
            ("1000000101", "10000001", "CUR", "3420.55", "3920.55", "500.00"),
            ("1000000102", "10000001", "SAV", "14200.00", "14200.00", "0.00"),
            ("1000000201", "10000002", "CUR", "8742.10", "9242.10", "500.00"),
            ("1000000202", "10000002", "SAV", "55000.00", "55000.00", "0.00"),
            ("1000000301", "10000003", "CUR", "1220.44", "1520.44", "300.00"),
            ("1000000401", "10000004", "CUR", "911.20", "1411.20", "500.00"),
            ("1000000501", "10000005", "CUR", "12500.00", "13000.00", "500.00"),
            ("1000000601", "10000006", "SAV", "32100.00", "32100.00", "0.00"),
            ("1000000701", "10000007", "CUR", "2210.00", "2710.00", "500.00"),
            ("1000000801", "10000008", "CUR", "4800.10", "5300.10", "500.00"),
            ("10001", "10000001", "CUR", "1000.00", "1000.00", "0.00"),
            ("10002", "10000002", "CUR", "2000.00", "2000.00", "0.00"),
        ]
        data: Dict[str, Dict[str, str]] = {}
        for acct, cid, typ, actual, avail, od in seeds:
            data[acct] = {
                "ACCOUNT_ID": acct,
                "ACCOUNT_NUMBER": acct,
                "CUSTOMER_ID": cid,
                "SORT_CODE": "204514",
                "ACCOUNT_TYPE": typ,
                "TYPE": typ,
                "INTEREST_RATE": "0.50" if typ == "CUR" else "2.25",
                "DATE_OPENED": "1984-04-01",
                "OVERDRAFT_LIMIT": od,
                "LAST_STATEMENT_DATE": "2026-04-30",
                "NEXT_STATEMENT_DATE": "2026-05-31",
                "AVAILABLE_BALANCE": avail,
                "ACTUAL_BALANCE": actual,
                "BALANCE": actual,
                "STATUS": "A",
                "OWNER": "GMVB",
                "CREATED_BY": "SYSTEM",
                "CREATED_TS": _ts(),
                "UPDATED_BY": "SYSTEM",
                "UPDATED_TS": _ts(),
            }
        return data

    def _seed_transactions(self) -> List[Dict[str, str]]:
        return [
            {"TRANSACTION_ID": "PTX000001", "ACCOUNT_NUMBER": "1000000101", "CUSTOMER_ID": "10000001", "TRANSACTION_TYPE": "CRE", "AMOUNT": "100.00", "CURRENCY": "GBP", "DESCRIPTION": "OPENING CREDIT", "RELATED_ACCOUNT": "", "OPERATOR_ID": "SYSTEM", "SOURCE": "SEED", "STATUS": "POSTED", "CREATED_TS": _ts()},
            {"TRANSACTION_ID": "PTX000002", "ACCOUNT_NUMBER": "1000000201", "CUSTOMER_ID": "10000002", "TRANSACTION_TYPE": "DEB", "AMOUNT": "25.50", "CURRENCY": "GBP", "DESCRIPTION": "ATM CASH", "RELATED_ACCOUNT": "", "OPERATOR_ID": "SYSTEM", "SOURCE": "SEED", "STATUS": "POSTED", "CREATED_TS": _ts()},
        ]

    def _seed_batches(self) -> Dict[str, Dict[str, str]]:
        return {
            "B2026A17": {"BATCH_ID": "B2026A17", "ITEM_COUNT": "00012", "TOTAL_VALUE": "245000.00", "CURRENCY": "GBP", "STATUS": "HELD-PIN-REQ", "CREATED_BY": "PAYOPS", "CREATED_TS": _ts(), "RELEASED_BY": "", "RELEASED_TS": "", "RELEASE_PIN_REQUIRED": "Y", "RELEASE_PIN_SIMULATED": self.BATCH_RELEASE_PIN, "ATTEMPT_COUNT": "0", "LAST_ATTEMPT_TS": "", "NOTES": "TRAINING BATCH"},
            "B2026A18": {"BATCH_ID": "B2026A18", "ITEM_COUNT": "00004", "TOTAL_VALUE": "18420.00", "CURRENCY": "GBP", "STATUS": "READY", "CREATED_BY": "PAYOPS", "CREATED_TS": _ts(), "RELEASED_BY": "", "RELEASED_TS": "", "RELEASE_PIN_REQUIRED": "Y", "RELEASE_PIN_SIMULATED": self.BATCH_RELEASE_PIN, "ATTEMPT_COUNT": "0", "LAST_ATTEMPT_TS": "", "NOTES": "LOW VALUE TRAINING BATCH"},
        }

    def _seed_swift(self) -> Dict[str, Dict[str, str]]:
        return {
            "SWF000001": {"MESSAGE_ID": "SWF000001", "MESSAGE_TYPE": "MT103", "UETR": str(uuid.uuid4()), "SENDER_BIC": "GMVBGB2L", "RECEIVER_BIC": "DEUTDEFF", "DEBIT_ACCOUNT": "1000000101", "VALUE_DATE": "260523", "CURRENCY": "GBP", "AMOUNT": "125000.00", "BENEFICIARY": "ACME EXPORTS", "BENEFICIARY_ACCOUNT": "DE89370400440532013000", "DETAILS": "INVOICE 7781", "STATUS": "PENDING", "CREATED_BY": "SYSTEM", "APPROVED_BY": "", "RELEASED_BY": "", "CREATED_TS": _ts(), "APPROVED_TS": "", "RELEASED_TS": "", "REPAIR_STATUS": "NONE", "NOTES": "TRAINING ONLY"},
            "SWF000002": {"MESSAGE_ID": "SWF000002", "MESSAGE_TYPE": "MT202", "UETR": str(uuid.uuid4()), "SENDER_BIC": "GMVBGB2L", "RECEIVER_BIC": "BNPAFRPP", "DEBIT_ACCOUNT": "1000000201", "VALUE_DATE": "260523", "CURRENCY": "EUR", "AMOUNT": "50000.00", "BENEFICIARY": "CONTOSO BANK", "BENEFICIARY_ACCOUNT": "FR7630006000011234567890189", "DETAILS": "BANK COVER", "STATUS": "REPAIR", "CREATED_BY": "SYSTEM", "APPROVED_BY": "", "RELEASED_BY": "", "CREATED_TS": _ts(), "APPROVED_TS": "", "RELEASED_TS": "", "REPAIR_STATUS": "BENEFICIARY REVIEW", "NOTES": "TRAINING ONLY"},
            "SWF000003": {"MESSAGE_ID": "SWF000003", "MESSAGE_TYPE": "MT103", "UETR": str(uuid.uuid4()), "SENDER_BIC": "GMVBGB2L", "RECEIVER_BIC": "BOFAUS3N", "DEBIT_ACCOUNT": "1000000301", "VALUE_DATE": "260523", "CURRENCY": "USD", "AMOUNT": "2500.00", "BENEFICIARY": "TRAINING SUPPLIER", "BENEFICIARY_ACCOUNT": "021000021000123456", "DETAILS": "SERVICES", "STATUS": "RELEASED", "CREATED_BY": "SYSTEM", "APPROVED_BY": "SUPR01", "RELEASED_BY": "SUPR01", "CREATED_TS": _ts(), "APPROVED_TS": _ts(), "RELEASED_TS": _ts(), "REPAIR_STATUS": "NONE", "NOTES": "TRAINING ONLY"},
        }

    def _next_customer_id(self) -> str:
        last = max(int(k) for k in self.customers if str(k).isdigit())
        return str(last + 1)

    def _next_account_id(self) -> str:
        last = max(int(k) for k in self.accounts if str(k).isdigit())
        return str(last + 1)

    def _next_txid(self) -> str:
        return f"PTX{len(self.transactions)+1:06d}"

    def _next_swift_id(self) -> str:
        return f"SWF{len(self.swift)+1:06d}"

    def audit_event(self, event_type: str, actor: str, action: str, result: str, details: str, *, resource: str = "GMVB", severity: str = "INFO", source: str = "gmvb-service") -> Dict[str, str]:
        row = {"EVENT_ID": f"AUD{len(self.audit)+1:06d}", "EVENT_TS": _ts(), "ACTOR": _s(actor, "ANON").upper(), "EVENT_TYPE": event_type, "ACTION": action, "RESULT": result, "RESOURCE": resource, "DETAILS": details[:200], "SEVERITY": severity, "SOURCE": source}
        self.audit.append(row)
        self.audit[:] = self.audit[-500:]
        try:
            self.state.record_security_event(row["ACTOR"], event_type, details[:100], result=result, service="GMVB")
        except Exception:
            pass
        return row

    # Customer methods
    def get_customer(self, customer_id: str) -> Optional[Dict[str, str]]:
        return self.customers.get(_s(customer_id).upper())

    def search_customers_by_name(self, name: str, limit: int = 10) -> List[Dict[str, str]]:
        needle = _s(name).upper()
        rows = [dict(v) for v in self.customers.values() if needle in v.get("FULL_NAME", "").upper() or needle in v.get("SURNAME", "").upper()]
        return rows[: int(limit or 10)]

    def create_customer(self, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        cid = _s(payload.get("CUSTOMER_ID") or payload.get("customer_id") or self._next_customer_id()).upper()
        row = {
            "CUSTOMER_ID": cid,
            "SORT_CODE": _s(payload.get("SORT_CODE") or payload.get("sort_code"), "204514"),
            "CUSTOMER_NUMBER": _s(payload.get("CUSTOMER_NUMBER") or payload.get("customer_number"), cid[-6:]),
            "FORENAME": _s(payload.get("FORENAME") or payload.get("forename"), "TRAINING").upper(),
            "SURNAME": _s(payload.get("SURNAME") or payload.get("surname"), "CUSTOMER").upper(),
            "ADDRESS_LINE_1": _s(payload.get("ADDRESS_LINE_1") or payload.get("address"), "TRAINING ADDRESS"),
            "ADDRESS_LINE_2": _s(payload.get("ADDRESS_LINE_2"), ""),
            "TOWN": _s(payload.get("TOWN") or payload.get("town"), "LONDON").upper(),
            "POSTCODE": _s(payload.get("POSTCODE") or payload.get("postcode"), "EC1A1AA").upper(),
            "DATE_OF_BIRTH": _s(payload.get("DATE_OF_BIRTH") or payload.get("dob"), "1970-01-01"),
            "CREDIT_SCORE": _s(payload.get("CREDIT_SCORE") or payload.get("credit_score"), "700"),
            "CREDIT_SCORE_REVIEW_DATE": _s(payload.get("CREDIT_SCORE_REVIEW_DATE"), "2026-12-31"),
            "STATUS": _s(payload.get("STATUS") or payload.get("status"), "A").upper()[:1],
            "KYC_STATUS": _s(payload.get("KYC_STATUS") or payload.get("kyc_status"), "PENDING").upper(),
            "CREATED_BY": operator.upper(), "CREATED_TS": _ts(), "UPDATED_BY": operator.upper(), "UPDATED_TS": _ts(),
        }
        row["FULL_NAME"] = f"{row['FORENAME']} {row['SURNAME']}"
        self.customers[cid] = row
        self.control["CUSTOMER_COUNT"] = str(len(self.customers)); self.control["CUSTOMER_LAST"] = cid; self.control["UPDATED_TS"] = _ts()
        self.audit_event("CUSTOMER", operator, "CREATE", "OK", f"Customer {cid} created", resource=cid)
        return dict(row)

    def update_customer(self, customer_id: str, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        cid = _s(customer_id).upper()
        if cid not in self.customers: raise KeyError(f"customer {cid} not found")
        row = self.customers[cid]
        mapping = {"forename":"FORENAME","surname":"SURNAME","address":"ADDRESS_LINE_1","town":"TOWN","postcode":"POSTCODE","status":"STATUS","kyc_status":"KYC_STATUS"}
        for k, v in payload.items():
            key = mapping.get(k, k.upper())
            if key in row and v is not None:
                row[key] = _s(v).upper() if key in {"FORENAME","SURNAME","TOWN","POSTCODE","STATUS","KYC_STATUS"} else _s(v)
        row["FULL_NAME"] = f"{row.get('FORENAME','')} {row.get('SURNAME','')}".strip()
        row["UPDATED_BY"] = operator.upper(); row["UPDATED_TS"] = _ts()
        self.audit_event("CUSTOMER", operator, "UPDATE", "OK", f"Customer {cid} updated", resource=cid)
        return dict(row)

    def delete_customer(self, customer_id: str, operator: str = "SYSTEM") -> Dict[str, str]:
        cid = _s(customer_id).upper()
        row = self.customers.pop(cid, None)
        if not row: raise KeyError(f"customer {cid} not found")
        self.control["CUSTOMER_COUNT"] = str(len(self.customers)); self.control["UPDATED_TS"] = _ts()
        self.audit_event("CUSTOMER", operator, "DELETE", "OK", f"Customer {cid} deleted", resource=cid)
        return dict(row)

    # Account methods
    def get_account(self, account_id: str) -> Optional[Dict[str, str]]:
        return self.accounts.get(_s(account_id).upper())

    def get_accounts_for_customer(self, customer_id: str) -> List[Dict[str, str]]:
        cid = _s(customer_id).upper()
        return [dict(a) for a in self.accounts.values() if a.get("CUSTOMER_ID") == cid]

    def create_account(self, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        acct = _s(payload.get("ACCOUNT_NUMBER") or payload.get("account_id") or payload.get("account_number") or self._next_account_id()).upper()
        cid = _s(payload.get("CUSTOMER_ID") or payload.get("customer_id"), "10000001").upper()
        row = {"ACCOUNT_ID": acct, "ACCOUNT_NUMBER": acct, "CUSTOMER_ID": cid, "SORT_CODE": _s(payload.get("SORT_CODE") or payload.get("sort_code"), "204514"), "ACCOUNT_TYPE": _s(payload.get("ACCOUNT_TYPE") or payload.get("account_type"), "CUR").upper(), "TYPE": _s(payload.get("ACCOUNT_TYPE") or payload.get("account_type"), "CUR").upper(), "INTEREST_RATE": _s(payload.get("INTEREST_RATE"), "0.50"), "DATE_OPENED": _s(payload.get("DATE_OPENED"), "2026-05-23"), "OVERDRAFT_LIMIT": str(_money(payload.get("OVERDRAFT_LIMIT") or payload.get("limit") or "0.00")), "LAST_STATEMENT_DATE": "2026-04-30", "NEXT_STATEMENT_DATE": "2026-05-31", "AVAILABLE_BALANCE": str(_money(payload.get("AVAILABLE_BALANCE") or payload.get("balance") or "0.00")), "ACTUAL_BALANCE": str(_money(payload.get("ACTUAL_BALANCE") or payload.get("balance") or "0.00")), "BALANCE": str(_money(payload.get("balance") or payload.get("ACTUAL_BALANCE") or "0.00")), "STATUS": _s(payload.get("STATUS") or payload.get("status"), "A").upper()[:1], "OWNER": "GMVB", "CREATED_BY": operator.upper(), "CREATED_TS": _ts(), "UPDATED_BY": operator.upper(), "UPDATED_TS": _ts()}
        self.accounts[acct] = row
        self.control["ACCOUNT_COUNT"] = str(len(self.accounts)); self.control["ACCOUNT_LAST"] = acct; self.control["UPDATED_TS"] = _ts()
        self.write_processed_transaction({"ACCOUNT_NUMBER": acct, "CUSTOMER_ID": cid, "TRANSACTION_TYPE": "OCA", "AMOUNT": "0.00", "DESCRIPTION": "OPEN ACCOUNT", "OPERATOR_ID": operator, "SOURCE": "GMVB"})
        self.audit_event("ACCOUNT", operator, "CREATE", "OK", f"Account {acct} created", resource=acct)
        return dict(row)

    def update_account(self, account_id: str, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        acct = _s(account_id).upper()
        if acct not in self.accounts: raise KeyError(f"account {acct} not found")
        row = self.accounts[acct]
        mapping = {"account_type":"ACCOUNT_TYPE","limit":"OVERDRAFT_LIMIT","balance":"ACTUAL_BALANCE","status":"STATUS"}
        for k, v in payload.items():
            key = mapping.get(k, k.upper())
            if key in row and v is not None:
                row[key] = str(_money(v)) if key in {"ACTUAL_BALANCE","AVAILABLE_BALANCE","BALANCE","OVERDRAFT_LIMIT"} else _s(v).upper()
        if "ACTUAL_BALANCE" in row: row["BALANCE"] = row["ACTUAL_BALANCE"]
        row["UPDATED_BY"] = operator.upper(); row["UPDATED_TS"] = _ts()
        self.audit_event("ACCOUNT", operator, "UPDATE", "OK", f"Account {acct} updated", resource=acct)
        return dict(row)

    def delete_account(self, account_id: str, operator: str = "SYSTEM") -> Dict[str, str]:
        acct = _s(account_id).upper()
        row = self.accounts.pop(acct, None)
        if not row: raise KeyError(f"account {acct} not found")
        self.control["ACCOUNT_COUNT"] = str(len(self.accounts)); self.control["UPDATED_TS"] = _ts()
        self.write_processed_transaction({"ACCOUNT_NUMBER": acct, "CUSTOMER_ID": row.get("CUSTOMER_ID",""), "TRANSACTION_TYPE": "ODA", "AMOUNT": "0.00", "DESCRIPTION": "DELETE ACCOUNT", "OPERATOR_ID": operator, "SOURCE": "GMVB"})
        self.audit_event("ACCOUNT", operator, "DELETE", "OK", f"Account {acct} deleted", resource=acct)
        return dict(row)

    def _adjust(self, account_id: str, delta: Decimal) -> Dict[str, str]:
        acct = _s(account_id).upper(); row = self.accounts.get(acct)
        if not row: raise KeyError(f"account {acct} not found")
        actual = _money(row.get("ACTUAL_BALANCE") or row.get("BALANCE") or "0.00") + delta
        od = _money(row.get("OVERDRAFT_LIMIT") or "0.00")
        avail = actual + od
        row["ACTUAL_BALANCE"] = row["BALANCE"] = str(actual); row["AVAILABLE_BALANCE"] = str(avail); row["UPDATED_TS"] = _ts()
        return row

    def write_processed_transaction(self, payload: Dict[str, Any]) -> Dict[str, str]:
        row = {"TRANSACTION_ID": _s(payload.get("TRANSACTION_ID"), self._next_txid()), "ACCOUNT_NUMBER": _s(payload.get("ACCOUNT_NUMBER") or payload.get("account") or payload.get("account_id")), "CUSTOMER_ID": _s(payload.get("CUSTOMER_ID") or payload.get("customer_id")), "TRANSACTION_TYPE": _s(payload.get("TRANSACTION_TYPE") or payload.get("type"), "CRE").upper(), "AMOUNT": str(_money(payload.get("AMOUNT") or payload.get("amount") or "0.00")), "CURRENCY": _s(payload.get("CURRENCY"), "GBP"), "DESCRIPTION": _s(payload.get("DESCRIPTION") or payload.get("description"), "GMVB TRANSACTION")[:80], "RELATED_ACCOUNT": _s(payload.get("RELATED_ACCOUNT") or payload.get("to_account")), "OPERATOR_ID": _s(payload.get("OPERATOR_ID") or payload.get("operator"), "SYSTEM").upper(), "SOURCE": _s(payload.get("SOURCE"), "GMVB"), "STATUS": _s(payload.get("STATUS"), "POSTED"), "CREATED_TS": _ts()}
        self.transactions.append(row)
        self.control["PROCTRAN_COUNT"] = str(len(self.transactions)); self.control["UPDATED_TS"] = _ts()
        return row

    def credit_account(self, account_id: str, amount: Any, description: str = "CREDIT", operator: str = "SYSTEM") -> Dict[str, Any]:
        val = _money(amount); row = self._adjust(account_id, val)
        tx = self.write_processed_transaction({"ACCOUNT_NUMBER": account_id, "CUSTOMER_ID": row.get("CUSTOMER_ID",""), "TRANSACTION_TYPE": "CRE", "AMOUNT": str(val), "DESCRIPTION": description, "OPERATOR_ID": operator})
        self.audit_event("TRANSACTION", operator, "CREDIT", "OK", f"Credited {account_id} {val}", resource=account_id)
        return {"account": dict(row), "transaction": tx}

    def debit_account(self, account_id: str, amount: Any, description: str = "DEBIT", operator: str = "SYSTEM") -> Dict[str, Any]:
        val = _money(amount); row = self._adjust(account_id, -val)
        tx = self.write_processed_transaction({"ACCOUNT_NUMBER": account_id, "CUSTOMER_ID": row.get("CUSTOMER_ID",""), "TRANSACTION_TYPE": "DEB", "AMOUNT": str(val), "DESCRIPTION": description, "OPERATOR_ID": operator})
        self.audit_event("TRANSACTION", operator, "DEBIT", "OK", f"Debited {account_id} {val}", resource=account_id)
        return {"account": dict(row), "transaction": tx}

    def transfer_funds(self, from_account: str, to_account: str, amount: Any, description: str = "TRANSFER", operator: str = "SYSTEM") -> Dict[str, Any]:
        val = _money(amount)
        from_row = self._adjust(from_account, -val)
        to_row = self._adjust(to_account, val)
        tx1 = self.write_processed_transaction({"ACCOUNT_NUMBER": from_account, "CUSTOMER_ID": from_row.get("CUSTOMER_ID",""), "TRANSACTION_TYPE": "TFR", "AMOUNT": str(val), "DESCRIPTION": description, "RELATED_ACCOUNT": to_account, "OPERATOR_ID": operator})
        tx2 = self.write_processed_transaction({"ACCOUNT_NUMBER": to_account, "CUSTOMER_ID": to_row.get("CUSTOMER_ID",""), "TRANSACTION_TYPE": "TFR", "AMOUNT": str(val), "DESCRIPTION": description, "RELATED_ACCOUNT": from_account, "OPERATOR_ID": operator})
        self.audit_event("TRANSACTION", operator, "TRANSFER", "OK", f"Transferred {val} from {from_account} to {to_account}", resource=from_account)
        return {"from_account": dict(from_row), "to_account": dict(to_row), "transactions": [tx1, tx2]}

    def list_transactions(self, account_id: str | None = None, customer_id: str | None = None, limit: int = 50) -> List[Dict[str, str]]:
        rows = list(self.transactions)
        if account_id:
            rows = [r for r in rows if r.get("ACCOUNT_NUMBER") == str(account_id)]
        if customer_id:
            rows = [r for r in rows if r.get("CUSTOMER_ID") == str(customer_id)]
        return [dict(r) for r in rows[-int(limit or 50):]]

    # Batch/SWIFT
    def create_batch(self, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        bid = _s(payload.get("BATCH_ID") or payload.get("batch_id"), f"B2026A{len(self.batches)+17}").upper()
        row = {"BATCH_ID": bid, "ITEM_COUNT": _s(payload.get("ITEM_COUNT") or payload.get("item_count"), "00001"), "TOTAL_VALUE": str(_money(payload.get("TOTAL_VALUE") or payload.get("total_value") or "0.00")), "CURRENCY": _s(payload.get("CURRENCY"), "GBP"), "STATUS": "HELD-PIN-REQ", "CREATED_BY": operator.upper(), "CREATED_TS": _ts(), "RELEASED_BY": "", "RELEASED_TS": "", "RELEASE_PIN_REQUIRED": "Y", "RELEASE_PIN_SIMULATED": self.BATCH_RELEASE_PIN, "ATTEMPT_COUNT": "0", "LAST_ATTEMPT_TS": "", "NOTES": _s(payload.get("NOTES"), "TRAINING BATCH")}
        self.batches[bid] = row; self.audit_event("BATCH", operator, "CREATE", "OK", f"Batch {bid} created", resource=bid)
        return dict(row)

    def get_batch(self, batch_id: str) -> Optional[Dict[str, str]]:
        b = self.batches.get(_s(batch_id).upper()); return dict(b) if b else None

    def list_batches(self, status: str | None = None) -> List[Dict[str, str]]:
        rows = list(self.batches.values())
        if status: rows = [r for r in rows if r.get("STATUS") == status]
        return [dict(r) for r in rows]

    def release_batch(self, batch_id: str, supervisor_id: str, pin: str, operator: str = "SYSTEM", injected: bool = False) -> Dict[str, Any]:
        bid = _s(batch_id, "B2026A17").upper(); row = self.batches.get(bid)
        if not row: raise KeyError(f"batch {bid} not found")
        row["ATTEMPT_COUNT"] = str(int(row.get("ATTEMPT_COUNT") or 0) + 1); row["LAST_ATTEMPT_TS"] = _ts()
        if str(pin) != self.BATCH_RELEASE_PIN:
            self.audit_event("BATCH", operator, "RELEASE", "DENIED", f"Wrong PIN for {bid}", resource=bid, severity="WARN")
            return {"released": False, "batch": dict(row), "message": "DFHBA7702 BATCH RELEASE PIN REJECTED", "pin_required": self.BATCH_RELEASE_PIN}
        row["STATUS"] = "RELEASED"; row["RELEASED_BY"] = _s(supervisor_id or operator).upper(); row["RELEASED_TS"] = _ts()
        tx = self.write_processed_transaction({"ACCOUNT_NUMBER": "BATCH", "CUSTOMER_ID": "", "TRANSACTION_TYPE": "BAT", "AMOUNT": row.get("TOTAL_VALUE"), "DESCRIPTION": f"BATCH {bid} RELEASED", "OPERATOR_ID": operator, "SOURCE": "HACK3270" if injected else "GMVB"})
        self.audit_event("BATCH", operator, "RELEASE", "OK", f"Batch {bid} released{' by injected PIN' if injected else ''}", resource=bid)
        return {"released": True, "batch": dict(row), "transaction": tx, "message": "DFHBA7701 BATCH RELEASED", "pin_used": self.BATCH_RELEASE_PIN}

    def reject_batch(self, batch_id: str, reason: str, operator: str = "SYSTEM") -> Dict[str, str]:
        row = self.batches.get(_s(batch_id).upper())
        if not row: raise KeyError(f"batch {batch_id} not found")
        row["STATUS"] = "REJECTED"; row["NOTES"] = reason[:80]
        self.audit_event("BATCH", operator, "REJECT", "OK", f"Batch {batch_id} rejected: {reason}", resource=batch_id)
        return dict(row)

    def create_swift_message(self, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        mid = _s(payload.get("MESSAGE_ID") or payload.get("message_id"), self._next_swift_id()).upper()
        row = {"MESSAGE_ID": mid, "MESSAGE_TYPE": _s(payload.get("MESSAGE_TYPE") or payload.get("message_type"), "MT103").upper(), "UETR": _s(payload.get("UETR"), str(uuid.uuid4())), "SENDER_BIC": _s(payload.get("SENDER_BIC") or payload.get("sender_bic"), "GMVBGB2L").upper(), "RECEIVER_BIC": _s(payload.get("RECEIVER_BIC") or payload.get("receiver_bic"), "DEUTDEFF").upper(), "DEBIT_ACCOUNT": _s(payload.get("DEBIT_ACCOUNT") or payload.get("debit_account"), "1000000101"), "VALUE_DATE": _s(payload.get("VALUE_DATE") or payload.get("value_date"), "260523"), "CURRENCY": _s(payload.get("CURRENCY") or payload.get("currency"), "GBP").upper(), "AMOUNT": str(_money(payload.get("AMOUNT") or payload.get("amount") or "0.00")), "BENEFICIARY": _s(payload.get("BENEFICIARY") or payload.get("beneficiary"), "TRAINING BENEFICIARY").upper(), "BENEFICIARY_ACCOUNT": _s(payload.get("BENEFICIARY_ACCOUNT") or payload.get("beneficiary_account"), "TRAINING-ACCT"), "DETAILS": _s(payload.get("DETAILS") or payload.get("details"), "TRAINING PAYMENT"), "STATUS": "PENDING", "CREATED_BY": operator.upper(), "APPROVED_BY": "", "RELEASED_BY": "", "CREATED_TS": _ts(), "APPROVED_TS": "", "RELEASED_TS": "", "REPAIR_STATUS": "NONE", "NOTES": "SIMULATED SWIFT ONLY"}
        self.swift[mid] = row; self.audit_event("SWIFT", operator, "CREATE", "OK", f"SWIFT {mid} created", resource=mid)
        return dict(row)

    def get_swift_message(self, message_id: str) -> Optional[Dict[str, str]]:
        r = self.swift.get(_s(message_id).upper()); return dict(r) if r else None

    def list_swift_messages(self, status: str | None = None) -> List[Dict[str, str]]:
        rows = list(self.swift.values())
        if status: rows = [r for r in rows if r.get("STATUS") == status]
        return [dict(r) for r in rows]

    def approve_swift_message(self, message_id: str, approver: str = "SUPR01") -> Dict[str, str]:
        mid = _s(message_id).upper(); row = self.swift.get(mid)
        if not row: raise KeyError(f"swift message {mid} not found")
        row["STATUS"] = "APPROVED"; row["APPROVED_BY"] = approver.upper(); row["APPROVED_TS"] = _ts()
        self.audit_event("SWIFT", approver, "APPROVE", "OK", f"SWIFT {mid} approved", resource=mid)
        return dict(row)

    def release_swift_message(self, message_id: str, releaser: str = "SUPR01") -> Dict[str, str]:
        mid = _s(message_id).upper(); row = self.swift.get(mid)
        if not row: raise KeyError(f"swift message {mid} not found")
        row["STATUS"] = "RELEASED"; row["RELEASED_BY"] = releaser.upper(); row["RELEASED_TS"] = _ts()
        self.write_processed_transaction({"ACCOUNT_NUMBER": row.get("DEBIT_ACCOUNT"), "TRANSACTION_TYPE": "SWF", "AMOUNT": row.get("AMOUNT"), "DESCRIPTION": f"SWIFT {mid} RELEASED", "OPERATOR_ID": releaser, "SOURCE": "GMVB"})
        self.audit_event("SWIFT", releaser, "RELEASE", "OK", f"SWIFT {mid} released - simulated only", resource=mid)
        return dict(row)

    def repair_swift_message(self, message_id: str, payload: Dict[str, Any], operator: str = "SYSTEM") -> Dict[str, str]:
        mid = _s(message_id).upper(); row = self.swift.get(mid)
        if not row: raise KeyError(f"swift message {mid} not found")
        for key in ["BENEFICIARY", "BENEFICIARY_ACCOUNT", "DETAILS", "RECEIVER_BIC"]:
            v = payload.get(key) or payload.get(key.lower())
            if v: row[key] = _s(v).upper() if key != "DETAILS" else _s(v)
        row["REPAIR_STATUS"] = "REPAIRED"; row["STATUS"] = "PENDING"; row["NOTES"] = "REPAIRED IN SIMULATOR"
        self.audit_event("SWIFT", operator, "REPAIR", "OK", f"SWIFT {mid} repaired", resource=mid)
        return dict(row)

    def export_evidence(self, filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"audit": list(self.audit), "transactions": list(self.transactions[-100:]), "batches": self.list_batches(), "swift": self.list_swift_messages(), "generated_ts": _ts()}

    # DB2 catalog integration
    def catalog(self) -> Dict[str, List[Dict[str, str]]]:
        customers_map = {k: dict(v) for k, v in self.customers.items()}
        accounts_map = {k: dict(v) for k, v in self.accounts.items()}
        lab = getattr(self.state, "banking_lab_service", None)
        if lab is not None:
            for cid, row in getattr(lab, "gmvb_customers", {}).items():
                merged = dict(customers_map.get(cid, {})); merged.update(dict(row)); merged.setdefault("CUSTOMER_ID", cid)
                customers_map[cid] = merged
            for acct, row in getattr(lab, "gmvb_accounts", {}).items():
                merged = dict(accounts_map.get(acct, {})); merged.update(dict(row)); merged.setdefault("ACCOUNT_NUMBER", acct); merged.setdefault("ACCOUNT_ID", acct)
                accounts_map[acct] = merged
        customers = [dict(v) for v in customers_map.values()]
        accounts = [dict(v) for v in accounts_map.values()]
        proctran = [dict(v) for v in self.transactions]
        batches = [dict(v) for v in self.batches.values()]
        swift = [dict(v) for v in self.swift.values()]
        audit = [dict(v) for v in self.audit]
        statements = []
        lab = getattr(self.state, "banking_lab_service", None)
        if lab is not None:
            for st in getattr(lab, "statements", []):
                statements.append(dict(st))
            for tr in getattr(lab, "transfers", []):
                r = dict(tr)
                r.setdefault("ACCTNO", r.get("ACCOUNT", r.get("ACCOUNT_NUMBER", "")))
                statements.append(r)
        for t in proctran:
            statements.append({
                "ACCTNO": t.get("ACCOUNT_NUMBER", ""),
                "ACCOUNT_NUMBER": t.get("ACCOUNT_NUMBER", ""),
                "TRANID": t.get("TRANSACTION_ID", ""),
                "TYPE": t.get("TRANSACTION_TYPE", ""),
                "AMOUNT": t.get("AMOUNT", ""),
                "DESC": t.get("DESCRIPTION", ""),
                "STATUS": t.get("STATUS", "POSTED"),
            })
        return {
            "GMVB.CUSTOMER": customers,
            "GMVB.ACCOUNT": accounts,
            "GMVB.CONTROL": [dict(self.control)],
            "GMVB.PROCTRAN": proctran,
            "GMVB.TRANSACTION": proctran,
            "GMVB.AUDITLOG": audit,
            "GMVB.BATCH_TRANSFER": batches,
            "GMVB.PAYMENT_BATCH": batches,
            "GMVB.SWIFT_MESSAGE": swift,
            "GMVB.SWIFT_AUDIT": [a for a in audit if a.get("EVENT_TYPE") == "SWIFT"],
            "GMVB.CARD_APPLICATION": [{"APP_ID":"CCA000183","CUSTOMER_ID":"10000001","REQUESTED_LIMIT":"5000","RISK_SCORE":"072","STATUS":"REFER"}],
            "GMVB.COBOL_SOURCE": [{"PROGRAM":"BNKMENU","PURPOSE":"GMVB menu routing"},{"PROGRAM":"BNK1TFN","PURPOSE":"Transfer funds"},{"PROGRAM":"VULNERABLE-BANK-UPDATE","PURPOSE":"Training vulnerabilities"}],
            "GMVB.API_AUDIT": [a for a in audit if a.get("SOURCE") in {"api", "gmvb-api"}],
            "GMVB.TN3270_CAPTURE": [{"CAPTURE_ID":"CAP000042","SESSION":"CICS0007","USERID":"GUEST","TRANSID":"BATCH","BUFFER_EXCERPT":"FIELD=RELEASE-PIN ATTR=NUM PROT=Y VALUE=****"}],
            "GMVB.HACK3270_EVENT": [a for a in audit if "HACK" in a.get("EVENT_TYPE", "")],
            "GIBSON.CUSTOMERS": customers,
            "GIBSON.ACCOUNTS": accounts,
            "GIBSON.TRANSFERS": statements,
            "GIBSON.STATEMENTS": statements,
        }

    def table_metadata(self) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        tables: List[Dict[str, str]] = []
        columns: List[Dict[str, str]] = []
        for full, rows in self.catalog().items():
            schema, _, name = full.partition(".")
            tables.append({"NAME": name, "CREATOR": schema, "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": name[:8]})
            keys = []
            for r in rows:
                for k in r.keys():
                    if k not in keys: keys.append(k)
            for k in keys:
                columns.append({"TBNAME": name, "TBCREATOR": schema, "NAME": k, "COLTYPE": "VARCHAR", "LENGTH": "128"})
        return tables, columns


# Public helper used by DB2, CICS, API and tests.
def get_gmvb_service(state: Any) -> GmvbBankingService:
    return GmvbBankingService.get(state)


# ---------------------------------------------------------------------------
# FIBS compatibility aliases
# ---------------------------------------------------------------------------
# FIBS is the user-facing banking application identity.  GMVB remains a
# backwards-compatible schema/route name.  The same row objects are exposed under
# both schemas so TSO DB2, ISPF SPUFI, React, REST and CICS share one state.
_ORIGINAL_GMVB_CATALOG = GmvbBankingService.catalog
_ORIGINAL_GMVB_TABLE_METADATA = GmvbBankingService.table_metadata


def _with_fibs_aliases(self: GmvbBankingService) -> Dict[str, List[Dict[str, str]]]:
    data = _ORIGINAL_GMVB_CATALOG(self)
    alias_pairs = {
        "GMVB.CUSTOMER": "FIBS.CUSTOMER",
        "GMVB.ACCOUNT": "FIBS.ACCOUNT",
        "GMVB.CONTROL": "FIBS.CONTROL",
        "GMVB.PROCTRAN": "FIBS.PROCTRAN",
        "GMVB.TRANSACTION": "FIBS.PROCTRAN",
        "GMVB.AUDITLOG": "FIBS.AUDITLOG",
        "GMVB.BATCH_TRANSFER": "FIBS.BATCH_TRANSFER",
        "GMVB.PAYMENT_BATCH": "FIBS.PAYMENT_BATCH",
        "GMVB.SWIFT_MESSAGE": "FIBS.SWIFT_MESSAGE",
        "GMVB.SWIFT_AUDIT": "FIBS.SWIFT_AUDIT",
        "GMVB.CARD_APPLICATION": "FIBS.CARD_APPLICATION",
        "GMVB.COBOL_SOURCE": "FIBS.COBOL_SOURCE",
        "GMVB.API_AUDIT": "FIBS.API_AUDIT",
        "GMVB.TN3270_CAPTURE": "FIBS.TN3270_CAPTURE",
        "GMVB.HACK3270_EVENT": "FIBS.HACK3270_EVENT",
    }
    for src, dst in alias_pairs.items():
        if src in data:
            data[dst] = data[src]
    return data


def _fibs_table_metadata(self: GmvbBankingService) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    tables: List[Dict[str, str]] = []
    columns: List[Dict[str, str]] = []
    for full, rows in self.catalog().items():
        schema, _, name = full.partition(".")
        tables.append({"NAME": name, "CREATOR": schema, "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": name[:8]})
        keys: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        for k in keys:
            columns.append({"TBNAME": name, "TBCREATOR": schema, "NAME": k, "COLTYPE": "VARCHAR", "LENGTH": "128"})
    return tables, columns


GmvbBankingService.catalog = _with_fibs_aliases
GmvbBankingService.table_metadata = _fibs_table_metadata
