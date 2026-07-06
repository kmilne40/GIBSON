# Gibson v18 TN3270 client compatibility

## What changed

Gibson v18 removes runtime network fingerprinting from the live VTAM/Telnet path. The live service now prioritises real client compatibility over cosmetic Nmap service identity. Optional scanner-support descriptions may remain as documentation or static helper metadata, but Gibson no longer uses fake IBM service prologues, HTTP Server spoof headers, or banner/probe tricks that can interfere with actual clients.

## NVT mode and 3270 mode

TN3270 clients begin in Telnet/NVT mode and enter 3270 mode only after Telnet option negotiation has established the required 3270 transport behaviour. Gibson keeps port 2023 as the main VTAM selector and sends only conservative Telnet option negotiation before deciding the mode.

Plain `telnet` and `nc` sessions remain ASCII/NVT. They receive the normal VTAM selector screen and can still route with `L TSO`, `L CICS`, and `L DB2`.

`c3270` and `x3270` sessions are switched to 3270 rendering only after Gibson sees a valid TN3270/TN3270E style negotiation, such as BINARY plus END-OF-RECORD or a likely 3270 terminal type.

## EOR handling

Gibson must not send an IAC EOR record marker before 3270 mode is established. Premature EOR can confuse clients that are still in NVT mode. In v18, EOR is emitted only by the TN3270 session after the negotiation layer has selected 3270 mode.

## Validation commands

```bash
nc 127.0.0.1 2023
telnet 127.0.0.1 2023
c3270 127.0.0.1:2023
x3270 127.0.0.1:2023
```

Expected results:

- `nc` and `telnet` display the ASCII VTAM selector.
- `c3270` and `x3270` negotiate 3270 mode cleanly.
- No client is blocked by fingerprinting logic.
- No raw 3270 screen is sent to ASCII clients.

## References

- RFC 1576, TN3270 Current Practices: https://www.rfc-editor.org/rfc/rfc1576.html
- RFC 2355, TN3270 Enhancements: https://www.ietf.org/rfc/rfc2355.html
- x3270/tcl3270 NVT mode behaviour: https://x3270.bgp.nu/Unix/tcl3270-man.html

## v20 stability note

v20 addresses a `c3270` hang seen after typing `L TSO` and pressing Enter. The fix keeps the Gibson TN3270 path intentionally small:

- use complete screen-boundary writes;
- restore the client keyboard with the 3270 write-control character;
- normalise inbound AID/EOR/order bytes into plain Gibson command text;
- avoid unbounded waits for newline or EOR;
- retain EBCDIC only as a simple inbound decode path with ASCII fallback.

This favours reliable classroom connectivity over strict full-screen 3270 emulation.

## v20 ANSI live terminal update

The merged v20 package uses ANSI/ASCII live terminal handling for TN3270, telnet and netcat. c3270/x3270 are kept on the reliable command path; Gibson does not require CP037/EBCDIC parsing for live commands.
