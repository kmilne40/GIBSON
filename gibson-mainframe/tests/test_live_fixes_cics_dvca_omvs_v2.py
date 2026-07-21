"""Live-testing punch list v2: CICS operator menu, DVCA, OMVS, TSO *** paging,
RACF menu realism and model-aware screen height.

All defensive/teaching-simulator behaviour. Verified at the engine/datastream
level (no live nmap/c3270 here).
"""
from gibson.core.state import GibsonState
from gibson.apps.cics3270.cics_session import Cics3270Session
from gibson.apps.ispf3270 import IspfSplitManager
from gibson.apps.omvs import OmvsShellSession
from gibson.apps.tso3270 import Tso3270App
from gibson.apps.tso3270.tso_session import rows_for_terminal
from gibson.render.panels import PanelInput


def PI(key="ENTER", **f):
    return PanelInput(aid=0, key=key, fields=f)


def _text(scr):
    return " ".join(scr.to_3270().decode("cp037", "ignore").split()) if scr else ""


def _st():
    st = GibsonState.create(); st.racf.load()
    return st


# ---------------------------------------------------------- CICS opmenu

def _cics_at_opmenu(st):
    s = Cics3270Session(st, peer_addr="9.9.9.9")
    s.initial_screen()
    s.handle(PI(TRAN="COPS"))
    return s


def test_cics_panels_emit_real_field_attributes():
    """build_fielded_panel must emit SFE field attributes (extended_attributes)
    so a real terminal sees the OPTION field as a modifiable field."""
    st = _st()
    s = _cics_at_opmenu(st)
    scr = st and Cics3270Session(st).cics.build_fielded_panel("CICS_OPERATOR_MAIN")
    assert scr.extended_attributes is True
    opt = [f for f in scr.fields if f.name == "OPTION"][0]
    assert not opt.protected
    # data position (attr+1) resolves back to OPTION
    assert scr.field_name_for_address(opt.address + 1) == "OPTION"


def test_cics_opmenu_options_dispatch():
    st = _st()
    expect = {"1": "CEMT", "5": "RUN", "9": "RUN", "10": "LAB", "11": "LAB"}
    for opt, scr_state in expect.items():
        s = _cics_at_opmenu(st)
        s.handle(PI(OPTION=opt))
        assert s._screen == scr_state, (opt, s._screen)


# ---------------------------------------------------------------- DVCA

def test_dvca_enter_advances_splash_then_selection_and_command():
    st = _st()
    s = _cics_at_opmenu(st)
    s.handle(PI(OPTION="10"))                 # enter DVCA lab
    assert s._dvca_screen() == "MCGM"
    s.handle(PI(key="ENTER"))                 # ENTER advances splash -> menu
    assert s._dvca_screen() == "MCMM"
    s.handle(PI(SELECT="1"))                  # numeric selection
    assert s._dvca_screen() == "MCOR"
    s.handle(PI(key="PF5"))                   # back to menu
    out = s.handle(PI(SELECT="HACK ON"))      # command typed in SELECT
    assert "INVALID SELECTION" not in _text(out).upper()
    assert "HACK ON" in _text(out).upper()


def test_dvca_screen_registers_unprotected_select_field():
    st = _st()
    s = _cics_at_opmenu(st)
    s.handle(PI(OPTION="10"))
    scr = s.handle(PI(key="PF5"))             # MCMM
    sel = [f for f in scr.fields if f.name == "SELECT"]
    assert sel and not sel[0].protected
    assert scr.extended_attributes is True
    assert scr.field_name_for_address(sel[0].address + 1) == "SELECT"


# ---------------------------------------------------------------- OMVS

def test_omvs_msfconsole_is_a_repl_submode():
    st = _st()
    sh = OmvsShellSession(st, "IBMUSER", mode="OMVS3270")
    banner = sh.execute("msfconsole")
    assert "Metasploit" in banner
    assert sh.shell_prompt().startswith("msf6")
    assert "Matching Modules" in sh.execute("search tomcat")
    assert sh.execute("exit") == ""          # leaves REPL
    assert sh.msf is None
    assert sh.shell_prompt().endswith("$")


def test_omvs_clear_returns_sentinel_not_ansi():
    st = _st()
    sh = OmvsShellSession(st, "IBMUSER", mode="OMVS3270")
    assert sh.execute("clear") == "__CLEAR__"   # never raw \x1b[2J -> Ý2JÝH
    # regular commands still work afterwards
    assert "/u/ibmuser" in sh.execute("pwd")


