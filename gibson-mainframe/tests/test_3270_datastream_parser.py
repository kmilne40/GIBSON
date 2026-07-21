from gibson.net.datastream3270 import *
from gibson.render.screen3270 import ScreenBuffer
from tests.helpers_3270_frames import frame_pf3, frame_pf7, frame_pf8, frame_enter_with_field, frame_enter_with_fields

def test_aid_key_bytes_parse():
    assert parse_3270_input_frame(frame_pf3()).aid == 'PF3'
    assert parse_3270_input_frame(frame_pf7()).aid == 'PF7'
    assert parse_3270_input_frame(frame_pf8()).aid == 'PF8'

def test_enter_with_ascii_and_registry_maps_to_name():
    s=ScreenBuffer(); f=s.add_field('COMMAND',3,14,20,protected=False)
    ev=parse_3270_input_frame(frame_enter_with_field(f.address,'SAVE'), s)
    assert ev.aid == 'ENTER'
    assert ev.fields_by_name['COMMAND'] == 'SAVE'
    assert ev.to_legacy_command() == 'SAVE'

def test_plain_ascii_not_misclassified():
    for raw in [b'L TSO\r\n', b'USER IBMUSER\r\n', b'L CICS\r\n', b'CEMT\r\n']:
        ev=normalise_terminal_input(raw)
        assert ev.client_mode == 'ascii'
        assert ev.fallback_used
        assert ev.to_legacy_command() in raw.decode('ascii','ignore')

def test_malformed_frame_safe():
    ev=normalise_terminal_input(b'\xf3\x00')
    assert ev is not None
