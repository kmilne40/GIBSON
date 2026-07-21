from gibson.render.screen3270 import ScreenBuffer


def test_no_ascii_payload_text():
    s = ScreenBuffer(); s.put(1, 1, 'READY')
    assert b'READY' not in s.to_3270()
