from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class FibsSession:
    session_id: str
    userid: str = "IBMUSER"
    current_app: str = "FIBS"
    current_map: str = "FIBSMENU"
    previous_map: str = "FIBSMENU"
    current_transaction: str = "FIBS"
    current_operation: str = "MENU"
    form_values: dict[str, str] = field(default_factory=dict)
    message_line: str = "FIBS READY"
    cursor_field: str = "COMMAND"
    last_customer_id: str = "10000002"
    last_account_id: str = "1000000201"
    source_program: str = "VULNERABLE-BANK-UPDATE"
    source_offset: int = 0
    source_find_text: str = ""
    transaction_audit_id: str = ""
    signed_on: bool = True
    hack3270_state_reference: dict[str, Any] = field(default_factory=dict)

def get_fibs_session(state: Any, key: str, userid: str = "IBMUSER") -> FibsSession:
    sessions = getattr(state, "fibs_sessions", None)
    if sessions is None:
        sessions = {}
        setattr(state, "fibs_sessions", sessions)
    sid = (key or userid or "IBMUSER").upper()
    if sid not in sessions:
        sessions[sid] = FibsSession(sid, (userid or "IBMUSER").upper())
    return sessions[sid]