def test_omvs_msfconsole_dash_x_still_one_shot():
    st = _st()
    sh = OmvsShellSession(st, "IBMUSER", mode="OMVS3270")
    out = sh.execute("msfconsole -x 'search tomcat'")
    assert sh.msf is None          # did NOT enter the REPL
    assert "Matching Modules" in out


# ------------------------------------------------------------ TSO *** paging

def _ready(st, rows=24):
    app = Tso3270App(st, peer_addr="9.9.9.9", rows=rows)
    app.initial_screen()
    app.handle(PI(USERID="IBMUSER", PASSWORD="SYS1"))
    return app


def test_tso_long_output_pages_with_three_stars():
    st = _st()
    app = _ready(st)
    out = app.handle(PI(CMD="LU *"))
    assert app._more is True
    assert "***" in out.to_3270().decode("cp037", "ignore")
    # ENTER advances; eventually lands on READY
    guard = 0
    while app._more and guard < 60:
        out = app.handle(PI(key="ENTER")); guard += 1
    assert app._more is False
    assert "READY" in _text(out)


def test_tso_short_output_does_not_page():
    st = _st()
    app = _ready(st)
    app.handle(PI(CMD="TIME"))
    assert app._more is False


# --------------------------------------------------- model-aware screen height

def test_terminal_model_to_rows():
    assert rows_for_terminal("IBM-3278-2") == 24
    assert rows_for_terminal("IBM-3278-3") == 32
    assert rows_for_terminal("IBM-3279-4-E") == 43
    assert rows_for_terminal("IBM-3278-5") == 27
    assert rows_for_terminal("IBM-DYNAMIC") == 24
    assert rows_for_terminal("") == 24


def test_tso_ready_panel_honours_model_height():
    st = _st()
    app = _ready(st, rows=32)
    out = app.handle(PI(CMD="TIME"))
    assert out.rows == 32
    assert app._pf_row == 32 and app._out_rows == 29
    # PF-key legend present on the last row
    assert "PF3=Logoff" in out.to_3270().decode("cp037", "ignore")


def test_large_screen_uses_ewa_and_command_field_is_reachable():
    """Regression: a Model 4 (43-row) READY screen must be sent with Erase/Write
    Alternate (0x7E) and expose an unprotected, correctly-addressed command
    field. With plain Erase/Write the field sat beyond the 24-row default buffer
    and the whole screen read as protected (no usable command line)."""
    from gibson.net.datastream3270 import (encode_3270_address, decode_3270_address,
                                           parse_3270_input_frame)
    from gibson.render.panels import panel_input_from_event
    st = _st()
    app = _ready(st, rows=43)
    scr = app.handle(PI(CMD="TIME"))
    ds = scr.to_3270()
    assert ds[0] == 0x7E, "43-row screen must use Erase/Write Alternate"
    cmd = [f for f in scr.fields if f.name == "CMD"][0]
    assert cmd.row == 42 and not cmd.protected
    # the command field address must round-trip (12-bit addressing up to 4095)
    assert decode_3270_address(*encode_3270_address(cmd.address)) == cmd.address
    # and a real typed command parses back from that address
    pkt = (bytes([0x7D]) + encode_3270_address(cmd.address) + bytes([0x11])
           + encode_3270_address(cmd.address) + "LISTC".encode("cp037"))
    pi = panel_input_from_event(parse_3270_input_frame(pkt, screen_registry=scr))
    assert pi.stripped("CMD") == "LISTC"


def test_address_encoding_covers_all_models():
    from gibson.net.datastream3270 import encode_3270_address, decode_3270_address
    for addr in (0, 1919, 1920, 2480, 3360, 3439, 3563, 4095):
        assert decode_3270_address(*encode_3270_address(addr)) == addr, addr


# ---------------------------------------------- SDSF-from-TSO ANSI corruption

