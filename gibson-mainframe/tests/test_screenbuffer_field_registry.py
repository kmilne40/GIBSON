from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import build_wcc

def test_field_registry_lookup_and_tab():
    s=ScreenBuffer(); f1=s.add_field('COMMAND',3,14,20,protected=False,tab_order=1); f2=s.add_field('SCROLL',3,70,5,protected=False,tab_order=2)
    assert s.field_name_for_address(f1.address) == 'COMMAND'
    assert s.tab_next('COMMAND').name == 'SCROLL'
    assert s.tab_previous('COMMAND').name == 'SCROLL'

def test_apply_modified_fields_and_export():
    s=ScreenBuffer(); f=s.add_field('OPTION',4,13,8,protected=False)
    assert s.apply_modified_fields({f.address:'3.4'}) == {'OPTION':'3.4'}
    assert s.export_registry()['fields'][0]['name'] == 'OPTION'

def test_wcc_keyboard_restore():
    assert build_wcc(reset_mdt=True, keyboard_restore=True) == 0x42
    data=ScreenBuffer().to_3270()
    assert data.startswith(bytes([0xf5,0x42]))
