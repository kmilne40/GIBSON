import socket
import select

from gibson.render.input import SocketInputDriver


def _read_line_payload(payload: bytes):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=True)
        client.sendall(payload)
        result = driver.read_line("===> ")
        echoed = b""
        try:
            r, _, _ = select.select([client], [], [], 0.01)
            if r:
                echoed = client.recv(4096)
        except Exception:
            pass
        return result, echoed
    finally:
        server.close(); client.close()


def _read_key_payload(payload: bytes):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        client.sendall(payload)
        return driver.read_key()
    finally:
        server.close(); client.close()


def test_caret_notation_function_keys_are_consumed_before_echo():
    cases = {
        b"^I": "TAB",
        b"^[OR": "F3",
        b"^[[15~": "F5",
        b"^[[18~": "F7",
        b"^[[19~": "F8",
    }
    for payload, expected in cases.items():
        result, echoed = _read_line_payload(payload)
        assert result.key == expected
        assert result.text == ""
        assert payload not in echoed


def test_actual_ansi_escape_function_keys_are_normalised():
    cases = {
        b"\x1bOR": "F3",
        b"\x1b[15~": "F5",
        b"\x1b[18~": "F7",
        b"\x1b[19~": "F8",
    }
    for payload, expected in cases.items():
        result = _read_key_payload(payload)
        assert result.key == expected
        assert result.text == ""
        assert result.event is not None
        assert result.event.aid == expected


def test_plain_ascii_commands_still_pass_through_read_line():
    result, _echoed = _read_line_payload(b"L TSO\r")
    assert result.key is None
    assert result.text == "L TSO"
