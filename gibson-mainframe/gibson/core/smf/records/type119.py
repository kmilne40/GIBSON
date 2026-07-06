from __future__ import annotations
from typing import Any
from ..writer import record_generic

def tcpip(state: Any, *, userid: str, application: str, remote_ip: str, remote_port: int = 0, local_ip: str = "127.0.0.1", local_port: int = 0, protocol: str = "TCP", result: str = "SUCCESS", bytes_in: int = 0, bytes_out: int = 0, correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"119","SUBTYPE":"CONNECTION","EVENT_NAME":"TCPIP_CONNECTION","RESULT":result,"APPLICATION":application,"REMOTE_IP":remote_ip,"REMOTE_PORT":str(remote_port),"LOCAL_IP":local_ip,"LOCAL_PORT":str(local_port),"PROTOCOL":protocol,"BYTES_IN":str(bytes_in),"BYTES_OUT":str(bytes_out),"CORRELATION_ID":correlation_id,"DETAIL":detail}
    return record_generic(state,119,userid,"TCPIP_CONNECTION",detail or application,subtype="CONNECTION",result=result,extra=extra,subsystem="TCPIP",source_component="NETWORK")


def tcp_connection(state, *, userid: str, application: str, remote_ip: str = "", local_port: str = "", remote_port: str = "", result: str = "SUCCESS", bytes_out: int = 0, resource: str = "", correlation_id: str = "", detail: str = ""):
    extra={"RECORD_TYPE":"119","SUBTYPE":"TCPIP","EVENT_NAME":"TCPIP_CONNECTION","RESULT":result,"APPLICATION":application,"REMOTE_IP":remote_ip,"LOCAL_PORT":local_port,"REMOTE_PORT":remote_port,"BYTES_OUT":str(bytes_out),"RESOURCE":resource,"CORRELATION_ID":correlation_id,"DETAIL":detail}
    from ..writer import record_generic
    return record_generic(state,119,userid,"TCPIP_CONNECTION",detail or application,subtype="TCPIP",result=result,extra=extra,subsystem="TCPIP",source_component="COMMUNICATIONS_SERVER")
