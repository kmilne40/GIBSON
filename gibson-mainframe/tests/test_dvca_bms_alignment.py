from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.dvca.store import get_dvca_store
from gibson.apps.dvca.screen_model import screen_for


def _screen(name):
    st = GibsonState.create(GibsonConfig())
    store = get_dvca_store(st)
    sess = store.session(None)
    sess.screen = name
    return screen_for(sess, store)


def test_mcmenu_select_and_hidden_option_source_positions():
    scr = _screen('MCMM')
    fields = scr.field_map()
    assert fields['SELECT'].row == 20 and fields['SELECT'].col == 17 and fields['SELECT'].length == 2
    assert fields['OPT99'].hidden is True
    assert 'Hidden option 99 exists' not in scr.render()


def test_mcorder_source_derived_field_positions_and_attrs():
    scr = _screen('MCOR')
    f = scr.field_map()
    assert (f['PRICE'].row, f['PRICE'].col) == (9, 20)
    assert (f['SHIP'].row, f['SHIP'].col) == (11, 20)
    assert (f['CANBUY'].row, f['CANBUY'].col) == (15, 20)
    assert f['CANBUY'].hidden and f['CANBUY'].protected and f['CANBUY'].fset
    assert (f['BUY'].row, f['BUY'].col) == (20, 19)


def test_mcaddr_pin_source_position_and_masking():
    scr = _screen('MCAD')
    pin = scr.field_map()['PIN']
    assert (pin.row, pin.col, pin.length) == (18, 23, 4)
    assert pin.masked and pin.numeric
    assert '1337' not in scr.render()
