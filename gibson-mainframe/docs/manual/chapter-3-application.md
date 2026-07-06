## Chapter 3. Application
### Architecture Deep Dive
This section maps Gibson internals: CLI, configuration, runtime state, command dispatch, RACF
stores, dataset access, REST services, dashboard and security features.
### Implementation evidence
### Area Source evidence
### CLI / startup gibson/cli.py
### Configuration gibson/core/config.py


<!-- page 50 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Runtime state gibson/core/state.py
### TSO command processor gibson/apps/tso.py
RACF dynamic store gibson/core/racf_dynamic.py
### Dataset catalog gibson/core/datasets.py
### Operational model
This architecture chapter maps user-facing commands to handlers, state stores, panels and routes.
### The point is to understand which layer answers a command before interpreting output as
evidence.
### Security relevance
The security value is traceability. Attackers and testers follow command surfaces; defenders follow
the same path in reverse to understand what component should have authenticated, authorised,
logged or rejected the action.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 03: Trace a READY command to implementation
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through trace a ready command to implementation as a practical evidence
exercise, not as a command checklist. The concept being taught is TSO READY command context
and simulator boundary. From a tester’s point of view, the aim is to produce a specific piece of
evidence: help text, catalog view, network view or command response at READY. From a defender’s
point of view, the same evidence explains what should be controlled, logged or challenged before
the activity becomes normalised. By the end of the lab, you should be able to say why each
command was used and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.


<!-- page 51 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
LISTUSER IBMUSER: queries the simulated RACF profile for IBMUSER. It is an identity enumeration
step: attributes and account state can change the whole assessment path.
NETSTAT CONN: shows connection/session-oriented network state. It answers who is connected
rather than merely what is listening.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTUSER IBMUSER
### NETSTAT CONN
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
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach trace a ready command to implementation by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
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
### A command name after
### HELP narrows the
output where
### Help is safe
enumeration. It tells
you what the simulator
### Evidence is a command
list or help panel that
can be compared with


<!-- page 52 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
context. implemented. exposes without
changing state.
the command
appendix.
### LISTUSER IBMUSER Displays a simulated
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
### NETSTAT CONN Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Trace HELP, LISTUSER and NETSTAT from command matrix to
handler evidence.
Prerequisites Phase 1 command matrix.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
