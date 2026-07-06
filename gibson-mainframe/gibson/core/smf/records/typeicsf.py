from __future__ import annotations
from typing import Any
from ..writer import record_generic

def master_key_refresh(state: Any, *, userid: str, key_type: str="AES", key_store: str="CKDS", result: str="SUCCESS", phase: str="COMPLETE", old_vp: str="", new_vp: str="", reason_code: str="OK", correlation_id: str="", detail: str=""):
    extra={"RECORD_TYPE":"ICSF","SUBTYPE":"MASTERKEY","EVENT_NAME":"ICSF_MASTER_KEY_REFRESH","RESULT":result,"CSF_COMPONENT":"ICSF","KEY_TYPE":key_type,"KEY_STORE":key_store,"OLD_KEY_VERIFICATION_PATTERN":old_vp,"NEW_KEY_VERIFICATION_PATTERN":new_vp,"REFRESH_PHASE":phase,"REASON_CODE":reason_code,"ICSF_RETURN_CODE":"0" if result.upper()=="SUCCESS" else "8","ICSF_REASON_CODE":reason_code,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,0,userid,"ICSF_MASTER_KEY_REFRESH",detail or key_store,subtype="ICSF_MASTERKEY",result=result,extra=extra,subsystem="ICSF",source_component="ICSF")
