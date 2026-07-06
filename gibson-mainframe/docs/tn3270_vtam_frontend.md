# Gibson v17 TN3270/VTAM Front End

## Purpose

v17 tightens the VTAM/TN3270/TN3270E front end so Gibson does not send `IAC EOR` or EOR-framed 3270 records until a client has negotiated a 3270-capable mode. This addresses TN3270 client messages such as `EOR received when not in 3270 mode, ignored.`

## Behaviour

Port 2023 remains a dual-mode front end:

- plain `nc` and ordinary `telnet` clients receive the existing ASCII/NVT VTAM screen and can still type `L TSO`, `L CICS`, or `L DB2`;
- TN3270-style clients negotiate BINARY and END-OF-RECORD, or TN3270E, before Gibson sends a 3270 Erase/Write screen terminated by `IAC EOR`;
- malformed or partial clients are handled with bounded timeouts and are not sent 3270 data before 3270 mode is established.

## Protocol notes

The implementation tracks per-session BINARY, EOR, terminal-type and TN3270E state. It treats classic TN3270 as ready only after both local and remote BINARY/EOR are agreed. If a client accepts TN3270E but does not complete TN3270E subnegotiation, Gibson backs TN3270E out before attempting classic TN3270 fallback.

## Validation commands

```bash
nc 127.0.0.1 2023
telnet 127.0.0.1 2023
x3270 127.0.0.1:2023
c3270 127.0.0.1:2023
nmap -sV -p 2023 127.0.0.1
```

If `x3270`, `c3270`, or `nmap` are not installed on the build host, use the synthetic socket tests in `tests/test_v17_tn3270_racf_mfa.py` and repeat live validation on a clean VM.
