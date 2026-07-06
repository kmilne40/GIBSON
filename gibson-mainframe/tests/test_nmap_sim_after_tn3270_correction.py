from gibson.net.telnet3270 import normalise_client_input


def test_nmap_sim_ascii_commands_remain_plain():
    assert normalise_client_input(b'L TSO\r\n') == 'L TSO'
    assert normalise_client_input(b'CEMT\r\n') == 'CEMT'
