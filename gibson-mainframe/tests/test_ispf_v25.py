from pathlib import Path
import tempfile
import re

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.ispf import IspfApp
from gibson.apps.editor import EditorModel, EditorCommandProcessor


def build_state():
    root = Path(tempfile.mkdtemp())
    state = GibsonState.create(GibsonConfig(sim_root=root, files_root=root/'f', gacf_path=root/'GACF.DB'))
    state.racf.adduser('IBMUSER', 'pass', special=True, omvs=True)
    state.datasets.allocate('IBMUSER', 'IBMUSER.TEST.DATA')
    state.datasets.write('IBMUSER', 'IBMUSER.TEST.DATA', 'LINE1\nLINE2')
    return state


def test_primary_menu_has_required_options():
    state = build_state()
    app = IspfApp(state, 'IBMUSER', lambda c: 'OK')
    panel = app.primary_menu()
    assert '3' in panel and 'Utilities' in panel
    assert '6' in panel and 'Command' in panel
    assert '8' in panel and 'Outlist' in panel
    assert 'S' in panel and 'SDSF' in panel


def test_utility_menu_has_32_33_34_38():
    state = build_state()
    app = IspfApp(state, 'IBMUSER', lambda c: 'OK')
    panel = app.utility_menu()
    assert '2' in panel and 'Data Set' in panel
    assert '3' in panel and 'Move/Copy' in panel
    assert '4' in panel and 'Dslist' in panel
    assert '8' in panel and 'Outlist' in panel


def test_option6_routes_to_tso():
    state = build_state()
    app = IspfApp(state, 'IBMUSER', lambda c: 'OUT:' + c)
    assert app.option6_command('LISTUSER IBMUSER') == 'OUT:LISTUSER IBMUSER'


def test_editor_primary_and_line_commands():
    model = EditorModel(['AAA', 'BBB'])
    proc = EditorCommandProcessor(model)
    assert proc.execute('FIND BBB').startswith('CHARS')
    assert proc.execute('CHANGE BBB CCC') == '1 OCCURRENCE(S) CHANGED'
    assert model.lines[1] == 'CCC'
    assert 'INSERTED' in proc.execute('I 1 2')
    assert len(model.lines) == 4
    assert 'DELETED' in proc.execute('D 1 1')


def test_primary_menu_stays_within_79_columns():
    state = build_state()
    app = IspfApp(state, 'IBMUSER', lambda c: 'OK')
    ansi = re.compile(r'\x1b\[[0-9;]*m')
    for line in app.primary_menu().splitlines():
        assert len(ansi.sub('', line)) <= 79
