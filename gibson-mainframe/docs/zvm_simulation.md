# Gibson z/VM Simulation

Gibson adds a simulated z/VM CP/CMS environment accessible over TN3270. It does
not implement a real hypervisor, real virtual-machine management, or real CMS
file I/O. It is a protocol-accurate training surface for learning z/VM
navigation, CP command syntax, and CMS workflows over a live TN3270 connection.

## Connecting

From the VTAM logon screen, enter either of the following:

```text
L ZVM
LOGON APPLID(ZVM)
```

You will land on the z/VM CP Logon screen. Logon now performs a **real CP
directory credential check**: the userid must exist in the CP directory and the
password must match its directory entry. An incorrect password — or, in hardened
mode, an unknown userid — is rejected with the authentic message:

```text
HCPLGA050E LOGON unsuccessful--incorrect password
```

Failed attempts are recorded as `LOGON_FAIL` security events. By design for the
lab, the seeded directory passwords are **weak and discoverable** (for example
`MAINT` / `MAINT` — the classic "default password never changed" finding), so the
environment teaches credential-based access control and weak-credential attacks
rather than accepting anything.

By default (`zvm_lab_vulnerable_mode = True`, env `GIBSON_ZVM_LAB_VULNERABLE`) an
**unknown** userid is admitted as a transient class-G guest, to keep exploration
easy. Set the flag off and unknown userids are rejected outright.

### CP directory, credentials and privilege classes

| Userid | Classes | Password | Role |
|--------|---------|----------|------|
| `MAINT` | ABCDEFG | `MAINT` | System maintenance (all classes) |
| `SYSADMIN` | ABCDEFG | `SYSADM` | Security administrator |
| `OPERATOR` | ABCDE | `OPER` | System operator console |
| `OPERATNS` | ABCDE | `OPERATNS` | Operations / automation |
| `DIRMAINT` | BG | `DIRMAINT` | Directory Maintenance service machine |
| `RACFVM` | BG | `RACFVM` | RACF/VM security server |
| `TCPIP` | BG | `TCPIP` | TCP/IP stack |
| `GUEST` / `DEMO` | G | `GUEST` / `DEMO` | General users |

Privilege classes follow z/VM: **A** primary system operator, **B** real
resource control, **C** alter host storage, **D** spool control, **E** examine
host storage, **F** service representative, **G** general user. A class-G guest
is denied privileged CP commands (FORCE, SHUTDOWN, ATTACH, STORE, DISPLAY of real
storage) — the central teaching point of the z/VM surface.

## Screen flow

```
CP Logon screen
      │  ENTER (userid / password)
      ▼
CP Ready prompt
      │  IPL CMS  (or CMS, IPL 190)   → CMS Ready
      │  CP Q <option>                 → CP Query response
      │  HELP                          → CP Help listing
      │  LOGOFF / DISC                 → return to VTAM
      ▼
CMS Ready prompt
      │  FILELIST  (or FL)             → FILELIST screen
      │  RDRLIST   (or RL)             → RDRLIST screen
      │  XEDIT <fn ft fm>              → XEDIT screen
      │  CP                            → back to CP Ready
      │  LOGOFF / #CP LOGOFF           → return to VTAM
```

## CP commands

### IPL CMS

```text
IPL CMS
CMS
IPL 190
IPL 191
```

Loads the CMS environment and moves to the CMS Ready prompt.

### CP QUERY

```text
CP Q TIME
CP Q CPLEVEL
CP Q USERID
CP Q NAMES
CP Q USERS
CP Q PRIVCLASS
CP Q STORAGE
CP Q VIRTUAL
CP Q DASD
CP Q CPUS
CP Q MDISK
CP Q LINK
CP Q VSWITCH
CP Q RDR
HELP
```

| Command | Returns |
|---------|---------|
| `Q TIME` | Current time, date, CPU time, and connect time |
| `Q CPLEVEL` | z/VM version, release and CP service level (64-bit) |
| `Q USERID` | Your userid and the node name (`userid AT node`) |
| `Q NAMES` / `Q USERS` | Virtual machines **actually logged on** this run |
| `Q PRIVCLASS` | Your held privilege classes with descriptions |
| `Q STORAGE` / `Q STOR` | Total system storage |
| `Q VIRTUAL` | Virtual and expanded storage allocation |
| `Q DASD` / `Q DISK` | Simulated DASD volumes (3390, R/W and R/O) |
| `Q CPUS` | Processor list |
| `Q MDISK` / `Q LINK` | Your minidisks / current minidisk links |
| `Q VSWITCH` | Virtual switches and their GRANTed users |
| `Q RDR` / `Q SPOOL` | Your reader/spool files |
| `HELP` | CP command reference listing |

Unrecognised CP commands return a `HCPCMD003E` error message, matching real
z/VM CP error formatting.

### Disconnect

```text
LOGOFF
LOG
DISC
DISCONNECT
```

From the CP Ready prompt any of the above ends the session and returns to VTAM.
PF3 from the CP Logon or CP Ready screen also disconnects.

## CMS commands

### FILELIST (FL)

Displays a simulated CMS minidisk file listing in standard FILELIST format:

