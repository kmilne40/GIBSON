"""hack3270 fielded-CBSA (OMEN) acceptance tests.

The CBSA high-value transfer lab (transid CBTR) emits a genuine fielded 3270
screen with a hidden, protected APPROVED flag - the COBOL "trust the terminal
map" finding hack3270 targets.  Vulnerable mode trusts the client flag; --secure
recomputes approval server-side and records a RACF/SMF80 denial.
"""
from gibson.core.state import GibsonState
from gibson.apps.cics3270 import Cics3270Session
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.core.cics_region import get_cics_region


def _inbound(screen, key="ENTER", **fieldvals):
    screen.to_3270()
    frame = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for name, text in fieldvals.items():
        f = [x for x in screen.fields if x.name == name][0]
        frame += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + text.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(frame, screen_registry=screen))


def _W(s):
    return s.to_3270().decode("cp037", "ignore")


def _cbtr(state):
    cs = Cics3270Session(state, peer_addr="203.0.113.7")
    e = cs.initial_screen()
    if cs._screen != "ENTRY":
        e = cs.handle(_inbound(e))
    return cs, cs.handle(_inbound(e, TRAN="CBTR"))


def test_cbtr_emits_genuine_fields():
    st = GibsonState.create(); st.racf.load()
    _cs, scr = _cbtr(st)
    fmap = {f.name: f for f in scr.fields if f.name}
    for name in ("FROMACC", "TOACC", "AMOUNT", "MAXLIMIT", "APPROVED"):
        assert name in fmap, f"missing field {name}"
    assert fmap["APPROVED"].protected and fmap["APPROVED"].hidden
    assert fmap["MAXLIMIT"].protected
    assert not fmap["AMOUNT"].protected
    assert b"\x1b" not in scr.to_3270()


def test_cbtr_vuln_trusts_approval_flag():
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "vuln"
    cs, scr = _cbtr(st)
    out = cs.handle(_inbound(scr, AMOUNT="50000.00", APPROVED="Y"))
    txt = _W(out)
    assert "HIGH-VALUE TRANSFER" in txt and "trusted client APPROVAL" in txt


def test_cbtr_secure_recomputes_and_denies():
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "secure"
    cs, scr = _cbtr(st)
    out = cs.handle(_inbound(scr, AMOUNT="50000.00", APPROVED="Y"))
    txt = _W(out)
    assert "REJECTED" in txt and "LIMIT" in txt
    incidents = [i for i in get_cics_region(st).incidents if "TAMPER" in (i.stage or "").upper()]
    assert len(incidents) >= 1 and all(i.result == "FAILURE" for i in incidents)


def test_cbtr_secure_allows_small_transfer():
    st = GibsonState.create(); st.racf.load(); st.config.security_mode = "secure"
    cs, scr = _cbtr(st)
    out = cs.handle(_inbound(scr, AMOUNT="250.00"))
    txt = _W(out)
    assert "APPROVED WITHIN SERVER LIMIT" in txt


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} CBSA hack3270 fielded tests passed")


if __name__ == "__main__":
    _run_all()
