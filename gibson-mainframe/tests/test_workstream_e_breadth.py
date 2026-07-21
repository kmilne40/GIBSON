"""Workstream E breadth - remaining DB2I, CICS and SDSF options.

DB2I options 3-6 and 8 (program prep, precompile, bind/rebind/free, run,
utilities); the additional CICS supervisory transactions (CEOT/CEST/CMAC/CWTO/
CRTE/CSGM); and the broader SDSF command set (OPERLOG/ULOG/AD/AS and the
PREFIX/OWNER filters) routed through the engine.
"""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.db2i3270 import Db2i3270Session
from gibson.apps.cics3270 import Cics3270Session
from gibson.apps.sdsf3270 import Sdsf3270Session


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _noansi(s):
    assert b"\x1b" not in s.to_3270(), "ANSI leaked into 3270 datastream"


def test_db2i_all_options_wired():
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    menu = db.initial_screen()

    def run(option, **fields):
        p = db.handle(_inbound(menu, OPTION=option)); _noansi(p)
        out = db.handle(_inbound(p, **fields)); _noansi(out)
        back = db.handle(_inbound(out, key="PF3")); _noansi(back)
        assert "DB2I PRIMARY OPTION MENU" in _W(back), option
        return _W(out)

    assert "PROGRAM PREPARATION" in run("3", MEMBER="PAYROLL") and "SUBMITTED" in run("3", MEMBER="PAYROLL")
    assert "PRECOMPILE" in run("4", MEMBER="PAYROLL")
    assert "SUCCESSFUL" in run("5", NAME="PAYPLAN", ACT="BIND")
    assert "FREED" in run("5", NAME="PAYPLAN", ACT="FREE")
    assert "RC=0" in run("6", PROG="PAYROLL", PLAN="PAYPLAN")
    assert "RETURN CODE=0" in run("8", ONAME="GIBDB.EMPLOYE", UTIL="RUNSTATS")
    # an empty required field re-prompts rather than crashing
    p = db.handle(_inbound(menu, OPTION="3"))
    out = db.handle(_inbound(p))
    assert "ENTER AN INPUT MEMBER" in _W(out)


def test_cics_extra_transactions():
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = False
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    gm = cs.initial_screen()
    ent = cs.handle(_inbound(gm))
    for transid, needle in [("CEOT", "TRANSCEIVE"), ("CEST", "SUPERVISORY"),
                            ("CMAC DFHAC2001", "DFHAC2001"), ("CWTO HELLO OPS", "CONSOLE"),
                            ("CRTE SYSID=CICB", "ROUTING")]:
        out = cs.handle(_inbound(ent, TRAN=transid)); _noansi(out)
        assert needle in _W(out), transid
        ent = cs.handle(_inbound(out, key="CLEAR"))
        if ent is None or "DFHCE" in _W(ent):
            cs = Cics3270Session(st, peer_addr="203.0.113.9")
            ent = cs.handle(_inbound(cs.initial_screen()))
    # unknown transid still yields the authentic DFHAC2001
    out = cs.handle(_inbound(ent, TRAN="ZZZZ"))
    assert "DFHAC2001" in _W(out)


def test_sdsf_broad_command_set():
    st = GibsonState.create(); st.racf.load()
    sd = Sdsf3270Session(st, userid="IBMUSER")
    s = sd.initial_screen()
    # the action bar and command line render natively (in colour, no box-char junk)
    assert "DISPLAY  FILTER  VIEW" in _W(s) and "COMMAND INPUT ===>" in _W(s)
    assert "?????" not in _W(s)
    for cmd in ("ST", "DA", "O", "H", "I", "LOG", "OPERLOG", "ULOG", "AD", "AS"):
        s = sd.handle(_inbound(s, CMD=cmd))
        _noansi(s)
        assert "?????" not in _W(s)
    # a job panel exposes the PREFIX/OWNER scope line, and OWNER filtering applies
    s = sd.handle(_inbound(s, CMD="DA"))
    s = sd.handle(_inbound(s, CMD="OWNER IBMUSER"))
    assert "OWNER=IBMUSER" in _W(s)


