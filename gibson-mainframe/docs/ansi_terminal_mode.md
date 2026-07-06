# Gibson ANSI/ASCII live terminal mode

The latest Gibson terminal path uses ANSI/ASCII-compatible command handling for live TN3270, telnet, and netcat sessions. The live parser does not depend on CP037/EBCDIC conversion or full 3270 field-map interpretation.

This design prioritises reliable classroom connectivity. c3270/x3270, telnet, and netcat clients should all be able to submit commands such as `L TSO`, `HELP`, `LOGON`, and `LOGOFF` through the compatibility path.

EBCDIC conversion helpers may remain in isolated legacy or non-live code, but live terminal routing must not block waiting for EBCDIC frames.
