## Chapter 6. RACF Administration
and Security Model
This section covers users, groups, dynamic profiles, dataset profiles, resource profiles, SETROPTS-
like settings, password policy, UADS, MFA segments and auditing attributes.
### Implementation evidence
### Area Source evidence
### RACF repository gibson/core/racf.py
Dynamic RACF gibson/core/racf_dynamic.py
### TSO integration gibson/apps/tso.py
### Operational model
This chapter works with RACF-style identity, group and resource profiles. The operational model is
profile-driven: commands inspect or change users, groups, classes, UACC, access lists and training-
mode controls.
### Security relevance
The security value is access-control interpretation. A tester looks for dangerous attributes, broad
permits, WARNING mode and impersonation paths; a defender looks for class activation, least
privilege, audit events and change control.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### RACF ADDUSER ADDUSER userid
PASSWORD(pw)|PASS(pw)
[SPECIAL|OPERATIONS|
AUDITOR|ROAUDIT|UAUDIT]
[TSO(...)] [OMVS(...)] [DFP(...)]
gibson/apps/tso.py
LEGACY_HELP
### RACF ALTUSER ALTUSER userid
PASSWORD(pw)|REVOKE|
RESUME [ROAUDIT|
NOROAUDIT] [TSO(...)|
NOTSO] [OMVS(...)|NOOMVS]
[DFP(...)|NODFP] [MFA(...)|
NOMFA].
gibson/apps/tso.py
LEGACY_HELP
### RACF SETROPTS LIST Displays system options
(restricted).
gibson/apps/tso.py
LEGACY_HELP
### RACF SEARCH CLASS(USER) Lists users with SPECIAL gibson/apps/tso.py


<!-- page 60 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
privileges. LEGACY_HELP
### RACF RACLIST Displays RACF profile details. gibson/apps/tso.py
LEGACY_HELP
RACF LISTUSER LISTUSER userid [ALL|TSO|
OMVS|DFP|MFA] - displays
user details and segments.
gibson/apps/tso.py
LEGACY_HELP
### RACF ADDGROUP ADDGROUP groupname -
define a RACF group.
gibson/apps/tso.py
LEGACY_HELP
RACF LISTGRP LISTGRP [group|*] - list RACF
groups.
gibson/apps/tso.py
LEGACY_HELP
### RACF CONNECT CONNECT userid
### GROUP(group)
[AUTHORITY(USE)].
gibson/apps/tso.py
LEGACY_HELP
### RACF REMOVE REMOVE userid
GROUP(group).
gibson/apps/tso.py
LEGACY_HELP
### RACF RDEFINE RDEFINE class profile
[UACC(access)].
gibson/apps/tso.py
LEGACY_HELP
### RACF RLIST RLIST class profile. gibson/apps/tso.py
LEGACY_HELP
This section has 28 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 06: Create, alter and review a training user
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create, alter and review a training user as a practical evidence
exercise, not as a command checklist. The concept being taught is identity, class, profile and
authority analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence:
user attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do


