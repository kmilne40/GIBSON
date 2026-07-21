## Chapter 10. CICS and Banking
Lab
### This section covers CICS transaction handling, CEMT/CEDA/CECI utility transactions,
CICSPWN/PWNPROBE and GMVB/MCGM banking lab screens.


<!-- page 126 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Implementation evidence
### Area Source evidence
### CICS app gibson/apps/cics.py
Region model gibson/core/cics_region.py
### Operational model
This CICS chapter uses transactions and banking panels to show how application logic sits behind
3270 screens. The operational model is transaction-driven: a short transaction ID invokes an
application path with its own security context.
### Security relevance
The security value is host-side validation. Screen fields, hidden flags and transaction IDs are not
security controls unless the CICS program and external security manager enforce them.
### Commands and features in scope
### Subsystem Command Syntax Evidence
CICS HELP/? HELP gibson/apps/cics.py:133
CICS CEMT CEMT [INQUIRE|SET|
PERFORM...]
gibson/apps/cics.py:165
CICS CEDA CEDA [DEFINE PROGRAM|
TRANSACTION...]
gibson/apps/cics.py:168
CICS CECI CECI EXEC CICS READ|
WRITE|READQ|WRITEQ...
gibson/apps/cics.py:171
### CICS CEBR/CEDF/CESL/CMSG/
### CESN/CESF
transaction ID gibson/apps/cics.py:142
CICS CICSPWN/PWNPROBE CICSPWN | PWNPROBE gibson/apps/cics.py:189
CICS Banking Lab GMVB/MCGM GMVB [MENU|CARG|ORDE|
ORDR|ACCT|STMT|XFER|
APRV|HACK|ADMN]
gibson/apps/cics.py:191,950
### Section labs
### Lab 14: Explore CICS transaction help
### Command context
Start from: VTAM/front-door or CICS entry point
Commands run from: CICS blank screen or CICS transaction context
Do not run these from: TSO READY, ISPF or OMVS
Why context matters: CICS transaction IDs are application commands, not TSO commands.


<!-- page 127 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll work through explore cics transaction help as a practical evidence exercise, not as
a command checklist. The concept being taught is CICS transaction and business-application
exposure. From a tester’s point of view, the aim is to produce a specific piece of evidence:
transaction response, GMVB menu path or transaction help. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
CEMT: opens or invokes the CICS master-terminal style control surface. In real CICS this is powerful
and heavily protected.
CEDA: relates to CICS resource definition administration. Its presence tells testers that management
transactions are part of the region exposure story.
CECI: is the CICS command-level interpreter. It is useful for learning but dangerous if exposed
because it can exercise CICS commands interactively.
GMVB MENU: enters the Gibson banking application menu, turning subsystem knowledge into a
business-application workflow.
### Starting state
Start from a terminal session that can reach the CICS/GMVB command path. If you are still at
READY, use the documented application path before issuing transaction commands.
### Lab steps
HELP
CEMT
CEDA
CECI
### GMVB MENU
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
CICS regions expose transaction IDs such as CEMT, CECI, CEDA, CESN and CESF. Security depends
on region settings and the external security manager checking transactions, commands and
resources.
### Defensive takeaway
Monitor access to system transactions, default-user activity and unusual business transaction
paths. CICS is often the business tier, not just a screen.


<!-- page 128 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If a transaction fails, confirm APPLID/session state, transaction spelling and whether the terminal
is at a CICS prompt rather than READY.
### Instructor note
Frame the lab as application-tier testing. Students should understand that a four-character
transaction can be a business function or a system-control function.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
context.
### A command name after
### HELP narrows the
output where
implemented.
### Help is safe
enumeration. It tells
you what the simulator
exposes without
changing state.
### Evidence is a command
list or help panel that
can be compared with
the command
appendix.
### CEMT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### CEDA Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### CECI Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB MENU Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
### Evidence is a
transaction panel,
menu or action result.


<!-- page 129 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
controls are behaving
safely.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
### Objective Identify CICS commands, management transactions and
GMVB/MCGM lab entry points.
Prerequisites CICS session.
Validation Source validated; interactive CICS session required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 15: Run the GMVB banking navigation path
### Command context
Start from: VTAM/front-door or CICS entry point
Commands run from: CICS blank screen or CICS transaction context
Do not run these from: TSO READY, ISPF or OMVS
Why context matters: CICS transaction IDs are application commands, not TSO commands.
### Why this lab matters
In this lab we’ll work through run the gmvb banking navigation path as a practical evidence
exercise, not as a command checklist. The concept being taught is CICS transaction and business-
application exposure. From a tester’s point of view, the aim is to produce a specific piece of
evidence: transaction response, GMVB menu path or transaction help. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
GMVB MENU: enters the Gibson banking application menu, turning subsystem knowledge into a
business-application workflow.
GMVB ACCT: navigates to account-oriented functionality in the training banking app.
GMVB STMT: shows statement-style data, useful for understanding data exposure paths.
GMVB XFER: models transfer functionality, where authorization and validation matter.
GMVB HACK: opens the intentionally insecure path used to teach application-control and 3270-style
testing concepts.
### Starting state


<!-- page 130 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start from a terminal session that can reach the CICS/GMVB command path. If you are still at
READY, use the documented application path before issuing transaction commands.
### Lab steps
### GMVB MENU
### GMVB ACCT
### GMVB STMT
### GMVB XFER
### GMVB HACK
### What the output tells us
For `GMVB MENU`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
CICS regions expose transaction IDs such as CEMT, CECI, CEDA, CESN and CESF. Security depends
on region settings and the external security manager checking transactions, commands and
resources.
### Defensive takeaway
Monitor access to system transactions, default-user activity and unusual business transaction
paths. CICS is often the business tier, not just a screen.
### Troubleshooting
If a transaction fails, confirm APPLID/session state, transaction spelling and whether the terminal
is at a CICS prompt rather than READY.
### Instructor note
Frame the lab as application-tier testing. Students should understand that a four-character
transaction can be a business function or a system-control function.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### GMVB MENU Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.


<!-- page 131 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### GMVB ACCT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB STMT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB XFER Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB HACK Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### Field Value
### Difficulty Intermediate
### Estimated time 50 minutes
### Objective Navigate GMVB/MCGM screens, identify training functions and
document security observations.
Prerequisites CICS banking lab enabled.
Validation Source validated; interactive screen flow required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 132 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
