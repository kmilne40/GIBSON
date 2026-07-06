from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def money(value: Any) -> str:
    return f"{Decimal(str(value)):.2f}"

@dataclass
class Customer:
    customer_id: str
    name: str
    address1: str = ""
    address2: str = ""
    date_of_birth: str = ""
    credit_score: str = "700"
    status: str = "ACTIVE"
    risk_score: str = "LOW"
    isAdmin: str = "false"
    creditLimit: str = "5000.00"
    created_at: str = ""
    updated_at: str = ""
    def row(self) -> dict[str, str]:
        d = {k.upper(): str(v) for k, v in asdict(self).items()}
        d["CUSTOMER_ID"] = self.customer_id
        return d

@dataclass
class Account:
    sort_code: str
    account_number: str
    customer_id: str
    account_type: str = "CURRENT"
    interest_rate: str = "0.01"
    opened_date: str = "2026-01-01"
    overdraft_limit: str = "500.00"
    available_balance: str = "0.00"
    actual_balance: str = "0.00"
    last_statement_date: str = "2026-01-01"
    next_statement_date: str = "2026-02-01"
    status: str = "OPEN"
    def row(self) -> dict[str, str]:
        d = {k.upper(): str(v) for k, v in asdict(self).items()}
        d["ACCOUNT_NUMBER"] = self.account_number
        d["CUSTOMER_ID"] = self.customer_id
        return d