def test_sdsf_native_render_actions_and_dialog():
    st = GibsonState.create(); st.racf.load()
    sd = Sdsf3270Session(st, userid="IBMUSER")
    m = sd.initial_screen()
    raw = m.to_3270().decode("cp037", "ignore")
    # native render: action bar + command line, and NO box-char "?????" junk
    assert "Display  Filter  View" in raw and "COMMAND INPUT ===>" in raw
    assert "?????" not in raw
    # several distinct field colours are emitted (not flat monochrome green)
    cols = {(f.colour or getattr(f, "color", None)) for f in m.fields}
    assert len([c for c in cols if c]) >= 3
    # menu rows carry NP action fields; S selects a panel
    npf = [f for f in m.fields if f.name.startswith("NP") and not f.protected]
    assert npf
    sel = sd.handle(_inbound(m, **{npf[0].name: "S"}))
    assert "SDSF" in _W(sel)
    # a panel with rows (LOG) supports the "/" System Command Extension dialog
    lg = sd.handle(_inbound(sel, CMD="LOG"))
    lnp = [f for f in lg.fields if f.name.startswith("NP") and not f.protected]
    assert lnp
    dlg = sd.handle(_inbound(lg, **{lnp[0].name: "/"}))
    assert "SYSTEM COMMAND EXTENSION" in _W(dlg)
    done = sd.handle(_inbound(dlg, DLGCMD="D A,L"))
    # the / extension now executes the operator command and shows its response
    assert "ACTIVITY DISPLAY" in _W(done) or "IEE114I" in _W(done)
    sd.handle(_inbound(done, key="PF3"))   # return from the command-response view
    # a non-select action yields an authentic message
    pmsg = sd.handle(_inbound(lg, **{lnp[0].name: "P"}))
    assert "PURGE" in _W(pmsg)


def test_ispf_primary_right_info_panel():
    from gibson.apps.ispf3270 import Ispf3270Session
    st = GibsonState.create(); st.racf.load()
    app = Ispf3270Session(st, userid="IBMUSER")
    raw = app.initial_screen().to_3270().decode("cp037", "ignore")
    for needle in ("User ID", "Time", "Terminal", "Screen", "Language",
                   "Appl ID", "TSO logon", "TSO prefix", "System ID",
                   "MVS acct", "Release"):
        assert needle in raw, needle


def test_vtam_banner_glow():
    import os
    from gibson.net.vtam_frontend import tn3270_vtam_screen
    from gibson.render.vtam_renderer import is_banner_line
    from gibson.render import colors
    for k in ("GIBSON_2023_PASSIVE", "GIBSON_HOSTNAME_GLOW", "GIBSON_BANNER_FILL", "GIBSON_HOSTNAME_PULSE"):
        os.environ.pop(k, None)
    s = tn3270_vtam_screen()
    banner = [f for f in s.fields if is_banner_line(f.text)]
    assert banner, "no hostname banner lines"
    for f in banner:
        assert getattr(f, "high_intensity", False) or getattr(f, "intensified", False)
        assert (f.colour or getattr(f, "color", None)) == colors.TURQUOISE
        assert getattr(f, "highlight", "") == "blink"  # animated pulse
    d = s.to_3270()
    assert d.startswith(bytes([0xF5, 0x42])) and d.endswith(b"\xff\xef") and b"\x1b" not in d
    os.environ["GIBSON_HOSTNAME_GLOW"] = "off"
    s2 = tn3270_vtam_screen()
    b2 = [f for f in s2.fields if is_banner_line(f.text)]
    assert all(getattr(f, "highlight", "") != "blink" for f in b2)
    os.environ.pop("GIBSON_HOSTNAME_GLOW", None)


