"""M4 - ISPF core in 3270: menu, jump, Settings/Command, 3.4 DSLIST, members, Browse."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270 import Ispf3270Session
from gibson.apps.tso3270 import Tso3270App


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


def _ispf():
    st = GibsonState.create(); st.racf.load()
    return st, Ispf3270Session(st, peer_addr="203.0.113.10", userid="IBMUSER")


def test_primary_menu_jump_and_pf3():
    st, app = _ispf()
    pm = app.initial_screen()
    assert "PRIMARY OPTION MENU" in _W(pm)
    _noansi(pm)
    se = app.handle(_inbound(pm, OPTION="=0"))
    assert "SETTINGS" in _W(se)
    back = app.handle(_inbound(se, key="PF3"))
    assert "PRIMARY OPTION MENU" in _W(back)


def test_command_option_runs_tso():
    st, app = _ispf()
    pm = app.initial_screen()
    cp = app.handle(_inbound(pm, OPTION="6"))
    assert any(f.name == "CMD" for f in cp.fields)
    cr = app.handle(_inbound(cp, CMD="TIME"))
    _noansi(cr)
    assert "READY" in _W(cr)


def test_dslist_browse_and_members():
    st, app = _ispf()
    pm = app.initial_screen()
    de = app.handle(_inbound(pm, OPTION="3.4"))
    assert "DATA SET LIST" in _W(de)
    dl = app.handle(_inbound(de, DSLEVEL="IBMUSER"))
    _noansi(dl)
    assert "DSLIST" in _W(dl)
    rows = app.dsl_rows
    ps_idx = [i for i, r in enumerate(rows) if r.org == "PS"][0]
    po_idx = [i for i, r in enumerate(rows) if r.org == "PO"][0]
    br = app.handle(_inbound(dl, **{f"LC{ps_idx:04d}": "B"}))
    _noansi(br)
    assert "BROWSE" in _W(br)
    found = app.handle(_inbound(br, COMMAND="FIND PIN"))
    _noansi(found)
    app.handle(_inbound(found, key="PF3"))  # back to dslist
    mem = app.handle(_inbound(dl, **{f"LC{po_idx:04d}": "M"}))
    _noansi(mem)
    assert "MEMBER LIST" in _W(mem)
    if app.mem_names:
        mb = app.handle(_inbound(mem, **{"LC0000": "B"}))
        _noansi(mb)
        assert "BROWSE" in _W(mb)


def test_ispf_launches_from_tso_ready_and_returns():
    st = GibsonState.create(); st.racf.load()
    app = Tso3270App(st, peer_addr="203.0.113.10")
    logon = app.initial_screen()
    ready = app.handle(_inbound(logon, USERID="BOB", PASSWORD="BOB"))
    assert "READY" in _W(ready)
    ispf = app.handle(_inbound(ready, CMD="ISPF"))
    assert "PRIMARY OPTION MENU" in _W(ispf)
    back = app.handle(_inbound(ispf, key="PF3"))
    assert "READY" in _W(back) and "PRIMARY OPTION MENU" not in _W(back)


def test_l_ispf_routes_into_panel_app():
    import socket
    st = GibsonState.create(); st.racf.load()
    from gibson.services.tn3270_server import Tn3270Session
    srv, _cli = socket.socketpair()
    sess = Tn3270Session(st, srv, ("203.0.113.7", 1))
    sess.in_3270_mode = True
    sess.current_registry = sess.vtam_screen()
    sess.handle_vtam("L ISPF")
    assert sess.mode == "ISPFAPP" and sess.ispf_app is not None
    assert "PRIMARY OPTION MENU" in _W(sess.current_screen)


def test_primary_menu_has_full_option_set():
    st, app = _ispf()
    pm = app.initial_screen()
    txt = _W(pm)
    for token in ("8", "S", "12", "R", "M", "OUTLIST", "SDSF", "DB2", "RACF", "MANAGEMENT"):
        assert token in txt, f"menu missing {token}"


def test_menu_launches_sdsf_and_db2i():
    st, app = _ispf()
    pm = app.initial_screen()
    sd = app.handle(_inbound(pm, OPTION="S"))
    _noansi(sd)
    assert "SDSF" in _W(sd) or "DISPLAY" in _W(sd)
    back = sd
    for _ in range(6):
        back = app.handle(_inbound(back, key="PF3"))
        if back is not None and "PRIMARY OPTION MENU" in _W(back):
            break
    assert back is not None and "PRIMARY OPTION MENU" in _W(back)
    db = app.handle(_inbound(back, OPTION="12"))
    _noansi(db)
    assert "DB2" in _W(db)


def test_cursor_lands_on_writable_position():
    st, app = _ispf()
    pm = app.initial_screen()
    opt = [f for f in pm.fields if f.name == "OPTION"][0]
    cr, cc = pm._effective_cursor()
    assert (cr, cc) == (opt.row, opt.col + 1), "cursor on protected attribute byte"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all M4 tests passed")
