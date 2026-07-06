"""M2 - CICS in authentic EBCDIC 3270: good-morning, CESN/CESF, CEMT, op menu."""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.cics3270 import Cics3270Session


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


def _nondisplay(ds):
    i = 0
    while i < len(ds) - 1:
        if ds[i] == 0x29:
            n = ds[i + 1]; j = i + 2
            for _ in range(n):
                if j + 1 < len(ds) and ds[j] == 0xC0 and (ds[j + 1] & 0x0C) == 0x0C:
                    return True
                j += 2
            i = j
        else:
            i += 1
    return False


def test_cics_goodmorning_and_entry_no_ansi():
    st = GibsonState.create()
    app = Cics3270Session(st, peer_addr="203.0.113.8")
    gm = app.initial_screen()
    assert "WELCOME TO CICS" in _W(gm)
    assert b"\x1b" not in gm.to_3270()
    entry = app.handle(_inbound(gm))
    assert any(f.name == "TRAN" for f in entry.fields)


def test_cics_cesn_password_nondisplay_and_validation():
    st = GibsonState.create(); st.racf.load()
    assert st.racf.verify_password("BOB", "BOB")
    app = Cics3270Session(st, peer_addr="203.0.113.8")
    entry = app.handle(_inbound(app.initial_screen()))
    cesn = app.handle(_inbound(entry, TRAN="CESN"))
    assert "SIGNON" in _W(cesn) and _nondisplay(cesn.to_3270())
    bad = app.handle(_inbound(cesn, USERID="BOB", PASSWORD="NOPE"))
    assert "DFHCE3520" in _W(bad)
    ok = app.handle(_inbound(bad, USERID="BOB", PASSWORD="BOB"))
    assert "DFHCE3549" in _W(ok)


def test_cics_cemt_and_operator_menu_and_unknown():
    st = GibsonState.create(); st.racf.load()
    app = Cics3270Session(st, peer_addr="203.0.113.8")
    entry = app.handle(_inbound(app.initial_screen()))
    run = app.handle(_inbound(entry, TRAN="CEMT INQUIRE TASK"))
    assert "INQUIRE TASK" in _W(run) and "STATUS" in _W(run)
    entry2 = app.handle(_inbound(run, key="CLEAR"))
    opm = app.handle(_inbound(entry2, TRAN="COPS"))
    assert any(f.name == "OPTION" for f in opm.fields)
    opr = app.handle(_inbound(opm, OPTION="1"))
    # Operator-menu option 1 (CEMT INQUIRE TASK) renders as a fielded CEMT panel,
    # consistent with typing the inquiry on the entry screen.
    assert "INQUIRE TASK" in _W(opr)
    entry3 = app.handle(_inbound(opr, key="CLEAR"))
    unk = app.handle(_inbound(entry3, TRAN="ZZZZ"))
    assert "DFHAC2001" in _W(unk)


def test_cics_pf3_returns_to_vtam():
    st = GibsonState.create()
    app = Cics3270Session(st, peer_addr="203.0.113.8")
    entry = app.handle(_inbound(app.initial_screen()))
    assert app.handle(_inbound(entry, key="PF3")) is None


def test_l_cics_routes_into_panel_app():
    import socket
    st = GibsonState.create()
    srv, _cli = socket.socketpair()
    from gibson.services.tn3270_server import Tn3270Session
    sess = Tn3270Session(st, srv, ("203.0.113.7", 1))
    sess.in_3270_mode = True
    sess.current_registry = sess.vtam_screen()
    sess.handle_vtam("L CICS")
    assert sess.mode == "CICSAPP" and sess.cics_app is not None
    assert "WELCOME TO CICS" in _W(sess.current_screen)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all M2 tests passed")