```text
Cmd   Filename  Filetype  Fm  Format  Lrecl  Records  Blocks  Date      Time
      PROFILE   EXEC      A1  V        80       42       1  2024-01-15 09:12:44
      DEMO      REXX      A1  V        80      123       2  2024-03-10 14:22:01
      MYJOB     JCL       A1  V        80       18       1  2024-04-01 11:05:33
      ...
```

PF3, ENTER, or CLEAR returns to CMS Ready.

### RDRLIST (RL)

Displays a simulated virtual reader queue in standard RDRLIST format:

```text
Cmd   Filename  Filetype  Fm  Origid   Date      Time     Recs  Class Pri Hold
      MYJOB     JOB       RDR  <userid>  04/27/24 09:14:02  250  A    1
      REPORT    DATA      RDR  SYSTEM    04/26/24 22:00:11  512  A    2
      SYSLOG    OUTPUT    RDR  SYSTEM    04/26/24 23:59:59 1024  A    5
```

PF3, ENTER, or CLEAR returns to CMS Ready.

### XEDIT

```text
XEDIT DEMO REXX A
XEDIT MYJOB JCL A
X PROFILE EXEC A
```

Opens the named file in a simulated XEDIT session. Any filename is accepted.
The screen displays a static REXX EXEC as content for demonstration. PF3 saves
and returns to CMS Ready. ENTER re-renders the same screen (useful for testing
macro or key behaviour).

### Return to CP

```text
CP
```

Drops back to CP Ready without logging off.

### Logoff from CMS

```text
LOGOFF
#CP LOGOFF
```

Ends the session and returns to VTAM. PF3 from CMS Ready returns to CP Ready
(not logoff) — matching real z/VM PF key conventions.

Unrecognised CMS commands return a `DMSEXT002S` error message.

## PF key map

| Key | CP Ready | CMS Ready | FILELIST / RDRLIST | XEDIT |
|-----|----------|-----------|--------------------|-------|
| PF3 | Logoff | Return to CP | Return to CMS | Return to CMS |
| PF7 | — | — | Backward (no-op) | Backward (no-op) |
| PF8 | — | — | Forward (no-op) | Forward (no-op) |
| PF12 | Retrieve (label) | Retrieve (label) | Cursor | Power input (label) |
| ENTER | Submit command | Submit command | Return to CMS | Re-render |
| CLEAR | — | — | Return to CMS | — |

## Simulated system identity

| Property | Value |
|----------|-------|
| z/VM version | 7 Release 4.0 (7.4.0), CP service level 2501 |
| System name | `ZVMPROD` |
| VM system ID | `ZVMSYS1` |
| LU name | `ZVMLU01` |
| Directory guests | MAINT, SYSADMIN, OPERATOR, OPERATNS, DIRMAINT, RACFVM, TCPIP, GUEST, DEMO |

The directory guests above are **defined** at IPL but are not logged on until a
session actually logs them on. `Q NAMES` / `Q USERS` therefore reflects only the
guests logged on during the current run (plus your own session), which is the
real z/VM behaviour — not a fixed list.

## Security event logging

Every successful logon records a security event through
`GibsonState.record_security_event` with service `TN3270/ZVM`, feeding the same
SMF80/audit pipeline used by TSO and CICS logons. **Failed logons** — wrong
password, or an unknown userid in hardened mode — are recorded as `LOGON_FAIL`
events (blank-password rejection is handled at the screen level).

## Security lab surface

The z/VM environment is a **security** training surface. The teachable, exploitable-
but-bounded mechanisms currently modelled are:

- **Credential control** — real password verification with deliberately weak,
  discoverable directory passwords (default-credential attacks).
- **Privilege classes** — class-G denial of privileged CP commands; class A–F
  authority required for FORCE / SHUTDOWN / ATTACH / STORE / DISPLAY.
- **Minidisk LINK passwords** — `LINK` enforces read/write link passwords;
  `MAINT 191` is deliberately readable by `ALL` (a classic exposure), while
  RACFVM/DIRMAINT disks are protected. Wrong link passwords are denied.
- **VSWITCH authorisation** — `Q VSWITCH` shows GRANTed users; GRANT/REVOKE is a
  network-access-control teaching model (not a real network stack).
- **DirMaint authority** — only authorised guests may drive directory edits.
- **Audit** — logons and `LOGON_FAIL` events flow to the SMF80/audit pipeline.

Deep hypervisor behaviour (guest IPL, IUCV/APPC, DIAGNOSE internals, SSI/live
guest relocation) is intentionally **not** implemented; such requests surface as
authentic denials and audit records rather than full emulation.

## Simulator boundary

Gibson z/VM is a training simulator. It does not implement:

- Real CP hypervisor operations or guest virtual-machine control
- Real CMS file I/O, minidisk formatting, or SFS
- Real XEDIT editing (content is static)
- Real RACFVM integration or VM directory management (DIRMAINT)
- Real spool operations (RDRLIST entries are static)
- Real TCP/IP stack management via TCPIP virtual machine
- IUCV, APPC, or inter-virtual-machine communication

It reproduces the TN3270 screen flow, CP/CMS command syntax, error message
formats, and PF key conventions for training purposes only.
