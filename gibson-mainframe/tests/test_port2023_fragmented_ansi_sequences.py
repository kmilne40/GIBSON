import socket
import threading
import time

from gibson.render.input import SocketInputDriver


def _read_key_fragmented(fragments, delay=0.05):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        def send():
            for frag in fragments:
                time.sleep(delay)
                client.sendall(frag)
        t = threading.Thread(target=send, daemon=True)
        t.start()
        result = driver.read_key()
        t.join(timeout=1)
        return result
    finally:
        server.close(); client.close()


def test_fragmented_actual_escape_pf8_is_key():
    result = _read_key_fragmented([b"\x1b", b"[19~"])
    assert result.key == "F8"
    assert result.text == ""
    assert result.event is not None
    assert result.event.client_mode == "ansi"


def test_fragmented_actual_escape_pf3_is_key():
    result = _read_key_fragmented([b"\x1b", b"O", b"R"])
    assert result.key == "F3"
    assert result.text == ""
