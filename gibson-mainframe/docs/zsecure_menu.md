# zSecure (CKR/C2R) ISPF Interface — Reference

Research notes on the real IBM Security zSecure Admin + Audit for RACF ISPF
interface, used to make Gibson's zSecure surface authentic. Current product
level is **zSecure 3.x** (3.1.0 / 3.2.0). The interactive panels generate
**CARLa** (CARLa Auditing and Reporting Language) commands that are run by the
**CKRCARLA** application program; results are displayed back through ISPF.

## Architecture

```
ISPF panels  ──generate──▶  CARLa commands  ──run by──▶  CKRCARLA load module
     ▲                                                          │
     └────────────────────  results displayed  ◀───────────────┘
```

Data sources: the live RACF database (and a point-in-time **CKFREEZE**), plus
**SMF** records (live data sets, log streams, or IFASMFDP/IFASMFDL unloads) for
event auditing. A typical ISPF user never writes CARLa directly — the panels
generate it.

## Primary menu

The action bar reads **Menu  Options  Info  Commands  Setup**. Options are
mnemonic (one or two letters), navigated like ISPF (`=AU.S`, etc.):

| Option | Area | Purpose |
|--------|------|---------|
| `SE` | Setup | Input files (CKFREEZE/UNLOAD/live), run options, confirm options (`SE.4`), alert config (`SE.A`) |
| `RA` | RACF administration | User-friendly RACF admin + reporting (see below) |
| `AU` | Audit | Status audit, audit concerns, SMF event reporting, compliance |
| `RE` | Resources | Resource/profile reports (datasets, general resources, Db2) |
| `EV` | Events | SMF event reporting and selection |
| `AM` | Access Monitor | Historic access-decision stats for RACF cleanup |
| `CO` / `C2R` | Command Verifier | zSecure Command Verifier policy |
| `IN` | Information | Product/system information |

### RA — RACF administration sub-options

| Path | Name | Purpose |
|------|------|---------|
| `RA.U` | USER | User information / selection |
| `RA.G` | GROUP | Group information |
| `RA.D` | DATASET | Data set profiles |
| `RA.R` | RESOURCE | General resource profiles |
| `RA.S` | SETTINGS | SETROPTS and class settings |
| `RA.H` | HELPDESK | One-panel help-desk actions |
| `RA.Q` | QUICK ADMIN | Quick user administration |
| `RA.1` | ACCESS | Access check |
| `RA.2` | QUEUED | Queued commands |
| `RA.3` | REPORTS | Reports with profiles and resources |
| `RA.4` | MASS UPDATE | Mass copy / recreate / delete |
| `RA.5` | RACDCERT | Certificates, key rings, tokens |
| `RA.C` | CUSTOM | User-defined (CARLa) display |

### AU — Audit (the audit report surface)

zSecure Audit analyses RACF + z/OS settings and SMF. Its core outputs:

- **Status Audit** — system posture by **audit concern**, each with a numeric
  **priority** (higher = more severe). Concerns include SETROPTS weaknesses,
  control-table issues (CDT, RACF router table), privileged/trusted started
  tasks, profiles in WARNING mode, high UACC, and Global Access Checking gaps.
- **SETROPTS audit concerns** — e.g. PROTECTALL not active, weak password rules
  (interval, history, mixed-case, revoke-count), audit class coverage.
- **Predefined SMF event reports** — among them:
  - `USEOPER` — access granted only because of the OPERATIONS attribute
  - `CMDSPEC` — commands issued by SPECIAL users
  - `CMDFAIL` — RACF command / access violations
  - data set access violations, RACF exceptions
- **Compliance** — framework testing (PCI DSS, STIG, CIS, DISA).

## RESULTS panel

After a query/command, zSecure shows a RESULTS panel. Selectable files with line
commands **B**rowse / **S** default / **E**dit / **R**un / **P**rint / **J**
submit / **V**iew / **W**rite / **M** e-mail:

```
_ SYSPRINT   messages
_ REPORT     printable reports
_ CKRTSPRT   output from the last TSO command(s)
_ CKRCMD     queued TSO commands
_ CKR2PASS   queued commands for zSecure
_ COMMANDS   zSecure input commands from last query
_ SPFLIST    printable output from the PRT command
_ OPTIONS    set print options
```

## How Gibson maps to this

- **`ZSEC AUDIT`** generates an authentic CKRCARLA **Status Audit Report**:
  SETROPTS audit concerns by priority, a privileged-user census
  (SPECIAL/OPERATIONS/AUDITOR/UID(0)/REVOKED), per-id privileged-user concerns,
  resource/data-set exposure (high UACC, WARNING mode), the predefined
  `USEOPER` / `CMDSPEC` / `CMDFAIL` SMF event reports, and an audit-priority
  summary — driven from the live simulator RACF + SMF state.
- The ISPF zSecure menu presents the audit-concern categories under the real
  zSecure option codes: **AU** (status audit), **RA.S** (SETROPTS), **AU.P**
  (privileged users), **AU.U** (UID(0)), **EV** (events), **CO** (compliance),
  **SE** (setup / input files), behind the authentic action-bar header
  (`Menu  Options  Info  Commands  Setup`). `AU` runs the Status Audit report
  above; `SE` lists the input set (live RACF / CKFREEZE / UNLOAD / SMF).

## Sources

IBM zSecure 3.1.0 / 3.2.0 documentation (RACF Administration Guide RA.* option
map; Status Audit and SMF report definitions; RESULTS panel), the zSecure Admin
and Audit Getting Started guides, and RACF SETROPTS audit-concern practice
(GASP/STIG). Product numbers: zSecure Admin 5655-N16, zSecure Audit 5655-N17.