def test_sdsf_from_tso_renders_without_ansi_corruption():
    """SDSF at the TSO READY prompt now *launches* the full-screen SDSF app
    instead of dumping a static, ANSI-laden transcript.  The rendered 3270
    screen must still be free of cp037-mangled escapes (Ý / 2J / ..m)."""
    st = _st()
    app = _ready(st)
    out = app.handle(PI(CMD="SDSF"))
    assert app.sdsf is not None          # full-screen SDSF session started
    raw = out.to_3270().decode("cp037", "ignore")
    assert "\x1b" not in raw and "2J" not in raw and "34m" not in raw
    assert "\u00dd" not in raw          # the cp037 '[' bracket glyph
    clean = " ".join(raw.split())
    assert "Display" in clean and "Filter" in clean   # SDSF action bar


def test_strip_ansi_handles_clear_and_box_glyphs():
    from gibson.render.ansi3270 import strip_ansi
    assert strip_ansi("\x1b[2J\x1b[Hhi\x1b[34mthere\x1b[0m") == "hithere"
    assert strip_ansi("\u2500" * 4) == "----"
    assert strip_ansi("a\u2502b") == "a|b"


# -------------------------------------- CICS transactions after menu navigation

def _cics(st):
    s = Cics3270Session(st, peer_addr="9.9.9.9")
    s.initial_screen(); s.handle(PI(TRAN="COPS"))
    return s


def test_cics_transaction_runs_after_submenu_navigation():
    """Navigating CECI sets the legacy panel_state; a freshly-typed transaction
    (CSMT) must not be trapped as an INVALID menu selection."""
    st = _st()
    s = _cics(st)
    s.handle(PI(OPTION="3"))                       # CECI -> panel_state=CECI_MAIN
    assert s.cics.panel_state == "CECI_MAIN"
    out = s.handle(PI(CMD="CSMT"))                  # fresh transaction
    t = _text(out).upper()
    assert "INVALID SELECTION" not in t and "CICS LOG" in t
    assert s.cics.panel_state == ""                # reset for the fresh transaction


def test_cics_submenu_option_still_navigates():
    """Numeric/keyword sub-options must still work inside a menu (panel_state
    preserved)."""
    st = _st()
    s = _cics(st)
    s.handle(PI(OPTION="3"))                        # CECI menu
    out = s.handle(PI(CMD="1"))                     # CECI sub-option
    assert "INVALID SELECTION" not in _text(out).upper()
    assert s.cics.panel_state == "CECI_MAIN"


# --------------------------------------------- DVCA hack3270 field bounding

def test_dvca_input_fields_are_bounded():
    """The DVCA fielded panel must bound its unprotected input fields so they do
    not balloon to the next attribute (the hack3270 'lots of yellow')."""
    import gibson.net.datastream3270 as D
    st = _st()
    s = _cics(st)
    s.handle(PI(OPTION="10")); scr = s.handle(PI(key="PF5"))   # DVCA MCMM
    assert scr.bound_input_fields is True
    ds = scr.to_3270()
    # walk the datastream, measuring the gap each unprotected field spans until
    # the next attribute - that is the modifiable region the terminal shows.
    i, addr, cur, spans = 2, 0, None, []
    while i < len(ds) - 2:
        b = ds[i]
        if b == 0x11:
            addr = D.decode_3270_address(ds[i + 1], ds[i + 2]); i += 3; continue
        if b == 0x29:
            attr = ds[i + 3]; prot = bool(attr & 0x20)
            if cur is not None and not cur[1]:
                spans.append(addr - cur[0])
            cur = (addr, prot); i += 2 + ds[i + 1] * 2; continue
        if b == 0x1d:
            i += 2; continue
        i += 1
    # every unprotected field is now bounded to roughly its declared width
    assert spans and max(spans) <= 30, spans


def test_dvca_hack3270_still_injects_protected_field():
    """Bounding the input fields must not disturb the protected CANBUY/PRICE/SHIP
    fields the hack3270 attack targets."""
    st = _st()
    s = _cics(st)
    s.handle(PI(OPTION="10")); s.handle(PI(key="PF5"))
    scr = s.handle(PI(SELECT="1"))                 # MCOR order screen
    canbuy = [f for f in scr.fields if f.name == "CANBUY"]
    assert canbuy and canbuy[0].protected and canbuy[0].hidden


# --------------------------------------------------------- L DB2 -> DSN

def test_l_db2_distinguishes_dsn_from_db2i_menu():
    from gibson.apps.db2i3270 import Db2i3270Session
    st = _st()
    d = Db2i3270Session(st, peer_addr="9.9.9.9")
    dsn = _text(d._enter_dsn()).upper()
    menu = _text(d.initial_screen()).upper()
    assert "DSN7100I" in dsn or "COMMAND PROCESSOR" in dsn
    assert "DISPLAY GROUP" in dsn
    assert "DB2I PRIMARY OPTION" in menu


