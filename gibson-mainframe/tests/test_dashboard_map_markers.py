from types import SimpleNamespace
from gibson.services.dashboard import _fake_geo, _client_location


def test_known_public_ip_uses_offline_fixture():
    lat, lon, label = _fake_geo('82.31.240.198')
    assert (round(lat, 4), round(lon, 4)) == (51.5074, -0.1278)
    assert 'fixture' in label.lower()


def test_private_ip_maps_to_lab_location():
    lat, lon, label = _fake_geo('127.0.0.1')
    assert (round(lat, 4), round(lon, 4)) == (55.9533, -3.1883)
    assert 'Private/Lab' in label


def test_client_location_supports_recent_marker():
    loc = _client_location('IBMUSER', '82.31.240.198', False, 'CEMT', '21:15:54')
    assert loc['marker_type'] == 'recent'
    assert loc['ip'] == '82.31.240.198'
    assert loc['last_command'] == 'CEMT'