def test_db2i_catalog_driven_functions():
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    from gibson.apps.db2 import Db2Simulator
    d = Db2Simulator(st)
    assert "PAYPLAN" in d.plans() and "PAYROLL" in d.packages()
    def to(option, **fields):
        db = Db2i3270Session(st, userid="IBMUSER")
        m = db.initial_screen()
        p = db.handle(_inbound(m, OPTION=option))
        out = db.handle(_inbound(p, **fields)) if fields else db.handle(_inbound(p))
        return _W(out), _W(p)

    # DCLGEN now reads richer ACCOUNTS columns from the catalog
    o2, p2 = to("2", OWNER="GIBSON", TABLE="ACCOUNTS")
    assert "ACCTNO" in o2 and "BALANCE" in o2
    assert "ACCOUNTS" in p2 and "EMPLOYEES" in p2
    # BIND of a catalogued plan reports REPLACED and lists the catalogue
    ob, pb = to("5", NAME="PAYPLAN", ACT="BIND")
    assert "REPLACED" in ob and "CATALOG PLANS" in ob
    assert "PAYPLAN" in pb
    # FREE of an unknown object is rejected
    db = Db2i3270Session(st, userid="IBMUSER")
    m = db.initial_screen()
    p = db.handle(_inbound(m, OPTION="5"))
    assert "NOT FOUND" in _W(db.handle(_inbound(p, NAME="NOSUCH", ACT="FREE")))
    # RUN validates the plan against the catalogue
    db = Db2i3270Session(st, userid="IBMUSER")
    m = db.initial_screen()
    p = db.handle(_inbound(m, OPTION="6"))
    assert "NOT IN CATALOG" in _W(db.handle(_inbound(p, PROG="X", PLAN="ZZZZ")))
    db = Db2i3270Session(st, userid="IBMUSER")
    m = db.initial_screen()
    p = db.handle(_inbound(m, OPTION="6"))
    assert "RC=0" in _W(db.handle(_inbound(p, PROG="PAYROLL", PLAN="PAYPLAN")))


def _cics_signed():
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = False
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    ent = cs.handle(_inbound(cs.initial_screen()))
    return st, cs, ent


def test_dvca_lab_interactive_in_ebcdic():
    st, cs, ent = _cics_signed()
    dv = cs.handle(_inbound(ent, TRAN="DVCA"))
    _noansi(dv)
    assert cs._lab == "DVCA" and "DVCA" in _W(dv)
    # PF5 -> Mel's Cargo main menu
    mm = cs.handle(_inbound(dv, key="PF5")); _noansi(mm)
    assert "MAIN MENU" in _W(mm) or "ORDER OFFICE" in _W(mm)
    # HACK ON / HACK OFF toggle through the command line
    ho = cs.handle(_inbound(mm, CMD="HACK ON")); _noansi(ho)
    assert "HACK ON" in _W(ho)
    hf = cs.handle(_inbound(ho, CMD="HACK OFF")); _noansi(hf)
    assert "HACK OFF" in _W(hf) or "NORMAL" in _W(hf)
    # PA3 secret path from a fresh start
    st2, cs2, ent2 = _cics_signed()
    dv2 = cs2.handle(_inbound(ent2, TRAN="DVCA"))
    sec = cs2.handle(_inbound(dv2, key="PA3")); _noansi(sec)
    assert "SECRET" in _W(sec)
    # PF3 on the splash quits the lab back to CICS
    st3, cs3, ent3 = _cics_signed()
    dv3 = cs3.handle(_inbound(ent3, TRAN="DVCA"))
    q = cs3.handle(_inbound(dv3, key="PF3"))
    assert cs3._lab is None and cs3._screen == "ENTRY"
    # CLEAR also exits the lab
    st4, cs4, ent4 = _cics_signed()
    dv4 = cs4.handle(_inbound(ent4, TRAN="DVCA"))
    cs4.handle(_inbound(dv4, key="CLEAR"))
    assert cs4._lab is None


def test_dvca_uses_tn3270_security():
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = True
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    # auth on -> the session presents a sign-on screen with a password field
    # before any transaction (so DVCA is gated behind TN3270/RACF security).
    signon = cs.initial_screen()
    txt = signon.to_3270().decode("cp037", "ignore")
    assert "Password" in txt
    assert any(f.name == "PASSWORD" and not f.protected for f in signon.fields)
    assert not any(f.name == "TRAN" and not f.protected for f in signon.fields)
    # sign on with valid RACF credentials, land on the entry screen, run DVCA
    ent = cs.handle(_inbound(signon, USERID="BOB", PASSWORD="BOB"))
    assert cs._screen == "ENTRY"
    cs.handle(_inbound(ent, TRAN="DVCA"))
    assert cs._lab == "DVCA"


def test_omen_lab_starts_in_ebcdic():
    st, cs, ent = _cics_signed()
    om = cs.handle(_inbound(ent, TRAN="OMEN"))
    _noansi(om)
    assert cs._lab == "OMEN" and len(_W(om).strip()) > 0


