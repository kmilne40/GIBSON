## Chapter 5. TSO READY
### Reference
### This section covers READY prompt behaviour and all TSO-facing commands, including command
syntax, expected outputs and security relevance.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
### The READY prompt is the command processor context for many RACF, catalog, network and JES
actions. In Gibson, READY is where command dispatch becomes explicit; inside ISPF you must use
option 6 or return to READY for the same class of commands.


<!-- page 56 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is command authority. READY commands can reveal identities, datasets, profiles
and jobs, so students must learn both what the command returns and what a real system would log
or restrict.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### ISPF launcher START Launches the ISPF menu. gibson/apps/tso.py
LEGACY_HELP
### ISPF launcher ISPF Launches the ISPF menu. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY EXIT Exits the session. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LOGOFF Logs off the current user. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY CONSOLE Enters the system console
mode (SPECIAL only).
gibson/apps/tso.py
LEGACY_HELP
### SDSF launcher SDSF Displays the SDSF screen. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY IPLINFO Restricted command. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LISTCAT LEVEL(SYS1) Lists SYS1 level files. gibson/apps/tso.py
LEGACY_HELP
TSO/READY SEND Sends a message. Format:
SEND 'message'
USER(username) NOW|
LOGON.
gibson/apps/tso.py
LEGACY_HELP
### TSO/READY EDIT Edits a data set or member. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY REXX Executes a REXX script. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LISTCAT Lists files in your catalog. gibson/apps/tso.py
LEGACY_HELP
This section has 29 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 05: Baseline READY commands
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step


<!-- page 57 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through baseline ready commands as a practical evidence exercise, not as a
command checklist. The concept being taught is TSO READY command context and simulator
boundary. From a tester’s point of view, the aim is to produce a specific piece of evidence: help
text, catalog view, network view or command response at READY. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
LISTDS IBMUSER.JCL.LAB: looks up a specific dataset-like object. It turns catalog discovery into a
targeted question: does this training dataset exist and can the current context see it?
SESSIONSTATS: summarises the current simulator session. It helps students separate command
output from session-level evidence.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### LISTDS IBMUSER.JCL.LAB
### SESSIONSTATS
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.


<!-- page 58 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
### Teach baseline ready commands by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
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
### LISTCAT Lists cataloged data
sets known to the
simulator.
### A high-level qualifier
may narrow results
where implemented.
### Catalog enumeration
tells you what objects
exist before you test
RACF or edit paths.
### Evidence is a list of
data set names and
attributes.
### LISTDS
### IBMUSER.JCL.LAB
### Displays simulated data
set information.
### The data set name
selects the object to
inspect.
### Data set visibility helps
you decide what can be
read, edited, submitted
or protected.
### Evidence is data set
metadata or content
availability.
### SESSIONSTATS Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Run safe READY commands and interpret output.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 59 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
