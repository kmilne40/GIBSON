from __future__ import annotations
from decimal import Decimal
from .models import Customer, Account, now_iso, money
from .store import get_cbsa_store
from .validation import require, valid_amount

class CbsaService:
    def __init__(self, state): self.state=state; self.store=get_cbsa_store(state)
    def reset(self): return self.store.seed()
    def customer(self, cid):
        c=self.store.customers.get(str(cid));
        if not c: raise KeyError("CUSTOMER NOT FOUND")
        return c
    def account(self, acc):
        a=self.store.accounts.get(str(acc).zfill(8));
        if not a: raise KeyError("ACCOUNT NOT FOUND")
        return a
    def list_accounts(self,cid): return [a for a in self.store.accounts.values() if a.customer_id==str(cid)]
    def create_customer(self, data, channel="REST"):
        cid=str(data.get("customer_id") or self.store.next_customer_id())
        ts=now_iso(); c=Customer(cid, require(data.get("name","NEW CUSTOMER"),"NAME"), data.get("address1",""), data.get("address2",""), data.get("date_of_birth",""), str(data.get("credit_score","700")), "ACTIVE", str(data.get("risk_score","LOW")), str(data.get("isAdmin","false")).lower(), str(data.get("creditLimit","5000.00")), ts, ts)
        self.store.customers[cid]=c; self.store.record_transaction("CRECUST", customer_id=cid, channel=channel); return c
    def update_customer(self, cid, data, channel="REST", vulnerable=False):
        c=self.customer(cid)
        for k in ["name","address1","address2","date_of_birth","credit_score","status"]:
            if k in data: setattr(c,k,str(data[k]))
        if vulnerable:
            for k in ["isAdmin","creditLimit","risk_score"]:
                if k in data: setattr(c,k,str(data[k]))
        c.updated_at=now_iso(); self.store.record_transaction("UPDCUST", customer_id=c.customer_id, channel=channel); return c
    def delete_customer(self,cid, channel="REST"):
        if self.list_accounts(cid): raise ValueError("CUSTOMER HAS ACCOUNTS")
        c=self.store.customers.pop(str(cid)); self.store.record_transaction("DELCUS", customer_id=cid, channel=channel); return c
    def create_account(self,data,channel="REST"):
        cid=require(data.get("customer_id"),"CUSTOMER_ID"); self.customer(cid)
        acc=str(data.get("account_number") or self.store.next_account_number()).zfill(8)
        bal=money(data.get("actual_balance",data.get("balance","0.00")))
        a=Account(str(data.get("sort_code","00-00-01")),acc,cid,str(data.get("account_type","CURRENT")),str(data.get("interest_rate","0.01")),str(data.get("opened_date","2026-01-01")),money(data.get("overdraft_limit","500.00")),bal,bal,str(data.get("last_statement_date","2026-01-01")),str(data.get("next_statement_date","2026-02-01")),"OPEN")
        self.store.accounts[acc]=a; self.store.record_transaction("CREACC", account=acc, customer_id=cid, channel=channel); return a
    def update_account(self,acc,data,channel="REST"):
        a=self.account(acc)
        for k in ["account_type","interest_rate","overdraft_limit","status","next_statement_date"]:
            if k in data: setattr(a,k,str(data[k]))
        self.store.record_transaction("UPDACC", account=a.account_number, customer_id=a.customer_id, channel=channel); return a
    def delete_account(self,acc,channel="REST"):
        a=self.store.accounts.pop(str(acc).zfill(8)); self.store.record_transaction("DELACC", account=a.account_number, customer_id=a.customer_id, channel=channel); return a
    def credit_debit(self,acc,amount,channel="REST", allow_negative_logic=False):
        a=self.account(acc); amt=valid_amount(amount)
        new=Decimal(a.actual_balance)+amt
        minimum=-Decimal(a.overdraft_limit)
        if new < minimum and not allow_negative_logic: raise ValueError("INSUFFICIENT FUNDS")
        a.actual_balance=money(new); a.available_balance=money(new+Decimal(a.overdraft_limit))
        self.store.record_transaction("DBCRFUN", account=a.account_number, amount=amt, customer_id=a.customer_id, channel=channel); return a
    def transfer(self,from_acc,to_acc,amount,channel="REST", vulnerable=False):
        amt=valid_amount(amount)
        if amt <= 0 and not vulnerable: raise ValueError("AMOUNT MUST BE POSITIVE")
        src=self.credit_debit(from_acc, -amt, channel=channel, allow_negative_logic=vulnerable)
        dst=self.credit_debit(to_acc, amt, channel=channel, allow_negative_logic=True)
        self.store.record_transaction("XFRFUN", from_account=src.account_number, to_account=dst.account_number, amount=amt, customer_id=src.customer_id, channel=channel); return src,dst
    def payment_envelope(self, payload, channel="REST"):
        pay=payload.get("PAYDBCR", payload)
        acc=str(pay.get("COMM_ACCNO", pay.get("account",""))).zfill(8); amt=pay.get("COMM_AMT", pay.get("amount","0"))
        try:
            a=self.credit_debit(acc, amt, channel=channel)
            return {"PAYDBCR":{"COMM_ACCNO":a.account_number,"COMM_SORTC":a.sort_code,"COMM_AV_BAL":a.available_balance,"COMM_ACT_BAL":a.actual_balance,"COMM_SUCCESS":"Y","COMM_FAIL_CODE":" ","COMM_AMT":money(amt)}}
        except Exception as e:
            self.store.abend("DBCRFUN","REST","PAYFAIL",str(e),str(payload))
            return {"PAYDBCR":{"COMM_ACCNO":acc,"COMM_SORTC":"","COMM_AV_BAL":"0.00","COMM_ACT_BAL":"0.00","COMM_SUCCESS":"N","COMM_FAIL_CODE":str(e)[:40],"COMM_AMT":str(amt)}}
