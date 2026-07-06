from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import html
import json
import os
import re
import uuid
from typing import Any, Dict, List

from gibson.core.state import GibsonState
from gibson.core.passticket import get_passticket_service
from gibson.render.screen3270 import ScreenBuffer


VULNERABLE_BANK_UPDATE_COBOL = r'''       IDENTIFICATION DIVISION.
       PROGRAM-ID. VULNERABLE-BANK-UPDATE.
       AUTHOR. SECURITY-TRAINER.
       REMARKS. THIS PROGRAM CONTAINS INTENTIONAL VULNERABILITIES FOR TRAINING.

      *===============================================================*
      *                MULTIPLE INTENTIONAL VULNERABILITIES            *
      *===============================================================*

       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *=================== UNSAFE DATA STRUCTURES ====================*
      * Vulnerability 1: Buffer overflow potential due to mismatched sizes
       01  INPUT-DATA.
           05  USER-INPUT               PIC X(100).  *> Large input buffer
           05  FILLER REDEFINES USER-INPUT.
               10  CUSTOMER-ID         PIC X(10).
               10  ACCOUNT-TYPE        PIC X(2).
               10  TRANSACTION-AMOUNT  PIC X(12).

      * Vulnerability 2: Sensitive data adjacent to overflowable buffers
       01  SECURITY-CONTROL-FLAGS.
           05  AUTHENTICATED-FLAG      PIC X VALUE 'N'.
           05  ADMIN-FLAG              PIC X VALUE 'N'.
           05  DEBUG-FLAG              PIC X VALUE 'N'.

      * Vulnerability 3: Fixed-size buffer for variable-length data
       01  CUSTOMER-RECORD.
           05  CUST-NAME               PIC X(30).
           05  CUST-ADDRESS            PIC X(50).
           05  CUST-BALANCE            PIC S9(9)V99 COMP-3.
           05  CUST-PIN                PIC X(4).  *> Easily overflowable

      * Vulnerability 4: Uninitialized sensitive data
       01  TEMP-STORAGE.
           05  SENSITIVE-TEMP          PIC X(100).
           05  LOG-BUFFER              PIC X(256).

      * Vulnerability 5: Format string in message buffer
       01  MESSAGE-AREA.
           05  MSG-TEXT                PIC X(100).
           05  MSG-SEVERITY            PIC X(1).

       LINKAGE SECTION.
      * Vulnerability 6: Exposed system control area
       01  DFHCOMMAREA.
           05  SYSTEM-CONTROL          PIC X(50).

       PROCEDURE DIVISION.

      *=================== VULNERABLE CODE SECTIONS ==================*
      * Vulnerability 15: Unsafe CICS channel communication
       500-GET-CHANNEL-DATA.
           EXEC CICS GET CONTAINER('USERDATA')
                        CHANNEL('BANKCHAN')
                        INTO(USER-INPUT)
                        FLENGTH(USER-INPUT-LENGTH) *> No MAXFLENGTH!
                        RESP(RESPONSE-CODE)
           END-EXEC.

           IF RESPONSE-CODE = DFHRESP(NORMAL)
               MOVE USER-INPUT TO CUSTOMER-RECORD. *> Potential overflow
           END-IF.

      * Vulnerability 7: Unsafe input handling with no length validation
       100-GET-INPUT.
           EXEC CICS RECEIVE MAP('BANKMAP') INTO(USER-INPUT) END-EXEC.

      * Vulnerability 8: Direct move with potential overflow
           MOVE USER-INPUT TO CUSTOMER-RECORD.

      * Vulnerability 9: Format string vulnerability in message
           STRING 'Tx for: ' CUST-NAME ' Amt: ' TRANSACTION-AMOUNT INTO MSG-TEXT.

      * Vulnerability 10: Authentication bypass via buffer overflow
           IF CUST-PIN = '9999' OR AUTHENTICATED-FLAG = 'Y'
               PERFORM 200-PROCESS-TRANSACTION
           ELSE
               PERFORM 800-SEND-ERROR
           END-IF.

      * Vulnerability 11: Debug backdoor via overflow
           IF DEBUG-FLAG = 'Y'
               PERFORM 700-DEBG-DUMP
           END-IF.

       200-PROCESS-TRANSACTION.
      * Vulnerability 12: Unsafe numeric conversion
           COMPUTE CUST-BALANCE = FUNCTION NUMVAL(TRANSACTION-AMOUNT).
      * Vulnerability 13: Logging sensitive data without sanitization
           MOVE CUSTOMER-RECORD TO LOG-BUFFER.
           EXEC CICS SEND MAP('BANKMAP') FROM(MESSAGE-AREA) END-EXEC.

       700-DEBG-DUMP.
      * Vulnerability 14: Exposing memory contents
           DISPLAY 'DEBUG DUMP: ' TEMP-STORAGE.

       800-SEND-ERROR.
           MOVE 'AUTHENTICATION FAILED' TO MSG-TEXT.
           EXEC CICS SEND MAP('BANKMAP') FROM(MESSAGE-AREA) END-EXEC.
'''


@dataclass
class FieldSpec:
    name: str
    label: str
    row: int
    col: int
    width: int
    value: str = ""
    hidden: bool = False
    protected: bool = False
    numeric: bool = False
    mdt: bool = False
    note: str = ""


@dataclass
class LabSession:
    sid: str
    current_screen: str = "LOGN"
    previous_screen: str = "LOGN"
    authenticated: bool = False
    user: str = ""
    status: str = "ENTER USERID AND PASSWORD"
    fields: dict[str, str] = field(default_factory=dict)
    last_rows: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    traces: list[dict[str, str]] = field(default_factory=list)
    last_challenge: str = "overview"
    hack: dict[str, bool] = field(default_factory=dict)
    tutorial_mode: str = "hint"
    show_solutions: bool = False
    toolbar_view: str = "terminal"
    current_appl: str = "CICS"
    current_ticket: str = ""


