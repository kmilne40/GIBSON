from gibson.core.state import GibsonState
from gibson.core.smf.records.type80 import racf_event
from gibson.core.smf.formatters import format_list, format_detail


def test_structured_smf_record_has_header_and_detail():
    st = GibsonState.create()
    rec = racf_event(st, userid="IBMUSER", event_name="LOGON", result="SUCCESS", class_name="APPL", resource_name="TSO", correlation_id="CORR1", detail="LOGON OK")
    d = rec.to_dict()
    assert d["record_type"] == "80"
    assert d["record_id"].startswith("SMF-")
    assert d["userid"] == "IBMUSER"
    assert d["correlation_id"] == "CORR1"
    assert "SMF STRUCTURED RECORD LIST" in format_list(st, "80")
    assert "SMF TYPE 80 STRUCTURED RECORD DETAIL" in format_detail(st, rec.header.record_id)
