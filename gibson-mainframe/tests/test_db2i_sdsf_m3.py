"""M3 - DB2I (menu + SPUFI + DB2 commands) and SDSF (ST/LOG + scroll), 3270."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.db2i3270 import Db2i3270Session
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


# ------------------------------------------------------------------ DB2I
def test_db2i_menu_and_spufi_runs_sql():
    st = GibsonState.create(); st.racf.load()
    d = Db2i3270Session(st, peer_addr="203.0.113.9")
    menu = d.initial_screen()
    assert "DB2I PRIMARY OPTION MENU" in _W(menu) and "SPUFI" in _W(menu)
    _noansi(menu)
    spufi = d.handle(_inbound(menu, OPTION="1"))
    assert any(f.name == "SQL01" for f in spufi.fields)
    out = d.handle(_inbound(spufi, SQL01="SELECT * FROM SYSIBM.SYSTABLES"))
    _noansi(out)
    assert "SQL" in _W(out)


def test_db2i_commands_and_exit():
    st = GibsonState.create(); st.racf.load()
    d = Db2i3270Session(st, peer_addr="203.0.113.9")
    menu = d.initial_screen()
    cmd = d.handle(_inbound(menu, OPTION="7"))
    assert any(f.name == "CMD" for f in cmd.fields)
    res = d.handle(_inbound(cmd, CMD="-DISPLAY GROUP"))
    _noansi(res)
    assert "GROUP" in _W(res)
    menu2 = d.handle(_inbound(cmd, key="PF3"))
    assert d.handle(_inbound(menu2, OPTION="X")) is None


# ------------------------------------------------------------------ SDSF
def test_sdsf_main_st_log_and_scroll_no_ansi():
    st = GibsonState.create(); st.racf.load()
    s = Sdsf3270Session(st, peer_addr="203.0.113.9")
    main = s.initial_screen()
    assert "SDSF" in _W(main) and any(f.name == "CMD" for f in main.fields)
    _noansi(main)
    stp = s.handle(_inbound(main, CMD="ST"))
    _noansi(stp)
    logp = s.handle(_inbound(stp, CMD="LOG"))
    _noansi(logp)
    scrolled = s.handle(_inbound(logp, key="PF8"))
    _noansi(scrolled)


def test_sdsf_pf3_back_then_exit():
    st = GibsonState.create(); st.racf.load()
    s = Sdsf3270Session(st, peer_addr="203.0.113.9")
    main = s.initial_screen()
    stp = s.handle(_inbound(main, CMD="ST"))
    back = s.handle(_inbound(stp, key="PF3"))
    assert back is not None
    assert s.handle(_inbound(back, key="PF3")) is None


# --------------------------------------------------------------- wiring
def test_l_db2_and_l_sdsf_route_into_panel_apps():
    import socket
    st = GibsonState.create(); st.racf.load()
    from gibson.services.tn3270_server import Tn3270Session
    for applid, attr, word in (("L DB2", "db2_app", "DB2I PRIMARY"), ("L SDSF", "sdsf_app", "SDSF")):
        srv, _cli = socket.socketpair()
        sess = Tn3270Session(st, srv, ("203.0.113.7", 1))
        sess.in_3270_mode = True
        sess.current_registry = sess.vtam_screen()
        sess.handle_vtam(applid)
        assert getattr(sess, attr) is not None
        assert word in _W(sess.current_screen)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all M3 tests passed")
