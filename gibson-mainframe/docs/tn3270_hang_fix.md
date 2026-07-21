# TN3270 c3270 Hang Fix

## Problem

A live c3270 client could connect and type `L TSO`, but pressing Enter caused the session to hang. Netcat did not hang, so the issue was isolated to TN3270-style negotiation/input handling.

## Fix

The live terminal path now uses ANSI/ASCII command handling for c3270, x3270, telnet and netcat. Gibson strips Telnet IAC/EOR/control bytes, ignores simple 3270 framing bytes when they appear, and extracts printable ANSI/ASCII command text.

## EBCDIC status

EBCDIC/CP037 is removed from live interactive terminal command parsing. Gibson no longer waits for a complete EBCDIC 3270 field map for commands such as `L TSO`, `HELP`, `LOGON`, or `LOGOFF`.

## Fingerprinting status

The TN3270 fingerprint prologue is disabled for live clients. This prevents scanner-oriented negotiation from forcing clients into a mode that Gibson is not using for classroom terminal interaction.
