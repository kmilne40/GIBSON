from gibson.net.datastream3270 import parse_3270_input_frame


def test_editor_pf8_not_ansi_sequence():
    ev = parse_3270_input_frame(bytes([0xF8, 0x40, 0x40]))
    assert ev.raw_aid == 0xF8
    assert '^[[19~' not in ev.raw_text
