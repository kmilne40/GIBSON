from __future__ import annotations
from typing import Any
from ..writer import record_generic

def cics_monitor(state: Any, *, userid: str, transaction_id: str, program: str = "UNKNOWN", result: str = "SUCCESS", applid: str = "CICS", terminal_id: str = "TERM", task_number: str = "000001", elapsed_ms: int = 1, db2_call_count: int = 0, abend_code: str = "", correlation_id: str = "", detail: str = ""):
    extra = {"RECORD_TYPE":"110","SUBTYPE":"1","EVENT_NAME":"CICS_TRANSACTION","RESULT":result,"APPLID":applid,"REGION":applid,"TRANSID":transaction_id,"TRANSACTION_ID":transaction_id,"PROGRAM":program,"TASK_NUMBER":task_number,"TERMINAL_ID":terminal_id,"TERMID":terminal_id,"USERID":userid,"ELAPSED_MS":str(elapsed_ms),"CPU_MS":"0","DB2_CALL_COUNT":str(db2_call_count),"ABEND_CODE":abend_code,"RESPONSE_CODE":result,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state, 110, userid, "CICS_TRANSACTION", detail or transaction_id, subtype="1", result=result, extra=extra, subsystem="CICS", source_component="CICS")
