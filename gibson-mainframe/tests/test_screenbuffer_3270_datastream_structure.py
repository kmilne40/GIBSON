from gibson.render.screen3270 import ScreenBuffer


def test_screenbuffer_datastream_structure():
    s = ScreenBuffer(); s.put(1, 1, 'READY'); data = s.to_3270()
    assert data[0] == 0xF5
    assert data[1] & 0x02
    assert 0x11 in data
    assert 0x13 in data
    assert data.endswith(b'\xff\xef')
