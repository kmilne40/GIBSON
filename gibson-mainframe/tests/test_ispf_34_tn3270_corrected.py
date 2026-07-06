from gibson.net.datastream3270 import parse_3270_input_frame


def test_ispf_pf3_not_ansi_text():
    ev = parse_3270_input_frame(bytes([0xF3, 0x40, 0x40]))
    assert ev.source == 'tn3270'
    assert ev.raw_text == ''
