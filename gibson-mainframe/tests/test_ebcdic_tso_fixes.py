"""EBCDIC (port 2023 / TN3270) parity fixes.

Before this change the 3270 path executed *no* TSO commands after logon - SEND,
OMVS, CONSOLE and every other command fell through to a blank READY screen,
while the ASCII/NVT (netcat) path handled them.  These tests drive the real
``Tn3270Session.handle_tso`` text path and assert parity.
"""
from gibson.core.state import GibsonState
from gibson.services.tn3270_server import Tn3270Session
from gibson.apps.tso import TsoCommandProcessor


class _FakeConn:
    def sendall(self, d):
        pass

    def close(self):
        pass


def _session(st, user="IBMUSER", ready=True):
    s = Tn3270Session(st, _FakeConn(), ("10.0.0.9", 5000))
    s.in_3270_mode = True
    s._screens = []
    s.send = lambda data: s._screens.append(data.decode("cp037", "ignore").upper())
    if ready:
        s.userid = user
        s.tso = TsoCommandProcessor(st, user)
        s.mode = "TSO_READY"
    return s


def _last(s):
    return s._screens[-1] if s._screens else ""


def _st():
    st = GibsonState.create(); st.racf.load()
    return st


# --- generic TSO commands now execute -----------------------------------
def test_generic_tso_command_executes():
    st = _st()
    s = _session(st)
    s.handle_tso("TIME")
    out = _last(s)
    assert out and out.strip() != "READY"          # not the blank fall-through
    s._screens = []
    s.handle_tso("LISTUSER IBMUSER")
    assert "IBMUSER" in _last(s)


def test_unknown_command_still_returns_screen():
    st = _st()
    s = _session(st)
    s.handle_tso("ZZZBOGUS")
    assert _last(s)                                  # never crashes / blank-hangs


# --- SEND: queue + deliver at logon -------------------------------------
def test_send_queues_message():
    st = _st()
    s = _session(st)
    s.handle_tso("SEND 'STANDUP AT 0900' USER(IBMUSER)")
    assert "QUEUED" in _last(s) or "MESSAGE" in _last(s)


def test_send_message_delivered_at_logon():
    st = _st()
    st.racf.verify_password = lambda u, p: True
    TsoCommandProcessor(st, "IBMUSER").run("SEND 'PAYROLL RUN TONIGHT' USER(IBMUSER)")
    s = _session(st, ready=False)
    s.mode = "TSO_USER"
    s.handle_tso("IBMUSER")
    s.handle_tso("pw")
    out = _last(s)
    assert "NEW MESSAGES" in out and "PAYROLL RUN TONIGHT" in out


# --- OMVS sub-mode ------------------------------------------------------
def test_omvs_enter_run_exit():
    st = _st()
    s = _session(st)                                # IBMUSER has OMVS segment
    s.handle_tso("OMVS")
    assert s.mode == "TSO_OMVS"
    s._screens = []
    s.handle_tso("pwd")
    assert "/U/IBMUSER" in _last(s) or "/" in _last(s)
    s.handle_tso("exit")
    assert s.mode == "TSO_READY"


def test_omvs_denied_without_segment():
    st = _st()
    # create a user with no OMVS segment
    TsoCommandProcessor(st, "IBMUSER").run("ADDUSER NOOMVS PASSWORD(PW123456)")
    s = _session(st, user="NOOMVS")
    s.handle_tso("OMVS")
    assert "OMVS SEGMENT" in _last(s) and s.mode != "TSO_OMVS"


# --- CONSOLE sub-mode ---------------------------------------------------
def test_console_enter_for_special_user():
    st = _st()
    s = _session(st)                                # IBMUSER is SPECIAL
    s.handle_tso("CONSOLE")
    assert s.mode == "TSO_CONSOLE"
    s._screens = []
    s.handle_tso("D T")
    assert _last(s)
    s.handle_tso("END")
    assert s.mode == "TSO_READY"


def test_console_denied_for_non_special():
    st = _st()
    TsoCommandProcessor(st, "IBMUSER").run("ADDUSER PLAINUSR PASSWORD(PW123456)")
    s = _session(st, user="PLAINUSR")
    s.handle_tso("CONSOLE")
    assert "DENIED" in _last(s) or "INSUFFICIENT" in _last(s)
    assert s.mode != "TSO_CONSOLE"


# --- MFA prompt in the EBCDIC stream ------------------------------------
def test_mfa_requested_in_ebcdic():
    st = _st()
    st.mfa_enabled = True
    TsoCommandProcessor(st, "IBMUSER").run("ADDUSER MFAU01 PASSWORD(START123)")
    s = _session(st, ready=False)
    s.mode = "TSO_USER"
    s.handle_tso("MFAU01")
    assert "PASSWORD" in _last(s)
    s.handle_tso("START123")
    assert s.mode == "TSO_MFA" and "MFA TOKEN REQUIRED" in _last(s)


def test_ibmuser_mfa_exempt():
    st = _st()
    st.mfa_enabled = True
    st.racf.verify_password = lambda u, p: True
    s = _session(st, ready=False)
    s.mode = "TSO_USER"
    s.handle_tso("IBMUSER")
    s.handle_tso("pw")
    assert s.mode == "TSO_READY"                     # IBMUSER is MFA-exempt


# --- app hand-off commands ----------------------------------------------
def test_sdsf_command_routes_to_vtam_app():
    st = _st()
    s = _session(st)
    s.handle_tso("SDSF")
    assert s.mode in ("SDSFAPP", "VTAM")             # left TSO_READY into the app


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
