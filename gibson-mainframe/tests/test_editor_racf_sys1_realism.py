from pathlib import Path

from gibson.apps.editor import InteractiveEditor
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult


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
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path / "f", commands_dir=tmp_path / "f" / "commands", gacf_path=tmp_path / "GACF.DB")
    cfg.ensure()
    cfg.gacf_path.write_text(
        "IBMUSER:SYS1:SPECIAL:OMVS:SYS1\n"
        "ALICE:ALICE:SPECIAL:OMVS:SYS1\n"
        "GUEST:GUEST:NONE:NOOMVS:STUDENT\n",
        encoding="utf-8",
    )
    return GibsonState.create(cfg)


def test_editor_tilde_escapes_to_command_and_tab_reaches_prefix_area():
    editor = InteractiveEditor('IBMUSER.TEST', 'LINE1\nLINE2\nLINE3', save_callback=lambda _text: None)
    editor.run(FakeKeyDriver(['~', 'L', 'C', ' ' ,'1', ' ' ,'I', '2', 'ENTER']), lambda _text: None)
    assert editor.lines[:5] == ['', '', 'LINE1', 'LINE2', 'LINE3']

    editor2 = InteractiveEditor('IBMUSER.TEST', 'ONE\nTWO\nTHREE', save_callback=lambda _text: None)
    editor2.run(FakeKeyDriver(['TAB', 'D', '2', 'ENTER']), lambda _text: None)
    assert editor2.lines == ['THREE']


def test_altuser_nospecial_and_noomvs_take_effect_immediately(tmp_path: Path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, 'IBMUSER')
    assert 'ICH01006I USERID ALICE ALTERED' in admin.run('ALTUSER ALICE NOSPECIAL NOOMVS')
    alice = TsoCommandProcessor(st, 'ALICE')
    assert 'INSUFFICIENT ACCESS' in alice.run('ADDUSER BOB PASS(TEST123)')
    assert 'does not have an OMVS segment' in alice.run("OGET '/u/alice/x' ALICE.TEST")


def test_listcat_level_and_lvl_show_seeded_sys1_and_user_prefix(tmp_path: Path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, 'IBMUSER')
    sys1 = tso.run('LISTCAT LVL(SYS1)')
    assert 'SYS1.PARMLIB' in sys1
    assert 'SYS1.PROCLIB' in sys1

    st.datasets.allocate('IBMUSER', 'IBMUSER.TEST.NEW.DATA')
    own = tso.run('LISTCAT LEVEL(IBMUSER.TEST)')
    assert 'IBMUSER.TEST.NEW.DATA' in own
    assert 'SYS1.PARMLIB.IEASYS00' not in sys1
