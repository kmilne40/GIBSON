from gibson.render.screen3270 import ScreenBuffer


def test_no_ansi_escape_output():
    s = ScreenBuffer(); s.put(1, 1, 'READY')
    assert b'\x1b[' not in s.to_3270()
