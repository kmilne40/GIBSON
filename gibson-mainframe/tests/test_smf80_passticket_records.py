from gibson.core.state import GibsonState
from gibson.core.passticket import get_passticket_service
from gibson.core.smf.writer import get_smf_writer


def test_passticket_generate_and_evaluate_emit_smf80_82_81():
    st = GibsonState.create()
    svc = get_passticket_service(st)
    gen = svc.generate("IBMUSER", "TSO", "IBMUSER", source="TEST")
    assert gen["ok"]
    val = svc.validate("IBMUSER", "TSO", gen["ticket"], consumer="TSO")
    assert val["ok"]
    rows = [r.to_flat_fields() for r in get_smf_writer(st).query(record_type=80)]
    codes = {r.get("EVENT_CODE") for r in rows}
    assert "82" in codes
    assert "81" in codes
    assert any(r.get("EVENT_NAME") == "PASSTICKET_GENERATE" for r in rows)
    assert any(r.get("EVENT_NAME") == "PASSTICKET_EVALUATE" for r in rows)


def test_passticket_replay_emits_failed_evaluate_record():
    st = GibsonState.create()
    svc = get_passticket_service(st)
    gen = svc.generate("IBMUSER", "TSO", "IBMUSER", source="TEST")
    svc.validate("IBMUSER", "TSO", gen["ticket"], consumer="TSO")
    replay = svc.validate("IBMUSER", "TSO", gen["ticket"], consumer="TSO")
    assert not replay["ok"]
    rows = [r.to_flat_fields() for r in get_smf_writer(st).query(record_type=80)]
    assert any(r.get("EVENT_CODE") == "81" and r.get("REASON_CODE") == "REPLAY" for r in rows)
