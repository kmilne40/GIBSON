from __future__ import annotations
from typing import Any
from ..writer import record_generic

def api_request(state: Any, *, userid: str, api_name: str, method: str, uri: str, status_code: int = 200, client_ip: str = "", result: str = "SUCCESS", correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"123","SUBTYPE":"1","EVENT_NAME":"API_PROVIDER_REQUEST","RESULT":result,"API_NAME":api_name,"METHOD":method,"URI":uri,"STATUS_CODE":str(status_code),"CLIENT_IP":client_ip,"AUTH_TYPE":"SIMULATED","CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,123,userid,"API_PROVIDER_REQUEST",detail or uri,subtype="1",result=result,extra=extra,subsystem="API",source_component="ZOSCONNECT")
