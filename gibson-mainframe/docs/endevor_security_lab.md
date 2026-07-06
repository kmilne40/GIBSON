# Gibson Endevor Security Lab — Broken Access Control

A guided demonstration of a **broken object-level authorization** flaw
(CWE-639) in a software change manager, built so a security team can *see* the
impact and the fix side by side. Every command and response below is reproduced
exactly by the simulator.

> Reach it from the TSO READY prompt: `ENDEVOR` for the primary menu, then the
> element actions `DISPLAY` / `BROWSE` / `RETRIEVE` / `ADD`.

---

## 0. Background — how Endevor *should* authorize

Endevor controls source as **Elements**, keyed by
`Environment . System . Subsystem . Type . Element` across lifecycle **Stages**
(Development → Test → QA → Production, plus Emergency). Who may act on an element
is decided by Endevor's **External Security Interface (ESI)**, which issues a
`RACROUTE REQUEST=AUTH` call to RACF to confirm the user is authorized for that
inventory area. No authorization → no access.

In this lab the inventory scope is:

| System.Subsystem | Authorized users | Contents |
|------------------|------------------|----------|
| `TRAINING.GENERAL` | TRAINEE, FIBSUSR, FIBSADM, IBMUSER | `HELLO` (harmless) |
| `PAYROLL.SALARY` | PAYADMIN, IBMUSER | `PAYCALC` (executive salary bands) |
| `BANKING.CORE` | FIBSADM, IBMUSER | `ACCTPOST` |

`TRAINEE` is a low-privilege developer with **no** scope for `PAYROLL.SALARY`.

---

## 1. The flaw

The element **browse/retrieve** path validates that the requested element
*exists* but — in the vulnerable build — never asks ESI whether *this* user is in
scope for it. The object reference is fully user-controlled
(`SYSTEM.SUBSYSTEM.TYPE.ELEMENT`), so any authenticated user can name another
team's element and read it. This is the same class of bug as an IDOR in a web
app: the authorization check on the object is simply missing.

---

## 2. Demonstration (vulnerable build — default)

As `TRAINEE`, list what's around and then read a payroll element you were never
granted:

```text
ENDEVOR DISPLAY
  SYSTEM   SUBSYS   TYPE     ELEMENT  VVLL   STAGE OWNER    SIGNOUT
  TRAINING GENERAL  COBOL    HELLO    01.03  DEV   TRAINEE  SO:*NONE*
  BANKING  CORE     COBOL    ACCTPOST 12.40  PROD  FIBSADM  SO:*NONE*
  PAYROLL  SALARY   COBOL    PAYCALC  07.11  PROD  PAYADMIN SO:*NONE*

ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC
 *** ESI SCOPE CHECK BYPASSED - element returned without authorization ***
     1        IDENTIFICATION DIVISION.
     2        PROGRAM-ID. PAYCALC.
     3       * CONFIDENTIAL - EXECUTIVE SALARY BANDS
     4        01  WS-EXEC-BAND.
     5            05  WS-CEO-BASE      PIC 9(7)V99 VALUE 1450000.00.
     ...
```

A trainee just read confidential production source. The element key was the only
thing the attacker controlled, and it was enough.

---

## 3. The fix (set `GIBSON_ENDEVOR_LAB_VULNERABLE=0`)

With the ESI scope check restored, the **identical** action is denied and
recorded — while authorized and in-scope access is unaffected:

```text
(as TRAINEE)  ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC
 ICH408I USER(TRAINEE ) GROUP(TRNGRP  ) NAME(########)
   PAYROLL.SALARY.COBOL.PAYCALC CL(ENDEVOR )
   INSUFFICIENT ACCESS AUTHORITY
   ACCESS INTENT(READ   )  PERMITTED(NONE   )
 C1G0000E  ESI SECURITY VIOLATION FOR ACTION BROWSE - REQUEST DENIED
```

The denial also writes an **SMF type-80** security record (visible to the audit
tooling, e.g. zSecure `CMDFAIL`). Meanwhile:

```text
(as IBMUSER, authorized)  ENDEVOR BROWSE PAYROLL.SALARY.COBOL.PAYCALC   → source returned
(as TRAINEE, in scope)    ENDEVOR BROWSE TRAINING.GENERAL.COBOL.HELLO   → source returned
```

The before/after is the whole point: the vulnerable and fixed builds differ by
exactly one missing authorization call, and the fix neither blocks legitimate
work nor needs any change to the data — only the check.

---

## 4. Findings & remediation

| # | Finding | Mechanism | Remediation |
|---|---------|-----------|-------------|
| 1 | Any user can read any element by naming it | Missing ESI scope check on browse/retrieve | Call `RACROUTE REQUEST=AUTH` for the element's inventory area on **every** read path |
| 2 | No audit trail of cross-scope reads | Vulnerable path returns source silently | Ensure denials (and ideally grants) write SMF80 so violations are detectable |
| 3 | Confidential production source in a browsable system | Sensitive code without restrictive ESI rules | Restrict `SYSTEM.SUBSYSTEM` profiles to least privilege; review who is permitted |

**The lesson for the team:** an input-validation / authorization gap on a
user-controlled object reference is not theoretical — it turns "list the
inventory" into "read anyone's production source." The fix is one check, and it
costs legitimate users nothing.

> Toggle: `GIBSON_ENDEVOR_LAB_VULNERABLE=1` (default) demonstrates the flaw;
> `=0` runs the hardened build with ESI enforcement and SMF auditing.
