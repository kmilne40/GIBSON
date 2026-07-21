from gibson.core.terminal_compat import (
    compact_vtam_screen,
    detect_terminal_profile,
    normalize_crlf,
    screen_lines_fit,
)


def test_guacamole_80x24_banner_no_wrap():
    text = compact_vtam_screen(ip_address="192.168.0.204", port=41194)
    assert "GIBSON MAINFRAME SIMULATOR" in text
    assert "LOGON using L TSO, L CICS or L DB2." in text
    assert "Logon Type:" in text
    assert screen_lines_fit(text, 80)


def test_guacamole_line_endings_crlf():
    out = normalize_crlf("READY\nLISTCAT\r\nIBMUSER.JCL.LAB\rREADY")
    assert "\r\n" in out
    assert "\r\r\n" not in out
    assert "\n" not in out.replace("\r\n", "")


def test_guacamole_profile_disables_duplicate_echo():
    prof = detect_terminal_profile(("172.18.0.4", 41194))
    assert prof.is_guacamole
    assert prof.cols == 80
    assert prof.rows == 24
    assert prof.echo_input is False
    assert prof.crlf is True


def test_raw_telnet_profile_preserved():
    prof = detect_terminal_profile(("192.168.0.50", 41194))
    assert prof.name == "RAW"
    assert prof.echo_input is True
    assert prof.crlf is False


def test_wide_banner_only_for_wide_terminal_policy():
    guac = detect_terminal_profile(("172.18.0.4", 1), cols=80, rows=24)
    raw = detect_terminal_profile(("192.168.0.50", 1), cols=132, rows=24)
    assert guac.cols < 120
    assert raw.cols >= 120


def test_guacamole_ready_prompt_alignment_sample():
    output = normalize_crlf("READY\nLISTCAT\nIBMUSER.JCL.LAB      PO FB LRECL=80\nREADY\n")
    lines = output.replace("\r\n", "\n").splitlines()
    assert lines[0] == "READY"
    assert lines[1] == "LISTCAT"
    assert lines[2].startswith("IBMUSER.JCL.LAB")
    assert "LLIISSTTCCAATT" not in output
