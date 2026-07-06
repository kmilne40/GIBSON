from gibson.net.telnet3270 import normalise_client_input

def test_ascii_nmap_commands_still_normalise():
    for cmd in ['L TSO','USER IBMUSER','L CICS','CEMT','CEDA','CECI','CSMT']:
        assert normalise_client_input((cmd+'\r\n').encode()) == cmd
