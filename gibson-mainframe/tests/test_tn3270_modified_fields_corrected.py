from gibson.net.datastream3270 import parse_3270_input_frame, encode_3270_address


def test_enter_with_modified_field_maps_registry():
    addr = 100
    frame = bytes([0x7D, 0x40, 0x40, 0x11]) + encode_3270_address(addr) + 'IBMUSER'.encode('cp037')
    ev = parse_3270_input_frame(frame, screen_registry={addr: 'DSNAME_LEVEL'})
    assert ev.fields_by_name['DSNAME_LEVEL'] == 'IBMUSER'
