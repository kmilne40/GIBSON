from gibson.core.state import GibsonState
from gibson.security.icsf import refresh
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.smf.writer import get_smf_writer


def test_icsf_master_key_refresh_emits_structured_record_and_views():
    st = GibsonState.create()
    out = refresh(st, "IBMUSER", "MASTERKEY")
    assert "MASTER KEY REFRESH" in out
    rows = [r.to_flat_fields() for r in get_smf_writer(st).records]
    assert any(r.get("EVENT_NAME") == "ICSF_MASTER_KEY_REFRESH" and r.get("KEY_STORE") == "CKDS" for r in rows)
    tso = TsoCommandProcessor(st, "IBMUSER")
    assert "ICSF_MASTER_KEY" in tso.run("SMF LIST ICSF") or "MASTERKEY" in tso.run("SMF LIST ICSF")
    assert "ZSECURE ICSF" in tso.run("ZSEC ICSF")