# ----------------------------- DVCA purchase override: hack3270 vs command

class _Ev:
    def __init__(self, fields, aid="ENTER"):
        self.fields_by_name = fields; self.aid = aid


def _dvca_buy(st, user, *, event=None, command=""):
    from gibson.apps.dvca.cics_session import execute_dvca
    from gibson.apps.dvca.store import get_dvca_store
    execute_dvca(st, user, command="MCOR")
    execute_dvca(st, user, command=command, event=event)
    store = get_dvca_store(st)
    sess = store.session(st.dvca_cics_sessions.get(user.upper()))
    buys = [e for e in store.events if e.action == "BUY"]
    return sess.last_message, (buys[-1] if buys else None)


def test_dvca_hack3270_wire_injection_is_primary_override():
    """Injecting Y into the protected CANBUY field over the wire (real hack3270)
    overrides the purchase block and is logged as a field injection."""
    st = _st()
    msg, log = _dvca_buy(st, "HACKW",
                         event=_Ev({"ITEM": "00005", "CANBUY": "Y", "PRICE": "0.01", "BUY": "Y"}))
    assert "ORDER ACCEPTED" in msg and "00005" in msg and "hack3270" in msg.lower()
    assert log.result == "OK" and log.scenario == "FIELD_INJECTION_BYPASS"
    assert "via=hack3270" in log.payload


def test_dvca_canbuy_command_is_secondary_override():
    """The CANBUY=Y command still works but is logged distinctly so it is not
    conflated with a genuine field injection."""
    st = _st()
    msg, log = _dvca_buy(st, "CMDW", command="ITEM=00005 CANBUY=Y PRICE=0.01 BUY=Y")
    assert "ORDER ACCEPTED" in msg and "command" in msg.lower()
    assert log.scenario == "HACK_COMMAND_BYPASS" and "via=command" in log.payload


def test_dvca_correct_field_wrong_response_blocks():
    """The correct field with the wrong response (CANBUY=N) does NOT override."""
    st = _st()
    msg, log = _dvca_buy(st, "BLKW",
                         event=_Ev({"ITEM": "00005", "CANBUY": "N", "BUY": "Y"}))
    assert "BLOCKED" in msg.upper() and log.result == "DENIED"


def test_dvca_legitimate_purchase_not_flagged_as_bypass():
    """A genuine office-supply purchase is not labelled as any kind of bypass."""
    st = _st()
    msg, log = _dvca_buy(st, "LEGW", event=_Ev({"ITEM": "00001", "BUY": "Y"}))
    assert "ORDER ACCEPTED" in msg and "BYPASS" not in (log.scenario or "")
    assert log.scenario == "OFFICE_SUPPLY_PURCHASE"


# ------------------------------------------------------- RACF menu realism

def test_racf_services_option_menu_is_authentic():
    st = _st()
    m = IspfSplitManager(st, peer_addr="9.9.9.9", userid="IBMUSER")
    m.initial_screen()
    scr = m.handle(PI(OPTION="R"))
    t = _text(scr)
    assert "RACF - SERVICES OPTION MENU" in t
    assert "SELECT ONE OF THE FOLLOWING" in t
    for needle in ("DATA SET PROFILES", "GENERAL RESOURCE PROFILES",
                   "GROUP PROFILES", "USER PROFILES", "SYSTEM OPTIONS",
                   "REMOTE SHARING FACILITY", "DIGITAL CERTIFICATES"):
        assert needle in t, needle


def test_racf_menu_authentic_option_routing():
    st = _st()
    expect = {
        "1": "Data Set Profile", "2": "General Resource",
        "3": "Group Profile", "4": "User Profile",
        "5": "SETROPTS",
    }
    for opt, needle in expect.items():
        m = IspfSplitManager(st, peer_addr="9.9.9.9", userid="IBMUSER")
        m.initial_screen(); m.handle(PI(OPTION="R"))
        scr = m.handle(PI(OPTION=opt))
        assert needle.upper() in _text(scr).upper(), (opt, needle)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        t(); print(f"  ok  {t.__name__}"); passed += 1
    print(f"all {passed} tests passed")
