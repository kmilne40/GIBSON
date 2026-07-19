# Gibson z/VM Security Lab

A guided walkthrough of the z/VM attack-and-audit surface. Every command and
response below is reproduced by the simulator exactly as shown. The lab takes a
low-privilege guest from reconnaissance through credential, minidisk, privilege,
service-machine and network findings, then shows how each is audited.

> Connect with `L ZVM` from the VTAM logon screen. See `zvm_simulation.md` for
> the directory, credentials and privilege-class reference.

---

## 0. Objective

Demonstrate the most common real-world z/VM security weaknesses on a system that
*looks* correctly configured: weak directory passwords, an over-shared minidisk,
privilege-class boundaries, service-machine authority, and network-access grants.

---

## 1. Reconnaissance (class-G guest)

Log on as the demonstration guest and enumerate your position:

```text
LOGON  ==> DEMO
PASSWORD ==> DEMO
...
Q CPLEVEL        →  z/VM Version 7 Release 4.0, service level 2501 (64-bit)
Q USERID         →  DEMO AT ZVMPROD
Q PRIVCLASS      →  PRIVCLASSES FOR DEMO: G
Q NAMES          →  logged-on guests this run
```

You hold **class G** only — a general user. Note what you *cannot* see yet.

---

## 2. Finding 1 — weak directory credentials

The CP directory entries use default, guessable passwords. The highest-value
target is `MAINT`, which holds **all** privilege classes (ABCDEFG):

```text
LOGON  ==> MAINT
PASSWORD ==> MAINT          ← the default was never changed
```

Logon succeeds. This is the classic mainframe finding: a fully privileged
service userid protected by a default password. (A wrong password now returns
`HCPLGA050E LOGON unsuccessful--incorrect password` and is audited as a
`LOGON_FAIL` event — credentials are enforced, they are simply *weak*.)

---

## 3. Finding 2 — over-shared minidisk (MAINT 191)

Back as the low-privilege `DEMO` guest, link MAINT's primary minidisk:

```text
LINK MAINT 191 391 RR
→  MAINT 191 LINKED AS 391 RR  (R/O exposure)
```

It links **without a password** because `MAINT 191` is seeded with read access
`ALL` — a deliberate exposure modelling a real misconfiguration where a sensitive
disk is readable system-wide. Contrast a properly protected disk:

```text
LINK RACFVM 490 493 RW BADPW
→  HCPLNM298E RACFVM 490 not linked; password incorrect
```

The RACFVM security-server disk requires the correct link password and denies the
attempt. **Finding:** audit every `MDISK` statement for `RR ALL` / `MR ALL` /
`WR ALL` link modes.

---

## 4. Finding 3 — privilege-class boundaries

A class-G guest is denied privileged CP commands:

```text
(as DEMO)  FORCE OPERATOR
→  HCPCMD003E You are not authorized to issue CP command FORCE.
      FORCE requires privilege class A; you hold class G.
```

The same command as the over-privileged `MAINT`:

```text
(as MAINT)  FORCE DEMO
→  USER DEMO LOGOFF AS OF hh:mm:ss BY MAINT
   HCPFRC045I DEMO forced off the system
```

**Finding:** the boundary is enforced, so the risk is *who holds class A–F*.
MAINT/SYSADMIN holding ABCDEFG is expected; any general-purpose or application
guest holding class A, B, C or D is a finding. The privileged-command attempt
(authorized or not) is recorded as a security event.

The same class-B boundary governs real device custody. `ATTACH rdev userid`
hands a real I/O device from the system pool to a guest's virtual
configuration — whichever guest holds it can read it, so handing one to the
wrong guest is a real exposure, not just a config error:

```text
(as MAINT)  ATTACH 0500 DEMO
→  0500 ATTACHED TO DEMO
   *** Offsite backup tape - RACF database export is now reachable from DEMO ***
```

A device already attached elsewhere is denied (`HCPATT046E ... is attached to
<userid>`), and `DETACH rdev` releases it — your own device is always
releasable, but detaching one attached to someone else also requires class B.

---

## 5. Finding 4 — service-machine authority

Directory edits flow through the DirMaint service machine, and only authorised
guests may drive it:

```text
(as DEMO)   DIRMAINT FOR DEMO GET       → DVH002E not authorised
(as MAINT)  DIRMAINT FOR DEMO GET       → DVHREQ2289I directory updated
(as MAINT)  RAC LISTUSER <userid>       → RACFVM profile response (ICH messages)
```

**Finding:** review the DirMaint authorisation list and the RACFVM administrator
set — these are the guests that can rewrite the directory or RACF profiles.

---

## 6. Finding 5 — network access control (VSWITCH)

Virtual-switch access is an authorisation list, not an open network:

```text
Q VSWITCH
→  VSWITCH VSW1  OWNER SYSTEM  GRANTED: MAINT, TCPIP
```

Only granted guests reach the switch; `SET VSWITCH … GRANT/REVOKE` (class B)
changes the list. **Finding:** treat the VSWITCH grant list as a firewall rule
set — every GRANT is network reachability that should be justified.

---

## 7. Audit trail

Each step leaves evidence in the same SMF80/audit pipeline used by TSO and CICS:

- **Logons** record a `LOGON` security event (`service = TN3270/ZVM`).
- **Failed logons** (wrong password, or unknown userid when hardened) record
  `LOGON_FAIL`.
- **Privileged CP commands** record a privilege event with the verb, the class
  required, and whether the caller was authorised.

This is what a z/VM auditor correlates: weak-credential logons, links to exposed
minidisks, and privileged-command use by unexpected guests.

---

## Findings summary

| # | Finding | Mechanism | Remediation |
|---|---------|-----------|-------------|
| 1 | Default password on a fully-privileged userid | `MAINT` / `MAINT` | Rotate directory passwords; enforce rules |
| 2 | System-wide-readable sensitive minidisk | `MAINT 191` read `ALL` | Remove `ALL`; set explicit link passwords |
| 3 | Over-broad privilege classes | class A–F on non-service guests | Pare directory class assignments to least privilege |
| 4 | Unrestricted directory/RACF authority | DirMaint / RACFVM admin set | Restrict and review the authorised-driver lists |
| 5 | Over-broad network reachability | VSWITCH GRANT list | Justify every GRANT; revoke unused |

> Hardening note: set `GIBSON_ZVM_LAB_VULNERABLE=0` to reject unknown userids at
> logon (no transient class-G guests), tightening the front door for exercises
> that should start from a known account only.
