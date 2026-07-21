from pathlib import Path

from gibson.net.vtam_frontend import ascii_vtam_screen, tn3270_vtam_screen, load_vtam_text


def _strip_telnet_iac(frame: bytes) -> bytes:
    out = bytearray(); i = 0
    while i < len(frame):
        b = frame[i]
        if b != 0xFF:
            out.append(b); i += 1; continue
        if i + 1 >= len(frame): break
        cmd = frame[i + 1]
        if cmd == 0xFF:
            out.append(0xFF); i += 2; continue
        if cmd == 0xEF:
            break
        if cmd in (0xFB, 0xFC, 0xFD, 0xFE):
            i += 3; continue
        if cmd == 0xFA:
            end = frame.find(b"\xff\xf0", i + 2)
            i = len(frame) if end == -1 else end + 2
            continue
        i += 2
    return bytes(out)


def test_vtam_source_file_is_packaged_and_authoritative():
    packaged = Path("gibson/screens/vtam.txt")
    assert packaged.exists()
    text = packaged.read_text(encoding="utf-8", errors="replace")
    assert "GIBSON PRODUCTION LPAR" in text
    assert "UNAUTHORIZED USE OF THE SYSTEM IS PROHIBITED UNDER SCOTTISH LAW." in text
    assert "LOGON using L TSO, L CICS or L DB2." in text
    assert "Logon Type:" in text


def test_ascii_vtam_screen_preserves_uploaded_text():
    text = load_vtam_text()
    rendered = ascii_vtam_screen(text)
    assert "GIBSON PRODUCTION LPAR" in rendered
    assert "####" in rendered
    assert "▇" not in rendered
    assert rendered.endswith("\n")


def test_tn3270_vtam_screen_is_eor_framed_and_contains_prompt():
    screen = tn3270_vtam_screen()
    data = screen.to_3270()
    assert data.startswith(bytes([0xF5, 0x42]))
    assert data.endswith(b"\xff\xef")
    assert b"\x29" in data
    assert b"\x42\xf1" in data
    assert b"\x42\xf2" in data
    assert b"\x42\xf4" in data
    decoded = _strip_telnet_iac(data).decode("cp037", errors="ignore")
    assert "GIBSON PRODUCTION LPAR" in decoded
    assert "Logon Type:" in decoded
