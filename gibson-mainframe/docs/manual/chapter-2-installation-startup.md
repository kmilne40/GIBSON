## Chapter 2. Installation, Startup,
### IPL, and Operations
This section explains package operation from a code-derived perspective: entry points,
configuration, startup flags, default ports, optional services, state creation and reset behaviour.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This startup chapter follows the host, container, service and console path from installation to a
listening training system. The operational model is not abstract: scripts prepare the environment,
services bind to ports, the console receives WTORs, and readiness is proven through health checks.
### Security relevance
The security value is knowing when the platform is really ready and what startup choices changed
its posture. A defender would care about startup replies, enabled services, open ports and whether
secure or vulnerable mode was selected.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 02: Verify ports and service model
### Command context
Start from: TSO READY for NETSTAT/PING or Linux host shell for nmap-sim/nc checks
Commands run from: The context stated beside each command
Do not run these from: ISPF editor or CICS
Why context matters: Network commands can be host-side tools or simulated TSO commands; the
manual must keep them separate.


<!-- page 48 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll work through verify ports and service model as a practical evidence exercise, not
as a command checklist. The concept being taught is TCP/IP listener and connection enumeration.
From a tester’s point of view, the aim is to produce a specific piece of evidence: listener list, active
connection list, ping/traceroute response or service display. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
D SVC,L: displays service-related information in the simulator, giving an operator-style view of
active services and service definitions.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
### NETSTAT PORTLIST
### D SVC,L
### What the output tells us
For `NETSTAT PORTLIST`, confirm the listener list and port/service names. The evidence is the
exposed service map, which is what a tester uses for attack-surface planning and a defender uses
for baselining.
### On a real z/OS system
z/OS Communications Server provides commands such as NETSTAT, PING and TRACERTE for
network monitoring. Open ports should be interpreted with subsystem ownership and network
controls such as SERVAUTH/NETACCESS.
### Defensive takeaway
Baseline listeners and alert on unexpected high ports, new services or sessions from unusual
sources.
### Troubleshooting
If a listener is missing, confirm the service was started and that the selected runtime profile
enables it.
### Instructor note
Ask students to translate every listening port into a subsystem hypothesis and a defender question.
This keeps scanning from becoming a screenshot exercise.
### Cleanup


<!-- page 49 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### NETSTAT PORTLIST Interrogates the
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
### D SVC,L Displays simulated
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
### Difficulty Beginner
### Estimated time 30 minutes
### Objective Map default ports to simulator subsystems and identify
optional web-terminal behaviour.
Prerequisites Fresh package and service matrix.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
