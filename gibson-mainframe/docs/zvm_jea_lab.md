# z/VM "Just Enough Authority" Privilege Lab

A guided lab on the Gibson z/VM subsystem that teaches **CP privilege-class
creep** and its blast radius. The lesson: on a mainframe hypervisor, the
privilege class a guest holds is the *only* thing standing between it and every
other guest's memory. Over-grant one Linux guest and you have the mainframe
analog of a VMware/ESXi VM-escape.

This is defensive training content: a sandboxed, deliberately vulnerable guest
with a vulnerable/fixed toggle so learners can see both the exploit and the
remediation.

## Background: CP privilege classes

z/VM Control Program (CP) gates every privileged command behind a privilege
class (A–G) held by a virtual machine in the CP directory:

| Class | Role | Example commands |
|-------|------|------------------|
| A | Primary system operator | FORCE, SHUTDOWN |
| B | Real resource control | ATTACH, VARY, DEFINE VSWITCH |
| C | System programmer — **alter host storage** | **STORE HOST** |
| D | Spooling control | manage other users' spool |
| E | System analyst — **examine host storage** | **DISPLAY/DUMP HOST**, INDICATE |
| F | Service representative | RDEVICE |
| G | General user — one's own virtual machine | QUERY, IPL, LINK, LOGOFF |

A standard Linux-on-IBM-Z guest needs only **class G**. Classes C and E let a
guest read and write **host real storage**, which is shared by all guests —
so C/E on a Linux guest is a cross-guest memory capability.

Reference: Altmark & Bitner, *z/VM Security and Integrity*, notes `CP STORE HOST`
(alter host real storage) is a **class C** command and examining storage is
**class E**. IBM *CP Planning and Administration* warns admins are routinely
over-powered and that HiperSockets (IQD) can cross the LPAR (PR/SM) EAL5+
isolation boundary.

## The scenario

`LINUX01` is a production Linux guest. In the vulnerable configuration it has
been granted classes **B C E G** — a pattern that happens when an admin clones an
operator/admin directory profile "to make networking work." It needs only G.

## Walkthrough

Connect to the z/VM service (TN3270, the z/VM port) and log on as `LINUX01`
(password `LINUX01`).

### 1. Examine host real storage — leak another guest's secret (class E)
```
DISPLAY HOST
```
Vulnerable: dumps the lab's tagged host real-storage map, including data owned by
*other* guests, each flagged `<== NOT YOUR GUEST`:
- `R021000` RACFVM — RACF database master key
- `R048000` MAINT — logon material in the CP work area
- `R0A4000` TCPIP — HiperSockets IQD frame buffer
- `R0C2000` DIRMAINT — directory password cache

`DISPLAY HOST 021000` targets a single real address.

### 2. Alter host real storage — corrupt another guest cross-guest (class C)
```
STORE HOST 021000 PWNED
```
Vulnerable: overwrites RACFVM's master-key region and prints
`*** cross-guest write: LINUX01 just corrupted RACFVM's memory ***`.

### 3. HiperSockets isolation bypass (network class)
```
QUERY HIPERSOCKETS
```
Vulnerable: the IQD device reaches `LP2`/`LP3`, i.e. traffic crosses the PR/SM
LPAR isolation boundary. A guest on one LPAR can reach services isolated on
another.

### 4. Privilege-class-creep audit
```
CPAUDIT            (also: QUERY PRIVCLASS ALL)
```
Reports every guest holding classes beyond its role baseline:
```
GUEST     HELD      BASELINE  EXCESS  RISK
LINUX01   BCEG      G         BCE     real device/network, alter/examine host storage
OPERATOR  ABCDE     ABDG      CE      alter/examine host storage
OPERATNS  ABCDE     ABDG      CE      alter/examine host storage
```
Note the audit also catches the seeded operators — over-privileged operators are
a real-world staple, not just the obvious Linux guest.

## Remediation — Just Enough Authority

Flip the lab to fixed mode (see toggle below). `LINUX01` is reduced to **class G**:

- `DISPLAY HOST` → `HCPCMD003E You are not authorized … DISPLAY requires class E;
  you hold class G.` (a CP COMMAND DENIED security event is recorded)
- `STORE HOST` → denied (requires class C)
- `QUERY HIPERSOCKETS` → `IQD confined to this LPAR; PR/SM isolation boundary intact`
- `CPAUDIT` → `LINUX01` no longer listed

The broader remediation the lab teaches:
1. **Least privilege** — grant each guest only the classes its role needs; a
   Linux guest gets G.
2. **Split admin roles** — replace a single all-class (`ABCDEFG`) admin with
   separate hypervisor-admin and storage-admin identities so no one guest both
   runs the system and can read all host memory.
3. **Audit for creep** — run the class audit routinely; treat C/E on a workload
   guest as a finding.

## Toggle

Default is vulnerable for training.

| Mode | Config | Env | LINUX01 classes |
|------|--------|-----|-----------------|
| Vulnerable | `zvm_jea_lab_vulnerable_mode=True` | `GIBSON_ZVM_JEA_VULNERABLE=1` | `BCEG` |
| Fixed (JEA) | `zvm_jea_lab_vulnerable_mode=False` | `GIBSON_ZVM_JEA_VULNERABLE=0` | `G` |

## Why it matters

A hypervisor compromise is never one VM. Security teams already understand this
from VMware/ESXi escapes; this lab shows the same blast-radius lesson in
mainframe terms, where the control is CP privilege classes rather than a
hypervisor CVE. The fix is boring and effective: least privilege and role
separation.

## Verification

Gate `zvm:jea` (in `tests/parity_harness.py`) drives the live `ZvmSession` in
both modes: vulnerable leaks RACFVM's key and corrupts it cross-guest, bridges
LPARs, and the audit flags `LINUX01`; fixed denies DISPLAY/STORE HOST, isolates
HiperSockets, and clears the `LINUX01` creep row. Pristine-baseline regression
diff remains empty.
