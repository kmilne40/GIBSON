from pathlib import Path

from gibson.apps.cics import CicsSimulator
from gibson.apps.editor import EditorModel, EditorCommandProcessor, InteractiveEditor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult
from gibson.apps.tso import TsoCommandProcessor


class FakeKeyDriver:
    def __init__(self, keys):
        self.keys = list(keys)

    def read_key(self):
        if not self.keys:
            return InputResult("", "EOF")
        item = self.keys.pop(0)
        if isinstance(item, tuple):
            return InputResult(item[0], item[1])
        if len(item) == 1:
            return InputResult(item, None)
        return InputResult("", item)


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / 'f', commands_dir=tmp_path / 'f' / 'commands', gacf_path=tmp_path / 'GACF.DB')
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_mcgm_terminal_supports_tilde_field_login(tmp_path):
    st = make_state(tmp_path)
    cics = CicsSimulator(st, 'IBMUSER')
    sent = []
    driver = FakeKeyDriver(list('IBMUSER') + ['~'] + list('SYS1') + ['ENTER', 'F12', 'F12'])
    cics.run_mcgm_terminal(driver, sent.append)
    rendered = ''.join(sent)
    assert 'LOGN - CUSTOMER SIGNON' in rendered
    assert 'MENU - MAIN MENU' in rendered
    assert 'SIGNED OFF FROM SIGHBERBANK' in rendered


def test_editor_command_processor_cut_paste_exclude_reset():
    model = EditorModel(['one', 'two', 'three', 'four'], recfm='FB', lrecl=80)
    proc = EditorCommandProcessor(model)
    assert proc.execute('CUT 2 3') == '2 LINE(S) CUT'
    assert model.lines == ['one', 'four']
    assert proc.execute('PASTE BEFORE 2') == '2 LINE(S) INSERTED'
    assert model.lines == ['one', 'two', 'three', 'four']
    assert proc.execute('X 2 3') == '2 LINE(S) EXCLUDED'
    assert model.excluded == {1, 2}
    assert proc.execute('RESET X') == '2 LINE(S) RESET'
    assert model.excluded == set()


def test_interactive_editor_supports_block_copy_move_and_exclude():
    editor = InteractiveEditor('IBMUSER.TEST', 'AA\nBB\nCC\nDD', save_callback=lambda text: None)
    assert editor._process_data_command('CC', 0) == 'CC BLOCK STARTED'
    assert editor._process_data_command('CC', 1) == '2 LINE(S) COPIED'
    assert editor._process_data_command('A', 3) == '2 LINE(S) INSERTED'
    assert editor.lines == ['AA', 'BB', 'CC', 'DD', 'AA', 'BB']

    editor2 = InteractiveEditor('IBMUSER.TEST', 'AA\nBB\nCC\nDD', save_callback=lambda text: None)
    assert editor2._process_data_command('XX', 1) == 'XX BLOCK STARTED'
    assert editor2._process_data_command('XX', 2) == '2 LINE(S) EXCLUDED'
    assert editor2.excluded_lines == {1, 2}
    assert editor2._process_global_command('RESET X') is None
    assert editor2.excluded_lines == set()


def test_pds_member_paths_are_supported_for_edit_flows(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, 'IBMUSER')
    member = tso.qualify_dataset_name('TESTLIB(MEMONE)')
    st.datasets.write('IBMUSER', member, 'HELLO MEMBER')
    assert st.datasets.read('IBMUSER', member) == 'HELLO MEMBER'
    lib_path = st.datasets.ds_path('IBMUSER', 'IBMUSER.TESTLIB')
    assert lib_path.is_dir()
    assert 'MEMONE' in st.datasets.read('IBMUSER', 'IBMUSER.TESTLIB')