CHALLENGE_GUIDE = {
    "overview": {
        "title": "Sighberbank vulnerable banking lab",
        "hint": "Start with GUEST/GUEST, then try ACCT 10001 or a statement search containing SQL-like input.",
        "guided": "Login, open ACCT, then look up an account you do not own. Next, open STMT and search using 10001' OR '1'='1 to observe the unsafe SQL branch and compare it with the trace.",
        "solution": "The lab intentionally trusts client-side field controls and simulates unsafe dynamic SQL. Use the Hack3270 panel to reveal hidden fields or remove protection, then compare the vulnerable flow to the server-side checks shown in the API trace.",
    },
    "sqli": {
        "title": "SQL injection in Db2-backed banking lookup",
        "hint": "Try an account or statement search containing OR or '1'='1.",
        "guided": "On the STMT or ACCT screen, enter 10001' OR '1'='1. The backend takes the input literally and the trace shows an unsafe WHERE clause built by string concatenation.",
        "solution": "Use host variables rather than concatenating user input. The simulation mirrors the COBOL pattern where input from USER-INPUT flows into a query without length or content validation.",
    },
    "idor": {
        "title": "IDOR / BOLA on account retrieval",
        "hint": "Login as GUEST and request IBMUSER's account 10001.",
        "guided": "Authenticate as GUEST, then request ACCT 10001. In mixed or vulnerable mode the screen still shows IBMUSER's account details and the trace marks it as an ownership bypass.",
        "solution": "Ownership checks must happen server-side on every read and transfer. Hidden or protected fields must not be treated as authorization evidence.",
    },
    "hidden": {
        "title": "Hidden-field tampering via Hack3270",
        "hint": "Reveal hidden fields and edit AUTHFLAG, ADMINFLAG, or DEBUGFLAG.",
        "guided": "Toggle Reveal Hidden Fields, then edit AUTHFLAG or DEBUGFLAG on XFER. The simulated application trusts those values the same way a vulnerable CICS/BMS program would trust inbound screen data or a container payload.",
        "solution": "Security flags must be derived from server-side session state. The COBOL training source shows AUTHENTICATED-FLAG, ADMIN-FLAG, and DEBUG-FLAG adjacent to user-controlled data, which is the exact trust-boundary mistake this panel demonstrates.",
    },
    "numeric": {
        "title": "Numeric-only restriction bypass",
        "hint": "Disable numeric-only restrictions and submit a crafted amount.",
        "guided": "On XFER, turn off Remove Numeric-only Restrictions and enter 50.00CR or -250.00. The screen attribute would normally constrain entry, but the receiving code still needs to validate it before FUNCTION NUMVAL is used.",
        "solution": "Numeric-only is a terminal presentation control, not a data-integrity control. The receiving program must validate range, format, and sign before using the amount.",
    },
    "debug": {
        "title": "Debug backdoor and memory disclosure",
        "hint": "Either set DEBUGFLAG to Y or use PIN 9999 in vulnerable mode.",
        "guided": "On XFER, reveal hidden fields and set DEBUGFLAG=Y or use PIN 9999. The simulated application discloses TEMP-STORAGE data and the trace points back to the DISPLAY 'DEBUG DUMP' branch in the COBOL.",
        "solution": "Remove debug code from production paths, never expose TEMP-STORAGE or message buffers to users, and do not allow special PINs or client-controlled flags to reach privileged branches.",
    },
    "workflow": {
        "title": "Workflow bypass on approval queue",
        "hint": "Open APRV directly or set ADMINFLAG to Y before approving.",
        "guided": "Use the menu or direct transaction input to reach APRV, then tamper with ADMINFLAG. The vulnerable flow trusts the request rather than the operator's role.",
        "solution": "Check user role server-side on every state transition. Protected screens and hidden fields only affect what a normal terminal will send; they do not enforce business authorization.",
    },
    "passticket": {
        "title": "PassTicket sign-on and trusted middleware",
        "hint": "Generate a PassTicket for CICS, then sign on without sending the RACF password.",
        "guided": "Use the PassTicket panel to request a ticket for a user and APPLID such as CICS. Then sign on from the LOGN screen with USERID + PASSTICKET + APPLID. Review the trace to see the simulated REQUEST PASSTICKET and PTKTDATA checks.",
        "solution": "PassTickets reduce password exposure, but they only work if PTKTDATA, IRRPTAUTH-style generation rights, APPL binding, clock handling, and replay controls are configured correctly.",
    },
    "ptkt_replay": {
        "title": "Replay protection bypass",
        "hint": "Disable replay protection for CICS, then try the same PassTicket twice within the validity window.",
        "guided": "In the PassTicket panel, turn replay protection off for CICS. Generate a ticket, use it once, then use it again. The first use should succeed; the second succeeds only when the profile has a NO REPLAY PROTECTION style setting.",
        "solution": "One-time use is one of the main security properties of a PassTicket. Bypassing replay protection widens the blast radius if a ticket is intercepted or logged.",
    },
    "ptkt_appl": {
        "title": "Application binding mismatch",
        "hint": "Generate a ticket for CICS, then attempt to validate it for another APPLID when application matching is relaxed.",
        "guided": "Enable the lab APPLID mismatch flag for CICS, request a PassTicket, and then validate it against DB2 or TSO. The trace will show the expected APPLID and the mismatched consumer.",
        "solution": "A PassTicket is supposed to bind a specific user to a specific application. Relaxing APPL checking undermines that guarantee and can let a ticket be replayed against the wrong target.",
    },
    "ptkt_trust": {
        "title": "Over-broad trusted caller",
        "hint": "Use WEBBANK to mint a ticket for another user such as IBMUSER.",
        "guided": "The lab seeds a generic IRRPTAUTH-style profile that lets WEBBANK request PassTickets for CICS. Generate a ticket for a different user and examine why that is dangerous when the middle tier is over-trusted.",
        "solution": "Generation rights should be narrowly scoped to the intended APPLID and identity set. Broad middleware generation rights turn a trusted front end into a lateral-movement and impersonation surface.",
    },
}


