from gibson.net.datastream3270 import parse_3270_input_frame


def test_pf3_pf5_pf7_pf8_are_aid_events():
    for aid in (0xF3, 0xF5, 0xF7, 0xF8, 0x6B):
        ev = parse_3270_input_frame(bytes([aid, 0x40, 0x40]))
        assert ev.is_aid
        assert ev.raw_aid == aid
        assert '^[' not in ev.raw_text
