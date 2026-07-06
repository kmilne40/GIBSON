## Chapter 13. FTP, TCP/IP and
### Network Enumeration
### This section covers NETSTAT, PING, TRACERTE, FTP client behaviour and service discovery
boundaries.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv


<!-- page 147 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Operational model
This network chapter starts with listeners and connections, then moves to FTP and enumeration
tools. The operational model is service-facing: open ports identify where a learner can connect and
which subsystem answers.
### Security relevance
The security value is attack-surface mapping. A defender should be able to explain why each
listener exists, who can reach it and what telemetry a connection creates.
### Commands and features in scope
### Subsystem Command Syntax Evidence
TCP/IP NETSTAT NETSTAT HOME|CONN|ALL|
DEVLINKS|ROUTE|ARP|
PORTLIST|TELNET|FTP.
gibson/apps/tso.py
LEGACY_HELP
### TCP/IP PING PING host - simulated z/OS
TCP/IP ping.
gibson/apps/tso.py
LEGACY_HELP
### TCP/IP TRACERTE TRACERTE host - simulated
z/OS traceroute.
gibson/apps/tso.py
LEGACY_HELP
FTP client FTP FTP host [port] - enters the
z/OS style FTP client
subcommand environment.
gibson/apps/tso.py
LEGACY_HELP
### Section labs
### Lab 20: Enumerate simulator TCP/IP listeners
### Command context
Start from: TSO READY for NETSTAT/PING or Linux host shell for nmap-sim/nc checks
Commands run from: The context stated beside each command
Do not run these from: ISPF editor or CICS
Why context matters: Network commands can be host-side tools or simulated TSO commands; the
manual must keep them separate.
### Why this lab matters
In this lab we’ll use Gibson to practise a first-pass TCP/IP listener review. On a real z/OS system,
open ports tell you which subsystems are reachable: TN3270 for terminal access, FTP for file and
JES workflows, DRDA for Db2, CICS web interfaces, REST services, NJE and sometimes site-specific
high ports. From a tester’s point of view, this is where the attack surface starts to become concrete.
From a defender’s point of view, it is also where you should be able to explain why each listener
exists, who can reach it, and what evidence a connection creates.
### What the commands do


<!-- page 148 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
NETSTAT CONN: shows connection/session-oriented network state. It answers who is connected
rather than merely what is listening.
PING 127.0.0.1: checks basic IP reachability to the local host. In this simulator it proves the network
command path before deeper enumeration.
TRACERTE 127.0.0.1: shows route/path behaviour. Against localhost it is simple by design; the point
is command-path validation.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
### NETSTAT PORTLIST
### NETSTAT CONN
### PING 127.0.0.1
### TRACERTE 127.0.0.1
### What the output tells us
At this point, you should have evidence of the simulated listeners, any current connections and
whether the basic TCP/IP command path is alive. The useful part is not simply that the commands
ran. The useful part is that you can now explain which services Gibson is presenting to the learner
and which ones would matter during a real assessment.
### On a real z/OS system
On a real z/OS system, this type of review would normally be paired with TCP/IP profile review,
SERVAUTH/NETACCESS checks, firewall scope, SMF records, daemon logs and subsystem-specific
evidence. An unexpected listener is not automatically a vulnerability, but it is always a question:
who started it, who can reach it, what data crosses it, and how is it monitored?
### Defensive takeaway
Defenders should be able to baseline expected listeners and alert on changes, especially high ports
or services that appear outside an approved change window. In Gibson, this connects directly to
the Master Console and OPERLOG/event-stream labs, where logon and high-port activity become
visible training evidence.
### Troubleshooting
If a listener is missing, confirm the service was started and that the selected runtime profile
enables it.
### Instructor note
Ask students to translate every listening port into a subsystem hypothesis and a defender question.
This keeps scanning from becoming a screenshot exercise.
### Cleanup


<!-- page 149 -->

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
### PING 127.0.0.1 Interrogates the
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
### TRACERTE 127.0.0.1 Interrogates the
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
### Difficulty Beginner
### Estimated time 30 minutes
Objective Use NETSTAT, PING and TRACERTE to build a network map.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 21: Enter z/OS-style FTP client environment
### Command context
Start from: FTP session after connecting from host or Gibson FTP client context
Commands run from: ftp> prompt; JES review happens after leaving FTP or in SDSF


<!-- page 150 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Do not run these from: TSO READY unless invoking FTP itself
Why context matters: SITE, PUT, STOR and GET are FTP subcommands; SDSF is a separate review
context.
### Why this lab matters
In this lab we’ll work through enter z/os-style ftp client environment as a practical evidence
exercise, not as a command checklist. The concept being taught is host file transfer and JES-style
workflows. From a tester’s point of view, the aim is to produce a specific piece of evidence: FTP
banner, connection state or transfer prompt. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
FTP 127.0.0.1 2111: starts the z/OS-style FTP client workflow against the simulator FTP listener.
### Starting state
Start with the FTP listener enabled and Gibson running. Confirm port 2111 is listening before
opening the client path.
### Lab steps
### FTP 127.0.0.1 2111
### What the output tells us
For `FTP 127.0.0.1 2111`, identify the exact returned line, return code, panel state or dataset change
that proves the lab objective. If that item is not present, pause and troubleshoot the current
command context before continuing.
### On a real z/OS system
z/OS FTP can transfer USS files and MVS datasets and, where configured, can interact with JES.
IND$FILE-style transfers are common in 3270 environments.
### Defensive takeaway
Monitor file transfers, JES mode usage and movement of JCL or data extracts. FTP is often a bridge
between workstation and host.
### Troubleshooting
If FTP fails, check port, credentials/session state, filetype mode and whether the simulator service is
enabled.
### Instructor note
Teach enter z/os-style ftp client environment by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup


<!-- page 151 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### FTP 127.0.0.1 2111 Opens the simulated
### FTP client/server
workflow.
### The host and port select
the target listener.
### FTP is historically
common on z/OS and
matters because it can
move files or submit
### JES jobs depending on
configuration.
### Evidence is an FTP
banner, login prompt
or session response.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Identify FTP client syntax and discuss FTP/JES/SQL mode
boundaries.
Prerequisites FTP service configured.
Validation Source validated; interactive FTP service required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