def test_db2_dsn_command_processor():
    st = GibsonState.create(); st.racf.load()
    db = Db2i3270Session(st, userid="IBMUSER")
    m = db.initial_screen()
    assert "COMMAND PROC" in _W(m)
    d = db.handle(_inbound(m, OPTION="DSN")); _noansi(d)
    w = _W(d)
    assert "DSN SYSTEM(DB2A)" in w and "DB2 COMMAND PROCESSOR" in w and "COMMANDS:" in w
    assert "DISPLAY GROUP" in _W(db.handle(_inbound(d, CMD="HELP")))
    g = db.handle(_inbound(d, CMD="DISPLAY GROUP")); assert "GROUP" in _W(g)
    assert len(_W(db.handle(_inbound(g, CMD="SHOW DBS"))).strip()) > 0
    lo = db.handle(_inbound(g, CMD="LOGOUT")); assert db._screen == "MENU"


def test_ansi3270_renderer():
    from gibson.render.ansi3270 import render_ansi_to_screen, strip_ansi
    from gibson.render import colors
    t = colors.BLUE + "BLUE" + colors.RESET + " mid " + colors.RED + "RED" + colors.RESET
    s = render_ansi_to_screen(t)
    raw = s.to_3270()
    assert b"\x1b" not in raw
    txt = raw.decode("cp037", "ignore")
    assert "BLUE" in txt and "RED" in txt and "mid" in txt
    used = {(f.colour or getattr(f, "color", None)) for f in s.fields}
    assert colors.BLUE in used and colors.RED in used
    assert strip_ansi(t) == "BLUE mid RED"


def test_field_at_address_prefers_unprotected():
    from gibson.render import colors
    s = ScreenBuffer()
    s.extended_attributes = True
    s.put(5, 1, "PROTECTED LABEL ===>", colors.GREEN)        # protected text
    s.add_field("CMD", 5, 10, 20, colour=colors.TURQUOISE, role="command")  # overlaps it
    from gibson.net.datastream3270 import row_col_to_address
    addr = row_col_to_address(5, 12, 80)
    f = s.field_at_address(addr)
    assert f is not None and not f.protected and f.name == "CMD"


def test_sdsf_real_job_state_changes():
    st = GibsonState.create(); st.racf.load()
    sd = Sdsf3270Session(st, userid="IBMUSER")
    m = sd.initial_screen()
    s = sd.handle(_inbound(m, CMD="ST"))
    npf = [f for f in s.fields if f.name.startswith("NP") and not f.protected]
    assert npf, "demo jobs should populate the ST panel"
    held = sd.handle(_inbound(s, **{npf[0].name: "H"}))
    assert "HELD" in _W(held)
    assert any(j.status.value == "HELD" for j in st.jes.jobs.values())
    s2 = sd.handle(_inbound(held, CMD="ST"))
    npf2 = [f for f in s2.fields if f.name.startswith("NP") and not f.protected]
    before = len([j for j in st.jes.jobs.values() if j.status.value != "PURGED"])
    sd.handle(_inbound(s2, **{npf2[0].name: "P"}))
    after = len([j for j in st.jes.jobs.values() if j.status.value != "PURGED"])
    assert after == before - 1


def test_cics_cemt_fielded_colour_panels():
    st = GibsonState.create(); st.racf.load(); st.config.realistic_cics_auth = False
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    ent = cs.handle(_inbound(cs.initial_screen()))
    for q, marker in [("CEMT I FILE", "INQUIRE FILE"), ("CEMT INQUIRE PROGRAM", "INQUIRE PROGRAM"),
                      ("CEMT I TASK", "INQUIRE TASK"), ("CEMT I TRANSACTION", "INQUIRE TRANSACTION"),
                      ("CEMT I TERMINAL", "INQUIRE TERMINAL")]:
        p = cs.handle(_inbound(ent, TRAN=q))
        _noansi(p)
        assert cs._screen == "CEMT" and marker in _W(p)
        assert any(f.name.startswith("AC") and not f.protected for f in p.fields)
        cols = {(f.colour or getattr(f, "color", None)) for f in p.fields}
        assert len([c for c in cols if c]) >= 3
        ent = cs.handle(_inbound(p, key="PF3"))
    fp = cs.handle(_inbound(ent, TRAN="CEMT I FILE"))
    acf = [f for f in fp.fields if f.name.startswith("AC") and not f.protected]
    if acf and cs.cics.files:
        fname = list(cs.cics.files.keys())[0]
        cs.handle(_inbound(fp, **{acf[0].name: "DISABLE"}))
        assert "DISABLED" in (cs.cics.files[fname].status or "").upper()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all Workstream E breadth tests passed")
