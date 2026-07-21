# Gibson Security Modes

Gibson v19 adds two explicit runtime modes.

## `--vuln`

`--vuln` is the compatibility and classroom training profile. It preserves the current Gibson behaviour, including vulnerable lab paths, nmap-sim training workflows, PassTicket demonstrations, CICS/DB2/FTP/REST labs, and the existing VTAM/TSO listener on port 2023.

This is the default mode unless `--secure` is supplied.

Example:

```bash
./gibsonctl.sh start --vuln
python -m gibson.cli --serve --with-ftp --with-rest --vuln
```

## `--secure`

`--secure` starts a CIS-aligned simulator profile. It is not a claim of complete z/OS compliance; it is a simulator implementation of the closest Gibson-equivalent controls from the CIS IBM z/OS V2R5 with RACF Benchmark.

Secure mode changes include:

- runtime mode banner and audit record
- TSO/TN3270 primary listener moved to port 1023
- TLS wrapping attempted for the TSO/TN3270 listener
- HTTPS wrapping attempted for the dashboard/API on port 8443
- MFA required for non-IBMUSER users where Gibson MFA is available
- IBMUSER retained as a break-glass recovery account
- IBMUSER break-glass use audited to SMF80/security log, console, and dashboard
- plaintext USS listener disabled by default
- plaintext FTP not started by the default secure startup path
- sensitive SYS1 and RACF datasets protected with UACC(NONE) or restricted READ
- PROTECTALL(FAIL), SAUDIT, CMDVIOL, OPERAUDIT and related SETROPTS output simulated
- vulnerable training shortcuts such as PTKTGEN/PTKTUSE and CICSPWN-style commands blocked from TSO command mode

Example:

```bash
./gibsonctl.sh start --secure
python -m gibson.cli --serve --with-rest --secure
```

## Conflict handling

Supplying both modes fails closed:

```bash
python -m gibson.cli --secure --vuln --diagnose
```

Expected result:

```text
GIBSON SECURITY MODE ERROR: --secure and --vuln are mutually exclusive
```

## IBMUSER break-glass

IBMUSER remains exempt from secure-mode lockout to prevent the training simulator from becoming unrecoverable during lab changes. This is a Gibson recovery design, not a real-world mainframe recommendation. Every IBMUSER secure-mode exemption event records:

- console alert
- SMF80-style security event
- dashboard alert
- SECEVENTS/security log entry
- normal audit event

Canonical event text:

```text
IBMUSER secure-mode break-glass exemption used
```

## v20 merge note

The v20 secure/TN3270 ANSI merged package was rebuilt from the v19 secure/vuln package. `--secure` and `--vuln` are preserved while the TN3270 stability fix, ANSI live terminal handling, and fingerprinting removal are applied.

## v21 entrypoint clarification

v21 keeps the existing Python CLI mode flags and makes the controller entrypoint explicit:

```bash
./gibsonctl.sh start --secure
./gibsonctl.sh start --vuln
```

The controller help now advertises both modes and fails closed if both are supplied.
