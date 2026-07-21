## Chapter 9. Master Console and
### OPERLOG
This section covers WTOR replies, IPL replies, service control, security displays, console metrics
and alert/OPERLOG workflows.
### Implementation evidence
### Area Source evidence
Master Console gibson/apps/master_console.py
Console events gibson/apps/master_console_events.py
### Operational model
The Master Console chapter is about operator evidence: WTORs, display commands, service state,
alerts and OPERLOG-style messages. It is the place to prove whether a system action reached the
console path and whether an operator response changed simulator progress.


<!-- page 120 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is defensive visibility. Logons, high-port listeners, ICSF refreshes and startup
replies should be visible operational events, not silent background details.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### Master Console R nn,reply R 01,CLPA or R nn,reply gibson/apps/
master_console.py:397
Master Console D R,L / D R,R D R,L | D R,R gibson/apps/
master_console.py:407
### Master Console D SVC,L / DISPLAY SERVICES D SVC,L gibson/apps/
master_console.py:415
### Master Console D A,L D A,L gibson/apps/
master_console.py:420
### Master Console D
### CPU/MEMORY/DASD/IPLINFO
D CPU|D MEMORY|D DASD|D
### IPLINFO
gibson/apps/
master_console.py:372
Master Console D SECURITY,RARE|DAILY|
WEEKLY|MONTHLY
### D SECURITY,period gibson/apps/
master_console.py:383
Master Console D ICSF / F ICSF,... D ICSF | F ICSF,REFRESH,... gibson/apps/
master_console.py:397
Master Console S/START service S service | START service gibson/apps/
master_console.py:434
### Master Console P/STOP/PAUSE/RESUME
service
P service | STOP service |
PAUSE service | RESUME
service
gibson/apps/
master_console.py:441
### Section labs
### Lab 12: Review console metrics and security summary commands
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through review console metrics and security summary commands as a
practical evidence exercise, not as a command checklist. The concept being taught is operator
console, event stream and system-state evidence. From a tester’s point of view, the aim is to
produce a specific piece of evidence: console display output, WTOR state, event line or security


<!-- page 121 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
summary. From a defender’s point of view, the same evidence explains what should be controlled,
logged or challenged before the activity becomes normalised. By the end of the lab, you should be
able to say why each command was used and what changed in your understanding of the Gibson
environment.
### What the commands do
D CPU: shows CPU/system state in the simulator console model.
D MEMORY: shows memory/resource state in the console model.
D DASD: shows disk/storage state in the console model.
D SECURITY,DAILY: shows the simulator security summary view. Its value is tying technical actions
to security reporting.
D R,L: displays outstanding replies/WTOR-like prompts. It is the evidence source before replying to
IPL prompts.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
D CPU
### D MEMORY
### D DASD
### D SECURITY,DAILY
D R,L
### What the output tells us
For `D CPU`, confirm the console response and any follow-on OPERLOG line. Console commands
matter because they show whether an operator-path action was accepted, rejected or left
outstanding.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
Teach review console metrics and security summary commands by asking students to explain the
purpose of each command before they run it and then identify the exact field, line or state change
that proves the point of the lab.


<!-- page 122 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### D CPU Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D MEMORY Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D DASD Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D SECURITY,DAILY Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D R,L Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Intermediate
### Estimated time 40 minutes
### Objective Use Master Console display commands to review simulated IPL,
activity and security summaries.
Prerequisites Master Console access.


<!-- page 123 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Validation Source validated; command handlers identified
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 13: Respond to IPL WTOR
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through respond to ipl wtor as a practical evidence exercise, not as a
command checklist. The concept being taught is operator console, event stream and system-state
evidence. From a tester’s point of view, the aim is to produce a specific piece of evidence: console
display output, WTOR state, event line or security summary. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
R 01,CLPA: replies to WTOR 01 with CLPA, modelling an IPL/startup operator response. This
changes system progress and must be understood before using the console.
D R,R: reviews outstanding replies after the response so students can prove the prompt was
handled.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
### R 01,CLPA
D R,R
### What the output tells us
For `R 01,CLPA`, confirm that the CLPA reply is accepted and the IPL WTOR sequence advances.
That is operator evidence: the system progressed because the expected reply was given.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.


<!-- page 124 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
Teach respond to ipl wtor by asking students to explain the purpose of each command before they
run it and then identify the exact field, line or state change that proves the point of the lab.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### R 01,CLPA Responds to a
simulated write-to-
operator-with-reply
prompt.
### The reply number and
response text pair the
command with the
outstanding request.
### WTOR handling is
operator control-plane
work. Bad replies can
change IPL or system
behaviour.
### Evidence is the cleared
request or continuation
message.
### D R,R Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Understand the IPL WTOR reply workflow and use R 01,CLPA
safely.
Prerequisites Console state at IPL prompt.
Validation Source validated; depends on console lifecycle
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 125 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### WTOR IPL and MFA Reply Sequence
The Master Console IPL flow now needs to show the complete reply contract because this is where
students see operator control and MFA setup meet. In Gibson, the IPL sequence is deliberately
explicit: reply 01 supplies CLPA, reply 02 continues the operator/user prompt, reply 03 answers the
MFA enablement question, and reply 04 sets the four-digit PIN used with the current HHMM token.
### Reply Meaning in Gibson What to watch for Security relevance
### R 01,CLPA Responds to the CLPA
### IPL WTOR and allows
startup to progress
### Console confirmation
and next outstanding
reply
### Shows operator IPL
control and must be
logged
### R 02,U Responds to the
second startup WTOR
in the Gibson IPL
contract
### Next prompt appears
rather than dropping
to terminal
### Teaches that IPL is a
sequence, not a single
command
### R 03,Y Enables MFA PIN
initialization for this
IPL
### MFAPIN WTOR
appears
### MFA setup is an
operational security
decision
### R 04,1357 Defines the 4-digit
MFA PIN; use your
chosen PIN, not
necessarily 1357
### MFA token becomes
PIN+HHMM
### PIN should not be
echoed or logged;
token is time-bound
### Example startup reply flow
### R 01,CLPA
### R 02,U
### R 03,Y
### R 04,1357
After this sequence, an MFA-protected logon uses the configured four-digit PIN followed by the
current host HHMM value. For example, if the PIN is 1357 and the host time is 09:42, the training
token is 13570942. On a real system, MFA product behaviour is site-specific, but the operational
principle is the same: startup security choices should be controlled, logged and recoverable.
