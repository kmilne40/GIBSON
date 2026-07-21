# Gibson v20 Runtime Fingerprinting Removal

Gibson v20 secure/TN3270 ANSI merged removes live runtime service fingerprinting from the terminal, FTP, REST and dashboard paths.

The previous scanner-oriented layer could make live services look more IBM-like to probes, but it also risked interfering with real clients such as c3270, x3270, telnet and netcat. Gibson now prioritises real client compatibility.

## Current behaviour

- TN3270/Telnet sends no fake scanner prologue.
- Live terminal sessions use the ANSI/NVT command path.
- FTP uses a plain Gibson FTP greeting.
- REST/dashboard no longer inject IBM HTTP Server style identity headers.
- nmap-sim.py remains a separate training tool and is not part of live service negotiation.

## Validation

Use c3270, x3270, telnet and netcat to validate live connectivity. Use nmap-sim.py separately for training workflows.
