from gibson.core.smf.m4m_smf import SCENARIOS, scenario_by_id
from gibson.core.state import GibsonState
from gibson.apps.welcome.routes import render_page


def test_all_attached_m4m_rows_have_smf_scenarios():
    assert len(SCENARIOS) == 10
    for sc in SCENARIOS:
        assert sc["attack_id"].startswith("MF-TTP")
        assert sc["expected_smf_records"]
        assert sc["zsecure_views"]
        assert sc["forensic_questions"]
        assert sc["investigation_steps"]
    assert scenario_by_id("MF-TTP05")["mitre_attack_id"] == "T1068"


def test_m4m_smf_forensics_routes_render():
    st = GibsonState.create()
    code, ctype, body = render_page("/cti/m4m/smf-forensics", st)
    assert code == 200
    assert "MF-TTP01" in body
    code, ctype, body = render_page("/cti/m4m/smf-forensics/MF-TTP10", st)
    assert code == 200
    assert "Dataset encryption" in body or "dataset encryption" in body.lower()
