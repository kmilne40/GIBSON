from gibson.apps.editor import InteractiveEditor
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


def test_tilde_always_returns_to_command_field():
    editor = InteractiveEditor('IBMUSER.TEST', 'ONE\nTWO', save_callback=lambda _text: None)
    editor.run(FakeKeyDriver(['~', 'S', 'A', 'V', 'E', 'ENTER']), lambda _text: None)
    assert editor.message == 'DATA SAVED'
    assert editor.cur_row == 1


def test_ln_and_text_aliases_work_from_command_line():
    editor = InteractiveEditor('IBMUSER.TEST', 'ONE\nTWO\nTHREE', save_callback=lambda _text: None)
    editor.run(FakeKeyDriver(['~', 'L', 'N', ' ', '2', 'ENTER', 'I', 'ENTER']), lambda _text: None)
    assert editor.lines == ['ONE', '', 'TWO', 'THREE']

    editor2 = InteractiveEditor('IBMUSER.TEST', 'ONE\nTWO', save_callback=lambda _text: None)
    editor2.run(FakeKeyDriver(['~', '1', ' ', 'R', 'E', 'P', 'L', 'A', 'C', 'E', 'D', 'ENTER']), lambda _text: None)
    assert editor2.lines[0] == 'REPLACED'
