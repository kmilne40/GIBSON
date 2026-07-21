import socket, threading

from gibson.net.vtam_frontend import negotiate_tn3270_or_ascii
from gibson.net.telnet3270 import normalise_client_input


def test_ascii_early_text_remains_ascii_and_not_lost():
    server, client = socket.socketpair()
    result = {}
    def run():
        result["mode"] = negotiate_tn3270_or_ascii(server, timeout=0.3)
    t = threading.Thread(target=run, daemon=True); t.start()
    client.sendall(b"L TSO\r\n")
    t.join(1)
    mode = result["mode"]
    assert mode.use_tn3270 is False
    assert mode.reason == "ASCII_EARLY_TEXT"
    assert normalise_client_input(b"L TSO\r\n") == "L TSO"
    server.close(); client.close()


def test_cp037_bytes_are_not_treated_as_ascii_commands():
    assert normalise_client_input("L TSO".encode("cp037")) != "L TSO"
