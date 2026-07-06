## Front Matter
This manual documents the Gibson Mainframe Simulator package gibson-mainframe-final1805.zip.
It is a practical training manual for mainframe security, penetration testing, blue-team monitoring,
and instructor-led labs. The manual is source-backed: the package code, command handlers,
runtime state objects, route definitions, seeded users, datasets, ports, and Phase 1 inventories are
treated as authoritative.
WARNING: Simulator boundary
Gibson is a simulator. It reproduces mainframe-like workflows, prompts, commands, outputs, and security
concepts for training. It is not a real z/OS system and should not be treated as a substitute for site-specific
IBM documentation or production change control.
IMPORTANT: Documentation source rule
Existing README files were intentionally not used as the source of truth for this manual. Where
README/version statements conflict with the code-derived inventory, the code-derived inventory wins and
the mismatch is recorded in Known Gaps.
### Audience
 Mainframe security analysts learning RACF, TSO, ISPF, SDSF, JES, CICS, Db2, OMVS and logging
concepts.
 Penetration testers and red-team trainers who need a safe environment for mainframe-style
enumeration and control-plane practice.
 Blue-team analysts who want to practise OPERLOG, SMF-like event review, alert triage and
service-state interpretation.
 Instructors building multi-day technical classes around a repeatable simulator.
### Manual conventions
### Convention Meaning
### READY command A command submitted to the simulated TSO READY command
processor.
Console command A command handled by the Master Console controller.
### Source evidence File and line or module evidence discovered in code-derived
inventories.
### Runtime validated Command sequence executed against a fresh temporary
GibsonState or safe command harness.
### Source validated Handler, route, command definition or inventory evidence


<!-- page 3 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
confirmed statically in code.


<!-- page 4 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 5 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
