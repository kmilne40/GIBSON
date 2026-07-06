import re

from gibson.apps.editor import InteractiveEditor
from gibson.screens.vtam_model import VtamScreenModel
from gibson.core.state import GibsonState
from gibson.core import dvcapin
from gibson.apps.pin_bruteforce import start_pin_bruteforce, run_pin_bruteforce, MAX_PIN_ATTEMPTS
from gibson.apps.dvca.cics_session import execute_dvca
from gibson.apps.zsecure_engine import zsecure_command
from gibson.core.smf.records.type7 import data_lost

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CURSOR_RE = re.compile(r"\x1b\[(\d+);(\d+)H")


def _strip_ansi(s):
    return ANSI_RE.sub('', s)


def _last_cursor(sent):
    matches = CURSOR_RE.findall(''.join(sent))
    assert matches
    return tuple(map(int, matches[-1]))


def test_editor_screen_fits_24_rows_without_truncating_status():
    ed = InteractiveEditor('SYS1.BRODCAST', '\n'.join(f'LINE {i}' for i in range(1, 50)), mode='EDIT')
    sent=[]
    ed._draw(lambda text: sent.append(text))
    visible = _strip_ansi(sent[0]).splitlines()
    assert len(visible) == ed.SCREEN_LINES
    assert any('FOCUS=' in line for line in visible)


def test_editor_ln_paren_moves_to_correct_line_command_row():
    ed = InteractiveEditor('SYS1.BRODCAST', '\n'.join(f'LINE {i}' for i in range(1, 50)), mode='EDIT')
    ed._process_global_command('LN(2)')
    assert ed.cur_row == ed.DATA_AREA_START + 1
    assert ed.cur_col == 0
    sent=[]
    ed._draw(lambda text: sent.append(text))
    row, col = _last_cursor(sent)
    assert row == ed.cur_row + 1
    assert col == 1


def test_editor_text_paren_moves_to_correct_text_row_after_scroll():
    ed = InteractiveEditor('SYS1.BRODCAST', '\n'.join(f'LINE {i}' for i in range(1, 80)), mode='EDIT')
    ed._handle_pf_or_nav('F8')
    ed._process_global_command('TEXT(25)')
    assert ed.cur_col == ed.COMMAND_FIELD_WIDTH
    assert ed._current_line_number() == 25
    sent=[]
    ed._draw(lambda text: sent.append(text))
    row, col = _last_cursor(sent)
    assert row == ed.cur_row + 1
    assert col == ed.COMMAND_FIELD_WIDTH + 1


def test_vtam_frame_aligned_and_ascii_safe_for_rasframe():
    lines = VtamScreenModel(system_name='RASFRAME', environment='RASFRAME PRODUCTION LPAR').full_lines()
    frame = lines[:3]
    indents = [len(line) - len(line.lstrip(' ')) for line in frame]
    assert len(set(indents)) == 1
    widths = [len(line.strip()) for line in frame]
    assert len(set(widths)) == 1
    text = '\n'.join(lines)
    assert '▇' not in text
    assert 'â' not in text
    assert all(len(line) <= 132 for line in lines)


def test_dvcapin_unset_fallback_is_1337_not_1234():
    st = GibsonState.create()
    assert dvcapin.verify(st, '1337') is True
    assert dvcapin.verify(st, '1234') is False


def test_dvca_pin_uses_configured_dvcapin_and_20_attempts():
    st = GibsonState.create()
    dvcapin.set_pin(st, '2468', actor='TEST')
    st.datasets.allocate('IBMUSER', 'IBMUSER.4CHAR.PIN', org='PS')
    st.datasets.write('IBMUSER', 'IBMUSER.4CHAR.PIN', '0000\n1337\n9999\n')
    assert 'ACCESS GRANTED' in execute_dvca(st, 'IBMUSER', 'PIN 2468')
    assert 'ACCESS DENIED' in execute_dvca(st, 'IBMUSER', 'PIN 1337')
    out = execute_dvca(st, 'IBMUSER', 'BRUTE FORCE PIN DATASET=IBMUSER.4CHAR.PIN')
    assert 'OF 00020' in out
    sess = [s for s in st.pin_brute_sessions.values() if s.app == 'DVCA MCAD'][0]
    assert len(sess.candidates) == MAX_PIN_ATTEMPTS
    assert '2468' in sess.candidates


def test_pin_bruteforce_long_dataset_forces_target_into_twenty():
    st = GibsonState.create()
    dvcapin.set_pin(st, '2468', actor='TEST')
    st.datasets.allocate('IBMUSER', 'IBMUSER.LONG.PIN', org='PS')
    st.datasets.write('IBMUSER', 'IBMUSER.LONG.PIN', '\n'.join(f'{i:04d}' for i in range(100)))
    sess = start_pin_bruteforce(st, 'IBMUSER', 'DVCA MCAD', 'IBMUSER.LONG.PIN')
    assert len(sess.candidates) == 20
    assert '2468' in sess.candidates
    assert sess.candidates[-1] == '2468'


def test_zsec_smf7_routes_to_structured_smf7_view():
    st = GibsonState.create()
    data_lost(st, count_lost=5, affected_record_types='80,110')
    out = zsecure_command(st, 'IBMUSER', 'ZSEC SMF7')
    assert 'ZSECURE SMF7 SMF REVIEW' in out
    assert 'TYPE' in out
    assert '7' in out
    assert 'NO STRUCTURED SMF RECORDS AVAILABLE' not in out
