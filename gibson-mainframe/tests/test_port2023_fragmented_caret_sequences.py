import socket
import threading
import time
import select

from gibson.render.input import SocketInputDriver


def _send_fragments(sock, fragments, delay=0.05, trailer=b""):
    for frag in fragments:
        time.sleep(delay)
        sock.sendall(frag)
    if trailer:
        time.sleep(delay)
        sock.sendall(trailer)


def _read_key_fragmented(fragments, delay=0.05):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        t = threading.Thread(target=_send_fragments, args=(client, fragments, delay), daemon=True)
        t.start()
        result = driver.read_key()
        t.join(timeout=1)
        return result
    finally:
        server.close(); client.close()


def _read_line_fragmented(fragments, delay=0.05):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=True)
        t = threading.Thread(target=_send_fragments, args=(client, fragments, delay), daemon=True)
        t.start()
        result = driver.read_line("===> ")
        t.join(timeout=1)
        echoed = b""
        try:
            r, _, _ = select.select([client], [], [], 0.05)
            if r:
                echoed = client.recv(4096)
        except Exception:
            pass
        return result, echoed
    finally:
        server.close(); client.close()


def test_fragmented_caret_tab_is_key_not_text():
    result = _read_key_fragmented([b"^", b"I"])
    assert result.key == "TAB"
    assert result.text == ""
    assert result.event is not None
    assert result.event.client_mode == "caret"


def test_fragmented_caret_pf_keys_are_keys_not_text():
    cases = [
        ([b"^", b"[", b"O", b"R"], "F3"),
        ([b"^", b"[", b"[", b"15", b"~"], "F5"),
        ([b"^", b"[", b"[18~"], "F7"),
        ([b"^", b"[", b"[19~"], "F8"),
    ]
    for fragments, expected in cases:
        result = _read_key_fragmented(fragments)
        assert result.key == expected
        assert result.text == ""
        assert result.event is not None


def test_fragmented_caret_sequences_are_consumed_before_line_echo():
    result, echoed = _read_line_fragmented([b"^", b"[", b"[19~"])
    assert result.key == "F8"
    assert result.text == ""
    assert b"^[[19~" not in echoed


def test_unknown_caret_text_is_preserved_as_text_after_timeout():
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=True)
        t = threading.Thread(target=_send_fragments, args=(client, [b"^", b"HELLO"], 0.01, b"\r"), daemon=True)
        t.start()
        result = driver.read_line("===> ")
        t.join(timeout=1)
        assert result.key is None
        assert result.text == "^HELLO"
    finally:
        server.close(); client.close()
