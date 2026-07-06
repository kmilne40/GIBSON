"""nmap NSE / service-detection compatibility for Gibson's real listeners.

Gibson is a z/OS security-teaching simulator. These tests pin the SERVER-SIDE
responses that let students drive the standard, public nmap mainframe scripts
(tso-enum, tso-brute, vtam-enum by Soldier of Fortran) and `nmap -sV` against
the safe simulator and get the same verdicts a real z/OS would produce.

Verified at the string/byte/screen level (no live nmap/socket here); the user
performs real-tool acceptance.
"""
import re
import types

from gibson.core.state import GibsonState
from gibson.net.fingerprints import ftp_greeting
from gibson.services import tn3270_server as T
from gibson.apps.tso3270 import Tso3270App
from gibson.render.panels import PanelInput


def _pi(**fields):
    return PanelInput(aid=0, key="ENTER", fields=fields)


def _decode(screen):
    return screen.to_3270().decode("cp037", "ignore")


def _new_session():
    """A Tn3270Session wired to a capture buffer, already in 3270 mode."""
    sent = bytearray()

    class FakeConn:
        def sendall(self, b):
            sent.extend(b)

        def send(self, b):
            sent.extend(b)
            return len(b)

    s = T.Tn3270Session.__new__(T.Tn3270Session)
    s.conn = FakeConn()
    s.negotiated_once = False
    s.in_3270_mode = True
    s.addr = ("9.9.9.9", 12345)
    s.terminal_type = "IBM-3278-2-E"
    s.tn3270e_device_type = "IBM-3278-2-E"
    s.state = GibsonState.create()
    s.state.racf.load()
    s.mode = "VTAM"
    s.current_screen = None
    s.send = types.MethodType(lambda self, b: self.conn.sendall(b), s)
    return s, sent


# ---------------------------------------------------------------- FTP -sV

def test_ftp_banner_matches_nmap_os390_signature():
    """nmap: match ftp m/^220-([-.\\w]+) IBM FTP.*(V\\d+R\\d+)/ -> IBM OS/390 ftpd."""
    banner = ftp_greeting("GIBSON")
    m = re.search(r"^220-([-.\w]+) IBM FTP.*(V\d+R\d+)", banner)
    assert m, f"FTP banner does not match nmap OS/390 signature: {banner!r}"
    assert m.group(2) == "V2R5", m.group(2)
    # nmap would render: p|IBM OS/390 ftpd| v/$2/  => "IBM OS/390 ftpd V2R5"


# ------------------------------------------------------- TN3270 (TN3270E)

def test_negotiate_offers_tn3270e_then_classic():
    """Opening telnet burst must contain IAC DO TN3270E (FF FD 28) so
    `nmap -sV` reports '(TN3270E)', while classic options remain on offer."""
    s, sent = _new_session()
    s.negotiate()
    burst = bytes(sent)
    assert b"\xff\xfd\x28" in burst, burst.hex(" ")          # IAC DO TN3270E
    assert burst[:3] == b"\xff\xfd\x28", burst.hex(" ")      # first, for strict match
    # classic TN3270 still offered for the fallback path the enum scripts use
    assert b"\xff\xfb\x00" in burst  # WILL BINARY
    assert b"\xff\xfd\x19" in burst  # DO EOR
    assert b"\xff\xfd\x18" in burst  # DO TERMINAL-TYPE


# --------------------------------------------------------- tso-enum verdicts

def _tso_login_screen(userid):
    """Drive the TSO/E LOGON panel like nmap tso-enum (userid only, no pw)."""
    st = GibsonState.create()
    st.racf.load()
    app = Tso3270App(st, peer_addr="9.9.9.9")
    app.initial_screen()
    return _decode(app.handle(_pi(USERID=userid, PASSWORD="")))


def test_tso_enum_valid_user_shows_tso_e_logon():
    text = _tso_login_screen("IBMUSER")  # seeded RACF user
    assert "TSO/E LOGON" in text
    assert "not authorized to use TSO" not in text
    # nmap verdict: not-invalid + TSO/E LOGON present -> "Valid User ID"


def test_tso_enum_invalid_user_shows_not_authorized():
    text = _tso_login_screen("NOTREAL")
    # exact literal nmap tso-enum/tso-brute matches (case-sensitive)
    assert "not authorized to use TSO" in text
    assert "IKJ56420I" in text
    # nmap checks invalid BEFORE valid, so panel may also show TSO/E LOGON


def test_tso_enum_unknown_user_not_password_prompted():
    """tso-enum's tso_test probes 'notreal'; if the host replies
    IKJ56476I ENTER PASSWORD it concludes enumeration is DISABLED.
    Gibson must keep enumeration possible (no premature password prompt)."""
    text = _tso_login_screen("NOTREAL")
    assert "IKJ56476I" not in text
    assert "ENTER PASSWORD" not in text


# --------------------------------------------------------- vtam-enum

def test_ibmtest_returns_ibmecho():
    """vtam-enum's vtam_test confirms VTAM via the IBMTEST echo."""
    s, _ = _new_session()
    s.handle_vtam("IBMTEST")
    text = _decode(s.current_screen)
    assert "IBMECHO ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" in text


def test_invalid_applid_is_vtam_error_not_invalid_userid():
    """Invalid applid must read as a VTAM session failure and must NOT contain
    'INVALID USERID' (which makes vtam_test decide it's TSO, not VTAM)."""
    s, _ = _new_session()
    s.handle_vtam("LOGON APPLID(FAKE)")
    text = _decode(s.current_screen)
    assert "INVALID USERID" not in text
    assert ("UNABLE TO ESTABLISH SESSION" in text) or ("NOT FOUND" in text)


def test_valid_applid_tso_changes_screen_to_logon_panel():
    """A valid applid (TSO) must produce a big screen change (the TSO/E LOGON
    panel) so vtam-enum's screen-diff marks it valid."""
    s, _ = _new_session()
    s.handle_vtam("LOGON APPLID(TSO)")
    text = _decode(s.current_screen)
    assert "TSO/E LOGON" in text


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        t()
        print(f"  ok  {t.__name__}")
        passed += 1
    print(f"all {passed} tests passed")
