from __future__ import annotations
from typing import Any
from ..writer import record_generic

def data_lost(state: Any, *, userid: str="SYSTEM", reason: str="SMF BUFFER FULL", count_lost: int=1, affected_record_types: str="UNKNOWN", correlation_id: str=""):
    extra={"RECORD_TYPE":"7","SUBTYPE":"DATA_LOST","EVENT_NAME":"SMF_DATA_LOST","RESULT":"WARNING","REASON_CODE":reason,"COUNT_LOST":str(count_lost),"AFFECTED_RECORD_TYPES":affected_record_types,"CORRELATION_ID":correlation_id}
    return record_generic(state,7,userid,"SMF_DATA_LOST",reason,subtype="DATA_LOST",result="WARNING",extra=extra,subsystem="SMF",source_component="SMF")
