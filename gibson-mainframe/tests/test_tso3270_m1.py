"""Phase 0 panel toolkit + M1 TSO/E 3270 logon/READY.

Datastream-level + round-trip + integration coverage. No network needed.
"""
from gibson.core.state import GibsonState
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import (
    Panel, Label, Field, ScrollList, panel_input_from_event, aid_key, KEY_TO_AID,
)
from gibson.apps.tso3270 import Tso3270App


def _inbound(screen, key="ENTER", **fieldvals):
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    ev = parse_3270_input_frame(frame, screen_registry=screen)
    return panel_input_from_event(ev)


def _words(screen):
    return screen.to_3270().decode("cp037", "ignore").upper()


def _has_nondisplay(ds):
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


# --------------------------------------------------------------- Phase 0
def test_panel_render_is_ebcdic_no_ansi():
    p = Panel(title="DEMO", cursor="A")
    p.add(Label(3, 2, "A ===>")).add(Field("A", 3, 10, 8))
    ds = p.render().to_3270()
    assert ds[:2] == bytes([0xF5, 0x42])
    assert ds.endswith(b"\xff\xef")
    assert b"\x1b" not in ds


def test_panel_roundtrip_named_fields():
    p = Panel()
    p.add(Field("USERID", 5, 17, 8)).add(Field("SIZE", 7, 17, 6, numeric=True))
    screen = p.render()
    pi = _inbound(screen, USERID="IBMUSER", SIZE="4096")
    assert pi.key == "ENTER"
    assert pi.stripped("USERID") == "IBMUSER"
    assert pi.stripped("SIZE") == "4096"


def test_aid_map_and_scrolllist():
    assert aid_key(0xF3) == "PF3" and aid_key(0x6D) == "CLEAR" and aid_key(0x7B) == "PF11"
    sl = ScrollList([f"R{i:03d}" for i in range(40)], height=10)
    sl.page_down(); assert sl.visible()[0] == "R010"
    sl.scroll("PF7"); assert sl.visible()[0] == "R000"
    assert sl.locate("r025") and sl.visible()[0] == "R025"


# --------------------------------------------------------------- M1 TSO
def test_tso_logon_panel_password_nondisplay():
    st = GibsonState.create()
    app = Tso3270App(st, peer_addr="203.0.113.5")
    logon = app.initial_screen()
    w = _words(logon)
    assert "TSO/E LOGON" in w and "USERID" in w and "PASSWORD" in w
    ds = logon.to_3270()
    assert b"\x1b" not in ds
    assert _has_nondisplay(ds), "password must be non-display"


def test_tso_valid_logon_reaches_ready_and_runs_command():
    st = GibsonState.create(); st.racf.load()
    assert st.racf.verify_password("BOB", "BOB"), "fixture creds changed"
    app = Tso3270App(st, peer_addr="203.0.113.5")
    logon = app.initial_screen()
    ready = app.handle(_inbound(logon, USERID="BOB", PASSWORD="BOB"))
    assert ready is not None and "READY" in _words(ready)
    out = app.handle(_inbound(ready, CMD="TIME"))
    assert "READY" in _words(out)
    assert app.handle(_inbound(out, CMD="LOGOFF")) is None


def test_tso_bad_password_and_unknown_user_stay_on_logon():
    st = GibsonState.create(); st.racf.load()
    app = Tso3270App(st, peer_addr="203.0.113.5")
    logon = app.initial_screen()
    s = app.handle(_inbound(logon, USERID="BOB", PASSWORD="WRONG"))
    assert s is not None and "NOT AUTHORIZED" in _words(s)
    s2 = app.handle(_inbound(logon, USERID="NOSUCH", PASSWORD="X"))
    # Authentic z/OS wording (matches nmap tso-enum's literal "not authorized to use TSO")
    assert "NOT AUTHORIZED TO USE TSO" in _words(s2)


def test_tso_pf3_on_logon_logs_off():
    st = GibsonState.create()
    app = Tso3270App(st, peer_addr="203.0.113.5")
    logon = app.initial_screen()
    assert app.handle(_inbound(logon, key="PF3")) is None


def test_l_tso_routes_into_panel_app():
    import socket
    st = GibsonState.create(); st.racf.load()
    srv, _cli = socket.socketpair()
    from gibson.services.tn3270_server import Tn3270Session
    sess = Tn3270Session(st, srv, ("203.0.113.7", 1))
    sess.in_3270_mode = True
    sess.current_registry = sess.vtam_screen()
    sess.handle_vtam("L TSO")
    assert sess.mode == "TSOAPP" and sess.tso_app is not None
    assert "TSO/E LOGON" in _words(sess.current_screen)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all M1 tests passed")
