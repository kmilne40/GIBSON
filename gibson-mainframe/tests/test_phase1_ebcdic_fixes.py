"""Phase 1 EBCDIC fixes - milestone tests (A1 DB2 route, A4 Outlist, A5 CICS).

Drives the 3270 apps through the real input-parsing path, mirroring how a live
c3270 terminal interacts, so routing and field-resolution fixes are verified.
"""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, PanelInput, KEY_TO_AID
from gibson.apps.ispf3270.ispf_session import Ispf3270Session
from gibson.apps.cics3270 import Cics3270Session


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _ispf():
    st = GibsonState.create(); st.racf.load()
    a = Ispf3270Session(st, userid="IBMUSER")
    return a, a.initial_screen()


# --- A1: L DB2 / DB2 / DSN / =12 launch DB2I from inside ISPF -------------
def test_a1_db2_aliases_launch_db2i():
    for typed in ("DB2", "L DB2", "12", "DSN"):
        a, m = _ispf()
        out = a.handle(_inbound(m, OPTION=typed))
        assert "DB2I" in _W(out), f"{typed!r} did not reach DB2I"


def test_a1_equals12_jump_launches_db2i():
    a, m = _ispf()
    out = a.handle(_inbound(m, OPTION="=12"))
    assert "DB2I" in _W(out)


# --- A4: option 8 = Outlist (not SDSF); S = SDSF -------------------------
def test_a4_option8_is_outlist_not_sdsf():
    a, m = _ispf()
    out = a.handle(_inbound(m, OPTION="8"))
    w = _W(out)
    assert "OUTLIST UTILITY" in w and "SDSF" not in w


def test_a4_option_s_still_sdsf():
    a, m = _ispf()
    out = a.handle(_inbound(m, OPTION="S"))
    assert "SDSF" in _W(out)


def _seed_held_job(st, jobname="PAYROLL", jobid="JOB00042"):
    from gibson.core.jes import Job, JobStatus, SpoolFile
    j = Job(jobid=jobid, jobname=jobname, owner="IBMUSER", jcl="//PAYROLL JOB\n",
            status=JobStatus.HELD, message_class="A", job_class="A")
    j.spool.append(SpoolFile("JESMSGLG", "$HASP373 PAYROLL STARTED\n"))
    j.spool.append(SpoolFile("SYSPRINT", "PAYROLL REPORT LINE 1\nLINE 2\n"))
    st.jes.jobs[jobid] = j
    return j


def test_a4_outlist_lists_and_displays_held_output():
    st = GibsonState.create(); st.racf.load()
    _seed_held_job(st)
    a = Ispf3270Session(st, userid="IBMUSER")
    m = a.initial_screen()
    panel = a.handle(_inbound(m, OPTION="8"))
    assert "PAYROLL" in _W(panel) and "JOB00042" in _W(panel)
    # L on the named job displays its spool in Browse
    disp = a.handle(_inbound(panel, OPTION="L", JOBNAME="PAYROLL"))
    w = _W(disp)
    assert "BROWSE" in w and "SYSPRINT" in w and "PAYROLL REPORT LINE 1" in w


def test_a4_outlist_delete_removes_job():
    st = GibsonState.create(); st.racf.load()
    _seed_held_job(st)
    a = Ispf3270Session(st, userid="IBMUSER")
    panel = a.handle(_inbound(a.initial_screen(), OPTION="8"))
    out = a.handle(_inbound(panel, OPTION="D", JOBNAME="PAYROLL"))
    assert "DELETED" in _W(out) and "JOB00042" not in st.jes.jobs


# --- A5: CICS options work over the live input path ----------------------
def _cics():
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = False
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    return cs, cs.initial_screen()


def test_a5_transid_carried_through_from_goodmorning():
    # GM is a banner with no input field, but if a transid ever arrives while
    # on GM it must be honoured, not discarded (defensive pass-through).
    cs, gm = _cics()
    pi = PanelInput(aid=0x7D, key="ENTER", fields={"TRAN": "CEMT I TASK"})
    out = cs.handle(pi)
    assert "TAS" in _W(out) or "CEMT" in _W(out)


def test_a5_operator_menu_numeric_options():
    cs, gm = _cics()
    ent = cs.handle(_inbound(gm))            # GM -> entry
    opmenu = cs.handle(_inbound(ent, TRAN="COPS"))
    assert "OPERATOR" in _W(opmenu)
    # numeric option 1 -> CEMT master terminal
    out = cs.handle(_inbound(opmenu, OPTION="1"))
    assert "CEMT" in _W(out) or "TAS" in _W(out)


def test_a5_input_found_regardless_of_field_name():
    # robustness: option/command resolves even if it lands in a non-OPTION field
    cs, gm = _cics()
    cs.handle(_inbound(gm))
    cs._screen = "ENTRY"
    pi = PanelInput(aid=0x7D, key="ENTER", fields={"ZCMD": "CEMT I TASK"})
    out = cs.handle(pi)
    assert out is not None and ("CEMT" in _W(out) or "TAS" in _W(out))


def test_a5_dvca_lab_starts_from_entry():
    cs, gm = _cics()
    ent = cs.handle(_inbound(gm))
    out = cs.handle(_inbound(ent, TRAN="DVCA"))
    assert out is not None and "DVCA" in _W(out)


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
