# What Gibson Can Do

Gibson is a self-contained z/OS mainframe **security-training simulator** (~68k LOC, 22 subsystems)
with a real network surface. The matrix below catalogs what it can do today. Items added or
substantially enhanced in the latest release are flagged 🆕 **NEW**.

**Network realism:** every service Gibson exposes responds the way a real z/OS system would. Service
banners, `nmap -sV` version detection, FTP FEAT extensions, and the mainframe NSE script responses
(`tn3270-screen`, `vtam-enum`, `tso-enum`/`tso-brute`, `cics-enum`, `nje-node-brute`) are matched to
genuine z/OS service-detection signatures — for example, the FTP listener fingerprints as
*IBM OS/390 ftpd V2R5*, exactly as a z/OS Communications Server daemon does.

> All techniques are intended for the sandboxed Gibson range and authorised security education only.

## Access & Terminal

| Capability | What it does | Status |
|---|---|---|
| VTAM / TN3270 front end | USS banner, APPLID selection, full 3270 datastream over c3270/x3270 | Stable |
| ASCII / netcat path | Merged TN3270/ANSI terminal mode for non-3270 clients | Stable |
| TSO LOGON | Userid/password logon with panel, PF-key handling | Stable |
| GIBSON welcome banner | Orientation banner shown once on first logon | 🆕 NEW |
| Forced password change | Initial/expired password change at logon (new-password-only round-trip) | 🆕 NEW |
| Multi-factor auth (MFA) | PIN+HHMM token prompt and validation, global enable + break-glass | 🆕 NEW |
| Re-logon | `LOGON`/`LOGON userid` at READY switches identity without dropping the session | 🆕 NEW |

## TSO & Core Commands

| Capability | What it does | Status |
|---|---|---|
| TSO READY prompt | Command-processor context with autocomplete and `?` help | Stable |
| Dataset commands | ALLOCATE, LISTDS, LISTCAT, DELETE, RENAME | Stable |
| SEND / notifications | Inter-user messages delivered to live sessions | Stable |
| IDCAMS / VSAM | DEFINE CLUSTER / AIX / PATH, DELETE, LISTCAT ENTRIES(...) ALL | 🆕 NEW |
| IND$FILE transfer | ASCII / BINARY / CRLF / NOCRLF bare-keyword syntax, CRLF text mode round-trips | 🆕 NEW |

## ISPF & Editor

| Capability | What it does | Status |
|---|---|---|
| ISPF primary menu | Option-driven navigation and settings | Stable |
| DSLIST | Dataset list utility, allocate/delete, member lists | Stable |
| ISPF editor | Line commands (I/D/C/M/R), primary commands (FIND, CHANGE, EXCLUDE, SAVE), wrap-aware | Stable |

## Datasets, Catalog & VSAM

| Capability | What it does | Status |
|---|---|---|
| Dataset allocation | Sequential and partitioned datasets, allocation parameters | Stable |
| SYS1 HLQ catalog | System dataset catalog with LISTCAT LEVEL(...) | Stable |
| VSAM clusters | Cluster / AIX / PATH define, associations, SMSDATA, attributes | 🆕 NEW |
| Live PARMLIB / PROCLIB / APF | Reads live members from the dataset store (incl. rogue APF detection) | 🆕 NEW |

## JES, JCL & Spool

| Capability | What it does | Status |
|---|---|---|
| JCL submit & lifecycle | Submit, convert, execute, spool output | Stable |
| SDSF | ST / DA / spool display, output browse, job actions | Stable |
| JCL converter / JECL | `/*JOBPARM /*ROUTE /*OUTPUT /*MESSAGE /*NOTIFY` acks; high-precision JCL-error detection | 🆕 NEW |
| JES2 `$` command surface | `$DA`, `$D INITS/PRT/SPOOL/NODE/SOCKET`, `$P/$S/$E PRT(n)`, `$T`, `$P/$S JES2` (live JES2PARM) | 🆕 NEW |

## Abends & Diagnostics

| Capability | What it does | Status |
|---|---|---|
| SYSUDUMP / symptom dump | Authentic IEA995I dumps: completion+reason code, PSW, INTC, CSECT+offset, GPRs | 🆕 NEW |
| Force-abend demos | Deliberate, repeatable S0C7 / S806 / S913 / S0C4 (ASRA) / S322 / Bx37 triggers | 🆕 NEW |
| Abends teaching lab | Manual appendix + runnable command-by-command walkthrough | 🆕 NEW |

## RACF & Security Administration