<!-- page 61 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC))
OMVS(UID(9001) HOME(/u/manlab)): creates a controlled training user with TSO and OMVS
attributes. It is state-changing and should be treated as proof that account provisioning controls
matter.
LISTUSER MANLAB ALL: confirms the created profile and exposes the exact attributes added by
ADDUSER.
ALTUSER MANLAB ROAUDIT MFA(PIN(1234)): alters the training user so students can see how
account properties and authentication controls change after creation.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC)) OMVS(UID(9001)
### HOME(/u/manlab))
### LISTUSER MANLAB ALL
### ALTUSER MANLAB ROAUDIT MFA(PIN(1234))
### What the output tells us
For `ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC))
OMVS(UID(9001) HOME(/u/manlab))`, identify the exact returned line, return code, panel state or
dataset change that proves the lab objective. If that item is not present, pause and troubleshoot the
current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your


<!-- page 62 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### ADDUSER MANLAB
### PASSWORD(PASS123)
### TSO(ACCTNUM(ACCT#)
### PROC(ISPFPROC))
### OMVS(UID(9001)
### HOME(/u/manlab))
### Creates a simulated
RACF user profile.
### PASSWORD sets the
initial credential; TSO()
adds TSO segment data;
### OMVS() adds UNIX
identity data.
### User creation teaches
how identity, TSO logon
capability and UNIX
identity are separate
but connected controls.
### Evidence is a LISTUSER
profile showing base,
### TSO and OMVS
segments.
### LISTUSER MANLAB
ALL
### Displays a simulated
### RACF user profile and
optional segments.
### ALL asks for broad
profile detail; a user ID
such as IBMUSER or
### MANLAB selects the
account to inspect.
### User profile review is
one of the first ways to
identify powerful
attributes, segment
data and
authentication
controls.
### Evidence includes
attributes, owner,
default group,
### TSO/OMVS/MFA
segments and
revoke/status
indicators.
### ALTUSER MANLAB
### ROAUDIT
### MFA(PIN(1234))
### Alters an existing
simulated RACF user
profile.
### ROAUDIT and MFA/PIN
style operands change
audit and
authentication posture
in Gibson.
### ALTUSER is
operationally powerful;
in the wrong hands it
becomes persistence,
privilege or
authentication control.
### Evidence is the
changed LISTUSER
output.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Create a user, add OMVS/TSO segments, apply ROAUDIT and
review output.
Prerequisites SPECIAL user such as IBMUSER.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 07: Create a resource profile and permit access
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists


<!-- page 63 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create a resource profile and permit access as a practical evidence
exercise, not as a command checklist. The concept being taught is identity, class, profile and
authority analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence:
user attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
RDEFINE FACILITY LAB.PROFILE UACC(NONE): defines a FACILITY-class resource profile with no
universal access. It teaches resource protection rather than user creation.
PERMIT LAB.PROFILE CLASS(FACILITY) ID(MANLAB) ACCESS(READ): adds an access-list entry so
MANLAB can read the protected resource. The teaching point is that access is explicit, class-based
and reviewable.
RLIST FACILITY LAB.PROFILE: lists the resource profile so students can validate UACC and the
access list rather than assume PERMIT worked.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### RDEFINE FACILITY LAB.PROFILE UACC(NONE)
### PERMIT LAB.PROFILE CLASS(FACILITY) ID(MANLAB) ACCESS(READ)
### RLIST FACILITY LAB.PROFILE
### What the output tells us
For `RDEFINE FACILITY LAB.PROFILE UACC(NONE)`, identify the exact returned line, return code,
panel state or dataset change that proves the lab objective. If that item is not present, pause and
troubleshoot the current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting


<!-- page 64 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### RDEFINE FACILITY
### LAB.PROFILE
### UACC(NONE)
### Defines a simulated
### RACF general resource
profile.
### CLASS selects the
resource class; UACC
controls universal
access.
### Resource profiles
protect FACILITY,
### OPERCMDS, SERVAUTH
and other security-
sensitive controls.
### Evidence is the profile
visible through RLIST.
### PERMIT LAB.PROFILE
### CLASS(FACILITY)
### ID(MANLAB)
### ACCESS(READ)
### Adds an access
permission to a
simulated RACF
resource profile.
### ID names the
user/group and ACCESS
sets the authority.
### PERMIT is where a
profile becomes usable
by a specific identity;
that is often where
least privilege fails.
### Evidence is the profile
access list showing the
new permit.
### RLIST FACILITY
### LAB.PROFILE
### Displays a simulated
### RACF general resource
profile.
### CLASS identifies the
resource class; AUTH
or ALL asks for access
list and authority
detail.
### RLIST converts a
profile name into
evidence: owner, UACC,
warning state and
access list.
### Evidence is the profile
detail and any explicit
permits.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Define a FACILITY resource, grant READ access and verify
RLIST output.
Prerequisites MANLAB user created or use IBMUSER.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 65 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab 08: Create and inspect a dataset profile
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create and inspect a dataset profile as a practical evidence exercise,
not as a command checklist. The concept being taught is identity, class, profile and authority
analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence: user
attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING: creates a dataset profile with READ
universal access and WARNING behaviour. This is intentionally risky because WARNING can
log/allow behaviour that looks enforced but is not fully blocking.
LISTDSD DATASET(IBMUSER.MANUAL.TEST) ALL: lists the dataset profile so UACC, WARNING and
access information can be interpreted as security evidence.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING
### LISTDSD DATASET(IBMUSER.MANUAL.TEST) ALL
### What the output tells us
For `ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING`, identify the exact returned line,
return code, panel state or dataset change that proves the lab objective. If that item is not present,
pause and troubleshoot the current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway


<!-- page 66 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
ADDSD
### IBMUSER.MANUAL.TES
### T UACC(READ)
### WARNING
### Defines a simulated
RACF data set profile.
### UACC sets default
access; WARNING
allows violations to be
logged rather than
blocked in real RACF
concepts.
### Creating a controlled
profile lets you practise
the same data-set
protection workflow
without touching real
SYS1 data.
### Evidence is the new
profile visible through
LISTDSD.
### LISTDSD
### DATASET(IBMUSER.MA
### NUAL.TEST) ALL
### Displays a simulated
RACF data set profile.
### DATASET() selects the
data set profile; ALL
requests full detail.
### Data set profiles are the
boundary between
ordinary users and
sensitive system
libraries, JCL,
credentials and
configuration.
### Evidence includes
### UACC, WARNING,
owner, audit settings
and access lists.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
Objective Create a training dataset profile and review LISTDSD output.
Prerequisites SPECIAL user.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 67 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The next labs move from RACF-style users, groups, classes and profiles into ACF2-style logonids,
UID strings, rules and GSO/control records. Keep comparing the evidence. The syntax changes, but
the security questions stay familiar: who is the identity, what resource is protected, who can use it,
what audit trail exists, and what would a defender change?
