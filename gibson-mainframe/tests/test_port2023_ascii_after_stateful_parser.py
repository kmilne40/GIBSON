import socket

from gibson.render.input import SocketInputDriver


def _line(payload: bytes):
    server, client = socket.socketpair()
    try:
        driver = SocketInputDriver(server, echo=False)
        client.sendall(payload + b"\r")
        return driver.read_line()
    finally:
        server.close(); client.close()


def test_ascii_commands_still_pass_through_stateful_parser():
    for command in ["L TSO", "USER IBMUSER", "L CICS", "CEMT", "CEDA", "CECI", "CSMT", "CEMT I CONNECTION"]:
        result = _line(command.encode())
        assert result.key is None
        assert result.text == command