class BankingLabService:
    def __init__(self, state: GibsonState):
        self.state = state
        self.lab_mode = os.getenv("BANK_LAB_MODE", "mixed").strip().lower() or "mixed"
        self.default_tutorial = os.getenv("BANK_TUTORIAL_MODE", "hint").strip().lower() or "hint"
        self.default_solutions = os.getenv("BANK_SHOW_SOLUTIONS", "0") in {"1", "true", "TRUE"}
        self.default_hack_panel = os.getenv("BANK_HACK3270_PANEL", "1") in {"1", "true", "TRUE"}
        self.accounts: dict[str, dict[str, str]] = {
            "10001": {"owner": "IBMUSER", "customer": "C0001", "type": "CHECKING", "balance": "25000.00", "status": "ACTIVE", "routing": "021000021", "pin": "1234"},
            "10002": {"owner": "GUEST", "customer": "C0002", "type": "SAVINGS", "balance": "125.15", "status": "ACTIVE", "routing": "021000022", "pin": "2222"},
            "10003": {"owner": "ALICE", "customer": "C0003", "type": "CHECKING", "balance": "944.22", "status": "PENDING REVIEW", "routing": "021000023", "pin": "3333"},
            "20001": {"owner": "AUDITOR", "customer": "C0004", "type": "BROKERAGE", "balance": "88001.99", "status": "ACTIVE", "routing": "021000024", "pin": "4444"},
        }
        self.customers: dict[str, dict[str, str]] = {
            "C0001": {"name": "IBMUSER PRIMARY", "address": "1 Gibson Plaza", "tier": "PLATINUM"},
            "C0002": {"name": "GUEST CUSTOMER", "address": "2 Gibson Plaza", "tier": "STANDARD"},
            "C0003": {"name": "ALICE BENTON", "address": "3 Gibson Plaza", "tier": "PREMIER"},
            "C0004": {"name": "AUDIT TRAINING", "address": "4 Gibson Plaza", "tier": "INTERNAL"},
        }
        self.cards: dict[str, dict[str, str]] = {
            "900001": {"account": "10001", "card_type": "VISA", "status": "ACTIVE", "last4": "4431"},
            "900002": {"account": "10002", "card_type": "MC", "status": "ACTIVE", "last4": "8892"},
            "900003": {"account": "10003", "card_type": "VISA", "status": "REVIEW", "last4": "1028"},
        }
        self.statements: list[dict[str, str]] = [
            {"STMTID": "S1000101", "ACCTNO": "10001", "PERIOD": "2026-04", "DESCRIPTION": "PAYROLL CREDIT", "AMOUNT": "2100.00"},
            {"STMTID": "S1000102", "ACCTNO": "10001", "PERIOD": "2026-04", "DESCRIPTION": "WIRE FEE", "AMOUNT": "-35.00"},
            {"STMTID": "S1000201", "ACCTNO": "10002", "PERIOD": "2026-04", "DESCRIPTION": "ATM WITHDRAWAL", "AMOUNT": "-40.00"},
            {"STMTID": "S1000301", "ACCTNO": "10003", "PERIOD": "2026-04", "DESCRIPTION": "EXPORT REVIEW HOLD", "AMOUNT": "0.00"},
            {"STMTID": "S2000101", "ACCTNO": "20001", "PERIOD": "2026-04", "DESCRIPTION": "INTERNAL AUDIT TRANSFER", "AMOUNT": "12000.00"},
        ]
        self.transfers: list[dict[str, str]] = []
        self.sessions: dict[str, LabSession] = {}
        self.transfer_seq = 90000
        self._seed_training_members()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def new_sid(self) -> str:
        sid = uuid.uuid4().hex[:12]
        self.ensure_session(sid)
        return sid

    def ensure_session(self, sid: str | None = None) -> LabSession:
        key = (sid or "").strip() or uuid.uuid4().hex[:12]
        sess = self.sessions.get(key)
        if sess is None:
            hack = {
                "panel_enabled": self.default_hack_panel,
                "hack_enabled": False,
                "reveal_hidden": False,
                "remove_protection": False,
                "remove_numeric": False,
                "show_metadata": True,
                "show_mdt": True,
                "show_positions": False,
                "show_standard": True,
            }
            sess = LabSession(
                sid=key,
                tutorial_mode=self.default_tutorial,
                show_solutions=self.default_solutions,
                hack=hack,
            )
            sess.fields = {"USERID": "", "PASSWORD": "", "PASSTICKET": "", "APPLID": "CICS", "CMD": ""}
            self.sessions[key] = sess
        return sess

    @staticmethod
    def _safe_mode(mode: str) -> bool:
        return (mode or "").lower() == "safe"

    def _current_mode(self) -> str:
        return self.lab_mode if self.lab_mode in {"safe", "vuln", "mixed"} else "mixed"

    def _log_trace(self, sess: LabSession, stage: str, detail: str, severity: str = "INFO") -> None:
        sess.traces.append({"stage": stage, "detail": detail, "severity": severity})
        sess.traces = sess.traces[-14:]

    def _set_challenge(self, sess: LabSession, key: str, note: str) -> None:
        sess.last_challenge = key
        sess.notes.append(note)
        sess.notes = sess.notes[-10:]

    def _seed_training_members(self) -> None:
        for uid in sorted(self.state.racf.users):
            try:
                lib = f"{uid}.COBOL.LAB"
                self.state.datasets.allocate(uid, lib, org="PO")
                members = {
                    f"{lib}(VBANKUPD)": VULNERABLE_BANK_UPDATE_COBOL,
                    f"{uid}.BMS.LAB(BANKMAP)": "DFHMSD TYPE=&SYSPARM,MODE=INOUT\nDFHMDI SIZE=(24,80),LINE=1,COLUMN=1\nDFHMDF POS=(7,24),LENGTH=8,ATTRB=(UNPROT)\nDFHMDF POS=(8,24),LENGTH=8,ATTRB=(PROT,NODISP)\nDFHMDI\nDFHMSD TYPE=FINAL\n",
                    f"{uid}.SQL.LAB(BANKDDL)": "CREATE TABLE GIBSON.ACCOUNTS (ACCTNO CHAR(5), OWNER VARCHAR(16), TYPE VARCHAR(12), BALANCE DECIMAL(9,2), STATUS VARCHAR(16));\n",
                    f"{uid}.JCL.LAB(BANKDEMO)": f"//BANKDEMO JOB (ACCT),'BANKLAB',CLASS=A,MSGCLASS=A\n//COBOL EXEC PGM=IKJEFT01\n//SYSTSIN DD *\n  EX 'IBMUSER.COBOL.LAB(VBANKUPD)'\n/*\n",
                }
                for dsn, content in members.items():
                    if not self.state.datasets.exists(uid, dsn):
                        self.state.datasets.write(uid, dsn, content)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Data / catalog exposure
    # ------------------------------------------------------------------
    def catalog(self) -> dict[str, list[dict[str, str]]]:
        rows_accounts = []
        for acct, meta in sorted(self.accounts.items()):
            rows_accounts.append(
                {
                    "ACCTNO": acct,
                    "OWNER": meta["owner"],
                    "CUSTOMER": meta["customer"],
                    "TYPE": meta["type"],
                    "BALANCE": meta["balance"],
                    "STATUS": meta["status"],
                    "ROUTING": meta["routing"],
                }
            )
        rows_customers = []
        for cid, meta in sorted(self.customers.items()):
            rows_customers.append({"CUSTOMERID": cid, "NAME": meta["name"], "ADDRESS": meta["address"], "TIER": meta["tier"]})
        rows_cards = []
        for card, meta in sorted(self.cards.items()):
            rows_cards.append({"CARDNO": card, "ACCTNO": meta["account"], "CARDTYPE": meta["card_type"], "STATUS": meta["status"], "LAST4": meta["last4"]})
        rows_transfers = [dict(x) for x in self.transfers[-20:]]
        rows_statements = [dict(x) for x in self.statements[-40:]]
        ptkt = get_passticket_service(self.state)
        rows_flags = [
            {"FLAGNAME": "BANK_LAB_MODE", "VALUE": self._current_mode()},
            {"FLAGNAME": "BANK_TUTORIAL_MODE", "VALUE": self.default_tutorial},
            {"FLAGNAME": "BANK_SHOW_SOLUTIONS", "VALUE": "Y" if self.default_solutions else "N"},
            {"FLAGNAME": "BANK_HACK3270_PANEL", "VALUE": "Y" if self.default_hack_panel else "N"},
        ]
        return {
            "GIBSON.ACCOUNTS": rows_accounts,
            "GIBSON.CUSTOMERS": rows_customers,
            "GIBSON.CARDS": rows_cards,
            "GIBSON.TRANSFERS": rows_transfers,
            "GIBSON.STATEMENTS": rows_statements,
            "GIBSON.LAB_FLAGS": rows_flags,
            "GIBSON.PASSTICKETS": ptkt.issued_rows(),
            "GIBSON.PTKT_AUDIT": ptkt.audit_rows(),
            "GIBSON.PTKT_PROFILES": ptkt.profile_rows(),
        }

    def table_metadata(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        tables = [
            {"NAME": "CUSTOMERS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "CUSTOMER"},
            {"NAME": "CARDS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "CARDS"},
            {"NAME": "TRANSFERS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "TRANSFER"},
            {"NAME": "STATEMENTS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "STATEMNT"},
            {"NAME": "LAB_FLAGS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "LABFLAGS"},
            {"NAME": "PASSTICKETS", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "PTKTISSU"},
            {"NAME": "PTKT_AUDIT", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "PTKTAUD"},
            {"NAME": "PTKT_PROFILES", "CREATOR": "GIBSON", "TYPE": "T", "DBNAME": "GIBDB", "TSNAME": "PTKTPRF"},
        ]
        columns = [
            {"TBNAME": "ACCOUNTS", "TBCREATOR": "GIBSON", "NAME": "BALANCE", "COLTYPE": "DECIMAL", "LENGTH": "11"},
            {"TBNAME": "CUSTOMERS", "TBCREATOR": "GIBSON", "NAME": "CUSTOMERID", "COLTYPE": "CHAR", "LENGTH": "5"},
            {"TBNAME": "TRANSFERS", "TBCREATOR": "GIBSON", "NAME": "TXID", "COLTYPE": "CHAR", "LENGTH": "6"},
            {"TBNAME": "STATEMENTS", "TBCREATOR": "GIBSON", "NAME": "STMTID", "COLTYPE": "CHAR", "LENGTH": "8"},
            {"TBNAME": "LAB_FLAGS", "TBCREATOR": "GIBSON", "NAME": "FLAGNAME", "COLTYPE": "VARCHAR", "LENGTH": "32"},
            {"TBNAME": "PASSTICKETS", "TBCREATOR": "GIBSON", "NAME": "TICKET", "COLTYPE": "CHAR", "LENGTH": "8"},
            {"TBNAME": "PASSTICKETS", "TBCREATOR": "GIBSON", "NAME": "APPLID", "COLTYPE": "CHAR", "LENGTH": "8"},
            {"TBNAME": "PTKT_AUDIT", "TBCREATOR": "GIBSON", "NAME": "STAGE", "COLTYPE": "VARCHAR", "LENGTH": "16"},
            {"TBNAME": "PTKT_PROFILES", "TBCREATOR": "GIBSON", "NAME": "PROFILE", "COLTYPE": "CHAR", "LENGTH": "8"},
        ]
        return tables, columns

    # ------------------------------------------------------------------
    # Core vulnerable actions
    # ------------------------------------------------------------------
    def login(self, sid: str, user: str, password: str, passticket: str = "", applid: str = "CICS", requester: str = "WEBBANK") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        user_u = (user or "").upper().strip()
        password_t = (password or "").strip()
        ticket_t = (passticket or "").upper().strip()
        appl_u = (applid or "CICS").upper().strip() or "CICS"
        sess.current_appl = appl_u
        sess.notes.clear()
        sess.last_rows = []
        sess.current_ticket = ticket_t
        self._log_trace(sess, "EXEC CICS RECEIVE", "MAP=BANKMAP INTO(USER-INPUT) WITHOUT LENGTH VALIDATION")
        if ticket_t:
            ptkt = get_passticket_service(self.state)
            self._log_trace(sess, "EXEC CICS REQUEST PASSTICKET", f"VALIDATE USERID({user_u}) APPL({appl_u}) TICKET({ticket_t})")
            result = ptkt.validate(user_u, appl_u, ticket_t, consumer="SIGHBERBANK-WEB")
            if result.get("leaked"):
                self._log_trace(sess, "MIDDLE TIER TRACE", f"DEBUG LEAK ENABLED - PASSTICKET={ticket_t} USERID={user_u} APPL={appl_u}", severity="WARN")
            if result.get("ok"):
                self.state.record_security_event(user_u, "LOGON", f"BANK PASSTICKET APPL={appl_u}", service="WEBBANK")
                sess.authenticated = True
                sess.user = user_u
                sess.current_screen = "MENU"
                sess.previous_screen = "LOGN"
                sess.status = f"PASS TICKET ACCEPTED FOR {user_u} / {appl_u}"
                sess.fields.update({"USERID": user_u, "PASSWORD": "", "PASSTICKET": ticket_t, "APPLID": appl_u})
                self._set_challenge(sess, "passticket", f"PassTicket accepted for {user_u} against APPL {appl_u}. Review the trace and PTKTDATA profile data.")
                return self.snapshot(sid)
            self.state.record_security_event(user_u or "UNKNOWN", "LOGON", str(result.get("message", "PASS TICKET REJECTED")), result="FAILURE", service="WEBBANK")
            sess.authenticated = False
            sess.user = user_u
            sess.current_screen = "LOGN"
            sess.status = str(result.get("message", "PASS TICKET REJECTED"))
            reason = str(result.get("reason", ""))
            if reason == "REPLAY":
                self._set_challenge(sess, "ptkt_replay", sess.status)
            elif reason == "APPLID_MISMATCH":
                self._set_challenge(sess, "ptkt_appl", sess.status)
            else:
                self._set_challenge(sess, "passticket", sess.status)
            sess.fields.update({"USERID": user_u, "PASSWORD": "", "PASSTICKET": ticket_t, "APPLID": appl_u})
            return self.snapshot(sid)
        self.state.racf.load(merge=True)
        if self.state.racf.verify_password(user_u, password_t):
            self.state.record_security_event(user_u, "LOGON", "BANK PASSWORD", service="WEBBANK")
            sess.authenticated = True
            sess.user = user_u
            sess.current_screen = "MENU"
            sess.previous_screen = "LOGN"
            sess.status = f"SIGNED ON AS {user_u}"
            self._set_challenge(sess, "overview", f"Login accepted for {user_u}. Continue into ACCT, STMT, XFER, APRV, HACK, or PTKT.")
        else:
            self.state.record_security_event(user_u or "UNKNOWN", "LOGON", "BANK PASSWORD FAILURE", result="FAILURE", service="WEBBANK")
            sess.authenticated = False
            sess.user = user_u
            sess.current_screen = "LOGN"
            sess.status = "INVALID USERID OR PASSWORD"
            if self._safe_mode(self._current_mode()):
                self._set_challenge(sess, "overview", "Login failed. Safe mode blocks further actions until valid credentials are supplied.")
            else:
                self._set_challenge(sess, "hidden", "Login failed, but the lab remains reachable so that weak authorization handling and hidden-field issues can still be explored.")
        sess.fields = {"USERID": user_u, "PASSWORD": password_t, "PASSTICKET": ticket_t, "APPLID": appl_u}
        return self.snapshot(sid)

    def passticket_generate(self, sid: str, userid: str = "", applid: str = "CICS", requester: str = "WEBBANK") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        user = (userid or sess.user or sess.fields.get("USERID", "IBMUSER")).upper().strip() or "IBMUSER"
        appl = (applid or sess.fields.get("APPLID", "CICS")).upper().strip() or "CICS"
        req = (requester or "WEBBANK").upper().strip() or "WEBBANK"
        ptkt = get_passticket_service(self.state)
        self._log_trace(sess, "EXEC CICS REQUEST PASSTICKET", f"USERID({user}) ESMAPPNAME({appl}) REQUESTER({req})")
        result = ptkt.generate(user, appl, req, source="WEBBANK")
        if result.get("ok"):
            ticket = str(result.get("ticket", ""))
            sess.fields.update({"USERID": user, "PASSTICKET": ticket, "APPLID": appl})
            sess.current_ticket = ticket
            sess.current_appl = appl
            sess.status = f"PASSTICKET {ticket} GENERATED FOR {user}"
            self._set_challenge(sess, "ptkt_trust" if user != (sess.user or user) else "passticket", str(result.get("message", "")))
            if result.get("leaked"):
                self._log_trace(sess, "MIDDLE TIER TRACE", f"DEBUG LEAK ENABLED - PASSTICKET={ticket} USERID={user} APPL={appl}", severity="WARN")
        else:
            sess.status = str(result.get("message", "PASSTICKET GENERATION FAILED"))
            self._set_challenge(sess, "passticket", sess.status)
        return self.snapshot(sid)

    def passticket_use(self, sid: str, userid: str = "", ticket: str = "", applid: str = "CICS") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        user = (userid or sess.fields.get("USERID", "") or sess.user).upper().strip()
        token = (ticket or sess.fields.get("PASSTICKET", "")).upper().strip()
        appl = (applid or sess.fields.get("APPLID", "CICS")).upper().strip() or "CICS"
        return self.login(sid, user, "", passticket=token, applid=appl)

    def passticket_scenario(self, sid: str, replay_protection: bool | None = None, appl_mismatch: bool | None = None, leak: bool | None = None, applid: str = "CICS") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        appl = (applid or sess.fields.get("APPLID", "CICS")).upper().strip() or "CICS"
        ptkt = get_passticket_service(self.state)
        flags = ptkt.set_profile_flags(appl, replay_protection=replay_protection, appl_mismatch=appl_mismatch, leak=leak)
        self._log_trace(sess, "RACF PTKTDATA", f"PROFILE {appl} UPDATED {flags}")
        if replay_protection is False:
            self._set_challenge(sess, "ptkt_replay", f"Replay protection disabled for {appl}.")
        elif appl_mismatch:
            self._set_challenge(sess, "ptkt_appl", f"Application mismatch relaxed for {appl}.")
        else:
            self._set_challenge(sess, "passticket", f"PTKTDATA flags updated for {appl}.")
        sess.status = f"PTKTDATA UPDATED FOR {appl}"
        sess.current_appl = appl
        sess.fields["APPLID"] = appl
        return self.snapshot(sid)

    def passticket_block(self, sid: str) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        ptkt = get_passticket_service(self.state)
        return {
            "current_appl": sess.current_appl,
            "current_ticket": sess.current_ticket,
            "profiles": ptkt.profile_rows(),
            "issued": ptkt.issued_rows(),
            "audit": ptkt.audit_rows(),
        }

    def menu_select(self, sid: str, selection: str) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        entered = (selection or "").strip().upper()
        mapping = {
            "1": "CARG", "2": "ORDE", "3": "ORDR", "4": "ACCT", "5": "STMT", "6": "XFER", "7": "APRV", "8": "HACK", "9": "PTKT", "0": "LOGN",
            "CARG": "CARG", "ORDE": "ORDE", "ORDR": "ORDR", "ACCT": "ACCT", "STMT": "STMT", "XFER": "XFER", "APRV": "APRV", "HACK": "HACK", "PTKT": "PTKT", "LOGN": "LOGN", "MENU": "MENU",
        }
        dest = mapping.get(entered, "")
        if not dest:
            sess.status = "ENTER A VALID MENU OPTION"
            return self.snapshot(sid)
        sess.previous_screen = sess.current_screen
        sess.current_screen = dest
        sess.status = f"{dest} READY"
        return self.snapshot(sid)

    def account_lookup(self, sid: str, account_id: str, *, screen: str = "ACCT") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        raw = (account_id or "").strip()
        sess.current_screen = screen
        sess.previous_screen = "MENU" if sess.previous_screen == "LOGN" else sess.previous_screen
        sess.last_rows = []
        sess.notes.clear()
        self._log_trace(sess, "EXEC CICS GET CONTAINER", "CHANNEL(BANKCHAN) INTO(USER-INPUT) FLENGTH(USER-INPUT-LENGTH) without MAXFLENGTH")
        self._log_trace(sess, "EXEC SQL", f"SELECT ACCTNO, OWNER, TYPE, BALANCE, STATUS FROM GIBSON.ACCOUNTS WHERE ACCTNO = '{raw}'")
        if not raw:
            sess.status = "ENTER AN ACCOUNT NUMBER"
            return self.snapshot(sid)
        upper = raw.upper()
        if ("'1'='1" in upper or " OR " in upper) and not self._safe_mode(self._current_mode()):
            sess.last_rows = self.catalog()["GIBSON.ACCOUNTS"]
            sess.status = "SQLI BRANCH RETURNED MULTIPLE ACCOUNTS"
            self._set_challenge(sess, "sqli", "Training SQL injection branch triggered: the lookup returned multiple accounts to demonstrate unsafe concatenation.")
            return self.snapshot(sid)
        meta = self.accounts.get(raw)
        if not meta:
            sess.status = f"ACCOUNT {raw} NOT FOUND"
            self._set_challenge(sess, "overview", f"Account {raw} was not found.")
            return self.snapshot(sid)
        row = {
            "ACCTNO": raw,
            "OWNER": meta["owner"],
            "CUSTOMER": meta["customer"],
            "TYPE": meta["type"],
            "BALANCE": meta["balance"],
            "STATUS": meta["status"],
            "ROUTING": meta["routing"],
        }
        if sess.user and meta["owner"].upper() != sess.user.upper():
            if self._safe_mode(self._current_mode()):
                sess.status = f"ACCESS DENIED TO ACCOUNT {raw}"
                self._set_challenge(sess, "idor", f"Safe mode blocked {sess.user} from viewing account {raw} owned by {meta['owner']}.")
                return self.snapshot(sid)
            self._set_challenge(sess, "idor", f"IDOR training branch triggered: {sess.user.upper()} can still view account {raw} owned by {meta['owner']}.")
        else:
            self._set_challenge(sess, "overview", f"Account {raw} loaded for {meta['owner']}.")
        sess.last_rows = [row]
        sess.status = f"ACCOUNT {raw} DISPLAYED"
        return self.snapshot(sid)

    def statement_lookup(self, sid: str, account_id: str, period: str = "") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        raw = (account_id or "").strip()
        per = (period or "2026-04").strip() or "2026-04"
        sess.current_screen = "STMT"
        sess.last_rows = []
        sess.notes.clear()
        self._log_trace(sess, "EXEC SQL", f"SELECT STMTID, ACCTNO, PERIOD, DESCRIPTION, AMOUNT FROM GIBSON.STATEMENTS WHERE ACCTNO = '{raw}' AND PERIOD = '{per}'")
        if ("'1'='1" in raw.upper() or " OR " in raw.upper()) and not self._safe_mode(self._current_mode()):
            sess.last_rows = [dict(x) for x in self.statements]
            sess.status = "STATEMENT QUERY RETURNED MULTIPLE ROWS"
            self._set_challenge(sess, "sqli", "Training SQL injection branch triggered against the statement search.")
            return self.snapshot(sid)
        matches = [dict(x) for x in self.statements if x["ACCTNO"] == raw and (not per or x["PERIOD"] == per)]
        if matches:
            if sess.user and self.accounts.get(raw, {}).get("owner", "").upper() not in {"", sess.user.upper()} and not self._safe_mode(self._current_mode()):
                self._set_challenge(sess, "idor", f"Statement IDOR branch triggered: {sess.user} can read statements for account {raw}.")
            elif sess.user and self.accounts.get(raw, {}).get("owner", "").upper() not in {"", sess.user.upper()}:
                sess.status = "ACCESS DENIED TO STATEMENTS"
                self._set_challenge(sess, "idor", f"Safe mode denied statement access to account {raw}.")
                return self.snapshot(sid)
            else:
                self._set_challenge(sess, "overview", f"Statement rows returned for account {raw}.")
            sess.last_rows = matches
            sess.status = f"{len(matches)} STATEMENT ROW(S) RETURNED"
        else:
            sess.status = "NO STATEMENT ROWS"
            self._set_challenge(sess, "overview", f"No statements matched {raw} / {per}.")
        return self.snapshot(sid)

    def _numval_like(self, amount: str) -> str:
        text = (amount or "").strip().upper()
        m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        return m.group(0) if m else "0"

    def transfer(self, sid: str, fields: dict[str, Any]) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        src = str(fields.get("SRCACCT", fields.get("source", ""))).strip()
        dst = str(fields.get("DSTACCT", fields.get("destination", ""))).strip()
        amt_raw = str(fields.get("AMOUNT", fields.get("amount", "0"))).strip()
        memo = str(fields.get("MEMO", fields.get("memo", "LAB TRANSFER"))).strip()
        pin = str(fields.get("PIN", fields.get("pin", ""))).strip()
        authflag = str(fields.get("AUTHFLAG", "N") or "N").upper()[:1]
        adminflag = str(fields.get("ADMINFLAG", "N") or "N").upper()[:1]
        debugflag = str(fields.get("DEBUGFLAG", "N") or "N").upper()[:1]
        sess.current_screen = "XFER"
        sess.last_rows = []
        sess.notes.clear()
        self._log_trace(sess, "EXEC CICS RECEIVE", "MOVE USER-INPUT TO CUSTOMER-RECORD without validating the container length")
        self._log_trace(sess, "COBOL", f"STRING 'Tx for: ' CUST-NAME ' Amt: ' TRANSACTION-AMOUNT INTO MSG-TEXT => memo={memo}")
        self._log_trace(sess, "FLAGS", f"AUTHENTICATED-FLAG={authflag} ADMIN-FLAG={adminflag} DEBUG-FLAG={debugflag}")
        sess.fields = {
            "SRCACCT": src,
            "DSTACCT": dst,
            "AMOUNT": amt_raw,
            "PIN": pin,
            "MEMO": memo,
            "AUTHFLAG": authflag,
            "ADMINFLAG": adminflag,
            "DEBUGFLAG": debugflag,
        }
        src_meta = self.accounts.get(src)
        dst_meta = self.accounts.get(dst)
        if not src_meta or not dst_meta:
            sess.status = "SOURCE OR DESTINATION NOT FOUND"
            self._set_challenge(sess, "overview", "Source or destination account was not found.")
            return self.snapshot(sid)
        amount_text = amt_raw
        if any(ch.isalpha() for ch in amt_raw) or (amt_raw.count("-") > 1):
            if self._safe_mode(self._current_mode()):
                sess.status = "AMOUNT FAILED VALIDATION"
                self._set_challenge(sess, "numeric", f"Safe mode rejected malformed amount {amt_raw}.")
                return self.snapshot(sid)
            amount_text = self._numval_like(amt_raw)
            self._set_challenge(sess, "numeric", f"Unsafe numeric conversion branch triggered: FUNCTION NUMVAL accepted {amt_raw} as {amount_text}.")
            self._log_trace(sess, "COMPUTE", f"CUST-BALANCE = FUNCTION NUMVAL('{amt_raw}') => {amount_text}")
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            sess.status = "AMOUNT FORMAT INVALID"
            self._set_challenge(sess, "numeric", f"Amount {amt_raw} could not be parsed.")
            return self.snapshot(sid)
        ownership_ok = bool(sess.user and src_meta["owner"].upper() == sess.user.upper())
        auth_ok = ownership_ok or pin == "9999" or authflag == "Y" or adminflag == "Y"
        if pin == "9999" and not ownership_ok:
            self._set_challenge(sess, "debug", "Authentication bypass branch triggered: PIN 9999 was treated as a privileged backdoor.")
        if authflag == "Y" or adminflag == "Y":
            self._set_challenge(sess, "hidden", f"Hidden control flag branch triggered: AUTHFLAG={authflag} ADMINFLAG={adminflag} bypassed normal checks.")
        if not auth_ok and self._safe_mode(self._current_mode()):
            sess.status = "AUTHENTICATION FAILED"
            self._log_trace(sess, "EXEC CICS SEND", "AUTHENTICATION FAILED")
            self._set_challenge(sess, "hidden", "Safe mode denied the transfer because the hidden or protected fields were not trusted.")
            return self.snapshot(sid)
        if not ownership_ok and not auth_ok and not self._safe_mode(self._current_mode()):
            self._set_challenge(sess, "idor", f"Unauthorized transfer simulation: {sess.user or 'UNKNOWN'} was allowed to request movement from {src} owned by {src_meta['owner']} to {dst} for {amount}.")
        self.transfer_seq += 1
        txid = f"T{self.transfer_seq:05d}"
        requires_approval = amount >= Decimal("5000.00") or adminflag == "Y" or src_meta["status"].upper().startswith("PENDING")
        if not requires_approval:
            src_balance = Decimal(src_meta["balance"])
            dst_balance = Decimal(dst_meta["balance"])
            src_meta["balance"] = f"{src_balance - amount:.2f}"
            dst_meta["balance"] = f"{dst_balance + amount:.2f}"
        transfer_row = {
            "TXID": txid,
            "SOURCE": src,
            "DESTINATION": dst,
            "AMOUNT": f"{amount:.2f}",
            "MEMO": memo,
            "REQUESTOR": sess.user or "ANON",
            "STATUS": "PENDING APPROVAL" if requires_approval else "POSTED",
        }
        self.transfers.append(transfer_row)
        self.last_statement_for_transfer(src, dst, amount, memo)
        sess.last_rows = [transfer_row]
        if requires_approval:
            sess.status = f"TRANSFER {txid} QUEUED FOR APPROVAL"
            self._set_challenge(sess, "workflow", f"Transfer {txid} requires approval. The APRV screen can be reached directly in vulnerable mode.")
        else:
            sess.status = f"TRANSFER {txid} POSTED"
            self._set_challenge(sess, "overview", f"Transfer {txid} posted from {src} to {dst} for {amount:.2f}.")
        if debugflag == "Y" and not self._safe_mode(self._current_mode()):
            self._log_trace(sess, "DEBUG DUMP", "TEMP-STORAGE = SENSITIVE-TEMP: PIN=****, ROUTING=021000021, BALANCE BUFFER=EXPOSED")
            self._set_challenge(sess, "debug", "Debug branch triggered: TEMP-STORAGE was disclosed because DEBUG-FLAG was trusted from the client-side payload.")
        return self.snapshot(sid)

    def last_statement_for_transfer(self, src: str, dst: str, amount: Decimal, memo: str) -> None:
        self.statements.append({"STMTID": f"S{self.transfer_seq}", "ACCTNO": src, "PERIOD": "2026-04", "DESCRIPTION": f"XFER TO {dst} {memo[:20]}", "AMOUNT": f"-{amount:.2f}"})
        self.statements.append({"STMTID": f"S{self.transfer_seq+1}", "ACCTNO": dst, "PERIOD": "2026-04", "DESCRIPTION": f"XFER FROM {src} {memo[:20]}", "AMOUNT": f"{amount:.2f}"})

    def approve(self, sid: str, txid: str) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        tx = next((t for t in reversed(self.transfers) if t["TXID"] == txid), None)
        sess.current_screen = "APRV"
        sess.last_rows = []
        sess.notes.clear()
        if tx is None:
            sess.status = f"TRANSFER {txid} NOT FOUND"
            self._set_challenge(sess, "workflow", f"Transfer {txid} was not found.")
            return self.snapshot(sid)
        role_ok = bool(sess.user and (self.state.racf.get(sess.user).special if self.state.racf.get(sess.user) else False))
        adminflag = str(sess.fields.get("ADMINFLAG", "N")).upper()[:1]
        if not role_ok and adminflag != "Y" and self._safe_mode(self._current_mode()):
            sess.status = "APPROVAL DENIED"
            self._set_challenge(sess, "workflow", "Safe mode denied the approval because the user is not privileged.")
            return self.snapshot(sid)
        if not role_ok and adminflag == "Y" and not self._safe_mode(self._current_mode()):
            self._set_challenge(sess, "workflow", "Workflow bypass branch triggered: ADMINFLAG=Y reached approval logic without a server-side role check.")
        if tx["STATUS"] == "PENDING APPROVAL":
            src = self.accounts.get(tx["SOURCE"])
            dst = self.accounts.get(tx["DESTINATION"])
            amount = Decimal(tx["AMOUNT"])
            if src and dst:
                src["balance"] = f"{Decimal(src['balance']) - amount:.2f}"
                dst["balance"] = f"{Decimal(dst['balance']) + amount:.2f}"
            tx["STATUS"] = "APPROVED"
        sess.last_rows = [dict(tx)]
        sess.status = f"TRANSFER {txid} APPROVED"
        return self.snapshot(sid)

    def update_hack(self, sid: str, toggles: dict[str, Any]) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        for key in list(sess.hack):
            if key in toggles:
                sess.hack[key] = bool(toggles[key])
        if "tutorial_mode" in toggles:
            sess.tutorial_mode = str(toggles.get("tutorial_mode") or self.default_tutorial).lower()
        if "show_solutions" in toggles:
            sess.show_solutions = bool(toggles.get("show_solutions"))
        sess.current_screen = sess.current_screen or "LOGN"
        onoff = "ON" if sess.hack.get("hack_enabled") else "OFF"
        sess.status = f"HACK3270 FIELD MANIPULATION {onoff}"
        return self.snapshot(sid)

    # ------------------------------------------------------------------
    # Screen rendering / snapshots
    # ------------------------------------------------------------------
    def _field_specs(self, sess: LabSession) -> list[FieldSpec]:
        cur = sess.current_screen.upper()
        fields: list[FieldSpec] = []
        if cur == "LOGN":
            fields = [
                FieldSpec("USERID", "User ID", 7, 24, 8, sess.fields.get("USERID", ""), hidden=False, protected=False),
                FieldSpec("PASSWORD", "Password", 8, 24, 8, sess.fields.get("PASSWORD", ""), hidden=True, protected=False),
                FieldSpec("PASSTICKET", "PassTicket", 9, 24, 8, sess.fields.get("PASSTICKET", ""), hidden=True, protected=False, note="One-time sign-on token for the selected APPLID."),
                FieldSpec("APPLID", "APPLID", 10, 24, 8, sess.fields.get("APPLID", sess.current_appl or "CICS"), hidden=False, protected=False),
            ]
        elif cur == "MENU":
            fields = [FieldSpec("SELECTION", "Selection", 14, 24, 4, sess.fields.get("SELECTION", ""))]
        elif cur == "ACCT":
            fields = [
                FieldSpec("ACCTNO", "Account", 8, 24, 18, sess.fields.get("ACCTNO", "10001"), protected=False),
                FieldSpec("AUTHFLAG", "AUTHFLAG", 18, 24, 1, sess.fields.get("AUTHFLAG", "N"), hidden=True, protected=True, note="Hidden authenticated flag from the training COBOL"),
            ]
        elif cur == "STMT":
            fields = [
                FieldSpec("ACCTNO", "Account", 8, 24, 18, sess.fields.get("ACCTNO", "10001"), protected=False),
                FieldSpec("PERIOD", "Period", 9, 24, 8, sess.fields.get("PERIOD", "2026-04"), protected=False),
            ]
        elif cur == "XFER":
            fields = [
                FieldSpec("SRCACCT", "Source", 8, 24, 18, sess.fields.get("SRCACCT", "10001"), protected=True, note="Protected field: normal terminals should not allow the operator to change it."),
                FieldSpec("DSTACCT", "Destination", 9, 24, 18, sess.fields.get("DSTACCT", "10002"), protected=False),
                FieldSpec("AMOUNT", "Amount", 10, 24, 18, sess.fields.get("AMOUNT", "50.00"), protected=False, numeric=True, note="Numeric-only field in the BMS-style view."),
                FieldSpec("PIN", "PIN", 11, 24, 4, sess.fields.get("PIN", ""), hidden=True, protected=False),
                FieldSpec("MEMO", "Memo", 12, 24, 24, sess.fields.get("MEMO", "LAB TRANSFER"), protected=False),
                FieldSpec("AUTHFLAG", "AUTHFLAG", 17, 24, 1, sess.fields.get("AUTHFLAG", "N"), hidden=True, protected=True),
                FieldSpec("ADMINFLAG", "ADMINFLAG", 18, 24, 1, sess.fields.get("ADMINFLAG", "N"), hidden=True, protected=True),
                FieldSpec("DEBUGFLAG", "DEBUGFLAG", 19, 24, 1, sess.fields.get("DEBUGFLAG", "N"), hidden=True, protected=True),
            ]
        elif cur == "APRV":
            txid = next((t["TXID"] for t in reversed(self.transfers) if t["STATUS"] == "PENDING APPROVAL"), "")
            fields = [
                FieldSpec("TXID", "Transfer ID", 8, 24, 10, sess.fields.get("TXID", txid), protected=False),
                FieldSpec("ADMINFLAG", "ADMINFLAG", 18, 24, 1, sess.fields.get("ADMINFLAG", "N"), hidden=True, protected=True),
            ]
        elif cur == "PTKT":
            fields = [
                FieldSpec("USERID", "User ID", 9, 24, 8, sess.fields.get("USERID", sess.user or "IBMUSER"), protected=False),
                FieldSpec("APPLID", "APPLID", 10, 24, 8, sess.fields.get("APPLID", sess.current_appl or "CICS"), protected=False),
                FieldSpec("PASSTICKET", "PassTicket", 11, 24, 8, sess.fields.get("PASSTICKET", sess.current_ticket), hidden=True, protected=False),
            ]
        elif cur == "HACK":
            fields = []
        return fields

    def _apply_hack_visibility(self, sess: LabSession, specs: list[FieldSpec]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, spec in enumerate(specs, start=1):
            visible = (not spec.hidden) or bool(sess.hack.get("reveal_hidden"))
            editable = (not spec.protected) or bool(sess.hack.get("remove_protection"))
            numeric = spec.numeric and not bool(sess.hack.get("remove_numeric"))
            value = spec.value
            display_value = value
            if spec.hidden and not sess.hack.get("reveal_hidden"):
                display_value = "*" * max(1, min(spec.width, len(value) or spec.width))
            out.append(
                {
                    "name": spec.name,
                    "label": spec.label,
                    "row": spec.row,
                    "col": spec.col,
                    "width": spec.width,
                    "value": value,
                    "display_value": display_value,
                    "hidden": spec.hidden,
                    "visible": visible,
                    "protected": spec.protected,
                    "editable": editable,
                    "numeric": numeric,
                    "mdt": spec.mdt or bool(value),
                    "note": spec.note,
                    "standard": not spec.hidden and not spec.protected,
                }
            )
        return out

    def _screen_lines(self, sess: LabSession) -> list[str]:
        cur = sess.current_screen.upper()
        body: list[str]
        if cur == "LOGN":
            body = [
                "DVCA STYLE BANKING REGION CICSGIB1 / TRANSID GMVB",
                "",
                "USERID . . . . . . .  ________",
                "PASSWORD . . . . . .  ________",
                "PASSTICKET  . . . .   ________",
                "APPLID  . . . . . .   ________",
                "",
                "ENTER USERID+PASSWORD OR USERID+PASSTICKET FOR CICS/TSO/DB2.",
                "PF3=EXIT  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "MENU":
            body = [
                f"SIGNED ON USER . . .  {sess.user or 'GUEST'}",
                "",
                "1  CARG - LEGACY ITEM LOOKUP",
                "2  ORDE - LEGACY ORDER ENTRY",
                "3  ORDR - LEGACY ORDER HISTORY",
                "4  ACCT - ACCOUNT INQUIRY",
                "5  STMT - STATEMENT SEARCH",
                "6  XFER - FUNDS TRANSFER",
                "7  APRV - APPROVAL QUEUE",
                "8  HACK - HACK3270 FIELD LAB",
                "9  PTKT - PASSTICKET LAB",
                "0  LOGN - RETURN TO SIGNON",
                "",
                "SELECTION . . . . .  ____",
                "TYPE A MENU NUMBER OR TRANSACTION ID.",
            ]
        elif cur == "ACCT":
            body = [
                "ACCOUNT LOOKUP",
                "",
                "ACCOUNT . . . . . .  _________________",
                "",
                "LOOK UP AN ACCOUNT OR TRY 10001' OR '1'='1",
                "HIDDEN AUTHFLAG MAY AFFECT TRUST IN TRAINING MODE.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "STMT":
            body = [
                "STATEMENT SEARCH",
                "",
                "ACCOUNT . . . . . .  _________________",
                "PERIOD . . . . . . .  ________",
                "",
                "SEARCH STATEMENTS OR TRY SQL-LIKE INPUT.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "XFER":
            body = [
                "FUNDS TRANSFER",
                "",
                "SOURCE ACCOUNT . . .  _________________",
                "DEST ACCOUNT . . . .  _________________",
                "AMOUNT . . . . . . .  _________________",
                "PIN . . . . . . . .   ____",
                "MEMO . . . . . . . .  ________________________",
                "",
                "HIDDEN AUTH/ADMIN/DEBUG FLAGS AVAILABLE IN HACK3270 MODE.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "APRV":
            body = [
                "APPROVAL QUEUE",
                "",
                "TRANSFER ID . . . .   __________",
                "",
                "APPROVE A PENDING TRANSFER. DIRECT ACCESS IS PART OF THE LAB.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "PTKT":
            body = [
                "PASSTICKET LAB",
                "",
                "USERID . . . . . . .  ________",
                "APPLID . . . . . . .  ________",
                "PASSTICKET . . . . .  ________",
                "",
                "USE THE WEB PANEL TO GENERATE OR TAMPER WITH PTKTDATA FLAGS.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        elif cur == "HACK":
            body = [
                "HACK3270 FIELD MANIPULATION",
                "",
                "TOGGLE HIDDEN FIELD REVEAL, FIELD PROTECTION, NUMERIC CHECKS,",
                "AND BMS/3270 METADATA USING THE PANEL TO THE RIGHT.",
                "",
                "THE GOAL IS TO SHOW THAT FIELD ATTRIBUTES ARE NOT SECURITY CONTROLS.",
                "PF3=BACK  PF4=MENU  PF12=LOGOFF",
            ]
        else:
            body = ["UNKNOWN SCREEN", "PF4=MENU"]
        return body

    def render_terminal(self, sid: str) -> str:
        sess = self.ensure_session(sid)
        specs = self._apply_hack_visibility(sess, self._field_specs(sess))
        screen = ScreenBuffer()
        screen.put(1, 1, " Menu  Utilities  PassTicket  Hack3270  API Trace  Tutorial  Solutions ")
        screen.put(2, 1, "=" * 79)
        screen.put(3, 1, "SIGHBERBANK MAINFRAME VULNERABLE BANKING LAB".center(79))
        screen.put(4, 1, f"STATUS: {sess.status}"[:79])
        lines = self._screen_lines(sess)
        row = 6
        for line in lines:
            screen.put(row, 1, line[:79])
            row += 1
        for spec in specs:
            if not spec["visible"] and not sess.hack.get("show_metadata"):
                continue
            value = str(spec["display_value"])[: int(spec["width"])]
            screen.add_field(int(spec["row"]), int(spec["col"]), int(spec["width"]), value, name=str(spec["name"]), protected=not bool(spec["editable"]), hidden=False)
        screen.put(22, 1, "PF1=HELP PF3=BACK PF4=MENU PF9=TRACE PF12=LOGOFF")
        screen.put(23, 1, f"MODE={self._current_mode().upper()}  HACK={'ON' if sess.hack.get('hack_enabled') else 'OFF'}  USER={sess.user or 'ANON'}")
        return screen.render_plain()

    def tutorial_block(self, sid: str) -> dict[str, str]:
        sess = self.ensure_session(sid)
        info = CHALLENGE_GUIDE.get(sess.last_challenge, CHALLENGE_GUIDE["overview"])
        return {
            "title": info["title"],
            "hint": info["hint"],
            "guided": info["guided"],
            "solution": info["solution"] if sess.show_solutions else "Solutions are disabled by configuration. Enable BANK_SHOW_SOLUTIONS=1 to expose them.",
        }

    def snapshot(self, sid: str) -> dict[str, Any]:
        sess = self.ensure_session(sid)
        specs = self._apply_hack_visibility(sess, self._field_specs(sess))
        return {
            "sid": sess.sid,
            "current_screen": sess.current_screen,
            "user": sess.user,
            "authenticated": sess.authenticated,
            "status": sess.status,
            "notes": list(sess.notes),
            "rows": list(sess.last_rows),
            "traces": list(sess.traces),
            "fields": specs,
            "hack": dict(sess.hack),
            "tutorial_mode": sess.tutorial_mode,
            "show_solutions": sess.show_solutions,
            "tutorial": self.tutorial_block(sid),
            "passticket": self.passticket_block(sid),
            "terminal_screen": self.render_terminal(sid),
            "feature_flags": {
                "BANK_LAB_MODE": self._current_mode(),
                "BANK_TUTORIAL_MODE": sess.tutorial_mode,
                "BANK_SHOW_SOLUTIONS": sess.show_solutions,
                "BANK_HACK3270_PANEL": sess.hack.get("panel_enabled", True),
                "CURRENT_APPLID": sess.current_appl,
            },
            "cobol_excerpt": html.escape("\n".join(VULNERABLE_BANK_UPDATE_COBOL.splitlines()[:40])),
        }

    def terminal_submit(self, sid: str, fields: dict[str, Any] | None = None, command: str = "", pf: str = "") -> dict[str, Any]:
        sess = self.ensure_session(sid)
        if fields:
            for key, value in fields.items():
                sess.fields[str(key).upper()] = str(value)
        pf_u = (pf or "").upper()
        if pf_u in {"PF12", "F12"}:
            sess.authenticated = False
            sess.user = ""
            sess.current_screen = "LOGN"
            sess.status = "SIGNED OFF FROM SIGHBERBANK"
            return self.snapshot(sid)
        if pf_u in {"PF4", "F4"}:
            sess.previous_screen = sess.current_screen
            sess.current_screen = "MENU"
            sess.status = "MENU REQUESTED"
            return self.snapshot(sid)
        if pf_u in {"PF3", "F3"}:
            target = sess.previous_screen if sess.current_screen != "MENU" else "LOGN"
            sess.previous_screen = "MENU"
            sess.current_screen = target or "MENU"
            sess.status = f"RETURNED TO {sess.current_screen}"
            return self.snapshot(sid)
        entered = (command or "").strip()
        if entered and sess.current_screen == "MENU":
            return self.menu_select(sid, entered)
        if sess.current_screen == "LOGN":
            return self.login(sid, sess.fields.get("USERID", ""), sess.fields.get("PASSWORD", ""), sess.fields.get("PASSTICKET", ""), sess.fields.get("APPLID", "CICS"))
        if sess.current_screen == "MENU":
            return self.menu_select(sid, sess.fields.get("SELECTION", entered))
        if sess.current_screen == "ACCT":
            return self.account_lookup(sid, sess.fields.get("ACCTNO", entered))
        if sess.current_screen == "STMT":
            return self.statement_lookup(sid, sess.fields.get("ACCTNO", entered), sess.fields.get("PERIOD", ""))
        if sess.current_screen == "XFER":
            return self.transfer(sid, sess.fields)
        if sess.current_screen == "APRV":
            return self.approve(sid, sess.fields.get("TXID", entered))
        if sess.current_screen == "PTKT":
            return self.passticket_use(sid, sess.fields.get("USERID", ""), sess.fields.get("PASSTICKET", ""), sess.fields.get("APPLID", "CICS"))
        if sess.current_screen == "HACK":
            sess.status = "USE THE HACK3270 PANEL TO ALTER FIELD ATTRIBUTES"
            return self.snapshot(sid)
        return self.snapshot(sid)



# Legacy GMVB/FIBS upgrade hooks removed; CBSA/DVCA are clean subsystems.

def get_banking_lab(state: GibsonState) -> BankingLabService:
    svc = getattr(state, "banking_lab_service", None)
    if svc is None:
        svc = BankingLabService(state)
        setattr(state, "banking_lab_service", svc)
    return svc
