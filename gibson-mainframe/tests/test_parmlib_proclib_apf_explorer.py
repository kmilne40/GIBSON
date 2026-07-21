from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def test_parmlib_proclib_apf_explorer():
    state = GibsonState.create()
    tso = TsoCommandProcessor(state, "IBMUSER")
    assert "SYS1.PARMLIB EXPLORER" in tso.run("PARMLIB")
    assert "SMFPRM00" in tso.run("PARMLIB")
    # The explorer now serves the live, seeded SYS1.PARMLIB(SMFPRM00) member
    # (not a hardcoded stub), so assert against its real content.
    smfprm = tso.run("PARMLIB SMFPRM00")
    assert "RECORDING(DATASET)" in smfprm
    assert "SYS1.MANA" in smfprm
    assert "TYPE(7,30,80,83,92,100,101,102,110,118,119,123)" in smfprm
    assert "SYS1.PROCLIB EXPLORER" in tso.run("PROCLIB")
    assert "APF AUTHORIZED LIBRARY LIST" in tso.run("APF")
    assert "LINKLIST" in tso.run("LINKLIST")
