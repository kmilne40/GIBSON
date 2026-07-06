"""Phase 4 - z/VM CP directory (z1), privilege classes (z2) and guest
lifecycle (z3).

The teaching crux: a general user (class G) is denied privileged CP commands
(FORCE, SHUTDOWN, ATTACH, STORE, DISPLAY) while MAINT (all classes) may issue
them, and every privileged attempt - allowed or denied - is audited.
"""
from gibson.core.state import GibsonState
from gibson.apps.zvm.zvm_session import ZvmSession, AID_ENTER
from gibson.apps.zvm.cp_directory import (
    CpDirectory, parse_cp_command, is_authorized, CP_CLASS_DESC,
)


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _logon(st, uid, pw=None):
    z = ZvmSession(st)
    if pw is None:                     # use the guest's real CP directory password
        g = st.cp_directory.get(uid)
        pw = g.password if g else "ACCESS"
    z.handle(AID_ENTER, uid)
    z.handle(AID_ENTER, pw)
    return z


def _cp(z, command):
    if z._screen == "CPQUERY":
        z.handle(AID_ENTER, "")            # return to CP read
    return z.handle(AID_ENTER, command)


# --- z1: directory state model ------------------------------------------
def test_z1_directory_seeded():
    d = CpDirectory()
    assert d.exists("MAINT") and d.exists("RACFVM") and d.exists("DIRMAINT")
    assert d.classes("MAINT") == "ABCDEFG"
    assert d.classes("GUEST") == "G"


def test_z1_logon_marks_directory():
    st = GibsonState.create()
    _logon(st, "MAINT")
    assert "MAINT" in st.cp_directory.logged_on_users()


def test_z1_unknown_user_is_class_g():
    st = GibsonState.create()
    z = _logon(st, "RANDOM01")
    assert z._classes == "G"
    assert st.cp_directory.exists("RANDOM01")


# --- z2: privilege classes ----------------------------------------------
def test_z2_parse_and_authorize():
    assert parse_cp_command("FORCE OPERATOR") == ("FORCE", "A")
    assert parse_cp_command("SET SECUSER OP") == ("SET SECUSER", "A")
    assert parse_cp_command("QUERY NAMES")[1] == ""        # universal
    assert is_authorized("ABCDEFG", "A") is True
    assert is_authorized("G", "A") is False
    assert is_authorized("G", "") is True                  # universal always ok


def test_z2_general_user_denied_privileged():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    for cmd, cls in [("FORCE OPERATOR", "A"), ("SHUTDOWN", "A"),
                     ("ATTACH 590 TO MAINT", "B"), ("STORE 0 FF", "C"),
                     ("DISPLAY 0", "E")]:
        out = _W(_cp(g, cmd))
        assert "NOT AUTHORIZED" in out and f"CLASS {cls}" in out, cmd


def test_z2_universal_commands_allowed_for_class_g():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    assert "CMS LEVEL" in _W(_cp(g, "IPL CMS"))


def test_z2_query_privclass_report():
    st = GibsonState.create()
    g = _logon(st, "MAINT")
    out = _W(_cp(g, "QUERY PRIVCLASS"))
    assert "PRIVCLASSES FOR MAINT: ABCDEFG" in out
    # each held class is described
    for c in "ABCDEFG":
        assert CP_CLASS_DESC[c].split(" -")[0].upper() in out


def test_z2_maint_authorized():
    st = GibsonState.create()
    m = _logon(st, "MAINT")
    assert "SHUTDOWN STARTED" in _W(_cp(m, "SHUTDOWN"))


# --- z3: lifecycle -------------------------------------------------------
def test_z3_force_logs_target_off():
    st = GibsonState.create()
    _logon(st, "OPERATOR")
    m = _logon(st, "MAINT")
    out = _W(_cp(m, "FORCE OPERATOR"))
    assert "FORCED OFF" in out
    assert not st.cp_directory.get("OPERATOR").logged_on


def test_z3_force_not_logged_on():
    st = GibsonState.create()
    m = _logon(st, "MAINT")
    assert "NOT LOGGED ON" in _W(_cp(m, "FORCE TCPIP"))


def test_z3_query_names_reflects_directory():
    st = GibsonState.create()
    _logon(st, "DEMO")
    m = _logon(st, "MAINT")
    out = _W(_cp(m, "QUERY NAMES"))
    assert "MAINT" in out and "DEMO" in out


# --- audit ---------------------------------------------------------------
def test_privileged_attempts_audited():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    _cp(g, "FORCE OPERATOR")                 # denied
    _logon(st, "OPERATOR")
    m = _logon(st, "MAINT")
    _cp(m, "FORCE OPERATOR")                 # allowed
    evs = [str(e).upper() for e in st.audit.events]
    assert any("DENIED" in e for e in evs), "denial not audited"
    assert any("FORCE" in e for e in evs), "force not audited"


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
