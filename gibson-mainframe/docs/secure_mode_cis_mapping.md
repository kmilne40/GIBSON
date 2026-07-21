# Gibson Secure Mode CIS Mapping

This document maps CIS IBM z/OS V2R5 with RACF Benchmark recommendations to Gibson v19 secure-mode simulation behaviour. Gibson is a simulator, so this is a CIS-aligned training profile, not a certification statement.

| CIS area | CIS recommendation theme | Gibson status | Secure-mode behaviour | Evidence/test |
|---|---|---|---|---|
| 1.1.1 | PASSWORD(INTERVAL) no longer than 90 days | Simulated | `SETROPTS LIST` reports 90 days | `test_secure_profile_applies_cis_dataset_controls` |
| 1.1.2 | PASSWORD(HISTORY) at least 4 | Simulated | secure profile records history value 4 | `SETROPTS LIST` documentation |
| 1.1.4 | PASSWORD(MINCHANGE) greater than zero | Simulated | `SETROPTS LIST` reports 1 day | targeted secure-mode test |
| 1.1.5 | PASSWORD(REVOKE) specified | Simulated | revoked users cannot authenticate; `ALTUSER userid REVOKE` supported | `test_altuser_revoke_resume_and_deluser_secure_breakglass` |
| 1.1.6 | KDFAES password algorithm | Partially simulated | `SETROPTS LIST` and secure profile report KDFAES intent; Gibson does not implement real RACF KDFAES | documented limitation |
| 1.1.7 | PASSWORD(WARNING) set | Simulated | `SETROPTS LIST` reports 5 day warning | targeted secure-mode test |
| 1.2.6 | OPERCMDS active and RACLISTed | Simulated | OPERCMDS raclist flag set in secure profile | `SETROPTS LIST` |
| 1.2.8 | FACILITY active and RACLISTed | Simulated | FACILITY raclist flag set in secure profile | `SETROPTS LIST` |
| 1.3.1 | SPECIAL use justified | Simulated | SPECIAL use and IBMUSER break-glass are audited | MFA/break-glass test |
| 2.1.8 | RACF security datasets protected | Simulated | `SYS1.RACFDS*` UACC(NONE), IBMUSER ALTER only | dataset profile test |
| 2.2.5 | PARMLIB datasets controlled | Simulated | `SYS1.PARMLIB` protected, UPDATE+ requires explicit authority | dataset access tests |
| 2.2.13 | PROCLIB datasets controlled | Simulated | `SYS1.PROCLIB` protected | dataset access tests |
| 2.2.15 | LINKLIB protected | Simulated | `SYS1.LINKLIB` protected | dataset access tests |
| 2.3.3 | PROTECTALL(FAIL) | Simulated | unprofiled protected access denied in secure-mode evaluator | secure profile tests |
| 3.1 | CMDVIOL logging | Simulated | blocked/failed security commands audited | secure block tests |
| 3.2 | SPECIAL activity logging | Simulated | SPECIAL commands emit SMF80-style events | user lifecycle tests |
| 3.3 | AUDIT for relevant classes | Simulated | DATASET, USER, GROUP, OPERCMDS, TSOAUTH, SDSF, FACILITY, UNIXPRIV, APPL listed in secure profile | SETROPTS output |
| 3.4 | OPERAUDIT | Simulated | `SETROPTS LIST` reports OPERAUDIT | secure profile test |
| 6.2 | FTP security and AT-TLS | Partially simulated | secure startup does not start plaintext FTP by default; dataset access remains centralised | live smoke recommended |
| 6.6.4 | TN3270 AT-TLS | Partially simulated | TSO/TN3270 listener is moved to 1023 and wrapped with TLS when local certificate generation succeeds | live TLS smoke recommended |
| 6.6.5 | TN3270 SMF recording | Simulated | TN3270/TLS startup and logons are SMF80-style audited | live smoke recommended |
| 9.23 | USS Telnet server not active | Simulated | plaintext USS listener disabled by default in secure startup | startup test |

## Not applicable or future enhancement

The following CIS areas require facilities Gibson does not fully model: real ICSF cryptographic key stores, SAF keyrings, AT-TLS policy agent configuration, real RACF database encryption, DFSMS storage classes, JES2 device-level security, z/OS UNIX mount flags, RRSF protocol conversion, and real Health Checker integration. These are documented as not applicable or future enhancements in the validation report.
