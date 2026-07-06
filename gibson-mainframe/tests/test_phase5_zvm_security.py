"""Phase 5 - z/VM minidisk LINK (z4), spool security (z5), DirMaint/RACFVM
service machines (z6) and VSWITCH + security dashboard (z7).

Each slice is a security surface: unauthorized minidisk LINK exposes data,
managing another guest's spool needs class D, driving DirMaint needs directory
authority, and defining/altering a VSWITCH needs class B.
"""
from gibson.core.state import GibsonState
from gibson.apps.zvm.zvm_session import ZvmSession, AID_ENTER
from gibson.apps.zvm.cp_directory import CpDirectory, DIRMAINT_AUTH


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
        z.handle(AID_ENTER, "")
    return z.handle(AID_ENTER, command)


# --- z4: minidisk LINK ---------------------------------------------------
def test_z4_link_exposed_disk_succeeds():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    out = _W(_cp(g, "LINK MAINT 191 391 RR"))      # MAINT 191 read_pw=ALL
    assert "LINKED AS 391 RR" in out


def test_z4_link_rw_wrong_password_denied():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    out = _W(_cp(g, "LINK MAINT 191 392 RW BADPW"))
    assert "NOT LINKED" in out


def test_z4_link_protected_disk_requires_password():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    assert "NOT LINKED" in _W(_cp(g, "LINK RACFVM 490 490 RR"))           # no pw
    assert "LINKED" in _W(_cp(g, "LINK RACFVM 490 490 RR RACFRD"))        # correct pw


def test_z4_query_links():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    _cp(g, "LINK MAINT 191 391 RR")
    assert "MAINT 191 LINKED" in _W(_cp(g, "QUERY LINKS"))


def test_z4_link_audited():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    _cp(g, "LINK RACFVM 490 490 RR")        # denied
    _cp(g, "LINK MAINT 191 391 RR")         # allowed
    evs = [str(e).upper() for e in st.audit.events]
    assert any("LINK DENIED" in e for e in evs)
    assert any("MINIDISK LINK" in e for e in evs)


# --- z5: spool -----------------------------------------------------------
def test_z5_purge_own_spool():
    st = GibsonState.create()
    g = _logon(st, "DEMO")                  # DEMO owns RDR 0101
    assert "0101 PURGED" in _W(_cp(g, "PURGE 0101"))
    assert st.cp_directory.find_spool("0101") is None


def test_z5_purge_others_spool_needs_class_d():
    st = GibsonState.create()
    g = _logon(st, "DEMO")                  # 0001 owned by MAINT
    out = _W(_cp(g, "PURGE 0001"))
    assert "NOT AUTHORIZED" in out and "CLASS D" in out
    assert st.cp_directory.find_spool("0001") is not None     # not purged


def test_z5_query_rdr():
    st = GibsonState.create()
    g = _logon(st, "MAINT")                 # MAINT owns RDR 0001, 0002
    out = _W(_cp(g, "QUERY RDR"))
    assert "SYSLOG" in out or "SERVICE" in out


# --- z6: DirMaint / RACFVM ----------------------------------------------
def test_z6_dirmaint_denied_for_general_user():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    out = _W(_cp(g, "DIRMAINT AMDISK 200 3390 10 USER"))
    assert "NOT AUTHORIZED" in out


def test_z6_dirmaint_allowed_for_maint():
    st = GibsonState.create()
    assert "MAINT" in DIRMAINT_AUTH
    m = _logon(st, "MAINT")
    out = _W(_cp(m, "DIRMAINT AMDISK 200 3390 10 USER"))
    assert "DIRECTORY UPDATED" in out or "COMPLETED" in out


def test_z6_rac_passthrough_to_racf_engine():
    st = GibsonState.create(); st.racf.load()
    m = _logon(st, "MAINT")
    out = _W(_cp(m, "RAC LISTUSER IBMUSER"))
    assert "IBMUSER" in out


# --- z7: VSWITCH + dashboard --------------------------------------------
def test_z7_define_vswitch_needs_class_b():
    st = GibsonState.create()
    g = _logon(st, "DEMO")
    assert "NOT AUTHORIZED" in _W(_cp(g, "DEFINE VSWITCH X"))
    m = _logon(st, "MAINT")
    assert "DEFINED" in _W(_cp(m, "DEFINE VSWITCH PRODSW"))


def test_z7_set_vswitch_grant():
    st = GibsonState.create()
    m = _logon(st, "MAINT")
    _cp(m, "DEFINE VSWITCH PRODSW")
    out = _W(_cp(m, "SET VSWITCH PRODSW GRANT DEMO"))
    assert "GRANT DEMO COMPLETE" in out
    assert "DEMO" in st.cp_directory.vswitches["PRODSW"]["grants"]


def test_z7_security_dashboard():
    st = GibsonState.create()
    _logon(st, "DEMO")
    m = _logon(st, "MAINT")
    out = _W(_cp(m, "QUERY SECURITY"))
    assert "SECURITY POSTURE" in out
    assert "PRIVILEGED GUESTS" in out and "MAINT(ABCDEFG)" in out
    assert "LINKABLE BY ALL" in out               # exposure surface reported


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
