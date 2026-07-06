from gibson.core.state import GibsonState
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.cbsa.cics_session import execute_omen
from gibson.core.smf.writer import get_smf_writer


def test_dvca_pin_bruteforce_emits_smf110():
    st = GibsonState.create()
    out = execute_dvca(st, "IBMUSER", "BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN")
    assert "PIN BRUTE" in out
    rows = [r.to_flat_fields() for r in get_smf_writer(st).query(record_type=110)]
    assert any(r.get("TRANSID") == "MCAD" and "PIN BRUTE" in r.get("DETAIL", "") for r in rows)


def test_cbsa_omen_pin_bruteforce_emits_smf110():
    st = GibsonState.create()
    st.config.cbpp_enabled = False
    out = execute_omen(st, "IBMUSER", "BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN")
    assert "PIN BRUTE" in out
    rows = [r.to_flat_fields() for r in get_smf_writer(st).query(record_type=110)]
    assert any(r.get("TRANSID") == "OMEN" for r in rows)
