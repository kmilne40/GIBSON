"""hack3270 fielded-DVCA acceptance tests (engine / datastream level).

These verify the two halves that make the real gglessner/hack3270 MITM proxy
work against Gibson's DVCA over TN3270:

  Half A - DVCA emits genuine fielded 3270 datastreams whose BMS fields carry
           their true attribute bytes (protected / non-display / numeric), so
           hack3270 has real hidden/protected fields to reveal and unlock.
  Half B - in vulnerable mode the server TRUSTS client-supplied values for those
           protected/hidden fields (the actual server-side-trust vulnerability);
           in --secure mode it revalidates, rejects the tamper and records a
           RACF/SMF80 denial.

We cannot drive a live x3270 + hack3270 here, so we assert at the datastream and
engine level: build the inbound frame exactly as an unlocked terminal would.
"""
from gibson.core.state import GibsonState
from gibson.apps.cics3270 import Cics3270Session
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.core.cics_region import get_cics_region


def _inbound(screen, key="ENTER", **fieldvals):
    # A real client always has the rendered datastream; populate field addresses.
    screen.to_3270()
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore")


def _to_order(state):
    cs = Cics3270Session(state, peer_addr="203.0.113.9")
    e = cs.initial_screen()
    if cs._screen != "ENTRY":
        e = cs.handle(_inbound(e))
    sp = cs.handle(_inbound(e, TRAN="DVCA"))
    mm = cs.handle(_inbound(sp, key="PF5"))
    return cs, cs.handle(_inbound(mm, CMD="MCOR"))


def test_dvca_emits_genuine_fielded_screen():
    """Half A: the order screen carries real protected/hidden/numeric fields."""
    st = GibsonState.create(); st.racf.load()
    _cs, order = _to_order(st)
    fmap = {f.name: f for f in order.fields if f.name}
    for name in ("ITEM", "PRICE", "SHIP", "CANBUY", "BUY"):
        assert name in fmap, f"missing genuine field {name}"
    # PRICE / SHIP are protected & numeric (hack3270 must unlock them).
    assert fmap["PRICE"].protected and fmap["PRICE"].numeric
    assert fmap["SHIP"].protected
    # CANBUY is the hidden, protected authorisation flag.
    assert fmap["CANBUY"].protected and fmap["CANBUY"].hidden
    # ITEM / BUY are genuine unprotected input fields.
    assert not fmap["ITEM"].protected and not fmap["BUY"].protected
    # And no ANSI escapes leak into the 3270 datastream.
    assert b"\x1b" not in order.to_3270()


def test_dvca_menu_has_hidden_admin_option():
    """The main menu carries the hidden OPT99 admin field hack3270 can reveal."""
    st = GibsonState.create(); st.racf.load()
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    e = cs.initial_screen()
    if cs._screen != "ENTRY":
        e = cs.handle(_inbound(e))
    sp = cs.handle(_inbound(e, TRAN="DVCA"))
    mm = cs.handle(_inbound(sp, key="PF5"))
    fmap = {f.name: f for f in mm.fields if f.name}
    assert "OPT99" in fmap and fmap["OPT99"].protected and fmap["OPT99"].hidden


def test_vuln_server_trusts_tampered_fields():
    """Half B vuln: a tampered PRICE/CANBUY is trusted - the restricted item is
    bought for the attacker-chosen price (the classic DVCA finding)."""
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "vuln"
    cs, order = _to_order(st)
    # Item 00005 is a restricted (canbuy=N) item; unlock+tamper to buy it for 0.01.
    out = cs.handle(_inbound(order, ITEM="00005", CANBUY="Y", PRICE="0.01", BUY="Y"))
    txt = _W(out)
    assert "ORDER ACCEPTED" in txt and "00005" in txt and "0.01" in txt


def test_secure_rejects_tamper_and_records_racf_denial():
    """Half B secure: the same tamper is revalidated server-side, blocked, and a
    RACF/SMF80 denial is recorded for both tampered fields."""
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "secure"
    cs, order = _to_order(st)
    out = cs.handle(_inbound(order, ITEM="00005", CANBUY="Y", PRICE="0.01", BUY="Y"))
    txt = _W(out)
    assert "BLOCKED" in txt or "REJECT" in txt or "VALIDATION" in txt
    assert "0.01" not in txt  # tampered price never used
    incidents = [i for i in get_cics_region(st).incidents if "TAMPER" in (i.stage or "").upper()]
    assert len(incidents) >= 1
    assert all(i.result == "FAILURE" for i in incidents)
    assert {i.resource for i in incidents} >= {"PRICE", "CANBUY"}


def test_legitimate_order_still_works_in_secure_mode():
    """A normal (canbuy=Y) purchase with no tampering succeeds in secure mode at
    the catalogue price - the control blocks tampering, not normal use."""
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "secure"
    cs, order = _to_order(st)
    out = cs.handle(_inbound(order, ITEM="00001", BUY="Y"))
    txt = _W(out)
    assert "ORDER ACCEPTED" in txt and "00001" in txt and "3.99" in txt


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} hack3270 fielded DVCA tests passed")


if __name__ == "__main__":
    _run_all()
