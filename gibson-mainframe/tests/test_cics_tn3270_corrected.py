from gibson.net.datastream3270 import parse_3270_input_frame


def test_cics_pf5_is_aid_not_text():
    ev = parse_3270_input_frame(bytes([0xF5, 0x40, 0x40]))
    assert ev.raw_aid == 0xF5
    assert ev.command_text == ''
