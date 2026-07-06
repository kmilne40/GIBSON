import socket, threading
from gibson.net.telnet3270 import IAC, DO, WILL, BINARY, END_OF_RECORD
from gibson.net.vtam_frontend import negotiate_tn3270_or_ascii


def test_dual_mode_routes_client_iac_without_sending_probe():
    server, client = socket.socketpair()
    result = {}
    def run():
        result['mode'] = negotiate_tn3270_or_ascii(server, timeout=0.25)
    t = threading.Thread(target=run, daemon=True); t.start()
    client.sendall(bytes([IAC, DO, BINARY, IAC, WILL, END_OF_RECORD]))
    t.join(1)
    mode = result['mode']
    assert mode.use_tn3270 is True
    assert mode.reason == 'TN3270_CLIENT_IAC_ROUTED'
    client.settimeout(0.05)
    try:
        assert client.recv(1) == b''
    except TimeoutError:
        pass
    server.close(); client.close()


def test_dual_mode_preserves_early_ascii_pushback_without_probe():
    server, client = socket.socketpair()
    result = {}
    def run():
        result['mode'] = negotiate_tn3270_or_ascii(server, timeout=0.25)
    t = threading.Thread(target=run, daemon=True); t.start()
    client.sendall(b"L TSO\r\n")
    t.join(1)
    mode = result['mode']
    assert mode.use_tn3270 is False
    assert mode.reason == 'ASCII_EARLY_TEXT'
    server.close(); client.close()