| Capability | What it does | Status |
|---|---|---|
| User/group admin | ADDUSER, ALTUSER, CONNECT, ADDGROUP, PERMIT, LISTUSER, LISTGRP | Stable |
| Profiles & SETROPTS | ADDSD, RDEFINE, RLIST, SEARCH, SETROPTS, class profiles | Stable |
| RACF DB materialisation | Live SYS1.RACFDS database, legacy-DES hashing | Stable |
| racf2john / John | Extract and crack RACF hashes in the OMVS lab | Stable |
| IRRADU00 audit unload | SMF type-80 audit-record unload + RACF audit reports menu | 🆕 NEW |
| IRRDBU00 database unload | **RACFHound / pyracf / mfpandas-parseable** unload: groups, users, connects, OMVS UID(0), dataset & general-resource profiles **with access lists** (SURROGAT, FACILITY/BPX, UNIXPRIV), realistic attack-path seed; no password hashes | 🆕 NEW |

## zSecure & Auditing

| Capability | What it does | Status |
|---|---|---|
| Event review | ZSEC EVENTS / RARE / SUMMARY over SMF + audit data | Stable |
| RACFDS / hash review | ZSEC RACFDS, OFFLINEHASH / HASHCRACK | Stable |
| Transfer/exfil review | ZSEC IND$FILE / TRANSFERS | Stable |
| Compliance baseline & drift | ZSEC BASELINE captures APF/SPECIAL/OPER/UID0/public-UACC; ZSEC DRIFT flags new exposures | 🆕 NEW |

## Master Console & Operations

| Capability | What it does | Status |
|---|---|---|
| MVS display commands | D IPLINFO, D PARMLIB, D SYMBOLS, D PROG,APF (live config) | 🆕 NEW |
| WLM / RMF | D WLM,SYSTEMS, D WLM service classes, D M=CPU (LPAR/CPC) | 🆕 NEW |
| Health checker | HZSPRINT health checks (RACF/APF/XCF findings) | 🆕 NEW |
| GRS contention | D GRS,C (ISG343I) | 🆕 NEW |
| OPERLOG & WTOR | Operator log, WTOR replies, V/START/STOP | Stable |
| RACFDS console alerting | Master-console alerts on sensitive RACF DB activity | Stable |

## OMVS / USS & Tooling

| Capability | What it does | Status |
|---|---|---|
| USS shell | Unix System Services shell on z/OS | Stable |
| Recon tooling | nmap (TN3270/VTAM/TSO/CICS scripts), nikto, FTP/JES anon, OSINT, dig/whois fixtures | Stable |
| Mainframe tooling | cicspwn, db2connect, tshocker/catso (safe sim), task manager, Lynx browser | Stable |
| Tool logging | OMVS security-tool activity feeds SMF / zSecure / console | Stable |

## Online Subsystems

| Capability | What it does | Status |
|---|---|---|
| CICS | CESN/CESF sign-on, CEMT, CECI, CEDA; CBSA banking app; DVCA (Damn Vulnerable CICS App) | Stable |
| CICS ASRA / overflow lab | Buffer-overflow path producing an authentic ASRA / S0C4 with secure-fix guidance | Stable |
| Db2 | SPUFI/SQL, catalog, DDF/DRDA, db2connect client | Stable |
| IMS | Hierarchical database and transactions | Stable |
| z/VM | CP command environment | Stable |
| zTPF | High-volume transaction processing model | Stable |

## Connectivity & Interfaces

| Capability | What it does | Status |
|---|---|---|
| FTP service | Anonymous and secure modes, JES anon path | Stable |
| NJE | Multi-node Network Job Entry (GIBSON/HAL/ORAC) over 175 / TLS 2252 | Stable |
| IND$FILE | Native 3270 file transfer (see TSO section for new bare-keyword/CRLF support) | Stable |
| REST API & web | CBSA REST, web terminal, dashboard, welcome services | Stable |
| Network fingerprints & nmap signatures | Listening services reproduce genuine z/OS responses: banners, `-sV` version detection (FTP as IBM OS/390 ftpd V2R5), FTP FEAT extensions, and NSE scripts (tn3270-screen, vtam-enum, tso-enum/brute, cics-enum, nje-node-brute) | Stable |

## SMF & Forensics

| Capability | What it does | Status |
|---|---|---|
| SMF engine | Types 30 / 80 / 110 / passticket, MANX log stream, recording modes | Stable |
| Forensic scenarios | RACFDS / hash / transfer forensic timelines across SMF + zSecure + console | Stable |

## Languages & Interpreters

| Capability | What it does | Status |
|---|---|---|
| REXX | Interpreter with common runtime | Stable |
| JCL | Job control interpreter (see JES section for new JECL/converter work) | Stable |
| COBOL | COBOL execution model (incl. the buffer-overflow teaching program) | Stable |
| HLASM | High Level Assembler model | Stable |

## Modes & Training

| Capability | What it does | Status |
|---|---|---|
| Secure vs Vulnerable mode | Toggle deliberate weaknesses on/off for attack vs hardened comparison | Stable |
| Blue-Team remediation | Every security lab pairs an attack with its defender-side fix | Stable |
| CTF mode | Capture-the-flag style challenge mode | Stable |

---

*🆕 NEW = added or substantially enhanced in the latest release.*
