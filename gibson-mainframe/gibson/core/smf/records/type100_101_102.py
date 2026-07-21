from __future__ import annotations
from typing import Any
from ..writer import record_generic

def db2_accounting(state: Any, *, userid: str, sql_verb: str, table_name: str = "", result: str = "SUCCESS", sqlcode: str = "0", rows_returned: int = 0, suspicious_payload_class: str = "", correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"101","SUBTYPE":"ACCOUNTING","EVENT_NAME":"DB2_ACCOUNTING","RESULT":result,"AUTHID":userid.upper(),"SQL_VERB":sql_verb.upper(),"TABLE_NAME":table_name,"SQLCODE":str(sqlcode),"ROWS_RETURNED":str(rows_returned),"SUSPICIOUS_PAYLOAD_CLASS":suspicious_payload_class,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,101,userid,"DB2_ACCOUNTING",detail or sql_verb,subtype="ACCOUNTING",result=result,extra=extra,subsystem="DB2",source_component="DB2")

def db2_audit(state: Any, **kwargs):
    rec = db2_accounting(state, **kwargs)
    f = rec.raw_fields; f["RECORD_TYPE"]="102"; rec.header.record_type=102; rec.header.subtype="AUDIT"
    return rec
