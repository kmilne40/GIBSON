from __future__ import annotations
from typing import Any
from ..writer import record_generic

def racf_event(state: Any, *, userid: str, event_name: str, result: str = "SUCCESS", event_code: str = "", qualifier: str = "", class_name: str = "RACF", resource_name: str = "", profile_name: str = "", access_requested: str = "", access_allowed: str = "", reason_code: str = "", jobname: str = "", applid: str = "", terminal: str = "TTY", source_ip: str = "", correlation_id: str = "", detail: str = ""):
    extra = {
        "RECORD_TYPE":"80", "SUBTYPE":"RACF", "EVENT_NAME":event_name.upper(),
        "EVENT_CODE":event_code, "EVENT_CODE_QUALIFIER":qualifier, "RESULT":result.upper(),
        "USERID":userid.upper(), "JOBNAME":jobname or userid[:8].upper(), "CLASS_NAME":class_name.upper(),
        "CLASS":class_name.upper(), "RESOURCE_NAME":resource_name, "RESOURCE":resource_name,
        "PROFILE_NAME":profile_name, "PROFILE":profile_name, "ACCESS_REQUESTED":access_requested,
        "ACCESS_ALLOWED":access_allowed, "REASON_CODE":reason_code, "APPLID":applid,
        "TERMINAL":terminal, "SOURCE_IP":source_ip, "ADDR":source_ip, "CORRELATION_ID":correlation_id,
        "MESSAGE_ID":"ICH408I" if result.upper() != "SUCCESS" else "ICH70001I", "DETAIL":detail,
    }
    return record_generic(state, 80, userid, event_name, detail or resource_name, subtype="RACF", result=result, extra=extra, subsystem="RACF", source_component="RACF")

def passticket_generate(state: Any, *, userid: str, requester: str, applid: str, result: str, reason_code: str = "OK", correlation_id: str = "", detail: str = ""):
    extra = {"EVENT_CODE":"82", "REQUESTER":requester.upper(), "APPLID":applid.upper(), "CLASS_NAME":"PTKTDATA", "RESOURCE_NAME":f"IRRPTAUTH.{applid.upper()}.{userid.upper()}", "PROFILE_NAME":applid.upper(), "REASON_CODE":reason_code, "CORRELATION_ID":correlation_id}
    return racf_event(state, userid=userid, event_name="PASSTICKET_GENERATE", result=result, event_code="82", class_name="PTKTDATA", resource_name=extra["RESOURCE_NAME"], profile_name=applid.upper(), access_requested="UPDATE", access_allowed="UPDATE" if result.upper()=="SUCCESS" else "NONE", reason_code=reason_code, correlation_id=correlation_id, detail=detail, applid=applid, terminal="PTKT")

def passticket_evaluate(state: Any, *, userid: str, consumer: str, applid: str, result: str, reason_code: str = "OK", correlation_id: str = "", detail: str = ""):
    return racf_event(state, userid=userid, event_name="PASSTICKET_EVALUATE", result=result, event_code="81", class_name="PTKTDATA", resource_name=applid.upper(), profile_name=applid.upper(), access_requested="READ", access_allowed="READ" if result.upper()=="SUCCESS" else "NONE", reason_code=reason_code, correlation_id=correlation_id, detail=detail, applid=applid, terminal=consumer.upper())
