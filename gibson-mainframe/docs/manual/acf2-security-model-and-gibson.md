## ACF2 Security Model and Gibson
### ACF2 Commands
### Why ACF2 matters in Gibson
### ACF2 is one of the major external security managers used on mainframes. Gibson implements
ACF2 command equivalents so students can compare RACF-style profiles with ACF2-style logonids,
UID strings, data set rules and resource rules. From a tester's point of view, this matters because
two sites can protect similar resources through very different command languages. From a
defender's point of view, it teaches why you must read the security product that is actually
running, rather than forcing every finding into RACF terminology.
### Command context
### Start from TSO READY. Enter ACF2 to switch the READY command processor into Gibson ACF2
mode. Use RACF to return to RACF command syntax. If you are already inside ISPF, use option 6
first, then enter ACF2 and the related commands. Do not type ACF2 commands at the ISPF primary
menu, in the ISPF editor line-command area, inside CICS, inside FTP, or at the OMVS shell unless a
documented bridge is being used.
### Gibson ACF2 simulation scope
Gibson maps ACF2 training concepts onto the simulator state. LID commands work against the
seeded user store and dynamic RACF-style backend. RULE commands store data set rule
equivalents. RESOURCE commands map ACF2 resource types such as FAC, SUR and OPR onto
SAF/RACF-style classes so the learner can practise the thought process safely. The point is not to


<!-- page 83 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
claim Gibson is a full ACF2 implementation. The point is to give students enough behaviour to
understand how ACF2 changes the security assessment workflow.
### ACF2 command reference
### ACF2 concept map
### ACF2 output interpretation
### Lab ACF2-1: Enter ACF2 mode and list logonids
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
In this lab we'll prove the ACF2 command context before doing anything state-changing. The
security lesson is simple: the same simulator can teach RACF and ACF2, but the commands and
mental model are different.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SHOW MODE
### SHOW DDSN
LIST *
### LIST IBMUSER
### What the output tells us
You should see ACF2 MODE ACTIVE, database dataset names and logonid records. The important
evidence is the identity fields, not just that the command ran. On a real ACF2 system, listing
logonids would be controlled by administrative scope and would feed user-review or privileged-ID
review.


<!-- page 84 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-2: Create and change a training logonid
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This lab shows how identity administration changes state. In a production system, this is high-risk
activity; in Gibson it is a safe way to see what privileged ACF2 administration looks like.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps


<!-- page 85 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ACF2
### SET LID
### INSERT ALICE PASSWORD(TEST123) SECURITY GROUP(LAB) UID(2001)
### LIST ALICE
### CHANGE ALICE NOSECURITY GROUP(SYS1) NO-OMVS
### LIST ALICE
### What the output tells us
The evidence is the transition from SECURITY to NOSECURITY and the OMVS/UID fields. Defenders
care because logonid creation and privilege changes are audit-significant events.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-3: Build and test a data set rule
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
Here we move from identity to access. ACF2 rules answer the question: can this logonid use this
data set at this service level?
### What the commands do


<!-- page 86 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SET RULE
### INSERT IBMUSER.SECRET.DATA
### RECKEY IBMUSER ADD(SECRET.DATA UID(ALICE) SERVICE(READ) ALLOW)
### LIST IBMUSER.SECRET.DATA
ACCESS DSNAME('IBMUSER.SECRET.DATA')
TEST DSNAME('IBMUSER.SECRET.DATA') LID(ALICE) SERVICE(READ)
### What the output tells us
Look for the $KEY, UID(ALICE), SERVICE(READ), ALLOW and TEST ALLOW lines. On real z/OS, this
would be paired with ACF2 rule reporting and access/audit records.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.


<!-- page 87 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab ACF2-4: Review a SURROGAT-style resource rule
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This lab connects ACF2 resource-rule thinking to a familiar security risk: submit-as authority. Even
if the syntax differs, the question is the same: who can act as whom?
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SET RESOURCE(SUR)
### RECKEY IBMUSER ADD(IBMUSER.SUBMIT UID(ALICE) SERVICE(READ) ALLOW)
### LIST IBMUSER.SUBMIT
### ACCESS RESOURCE(IBMUSER.SUBMIT) TYPE(SUR)
TEST IBMUSER RSRCNAME('IBMUSER.SUBMIT') LID(ALICE) SERVICE(READ)
### What the output tells us
The evidence is TYPE(SUR) and the allowed UID/service line. Defenders should treat submit-as
authority as privilege delegation, not as a harmless batch convenience.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note


<!-- page 88 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-5: Translate ACF2 evidence into a security finding
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This capstone lab forces the student to stop collecting output and start explaining risk. ACF2 output
should turn into a finding only when the affected identity, rule, resource and consequence are
clear.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
Choose one previous ACF2 output line.
Write: Evidence, Impact, Likelihood, Recommendation, Defensive Validation.
### What the output tells us
A good answer explains the protected resource, the logonid or UID that can use it, the service level,
and the control that should govern the access. On real z/OS, that evidence would be supported by
ACF2 reports, SMF/security records and change history.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway


<!-- page 89 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
