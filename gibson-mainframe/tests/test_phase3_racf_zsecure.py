"""Phase 3 - RACF administration panels (R) and zSecure menu (M).

The panels are a front end over the existing RACF/TSO engine, so they emit the
same RACF command output and SMF type-80 records as the command path.  Tests
drive through the real input-parsing path and assert SMF parity (B4).
"""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270.ispf_session import Ispf3270Session
from gibson.apps.tso import TsoCommandProcessor


def _inbound(s, key="ENTER", **fv):
    fr = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for n, t in fv.items():
        f = [x for x in s.fields if x.name == n][0]
        fr += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + t.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(fr, screen_registry=s))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _racf():
    st = GibsonState.create(); st.racf.load()
    a = Ispf3270Session(st, userid="IBMUSER")
    return st, a, a.handle(_inbound(a.initial_screen(), OPTION="R"))


def _view(a, racf_menu, opt):
    return a.handle(_inbound(racf_menu, OPTION=opt))


# --- B1: RACF menu + user administration --------------------------------
def test_b1_racf_menu_reached():
    _st, _a, r = _racf()
    assert "RACF - SERVICES OPTION MENU" in _W(r)


def test_b1_user_list_and_add():
    st, a, r = _racf()
    u = _view(a, r, "4")
    assert "USER PROFILE ADMINISTRATION" in _W(u)
    out = a.handle(_inbound(u, OPTION="L", USERID="IBMUSER"))
    assert "IBMUSER" in _W(out)
    out = a.handle(_inbound(u, OPTION="A", USERID="NEWU01", PASSWORD="PW123456"))
    assert st.racf.exists("NEWU01")


def test_b1_user_revoke_resume_delete():
    st, a, r = _racf()
    u = _view(a, r, "4")
    a.handle(_inbound(u, OPTION="A", USERID="VICTIM1", PASSWORD="PW123456"))
    a.handle(_inbound(u, OPTION="R", USERID="VICTIM1"))         # revoke
    assert st.racf.get("VICTIM1").revoked
    a.handle(_inbound(u, OPTION="E", USERID="VICTIM1"))         # resume
    assert not st.racf.get("VICTIM1").revoked
    a.handle(_inbound(u, OPTION="D", USERID="VICTIM1"))         # delete
    assert not st.racf.exists("VICTIM1")


# --- B2: group / dataset / general-resource profiles --------------------
def test_b2_group_admin():
    st, a, r = _racf()
    g = _view(a, r, "3")
    assert "GROUP PROFILE" in _W(g)
    a.handle(_inbound(g, OPTION="A", GROUP="NEWGRP"))
    out = a.handle(_inbound(g, OPTION="L", GROUP="NEWGRP"))
    assert "NEWGRP" in _W(out)


def test_b2_dataset_profile_panel():
    _st, a, r = _racf()
    d = _view(a, r, "1")
    assert "DATA SET PROFILE" in _W(d)
    out = a.handle(_inbound(d, OPTION="A", PROFILE="IBMUSER.SECRET.**", UACC="NONE"))
    assert "COMMAND ===> ADDSD" in _W(out)


def test_b2_general_resource_panel():
    _st, a, r = _racf()
    gr = _view(a, r, "2")
    assert "GENERAL RESOURCE" in _W(gr)
    out = a.handle(_inbound(gr, OPTION="A", CLASS="FACILITY", PROFILE="BPX.SUPERUSER", UACC="NONE"))
    assert "COMMAND ===> RDEFINE FACILITY" in _W(out)


# --- B3: SETROPTS + search + zSecure ------------------------------------
def test_b3_setropts_report():
    _st, a, r = _racf()
    out = _view(a, r, "5")
    assert "SETROPTS" in _W(out)


def test_b3_search():
    _st, a, r = _racf()
    sr = _view(a, r, "S")
    assert "RACF SEARCH" in _W(sr)
    out = a.handle(_inbound(sr, OPTION="L", CLASS="USER"))
    assert "COMMAND ===> SEARCH CLASS(USER)" in _W(out)


def test_b3_zsecure_menu_and_reports():
    st = GibsonState.create(); st.racf.load()
    a = Ispf3270Session(st, userid="IBMUSER")
    mm = a.handle(_inbound(a.initial_screen(), OPTION="M"))
    assert "ZSECURE" in _W(mm)
    for opt, needle in [("1", "PRIVILEGE"), ("2", "SETROPTS"), ("5", "EVENTS")]:
        out = a.handle(_inbound(mm, OPTION=opt))
        assert f"ZSEC {needle}" in _W(out) or needle in _W(out), opt


# --- B4: SMF parity (panel path == command path) ------------------------
def _audit_strings(st):
    return [str(e) for e in getattr(st.audit, "events", [])]


def test_b4_panel_adduser_emits_smf_like_command():
    # panel path - delete-first so ADDUSER genuinely creates (states share an
    # on-disk RACF DB, so use distinct userids per path)
    stp = GibsonState.create(); stp.racf.load()
    ap = Ispf3270Session(stp, userid="IBMUSER")
    rp = ap.handle(_inbound(ap.initial_screen(), OPTION="R"))
    up = ap.handle(_inbound(rp, OPTION="4"))
    ap.handle(_inbound(up, OPTION="D", USERID="PNLADD"))       # clear any leftover
    before = len(getattr(stp.audit, "events", []))
    ap.handle(_inbound(up, OPTION="A", USERID="PNLADD", PASSWORD="PW123456"))
    panel_events = _audit_strings(stp)[before:]
    assert any("ADDUSER" in e and "PNLADD" in e for e in panel_events), panel_events

    # command path on a fresh state, distinct userid
    stc = GibsonState.create(); stc.racf.load()
    tp = TsoCommandProcessor(stc, "IBMUSER")
    tp.run("DELUSER CMDADD")
    before_c = len(getattr(stc.audit, "events", []))
    tp.run("ADDUSER CMDADD PASSWORD(PW123456)")
    cmd_events = _audit_strings(stc)[before_c:]
    assert any("ADDUSER" in e and "CMDADD" in e for e in cmd_events), cmd_events


def test_b4_panel_revoke_audited():
    st = GibsonState.create(); st.racf.load()
    a = Ispf3270Session(st, userid="IBMUSER")
    r = a.handle(_inbound(a.initial_screen(), OPTION="R"))
    u = a.handle(_inbound(r, OPTION="4"))
    a.handle(_inbound(u, OPTION="A", USERID="REVTEST", PASSWORD="PW123456"))
    before = len(getattr(st.audit, "events", []))
    a.handle(_inbound(u, OPTION="R", USERID="REVTEST"))
    after = _audit_strings(st)[before:]
    assert any("ALTUSER" in e or "REVOKE" in e for e in after), after


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
