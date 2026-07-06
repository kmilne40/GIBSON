# Gibson v20 Secure/TN3270 ANSI Merged Release

This release is rebuilt from the v19 secure/vuln package and reapplies the TN3270 stability fix as a minimal merge.

## Preserved from v19

- `--secure`
- `--vuln`
- secure terminal listener on port 1023
- HTTPS/dashboard/API on port 8443
- IBMUSER break-glass
- secure MFA behaviour
- CIS-aligned simulator profile
- DELUSER
- ALTUSER REVOKE / RESUME

## Added/changed in v20

- TN3270/c3270 `L TSO` hang mitigation.
- Bounded TN3270-style input normalisation.
- ANSI/ASCII-only live terminal command handling.
- EBCDIC/CP037 removed from live terminal command parsing.
- Runtime service fingerprinting disabled.

## Compatibility decision

Gibson uses ANSI/ASCII-compatible live terminal handling for reliability and classroom usability. It does not attempt full live EBCDIC/3270 field-map emulation. Offline/static helper metadata may remain, but live services must not depend on scanner-oriented negotiation or EBCDIC decoding.
