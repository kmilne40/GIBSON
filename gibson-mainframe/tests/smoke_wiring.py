from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor

state = GibsonState.create()
assert state.racf.users, "no users loaded"
tso = TsoCommandProcessor(state, "IBMUSER")
assert "USER=IBMUSER" in tso.run("LISTUSER IBMUSER")
assert "SUBMITTED" in tso.run("SUBMIT TEST")
assert state.jes.list_jobs(), "job not added to JES"
assert "SDSF" in tso.run("SDSF")
print("smoke_wiring: OK")
