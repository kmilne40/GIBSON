from gibson.render.screen3270 import ScreenBuffer


def test_screenbuffer_uses_cp037_text():
    s = ScreenBuffer(); s.put(1, 1, 'GIBSON')
    data = s.to_3270()
    assert 'GIBSON'.encode('cp037') in data
    assert b'GIBSON' not in data
