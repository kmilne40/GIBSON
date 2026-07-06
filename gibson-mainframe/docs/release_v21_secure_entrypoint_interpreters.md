# Gibson v21 secure entrypoint and interpreter documentation update

v21 is a compatibility-preserving package built from the v20 secure/TN3270/ANSI merged level. It clarifies and hardens the runtime entrypoint experience for `--secure` and `--vuln` while preserving the v20 ANSI/no-EBCDIC/no-runtime-fingerprinting behaviour.

## Changes

- `gibsonctl.sh --help` now explicitly documents `start --secure` and `start --vuln`.
- `gibsonctl.sh start --secure` and `start --vuln` are parsed as first-class mode selections and forwarded to `python -m gibson.cli`.
- `--secure` and `--vuln` together fail closed before startup.
- secure-mode port preflight now checks secure ports 1023 and 8443 rather than only vulnerable-mode ports.
- vulnerable-mode port preflight remains classroom-compatible.
- added tests covering CLI mode state, gibsonctl forwarding, REXX, JCL/JES, and COBOL compile simulation.
- added interpreter reference documentation for REXX, JCL/JES, and COBOL simulation.

## Preserved behaviour

- `--vuln` remains the default compatibility mode.
- secure mode remains the CIS-aligned simulator profile.
- v20 ANSI/ASCII live terminal handling remains intact.
- live EBCDIC/CP037 terminal parsing remains disabled.
- runtime service fingerprinting remains disabled.
- nmap-sim remains a separate training tool.
