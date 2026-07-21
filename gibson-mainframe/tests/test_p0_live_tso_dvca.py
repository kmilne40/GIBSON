"""P0 live-path fixes: Tso3270App (OMVS/CONSOLE/SEND) + DVCA selection.

These drive the *live* TSO 3270 path (`Tso3270App`, reached from VTAM `L TSO`),
which is the path the user's c3270 session actually uses.
"""
from gibson.core.state import GibsonState
from gibson.apps.tso3270 import Tso3270App
from gibson.render.panels import PanelInput
from gibson.apps.dvca.cics_session import execute_dvca


def _PI(key="ENTER", **fields):
    return PanelInput(aid=0, key=key, fields=fields)


def _txt(scr):
    if scr is None:
        return "<<NONE>>"
    return scr.to_3270().decode("cp037", "ignore").upper()


def _logged_in_app(user="IBMUSER"):
    st = GibsonState.create(); st.racf.load()
    st.racf.verify_password = lambda u, p: True
    app = Tso3270App(st, peer_addr="1.2.3.4")
    app.initial_screen()
    app.handle(_PI(USERID=user))
    app.handle(_PI(USERID=user, PASSWORD="pw"))
    return st, app


# ---- OMVS in the live TSO path ----
def test_omvs_enters_submode_no_sentinel_leak():
    st, app = _logged_in_app()
    scr = app.handle(_PI(CMD="omvs"))
    t = _txt(scr)
    assert app._submode == "OMVS"
    assert "GIBSON-INTERACTIVE" not in t


def test_omvs_runs_and_exits():
    st, app = _logged_in_app()
    app.handle(_PI(CMD="omvs"))
    scr = app.handle(_PI(CMD="pwd"))
    assert "/" in _txt(scr)
    app.handle(_PI(CMD="exit"))
    assert app._submode is None


def test_omvs_denied_without_segment():
    st, app = _logged_in_app()
    rec = st.racf.get("IBMUSER")
    rec.omvs_segment = None                    # strip the OMVS segment
    rec.omvs = "NOOMVS"
    rec.attributes = [a for a in rec.attributes if a.upper() != "OMVS"]
    assert not rec.has_omvs
    scr = app.handle(_PI(CMD="omvs"))
    assert "OMVS SEGMENT" in _txt(scr) and app._submode is None


# ---- CONSOLE in the live TSO path ----
def test_console_enters_submode_no_leak():
    st, app = _logged_in_app()
    scr = app.handle(_PI(CMD="console"))
    assert app._submode == "CONSOLE"
    assert "GIBSON-INTERACTIVE" not in _txt(scr)


def test_console_runs_and_exits():
    st, app = _logged_in_app()
    app.handle(_PI(CMD="console"))
    scr = app.handle(_PI(CMD="D T"))
    assert len(_txt(scr)) > 40
    app.handle(_PI(CMD="END"))
    assert app._submode is None


# ---- SEND in the live TSO path ----
def test_send_now_delivers_immediately():
    st, app = _logged_in_app()
    scr = app.handle(_PI(CMD="SEND 'hello me' user(ibmuser) now"))
    t = _txt(scr)
    assert "SENT IMMEDIATELY" in t
    assert "MESSAGE FROM IBMUSER: HELLO ME" in t


def test_session_registered_on_logon():
    st, app = _logged_in_app()
    assert "IBMUSER" in st.sessions.sessions
    assert st.sessions.sessions["IBMUSER"].connected


def test_send_to_offline_user_queues():
    st, app = _logged_in_app()
    from gibson.apps.tso import TsoCommandProcessor
    TsoCommandProcessor(st, "IBMUSER").run("ADDUSER FRED PASSWORD(PW123456)")
    scr = app.handle(_PI(CMD="SEND 'ping' user(fred) logon"))
    assert "QUEUED" in _txt(scr)


# ---- DVCA selection ----
class _Ev:
    def __init__(self, aid="ENTER", **f):
        self.aid = aid
        self.fields_by_name = f


def _dvca_menu(st):
    execute_dvca(st, userid="IBMUSER", command="DVCA")
    return execute_dvca(st, userid="IBMUSER", command="MCMM")


def test_dvca_all_selections_route():
    st = GibsonState.create()
    for sel, expect in [("1", "ORDER"), ("2", "ADDRESS"), ("3", "HISTORY"), ("H", "HELP")]:
        _dvca_menu(st)
        out = execute_dvca(st, userid="IBMUSER", command="", aid="ENTER", event=_Ev(SELECT=sel)).upper()
        assert "INVALID SELECTION" not in out, f"selection {sel} rejected"
        assert expect in out, f"selection {sel} did not reach {expect}"


def test_dvca_bad_selection_still_invalid():
    st = GibsonState.create()
    _dvca_menu(st)
    out = execute_dvca(st, userid="IBMUSER", command="", aid="ENTER", event=_Ev(SELECT="7")).upper()
    assert "INVALID SELECTION" in out


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
