"""P1-P3 live-testing fixes: ISPF option 6, jump, scroll primaries, DSLIST E +
EDIT entry panel, seeded code libraries, bracket codepage fix, SDSF / dialog."""
from gibson.core.state import GibsonState
from gibson.apps.ispf3270 import Ispf3270Session
from gibson.apps.sdsf3270 import Sdsf3270Session
from gibson.apps.tso import TsoCommandProcessor
from gibson.render.panels import PanelInput


def _PI(key="ENTER", cursor=(None, None), **fields):
    return PanelInput(aid=0, key=key, fields=fields, cursor=cursor)


def _txt(scr):
    return scr.to_3270().decode("cp037", "ignore") if scr else "<<NONE>>"


def _ispf():
    st = GibsonState.create(); st.racf.load()
    st.datasets.seed_user_training("IBMUSER")
    app = Ispf3270Session(st, userid="IBMUSER")
    app.initial_screen()
    return st, app


# ---- P1-D: ISPF option 6 ----
def test_opt6_runs_and_returns_to_shell():
    st, app = _ispf()
    app.handle(_PI(OPTION="6"))
    scr = app.handle(_PI(CMD="TIME"))
    assert app._screen == "CMDOUT"            # output on its own panel
    app.handle(_PI(key="ENTER"))
    assert app._screen == "COMMAND"           # back to the shell (loops)


def test_opt6_retrieve_list_and_cursor_retrieve():
    st, app = _ispf()
    app.handle(_PI(OPTION="6"))
    for c in ("TIME", "LISTUSER IBMUSER", "UADS LIST"):
        app.handle(_PI(CMD=c)); app.handle(_PI(key="ENTER"))
    scr = app.handle(_PI(key="ENTER"))
    t = _txt(scr)
    assert "=> TIME" in t and "=> UADS LIST" in t
    time_row = [r for r, c in app._retrieve_rows.items() if c == "TIME"][0]
    scr = app.handle(_PI(key="ENTER", cursor=(time_row, 3)))
    assert "TIME" in _txt(scr).split("Place cursor")[0]


def test_opt6_f3_returns_to_primary():
    st, app = _ispf()
    app.handle(_PI(OPTION="6"))
    scr = app.handle(_PI(key="PF3"))
    assert app._screen == "PRIMARY" and scr is not None


# ---- P1-E: global jump switcher ----
def test_global_jump_switches_apps():
    from gibson.services.tn3270_server import Tn3270Session
    st = GibsonState.create(); st.racf.load(); st.datasets.seed_user_training("IBMUSER")
    s = object.__new__(Tn3270Session)
    s.state = st; s.addr = ("1.2.3.4", 0); s.current_registry = None
    s.tso_app = s.cics_app = s.db2_app = s.sdsf_app = s.ispf_app = None
    s._send_screen = lambda scr: None
    s.vtam_screen = lambda: "VTAM"

    class _App:
        userid = "IBMUSER"
    s.tso_app = _App(); s.mode = "TSOAPP"
    assert s._do_global_jump("3.4") and s.mode == "ISPFAPP" and s.ispf_app is not None
    s.sdsf_app = _App(); s.mode = "SDSFAPP"
    assert s._do_global_jump("S") and s.mode == "SDSFAPP"
    assert s._do_global_jump("X") and s.mode == "VTAM"
    assert s._do_global_jump("FOO") is False


# ---- P1-F: TOP / BOTTOM ----
def test_dslist_top_bottom():
    st, app = _ispf()
    app.handle(_PI(OPTION="3.4"))
    app.handle(_PI(DSLEVEL="SYS1"))
    start = app.dsl_scroll.top
    app.handle(_PI(COMMAND="BOTTOM"))
    assert app.dsl_scroll.top > start
    app.handle(_PI(COMMAND="TOP"))
    assert app.dsl_scroll.top == 0


# ---- P2-G/H: DSLIST E new member + EDIT entry panel ----
def test_dslist_e_creates_member_via_edit_entry_panel():
    st, app = _ispf()
    # guarantee a genuinely new member (files_root may persist across runs)
    libp = st.datasets.ds_path("IBMUSER", "IBMUSER.COBOL.LAB")
    (libp / "NEWPROG").unlink(missing_ok=True)
    app.handle(_PI(OPTION="3.4"))
    app.handle(_PI(DSLEVEL="IBMUSER.COBOL"))
    i = [n for n, r in enumerate(app.dsl_rows)
         if getattr(r, "name", "") == "IBMUSER.COBOL.LAB"][0]
    scr = app.handle(_PI(**{f"LC{i:04d}": "E", f"DSN{i:04d}": "IBMUSER.COBOL.LAB(NEWPROG)"}))
    t = _txt(scr)
    assert "EDIT Entry Panel" in t and "New member" in t and "NEWPROG" in t
    app.handle(_PI(key="ENTER"))                 # -> editor
    assert app.editor is not None
    app.editor.lines = ["       DISPLAY 'HI'."]
    app.handle(_PI(key="PF3"))                    # save+exit
    assert (libp / "NEWPROG").exists()


# ---- P2-I: seeded code libraries ----
def test_lab_code_libraries_seeded():
    st = GibsonState.create(); st.racf.load()
    st.datasets.seed_user_training("IBMUSER")
    for dsn, want in [("IBMUSER.COBOL.LAB", "HELLO"),
                      ("IBMUSER.REXX.LAB", "HELLO"),
                      ("IBMUSER.JCL.LAB", "SURRJOB")]:
        p = st.datasets.ds_path("IBMUSER", dsn)
        assert p.exists()
        members = {x.name.upper() for x in p.iterdir() if x.is_file() and not x.name.endswith(".meta")}
        assert want in members, f"{dsn} missing {want}"


# ---- P3-J: bracket codepage fix ----
def test_adduser_usage_has_no_brackets():
    st = GibsonState.create(); st.racf.load()
    t = TsoCommandProcessor(st, "IBMUSER")
    assert "[" not in t.run("ADDUSER") and "]" not in t.run("ADDUSER")
    assert "[" not in t.run("ALTUSER")
    assert "[" not in t.run("HELP ADDUSER")


# ---- P3-K: SDSF / system command extension ----
def test_sdsf_slash_opens_dialog_and_runs_command():
    st = GibsonState.create(); st.racf.load()
    sd = Sdsf3270Session(st, userid="IBMUSER"); sd.initial_screen()
    scr = sd.handle(_PI(CMD="/"))
    assert sd.mode == "DIALOG" and "System Command Extension" in _txt(scr)
    scr = sd.handle(_PI(DLGCMD="D T"))
    assert len(_txt(scr)) > 60     # a response was produced


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
