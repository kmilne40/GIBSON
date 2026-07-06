from gibson.core.state import GibsonState
from gibson.core.security.racf_authorization import check_access, permit
from gibson.apps.racf_admin import get_racf_store


def test_racf_authorization_deny_permit_and_smf80():
    state = GibsonState.create()
    st = get_racf_store(state)
    st.profiles.setdefault("DATASET", {})["FIBS.SECRET.DATA"] = {"UACC": "NONE", "PERMITS": {}}
    deny = check_access(state, "TRAINEE", "DATASET", "FIBS.SECRET.DATA", "UPDATE")
    assert not deny.allowed
    assert "ICH408I" in deny.message
    permit(state, "FIBS.SECRET.DATA", "DATASET", "TRAINEE", "UPDATE")
    allow = check_access(state, "TRAINEE", "DATASET", "FIBS.SECRET.DATA", "UPDATE")
    assert allow.allowed
    assert allow.effective == "UPDATE"
    assert any(e.component == "SMF80" for e in state.audit.events)
