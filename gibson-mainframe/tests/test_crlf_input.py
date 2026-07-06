import socket
import threading
import time

from gibson.render.input import SocketInputDriver


def test_crlf_is_consumed_as_one_line():
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        client.sendall(b"L TSO\r\nIBMUSER\r\n")
        first = driver.read_line().text
        second = driver.read_line().text
        assert first == "L TSO"
        assert second == "IBMUSER"
    finally:
        server.close()
        client.close()
