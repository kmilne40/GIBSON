import socket
import threading
import time
import select

from gibson.render.input import SocketInputDriver


def test_fragmented_pf8_is_not_echoed_to_prompt():
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=True)
        def send():
            for frag in (b"^", b"[", b"[19~"):
                time.sleep(0.04)
                client.sendall(frag)
        t = threading.Thread(target=send, daemon=True)
        t.start()
        result = driver.read_line("===> ")
        t.join(timeout=1)
        echoed = b""
        r, _, _ = select.select([client], [], [], 0.05)
        if r:
            echoed = client.recv(4096)
        assert result.key == "F8"
        assert b"^[[19~" not in echoed
    finally:
        server.close(); client.close()
