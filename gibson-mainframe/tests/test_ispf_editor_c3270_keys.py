import socket

from gibson.render.input import SocketInputDriver


def _read_key(payload: bytes):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        client.sendall(payload)
        return driver.read_key()
    finally:
        server.close(); client.close()


def test_editor_live_key_inputs_are_keys_not_printable_text():
    for payload, expected in [(b"^I", "TAB"), (b"^[OR", "F3"), (b"^[[18~", "F7"), (b"^[[19~", "F8")]:
        result = _read_key(payload)
        assert result.key == expected
        assert result.text == ""
        assert result.event is not None
