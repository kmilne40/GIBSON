from __future__ import annotations
from dataclasses import asdict
from decimal import Decimal
from typing import Any
import itertools
import hashlib
from .models import Customer, Account, now_iso, money
from .vuln_scenarios import SCENARIOS


def _corr(prefix="CBSA") -> str:
    import datetime, random
    return f"{prefix}-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"

class CbsaStore:
    def __init__(self):
        self.customers: dict[str, Customer] = {}
        self.accounts: dict[str, Account] = {}
        self.control: dict[str, str] = {"LAST_CUSTOMER_NUMBER": "1003", "LAST_ACCOUNT_NUMBER": "00000103"}
        self.proctran: list[dict[str, str]] = []
        self.abndfile: list[dict[str, str]] = []
        self.api_audit: list[dict[str, str]] = []
        self.cics_audit: list[dict[str, str]] = []
        self.sqli_events: list[dict[str, str]] = []
        self.vuln_events: list[dict[str, str]] = []
        self.web_users: dict[str, dict[str, str]] = {}
        self.web_sessions: dict[str, dict[str, str]] = {}
        self.web_audit: list[dict[str, str]] = []
        self.payees: list[dict[str, str]] = []
        self.statements: list[dict[str, str]] = []
        self.web_messages: list[dict[str, str]] = []
        self.web_lab_events: list[dict[str, str]] = []
        self.scenarios: dict[str, bool] = dict(SCENARIOS)
        self.seed()

    def seed(self):
        self.customers.clear(); self.accounts.clear(); self.proctran.clear(); self.abndfile.clear(); self.api_audit.clear(); self.cics_audit.clear(); self.sqli_events.clear(); self.vuln_events.clear()
        self.web_users.clear(); self.web_sessions.clear(); self.web_audit.clear(); self.payees.clear(); self.statements.clear(); self.web_messages.clear(); self.web_lab_events.clear()
        ts=now_iso()
        for c in [
            Customer("1001","ALICE MORGAN","1 HIGH STREET","LONDON","1980-01-01","740","ACTIVE","LOW","false","5000.00",ts,ts),
            Customer("1002","BOB SMITH","2 BANK ROAD","GLASGOW","1975-05-12","680","ACTIVE","MEDIUM","false","2500.00",ts,ts),
            Customer("1003","CAROL JONES","3 MAIN AVE","CARDIFF","1990-09-30","710","ACTIVE","LOW","false","7500.00",ts,ts),
        ]: self.customers[c.customer_id]=c
        for a in [
            Account("00-00-01","00000101","1001","CURRENT","0.01","2026-01-01","500.00","1500.00","1500.00"),
            Account("00-00-01","00000102","1001","SAVINGS","0.03","2026-01-01","0.00","3500.00","3500.00"),
            Account("00-00-01","00000103","1002","CURRENT","0.01","2026-01-01","250.00","250.00","250.00"),
            Account("00-00-01","00000104","1003","CURRENT","0.01","2026-01-01","1000.00","50.00","50.00"),
        ]: self.accounts[a.account_number]=a
        self.control["LAST_ACCOUNT_NUMBER"]="00000104"; self.control["LAST_CUSTOMER_NUMBER"]="1003"
        self.ensure_web_user("alice", "training1", "1001", "customer", "ALICE MORGAN")
        self.ensure_web_user("bob", "training1", "1002", "customer", "BOB SMITH")
        self.ensure_web_user("carol", "training1", "1003", "customer", "CAROL JONES")
        self.ensure_web_user("teller", "cics", "", "teller", "FIBS Teller")
        self.ensure_web_user("admin", "sys1", "", "instructor", "FIBS Instructor")
        self.payees.extend([
            {"PAYEE_ID":"P001","CUSTOMER_ID":"1001","NAME":"Highland Energy","ACCOUNT_NUMBER":"00000103","REFERENCE":"UTILITIES"},
            {"PAYEE_ID":"P002","CUSTOMER_ID":"1001","NAME":"Caledonia Council Tax","ACCOUNT_NUMBER":"00000104","REFERENCE":"COUNCIL"},
        ])
        self.web_messages.append({"ID":"MSG001","TEXT":"Welcome to FIBS BANK - First International Bank of Scotland.","LEVEL":"INFO"})
        return {"status":"SEEDED","customers":len(self.customers),"accounts":len(self.accounts),"web_users":len(self.web_users)}

    def next_customer_id(self)->str:
        n=int(self.control.get("LAST_CUSTOMER_NUMBER","1000"))+1; self.control["LAST_CUSTOMER_NUMBER"]=str(n); return str(n)
    def next_account_number(self)->str:
        n=int(self.control.get("LAST_ACCOUNT_NUMBER","0"))+1; self.control["LAST_ACCOUNT_NUMBER"]=f"{n:08d}"; return f"{n:08d}"
    def audit(self, channel:str, kind:str, payload:str, result:str="OK", rows:int=0, user:str="IBMUSER", scenario:str="") -> dict[str,str]:
        ev={"EVENT_ID":_corr("CBSA"),"TIMESTAMP":now_iso(),"CHANNEL":channel,"USER":user,"ACTION":kind,"PAYLOAD":payload[:240],"RESULT":result,"ROWS_RETURNED":str(rows),"SCENARIO":scenario,"CORRELATION_ID":_corr("CORR"),"TRAINING_CONTROL":scenario or "CBSA"}
        if channel=="REST": self.api_audit.append(ev)
        elif channel=="CICS": self.cics_audit.append(ev)
        elif channel=="DB2": self.sqli_events.append(ev)
        elif channel=="WEB9080": self.web_audit.append(ev)
        else: self.vuln_events.append(ev)
        if scenario:
            self.vuln_events.append(dict(ev)); self.web_lab_events.append(dict(ev))
        return ev
    def _web_hash(self, password: str) -> str:
        return "sha256$" + hashlib.sha256((password or "").encode("utf-8")).hexdigest()
    def ensure_web_user(self, username: str, password: str, customer_id: str="", role: str="customer", name: str="") -> dict[str,str]:
        user_id=(username or "").strip().upper()
        rec={"USER_ID":user_id,"USERNAME":(username or "").strip().lower(),"PASSWORD_HASH":self._web_hash(password),"ROLE":(role or "customer").lower(),"CUSTOMER_ID":str(customer_id or ""),"STATUS":"ACTIVE","NAME":name or user_id,"CREATED_AT":now_iso(),"UPDATED_AT":now_iso(),"LAST_LOGIN":"","FAILED_LOGINS":"0","CREATED_BY":"SYSTEM","RESET_REQUIRED":"false","MFA_FLAG":"false"}
        self.web_users[user_id]=rec
        return rec
    def verify_web_user(self, username: str, password: str, *, allow_weak: bool=False) -> dict[str,str] | None:
        rec=self.web_users.get((username or "").strip().upper())
        if not rec or rec.get("STATUS")!="ACTIVE": return None
        if allow_weak and password == "": return rec
        return rec if rec.get("PASSWORD_HASH")==self._web_hash(password) else None
    def create_web_session(self, rec: dict[str,str]) -> str:
        sid=_corr("WEB")
        self.web_sessions[sid]={"SESSION_ID":sid,"USER_ID":rec.get("USER_ID",""),"USERNAME":rec.get("USERNAME",""),"ROLE":rec.get("ROLE",""),"CUSTOMER_ID":rec.get("CUSTOMER_ID",""),"CREATED_AT":now_iso(),"LAST_SEEN":now_iso(),"STATUS":"ACTIVE"}
        rec["LAST_LOGIN"]=now_iso()
        return sid
    def get_web_session(self, sid: str) -> dict[str,str] | None:
        rec=self.web_sessions.get(sid or "")
        if rec and rec.get("STATUS")=="ACTIVE":
            rec["LAST_SEEN"]=now_iso(); return rec
        return None
    def abend(self, program:str, transaction:str, code:str, text:str, snap:str=""):
        self.abndfile.append({"TIMESTAMP":now_iso(),"PROGRAM":program,"TRANSACTION":transaction,"ERROR_CODE":code,"ERROR_TEXT":text,"INPUT_SNAPSHOT":snap[:200],"CORRELATION_ID":_corr("ABND")})
    def record_transaction(self, typ:str, account:str="", from_account:str="", to_account:str="", amount:str="0.00", customer_id:str="", result:str="OK", origin:str="CBSA", channel:str="CICS"):
        rec={"TRANSACTION_ID":_corr("TRN"),"TIMESTAMP":now_iso(),"TRANSACTION_TYPE":typ,"ACCOUNT_NUMBER":account,"FROM_ACCOUNT":from_account,"TO_ACCOUNT":to_account,"AMOUNT":money(amount),"CUSTOMER_ID":customer_id,"RESULT":result,"ORIGIN":origin,"CHANNEL":channel,"CORRELATION_ID":_corr("CORR")}
        self.proctran.append(rec); return rec
    def tables(self) -> dict[str, list[dict[str,str]]]:
        return {
            "CBSA.CUSTOMER":[c.row() for c in self.customers.values()],
            "CBSA.ACCOUNT":[a.row() for a in self.accounts.values()],
            "CBSA.CONTROL":[{"KEY":k,"VALUE":v} for k,v in self.control.items()],
            "CBSA.PROCTRAN":list(self.proctran),
            "CBSA.ABNDFILE":list(self.abndfile),
            "CBSA.SQLI_EVENTS":list(self.sqli_events),
            "CBSA.API_AUDIT":list(self.api_audit),
            "CBSA.CICS_AUDIT":list(self.cics_audit),
            "CBSA.VULN_EVENTS":list(self.vuln_events),
            "CBSA.WEB_USERS":list(self.web_users.values()),
            "CBSA.GACF_USERS":list(self.web_users.values()),
            "CBSA.WEB_SESSIONS":list(self.web_sessions.values()),
            "CBSA.WEB_AUDIT":list(self.web_audit),
            "CBSA.PAYEES":list(self.payees),
            "CBSA.STATEMENTS":list(self.statements),
            "CBSA.WEB_MESSAGES":list(self.web_messages),
            "CBSA.WEB_LAB_EVENTS":list(self.web_lab_events),
            "CBSA.VULN_ACCOUNT_LOOKUP":[a.row() | {"CUSTOMER_INPUT":"<training>"} for a in self.accounts.values()],
            "CBSA.VULN_CUSTOMER_SEARCH":[c.row() | {"CUSTOMER_INPUT":"<training>"} for c in self.customers.values()],
        }
    def metadata(self):
        tables=[]; cols=[]
        for full, rows in self.tables().items():
            creator,name=full.split('.',1); tables.append({"NAME":name,"CREATOR":creator,"TYPE":"T","DBNAME":"CBSADB","TSNAME":name[:8]})
            sample=rows[0] if rows else {}
            for k in sample: cols.append({"TBNAME":name,"TBCREATOR":creator,"NAME":k,"COLTYPE":"VARCHAR","LENGTH":"128"})
        return tables, cols

def get_cbsa_store(state) -> CbsaStore:
    if not hasattr(state, "cbsa_store"):
        setattr(state, "cbsa_store", CbsaStore())
    return getattr(state, "cbsa_store")
