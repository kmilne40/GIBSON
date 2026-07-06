# Endevor Package — Separation-of-Duties Bypass Lab

A guided lab on the Gibson Endevor subsystem that teaches a **change-control
separation-of-duties (SoD) bypass**: a developer who can both author *and*
approve a package promotes code to PROD with no independent review.

This is defensive training content: a sandboxed package workflow with a
vulnerable/fixed toggle so learners see both the bypass and the control that
stops it.

## Background: Endevor packages

CA/Broadcom Endevor promotes element changes through stages (DEV → TEST → QA →
PROD) inside a **package** — a unit of work with its own lifecycle:

```
CREATE   -> build the package and its action(s)        (engineer)
CAST     -> freeze it; nothing further can be edited    (engineer)
APPROVE  -> a change-control approver signs off         (must be someone else)
EXECUTE  -> the cast actions run; code moves to PROD
```

Sound change control requires **separation of duties**: the engineer who creates
and casts a package must not be the one who approves it. That independent
approval is the control that catches a bad or malicious change before PROD.

## The scenario

A developer `DEVUSER` has been mistakenly added to the package approver group
`#ENDVAPR` (a real-world misconfiguration — approver groups drift as people
change teams). The lab shows what that one mistake enables.

## Walkthrough

From the TSO READY prompt (or the Endevor menu), as `DEVUSER`:

```
ENDEVOR PACKAGE CREATE  PKG0001 BANKING.CORE.COBOL.ACCTPOST TO P
ENDEVOR PACKAGE CAST    PKG0001
ENDEVOR PACKAGE APPROVE PKG0001
ENDEVOR PACKAGE EXECUTE PKG0001
ENDEVOR PACKAGE LIST            (also DISPLAY PKG0001)
```

### Vulnerable (default)
`APPROVE` by the creator succeeds and prints:
```
*** SEPARATION-OF-DUTIES BYPASS: package was created AND approved
*** by the same engineer (DEVUSER); no independent review occurred.
```
`EXECUTE` then promotes the change and notes the change reached PROD on a
self-approved package — the SoD control was bypassed. `LIST` flags the package
`SELF-APPROVED`. An `ENDEVOR SOD BYPASS` security event is recorded.

### Fixed (`GIBSON_ENDEVOR_SOD_VULNERABLE=0`)
Creator self-approval is rejected — even though `DEVUSER` is in the approver
group:
```
ICH408I USER(DEVUSER ) GROUP(#ENDVAPR) NAME(########)
  PACKAGE PKG0001 CL(ENDEVOR )
  SEPARATION OF DUTIES - CREATOR MAY NOT APPROVE OWN PACKAGE
C1X0007E  APPROVAL DENIED; A DIFFERENT APPROVER IS REQUIRED
```
An independent approver (`FIBSADM`) must approve before `EXECUTE` will run, and
an `ENDEVOR SOD VIOLATION` audit event is cut on the denied self-approval.

### Both modes
A user outside the approver group (e.g. `TRAINEE`) is denied at `APPROVE` with
an `ICH408I … NOT IN APPROVER GROUP #ENDVAPR` — group membership is always
enforced; the *toggle only governs the creator-equals-approver SoD check*.

## Remediation

1. **Enforce SoD in the tool** — the creator/caster of a package can never be an
   approver of that same package, regardless of group membership.
2. **Curate the approver group** — review `#ENDVAPR` membership; developers do
   not belong in it. Treat membership drift as an audit finding.
3. **Audit self-approval attempts** — alert on `ENDEVOR SOD VIOLATION` /
   `ENDEVOR SOD BYPASS` events; a self-approval attempt is a signal.
4. **Require N approvers for sensitive inventory** — high-stakes systems
   (BANKING.CORE, PAYROLL.SALARY) should need more than one independent sign-off.

## Toggle

| Mode | Config | Env |
|------|--------|-----|
| Vulnerable (default) | `endevor_sod_lab_vulnerable_mode=True` | `GIBSON_ENDEVOR_SOD_VULNERABLE=1` |
| Fixed | `endevor_sod_lab_vulnerable_mode=False` | `GIBSON_ENDEVOR_SOD_VULNERABLE=0` |

This is independent of the Phase 1 broken-access-control toggle
(`endevor_lab_vulnerable_mode`), so the two Endevor labs can be run separately.

## Why it matters

SoD failures are one of the most common audit findings in mainframe change
management, and they map directly to modern CI/CD lessons — the person who
opens a pull request shouldn't be the one who approves and merges it to prod.
The fix is a control, not a CVE: enforce independence and curate who can approve.

## Verification

Gate `endevor:package-sod` (in `tests/parity_harness.py`) drives the package
lifecycle in both modes: vulnerable lets the creator self-approve and execute to
PROD (bypass banner + event); fixed denies self-approval, requires a distinct
approver, and a non-approver is denied in both modes. Pristine-baseline
regression diff remains empty.
