from gibson.net.telnet3270 import normalise_client_input


def test_netcat_ascii_remains_readable():
    assert normalise_client_input(b'USER IBMUSER\n') == 'USER IBMUSER'
