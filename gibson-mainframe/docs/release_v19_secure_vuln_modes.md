# Gibson v19 Secure/Vulnerable Mode Release Notes

## Added

- `--secure` runtime switch
- `--vuln` runtime switch
- central runtime security-mode helpers
- CIS-aligned secure simulator profile
- secure-mode SETROPTS output for password, audit, RACLIST and PROTECTALL controls
- secure-mode sensitive dataset profile hardening
- secure-mode MFA requirement for non-IBMUSER users
- IBMUSER break-glass auditing
- TLS wrapping for TSO/TN3270 and dashboard/API when certificate generation succeeds
- DELUSER command support
- ALTUSER REVOKE and ALTUSER RESUME support
- vulnerable training command blocking in secure mode
- v19 tests and validation report

## Preserved

- `--vuln` keeps existing Gibson training behaviour
- existing v18 TN3270/RACF/IND$FILE fixes remain present
- nmap-sim and vulnerable workflows remain available in vulnerable mode

## Known limitations

- This is a CIS-aligned simulator profile, not complete real z/OS CIS compliance.
- TLS depends on local certificate generation or configured certificate/key files.
- Real AT-TLS policy agent, ICSF, SAF keyrings, DFSMS, JES2 device security, RRSF and z/OS UNIX mount controls are represented only as simulator mappings or future enhancements.
