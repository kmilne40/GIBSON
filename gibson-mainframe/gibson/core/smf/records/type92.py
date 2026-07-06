from __future__ import annotations
from typing import Any
from ..writer import record_generic

def uss_file(state: Any, *, userid: str, path: str, operation: str, program: str = "OMVS", result: str = "SUCCESS", bytes_count: int = 0, errno: str = "", correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"92","SUBTYPE":"FILE","EVENT_NAME":"USS_FILE_ACTIVITY","RESULT":result,"PATH":path,"OPERATION":operation.upper(),"PROGRAM":program,"BYTES":str(bytes_count),"ERRNO":errno,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,92,userid,"USS_FILE_ACTIVITY",detail or path,subtype="FILE",result=result,extra=extra,subsystem="OMVS",source_component="USS")
