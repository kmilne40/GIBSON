from __future__ import annotations
from typing import Any
from ..writer import record_generic

def job_step(state: Any, *, userid: str, jobname: str, stepname: str = "STEP1", program: str = "UNKNOWN", result: str = "SUCCESS", condition_code: str = "0000", abend_code: str = "", correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"30","SUBTYPE":"JOBSTEP","EVENT_NAME":"JOB_STEP","RESULT":result,"JOBNAME":jobname,"STEPNAME":stepname,"PROGRAM":program,"CONDITION_CODE":condition_code,"ABEND_CODE":abend_code,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,30,userid,"JOB_STEP",detail or program,subtype="JOBSTEP",result=result,extra=extra,subsystem="JES",source_component="JES")
