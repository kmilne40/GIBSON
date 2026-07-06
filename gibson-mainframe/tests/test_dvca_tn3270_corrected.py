from gibson.net.datastream3270 import parse_3270_input_frame, encode_3270_address


def test_dvca_select_field_maps():
    addr = 160
    frame = bytes([0x7D, 0x40, 0x40, 0x11]) + encode_3270_address(addr) + b'1'
    ev = parse_3270_input_frame(frame, screen_registry={addr: 'SELECT'})
    assert ev.command_text == '1'
