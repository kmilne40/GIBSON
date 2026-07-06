## Chapter 4. Access, Logon, MFA,
and VTAM
This section documents access paths, logon flow, PIN + HHMM MFA behaviour, optional services
and authentication-related alerts.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv


<!-- page 53 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Operational model
This access chapter follows a session from the front-door application choice into TSO, CICS, Db2 or
MFA-protected flows. The operational model is session-driven: what you can type depends on
where the logon path placed you.
### Security relevance
The security value is identity assurance. Students should watch for accepted APPLIDs, failed
credentials, MFA state and logon alerts, because those are the same clues a defender would use to
separate normal access from probing.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 04: Review MFA and user state
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through review mfa and user state as a practical evidence exercise, not as a
command checklist. The concept being taught is identity, class, profile and authority analysis. From
a tester’s point of view, the aim is to produce a specific piece of evidence: user attributes, profile
class, UACC, access list, WARNING or audit fields. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do
MFA STATUS: shows the simulator MFA state. It proves whether the authentication layer is active
before students test logon or PassTicket behaviour.
LISTUSER IBMUSER ALL: asks for the fuller identity view. In a real RACF workflow, the ALL-style
view is where default group, attributes, revoke/protected state and audit-relevant details become
visible.


<!-- page 54 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
UADS LIST: lists legacy-style user/session data in Gibson. Its teaching value is to compare modern
RACF/MFA thinking with older TSO account concepts.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### MFA STATUS
### LISTUSER IBMUSER ALL
### UADS LIST
### What the output tells us
For `MFA STATUS`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
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
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### MFA STATUS Displays or manages
Gibson’s simulated
MFA posture.
### STATUS reports
global/user state;
### ENROLL/VERIFY/RESET
change or test MFA
state where
### MFA is part of the
logon control path. A
tester cares because
weak recovery or
bypass paths matter as
### Evidence is MFA status
or a verification result.


<!-- page 55 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
implemented. much as the password.
### LISTUSER IBMUSER
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
### UADS LIST Inspects simulated
legacy TSO user
attribute data.
### LIST reports the legacy-
style inventory.
### Legacy identity stores
are useful because
older controls can
remain in place beside
RACF-style logic.
### Evidence is a user/state
listing.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Determine MFA global state and user-specific segment status.
Prerequisites IBMUSER access.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
