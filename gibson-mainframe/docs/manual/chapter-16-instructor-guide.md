## Chapter 16. Instructor Guide
and Assessment
This section provides course flow, timing, reset points, demo sequencing, capstone tasks and
answer-key guidance.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This instructor chapter turns Gibson features into teachable sequences. The operational model is
facilitation: set the state, run the workflow, ask what changed, and make students explain the
evidence.
### Security relevance
The security value is assessment quality. A good class does not reward command completion; it
rewards correct interpretation, safe boundaries and defensible reporting.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 26: Run a capstone readiness check
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed


<!-- page 183 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through run a capstone readiness check as a practical evidence exercise, not
as a command checklist. The concept being taught is TSO READY command context and simulator
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
MFA STATUS: shows the simulator MFA state. It proves whether the authentication layer is active
before students test logon or PassTicket behaviour.
JES STATUS: summarises the simulated job-entry environment. It is the starting point before
creating or browsing job output.
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
PTKTSTAT: shows PassTicket-related simulator state from the TSO/command side.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### MFA STATUS
### JES STATUS
### NETSTAT PORTLIST
### PTKTSTAT
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.


<!-- page 184 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach run a capstone readiness check by asking students to explain the purpose of each command
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
### MFA STATUS Displays or manages
Gibson’s simulated
MFA posture.
### STATUS reports
global/user state;
### ENROLL/VERIFY/RESET
change or test MFA
state where
implemented.
### MFA is part of the
logon control path. A
tester cares because
weak recovery or
bypass paths matter as
much as the password.
### Evidence is MFA status
or a verification result.
### JES STATUS Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
where implemented.
### SDSF is where job
status and output
become evidence. It is
also where credentials
and system messages
often leak.
### Evidence is a job list,
output panel or JES
state summary.
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
### PTKTSTAT Inspects or exercises APPL() or endpoint PassTickets remove Evidence is a


<!-- page 185 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
simulated PassTicket
behaviour.
parameters select the
application and ticket
operation where
implemented.
reusable password
transmission, but weak
setup or replay
windows become
security findings.
generated, accepted,
rejected or listed ticket
state.
### Field Value
### Difficulty Advanced
### Estimated time 60 minutes
### Objective Verify lab prerequisites, services, seeded data and known gaps
before class delivery.
Prerequisites Fresh lab environment.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 186 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix A. Command
### Reference by Execution Context
### Use this appendix when you know what you are trying to test but cannot remember where the
command belongs. Mainframe commands are context-sensitive. LISTUSER belongs at READY or
ISPF option 6. SAVE belongs inside the ISPF editor. SITE FILETYPE=JES belongs inside FTP. Mixing
those contexts is one of the fastest ways to confuse yourself, so this appendix is organised by where
the command actually runs.
### A.1 Gibson host and runtime commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.2 Connection commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
nc 127.0.0.1
2023
### Linux host
shell
nc 127.0.0.1
2023
### Connects to
the
simulator
terminal
service as a
raw TCP
client.
### Banner/
front-door
prompt;
simple text
response.
### Proves the
service is
reachable
but not full
3270
behaviour.
### A raw TCP
test, not a
normal
3270
terminal
session.
### QS-3 Read-only
connection
c3270
127.0.0.1:20
23
### Linux host
shell
c3270
127.0.0.1:20
23
### Opens a
3270
terminal
emulator to
the training
service.
3270/logon
panel or
front-door
screen.
### Correct
client for
### ISPF/CICS-
style
workflows.
### TN3270/
### TN3270E
client
access to
VTAM apps.
### QS-4 Session
state
### A.3 VTAM/front-door commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### L TSO VTAM/
front-door
prompt
### L TSO Selects the
simulated
TSO
### TSO logon
prompt or
READY
### Moves from
application
selection to
VTAM
### APPLID
selection/lo
### QS-7 Session
transition


<!-- page 187 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
application. path. user
command
environme
nt.
gon.
### A.4 TSO READY commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### ISPF TSO READY ISPF Launches
the ISPF
panel
environme
nt.
ISPF
primary
menu
appears.
### After this,
READY
commands
need option
6 or exit to
READY.
### ISPF dialog
manager.
### Lab 09 Session
transition
### LISTCAT TSO READY
or ISPF
option 6
### LISTCAT
### LVL(userid)
Lists
catalog
entries
matching a
level.
### Datasets
under the
HLQ;
missing
dataset
evidence.
### Dataset
discovery
and lab
prerequisit
e checking.
### Catalog
search via
### TSO/E/IDCA
### MS-type
facilities.
### Lab 09 Read-only
### LISTUSER TSO READY
or ISPF
option 6
### LISTUSER
userid
### Displays a
### RACF-style
user
profile.
### Attributes,
default
group,
revoke
state, last
access.
### Identifies
privileged,
stale or
usable
accounts.
### RACF user
profile
display.
### RACF labs Read-only
### SEARCH
ALL
### WARNING
### NOMASK
### TSO READY
or ISPF
option 6
### SEARCH
ALL
### WARNING
### NOMASK
Finds
profiles in
### WARNING
mode
where
supported.
### Profiles
that warn
rather than
fully deny.
### A classic
mainframe
security
finding:
logged
violation
but allowed
access.
RACF
### SEARCH
against
active
profiles.
### WARNING
mode lab
### Read-only
discovery
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
### TSO READY
or ISPF
option 6
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
Finds
### SURROGAT
submit-as
resources.
userid.SUB
### MIT style
resource
names.
### Identifies
potential
batch
impersonat
ion paths.
RACF
### SURROGAT
class profile
discovery.
### SURROGAT
lab
### Read-only
discovery
RLIST
### SURROGAT
profile ALL
### TSO READY
or ISPF
option 6
RLIST
### SURROGAT
### IBMUSER.S
### UBMIT ALL
### Inspects a
specific
### SURROGAT
resource.
UACC,
owner and
permitted
users/group
s.
### Shows who
may submit
jobs as
another
user.
RACF
resource
profile
listing.
### SURROGAT
lab
### Read-only
### A.5 RACF commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### LISTUSER TSO READY
or ISPF
### LISTUSER
userid
### Displays a
### RACF-style
### Attributes,
default
### Identifies
privileged,
### RACF user
profile
### RACF labs Read-only


<!-- page 188 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
option 6 user
profile.
group,
revoke
state, last
access.
stale or
usable
accounts.
display.
### SEARCH
ALL
### WARNING
### NOMASK
### TSO READY
or ISPF
option 6
### SEARCH
ALL
### WARNING
### NOMASK
Finds
profiles in
### WARNING
mode
where
supported.
### Profiles
that warn
rather than
fully deny.
### A classic
mainframe
security
finding:
logged
violation
but allowed
access.
RACF
### SEARCH
against
active
profiles.
### WARNING
mode lab
### Read-only
discovery
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
### TSO READY
or ISPF
option 6
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
Finds
### SURROGAT
submit-as
resources.
userid.SUB
### MIT style
resource
names.
### Identifies
potential
batch
impersonat
ion paths.
RACF
### SURROGAT
class profile
discovery.
### SURROGAT
lab
### Read-only
discovery
RLIST
### SURROGAT
profile ALL
### TSO READY
or ISPF
option 6
RLIST
### SURROGAT
### IBMUSER.S
### UBMIT ALL
### Inspects a
specific
### SURROGAT
resource.
UACC,
owner and
permitted
users/group
s.
### Shows who
may submit
jobs as
another
user.
RACF
resource
profile
listing.
### SURROGAT
lab
### Read-only
### A.6 USS/OMVS commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
cp
"//'HLQ.DAT
A'" file.txt
### OMVS/USS
shell
cp
"//'HLQ.DAT
A'" file.txt
### Copies an
MVS
dataset into
a USS file
where
supported.
### Created
USS file;
content
visible with
cat.
Shows
movement
between
dataset
world and
UNIX
world.
z/OS UNIX
MVS
dataset
pathname
support /
### OCOPY/OPU
T
equivalents
.
### USS copy
lab
### May create
file
### Syntax Direction Run From What It Does What To
### Watch For
### Real z/OS
### Equivalent
### Security
### Relevance
cp source.txt
target.txt
### USS file to USS
file
### OMVS/USS shell Copies text
from a USS file
in the
simulated USS
tree to another
USS path.
### Returns no
output on
success.
cp: <source>:
unsupported
source when
source is absent
or a directory.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18A
cp
"//'IBMUSER.TE
ST.DATA'"
sample.txt
### MVS dataset to
### USS file
### OMVS/USS shell Reads the
simulated MVS
dataset/membe
r through
dataset services
and writes the
content into a
cp: <source>:
data set not
found; cp:
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
### Add Lab 18B


<!-- page 189 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
USS file. considerations).
cp from_uss.txt
"//'IBMUSER.TE
ST.COPY'"
### USS file to MVS
dataset
### OMVS/USS shell Reads the USS
file and writes
content into the
target MVS
dataset name.
unsupported
source if the
### USS path is
absent or a
directory;
permission
denied if
dataset write is
blocked.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18C
cp
"//'IBMUSER.A.D
ATA'"
"//'IBMUSER.B.D
ATA'"
### MVS dataset to
### MVS dataset
### OMVS/USS shell Reads one
simulated
dataset/membe
r and writes an
identical target
dataset/membe
r.
data set not
found;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document and
include in
reference;
optional lab
step.
cp
"//'IBMUSER.PD
S.CODE(TIME)'"
member.txt
### PDS/PDSE
member to USS
file
### OMVS/USS shell Reads the
named member
and writes a
USS file.
data set not
found if
member does
not exist.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18D
Updated coverage: USS/OMVS cp supports USS-to-USS, MVS-to-USS, USS-to-MVS, MVS-to-MVS and
### PDS/PDSE member copy patterns where the operands are supported by Gibson. Run these only
from the OMVS/USS shell.
### A.7 ISPF navigation commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
=6 ISPF
primary
menu
=6 Jumps to
the ISPF
command
shell/panel
for TSO
commands.
A TSO
command
entry
panel.
### Correct
way to run
### TSO/RACF
commands
once inside
ISPF.
### ISPF option
6.
### Lab 09,
### RACF labs
Panel
transition
### A.8 ISPF editor primary commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### SAVE ISPF editor
command
line
### SAVE Saves the
current edit
buffer.
### Member/
data set
content
persists
after
leaving
editor.
### Edit access
to
### JCL/REXX/c
onfig is
security-
sensitive.
### ISPF Edit
SAVE.
### ISPF edit
lab
### State-
changing


<!-- page 190 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Primary
### Command /
### Feature
### Syntax Run From What It Does What To
### Look For
### Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### SAVE SAVE ISPF editor
### Command
===> or PF
key
### Writes editor
buffer to the
target
dataset/mem
ber and
remains in
the editor
with DATA
SAVED.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
### END / PF3 /
F3
### END or PF3 ISPF editor
### Command
===> or PF
key
### Exits the
editor if data
is clean. If
data is dirty,
### Gibson
prompts to
SAVE,
### CANCEL or
END again.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A/09B
### CANCEL /
### CAN / PF12 /
F12
### CANCEL or
PF12
### ISPF editor
### Command
===> or PF
key
### Restores the
original lines
and exits
without
saving the
edit buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09B
### HELP / PF1 /
F1
### HELP ISPF editor
### Command
===> or PF
key
### Displays
available
primary and
focus
commands.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### FIND / F FIND string ISPF editor
### Command
===> or PF
key
### Searches for
a string and
positions the
cursor on a
match.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### RFIND RFIND ISPF editor
### Command
### Repeats the
previous
### INVALID
EDIT
### Source-
backed in
### ISPF edit
primary
### Lab 09C


<!-- page 191 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
===> or PF
key
### FIND. COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Gibson editor command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### CHANGE / C CHANGE old
new [ALL]
### ISPF editor
### Command
===> or PF
key
### Changes the
next or all
matching
strings,
depending on
ALL.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### RCHANGE RCHANGE ISPF editor
### Command
===> or PF
key
### Repeats the
previous
CHANGE.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### TOP TOP ISPF editor
### Command
===> or PF
key
### Moves the
view to the
top of data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### BOTTOM /
BOT
### BOTTOM ISPF editor
### Command
===> or PF
key
### Moves the
view to the
bottom of
data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### LOCATE / L LOCATE n or
### LOCATE text
### ISPF editor
### Command
===> or PF
key
### Locates a line
number or
searches for
text.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 192 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BROWSE/VIE
### W as appli
CAPS CAPS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
upper-case
normalizatio
n in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
HEX HEX ON|OFF ISPF editor
### Command
===> or PF
key
### Toggles
### Gibson hex
display state
message.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RECOVERY /
### RECOVER
### RECOVERY
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
recovery
state in the
editor profile.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### AUTOSAVE AUTOSAVE
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
autosave
state in
profile; SAVE
remains
explicit in
labs.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
NULLS NULLS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles null
display/profil
e state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
TABS TABS ON|
OFF
### ISPF editor
### Command
===> or PF
### Toggles tab
profile state.
### INVALID
EDIT
### COMMAND,
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
### Lab 09E


<!-- page 193 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
key NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
ofile/key
concept; see
### IBM ISPF Edit
docs
### PROFILE PROFILE ISPF editor
### Command
===> or PF
key
### Displays
editor profile
settings:
### RECOVERY,
### CAPS, NULLS,
TABS,
### AUTOSAVE
and HEX.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RESET RESET /
### RESET X /
RESET
### EXCLUDED
### ISPF editor
### Command
===> or PF
key
### Clears
excluded line
state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
CUT CUT [start
[end]]
### ISPF editor
### Command
===> or PF
key
### Cuts current
or numbered
range into
copy buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
PASTE PASTE [line]
[BEFORE]
### ISPF editor
### Command
===> or PF
key
### Pastes copy
buffer after
line or before
line when
### BEFORE is
specified.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### EXCLUDE EXCLUDE
ALL |
EXCLUDE n |
### EXCLUDE
string
### ISPF editor
### Command
===> or PF
key
### Excludes
matching
lines or
numeric line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 194 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### W as appli
### SUB / SUBMIT SUB or
### SUBMIT
### ISPF editor
### Command
===> or PF
key
### Submits
current
editor text as
### JCL via
configured
submitter if
available.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09F
### LINE / LC /
### LINECMD /
LN
### LINE, LC, LN
or LC n
command
### ISPF editor
### Command
===> or PF
key
### Moves focus
to line-
command
area or
executes
explicit line
command for
a numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09D
### TEXT / TXT /
DATA
### TEXT, TEXT n
text, or n text
### ISPF editor
### Command
===> or PF
key
### Moves focus
to text area
or replaces a
numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
~ ~ ISPF editor
### Command
===> or PF
key
### Moves focus
back to the
command
field.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### TAB TAB key ISPF editor
### Command
===> or PF
key
### Cycles
between
command,
line-
command
and text
fields in the
interactive
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### PF7/PF8 PF7/PF8 ISPF editor
### Command
===> or PF
key
### Pages up and
down in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
### Reference


<!-- page 195 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
concept; see
### IBM ISPF Edit
docs
Updated coverage: primary commands are editor commands. They are not TSO READY commands.
### A.9 ISPF editor line commands
The commands in this context are covered in the grouped tables and lab-specific context blocks.
Use the Command-to-Lab index when you need the teaching path rather than a raw command list.
Line
### Command
### Syntax Type What It
Does
### Target
Required?
### Example Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### I I or In line
command
### Inserts one
or n blank
lines at the
target line.
### No I Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### D D or Dn line
command
### Deletes one
or n lines.
### No D Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### DD DD ... DD block line
command
### Deletes a
marked
block of
lines.
### Second
marker
### DD Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### C C or Cn line
command
### Copies one
or n lines
into the
buffer.
### Requires
### A/B/P to
place.
### No C Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### CC CC ... CC block line
command
### Copies a
marked
block into
the buffer.
### Second
marker
### CC Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### M M or Mn line
command
### Moves one
or n lines
into the
buffer by
removing
them from
source.
### Requires
### A/B/P to
place.
### No M Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### MM MM ... MM block line
command
### Moves a
marked
block into
the buffer.
### Second
marker
### MM Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D


<!-- page 196 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### A A or An target line
command
### Places
copied/mov
ed lines
after the
target line.
### Yes A Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### B B or Bn target line
command
### Places
copied/mov
ed lines
before the
target line.
### Yes B Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### P P or Pn target line
command
### Places
copied/mov
ed lines
after the
target line;
### Gibson
synonym
for paste
target.
### Yes P Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### R R or Rn line
command
### Repeats
one line n
times.
### No R Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### RR RR ... RR block line
command
### Repeats a
marked
block of
lines.
### Second
marker
### RR Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### X X or Xn line
command
### Excludes
one or n
lines from
display.
### No X Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### XX XX ... XX block line
command
### Excludes a
marked
block of
lines.
### Second
marker
### XX Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### O O or On line
command
### Marks one
or n lines
as overlay
source.
### No O Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### OO OO ... OO block line
command
### Marks a
block as
overlay
source.
### Second
marker
### OO Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### S/F/L show-
excluded
### S/F/L real ISPF
line
commands
Not
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
only.
### No S/F/L No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab
shift (, ), <, > real ISPF Not No (, No - real Real ISPF No lab


<!-- page 197 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
commands
((, )), <, >
line
commands
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
only.
### ISPF only equivalent
or marked
real-only
Updated coverage: line commands are entered in the left line-command area, or through Gibson
terminal fallbacks such as LC n command.
### A.10 SDSF/JES commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### ST SDSF panel ST Displays
jobs/status
in SDSF
where
implement
ed.
### Job list,
owner,
status and
return
code.
Spool
output
often
contains
sensitive
evidence.
### SDSF Status
panel.
### SDSF lab Read-only
unless line
actions
change
state
### A.11 FTP/JES commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
SITE
FILETYPE=J
ES
### FTP session QUOTE
SITE
FILETYPE=J
ES
### Switches
z/OS FTP to
### JES mode
where
implement
ed.
### FTP server
accepts jobs
as internal
reader
input.
File
transfer
can become
job
execution.
z/OS FTP
SITE
FILETYPE=J
ES.
### FTP/JES lab Changes
### FTP mode
### A.12 CICS transactions and commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs Linux host ./ Installs Successful Build Linux QS-1 State-


<!-- page 198 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
on.sh --
venv
shell install_gibs
on.sh --
venv
### Gibson
dependenci
es using a
virtual
environme
nt.
install
messages;
venv
created; no
missing
packages.
hygiene
and
reproducibl
e lab setup.
install
process; not
z/OS.
changing
on host
CEMT
### INQUIRE
### SYSTEM
CICS
transaction
context
CEMT
### INQUIRE
### SYSTEM
### Queries
### CICS system
details
when
authorised.
### CICS level,
region/syst
em state.
### CICS admin
visibility
and
transaction
protection.
CICS
supplied
transaction
protected
by
### ESM/transa
ction
security.
### CICS lab Read-only
if inquiry
### A.13 Db2 commands and workflows
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.14 REST/API and browser workflows
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.15 nmap-sim.py and external security tools
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
python3
nmap-
### Linux host
shell
python3
nmap-
### Runs safe
standalone
### CONFIRME
### D, DENIED,
### Teaches
enumeratio
### NSE-style
### TN3270/TS
nmap-sim
lab
### Read-only/
offline by


<!-- page 199 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
sim.py --
script tso-
enum
sim.py --
offline --
script tso-
enum
### TSO user
enumeratio
n
simulation.
### UNAVAILA
### BLE user
states.
n without
touching
real
accounts.
O
enumeratio
n concept.
design
### A.16 Master Console / OPERLOG / alert actions
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.17 ACF2 commands and security-manager comparison
Use this reference when the command syntax stops looking like RACF. ACF2 commands in Gibson
run from TSO READY after entering ACF2 mode. If you are in ISPF, use option 6 first. ACF2 material
is deliberately grouped because students need to compare LID, RULE, RESOURCE and SHOW
commands side by side.
ACF2
### Command
### Syntax Run From What It Does What To
### Look For
### Security
### Meaning
### Real ACF2
### Meaning
Lab
### ACF2 ACF2 TSO READY Switches the
READY
processor into
### ACF2 command
mode.
### ACF2 MODE
### ACTIVE and
### CURRENT
SETTING: LID.
### Tells the
learner they
are now using
### ACF2-style
commands
rather than
RACF
commands.
### Real systems
enter ACF2
through site-
defined
command
processors and
panels.
### ACF2-1
### SET LID SET LID or SET
ACF
### ACF2 mode Selects logonid
processing.
### LID SETTING
ACTIVE.
### LIDs are the
identity
records that
define who the
user or task is.
### Logonids are
### ACF2 identity
records.
### ACF2-1
LIST LIST userid |
LIST * | LIST
LIKE(mask) |
### LIST UID(n)
### ACF2 LID
setting
### Lists logonids
or selected
identity fields.
### SECURITY,
### NON-CNCL,
### GROUP, UID,
### HOME and
### OMVSPGM
fields.
### Identifies
privileged IDs,
### OMVS access
and grouping.
### LIST displays
logonid records
according to
setting and
scope.
### ACF2-1, ACF2-2
SHOW SHOW ACF2 |
SHOW TSO |
SHOW PSWD |
SHOW DDSN |
### SHOW OMVS
### ACF2 mode Displays ACF2
system, TSO,
password, data
set and OMVS
state.
### Database
names,
password
policy, current
mode and
### OMVS UID/GID
data.
### Shows whether
the security
environment is
enforceable,
auditable and
well
configured.
SHOW
commands
expose ACF2
control
information
subject to
authority.
### ACF2-1
### INSERT/
### CHANGE/
### INSERT userid
### PASSWORD(pw
### ACF2 LID Creates,
modifies or
### LOGONID
### DEFINED,
### State-changing
identity
### Logonid
administration
### ACF2-2


<!-- page 200 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
DELETE LID ) [SECURITY]
[GROUP(g)]
[UID(n)]
setting deletes
simulated
logonids.
### ALTERED or
### DELETED
messages.
administration;
requires
### SPECIAL in
Gibson.
is tightly
controlled and
auditable.
### SET RULE /
### RECKEY
SET RULE;
### RECKEY key
### ADD(resource
### UID(id)
### SERVICE(READ)
### ALLOW)
### ACF2 RULE
setting
### Creates or
updates data
set rule lines.
$KEY output,
### UID clauses
and
### ALLOW/PREVE
### NT service
decisions.
### Shows who can
access a
protected data
set and at what
service level.
### ACF2 rule sets
use
key/resource
and UID
matching
rather than
### RACF profile
syntax.
### ACF2-3
SET
### RESOURCE /
### RECKEY
SET
### RESOURCE(SUR
); RECKEY
### IBMUSER
ADD(IBMUSER.
### SUBMIT
### UID(ALICE)
### SERVICE(READ)
### ALLOW)
ACF2
### RESOURCE
setting
### Creates or
updates
resource rules
such as
### SURROGAT-
style submit-as
controls.
### TYPE(SUR), UID
and SERVICE
fields.
### Resource rules
can control
powerful non-
dataset
capabilities.
### ACF2 resource
rules
participate in
### SAF decisions
for protected
resources.
### ACF2-4
### ACCESS / TEST ACCESS
DSNAME('dsn');
TEST
DSNAME('dsn')
### LID(id)
### SERVICE(READ)
### ACF2 mode Displays
matching rules
or tests
simulated
access.
### ALLOW or
### PREVENT
decision and
matching rule
lines.
### Turns rule
listings into an
evidence-
backed access
decision.
### Real access
tests and
reporting are
central to audit
and
troubleshootin
g.
### ACF2-3, ACF2-4
 Appendix B. Security Testing Workflow Reference
 Appendix C. Output Interpretation Reference
### Appendix B. Security Testing
### Workflow Reference
Use this appendix by task. A tester rarely starts with an alphabetical command list; they start with
a security question. Each row below links the task, the command family, the expected evidence and
the defensive follow-up.
### Task Command /
### Tool Run From What It Proves Follow-Up Defensive
### Evidence Lab Reference
### Reconnaissance
and OSINT
### Browser, whois,
dig, Shodan-
style thinking,
### SighberBank
clues
### Host-side
browser/shell
### Likely users,
technologies,
services and
naming
patterns
### Move to service
discovery and
safe
enumeration
### OSINT record,
scope notes and
source
timestamps
### Security OSINT
lab
### Service
discovery and
port review
gibsonctl ports,
ss, nc, nmap-
sim tn3270-
screen
### Linux host shell Which Gibson
services are
reachable
### Choose
terminal/API/CI
### CS/Db2 path
### Connection
attempts,
### Master Console
events where
implemented
### QS-2, QS-3,
nmap-sim labs
### TSO user
enumeration
nmap-sim tso-
enum;
nmap-sim tool / CONFIRMED,
### DENIED or
### Avoid noisy
guesses; check
### Logon failures
and identity
TSO
enumeration


<!-- page 201 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### LISTUSER
where
authorised
### TSO READY UNAVAILABLE
identity
evidence
lockout policy audit trail lab
RACF
### WARNING
testing
### SEARCH ALL
### WARNING
NOMASK;
### LISTDSD/RLIST
### TSO READY or
### ISPF option 6
### Profiles that
warn rather
than enforce
### Inspect profile,
validate access
and report risk
### RACF/SMF
access and
warning
evidence
### WARNING
mode lab
### SURROGAT
testing
### SEARCH
### CLASS(SURROG
AT); RLIST
SURROGAT; JCL
USER=
TSO
### READY/option 6
and JCL
submission
context
### Submit-as
relationships
### Check whether
privileged IDs
can be
impersonated
### JES/RACF
messages and
job ownership
evidence
### SURROGAT lab
### APF-library
review
D PROG,APF;
ENUM APF;
### ELV.APF LIST
where
supported
### Console/SDSF or
uploaded tool
context
### Trusted
libraries and
dangerous
write access
### Inspect permits
and change
controls
### Console output,
### RACF permits,
change records
### APF lab
CICS
transaction
testing
cics-info, cics-
enum,
### CESN/CEMT/CE
### CI/CEDA
nmap-sim tool
or CICS context
### Reachable,
denied or
disabled
transactions
Check
transaction
security and
default user
exposure
### CICS security
events and
transaction logs
### CICS labs
### FTP/JES testing SITE
FILETYPE=JES;
PUT; GET; SDSF
review
### FTP session
then SDSF
### Whether file
transfer can
submit jobs
### Review JCL, job
owner and
spool output
### FTP logs, JES
output,
### JESSPOOL
controls
### FTP/JES lab
### Defensive
detection and
reporting
### Master Console,
### OPERLOG, alert
stream, lab
evidence
### Browser/Master
### Console plus
source
subsystem
### Whether action
is visible to
defenders
### Write finding
with evidence
and
remediation
### OPERLOG/
### SYSLOG/SMF-
like events
### Detection and
report labs
### Appendix C. Output
### Interpretation Reference
### Use this appendix after a command has run. The important question is not only whether the
command completed; it is what the output proves. These tables explain the fields and statuses
students should learn to read.
### C.1 LISTUSER output fields
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### USER The RACF user profile
being displayed.
### Ties output to the
identity under review.
### User profiles are
governed by RACF and
may be audited when
listed depending on site
policy.
### Check attributes and
groups.


<!-- page 202 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
DEFAULT-GROUP The user's default
connected group.
### Shows inherited
context and likely
dataset HLQ/group
access.
### Group connection can
influence access and
ownership.
### Follow with LISTGRP or
CONNECT review.
### ATTRIBUTES SPECIAL, OPERATIONS,
### AUDITOR or similar
high-value attributes.
### These can change the
entire risk profile of
the account.
### RACF administrative
privileges should be
tightly controlled and
audited.
### Report unexpected
privilege.
### SPECIAL RACF administrative
authority.
### Potential to alter RACF
controls.
### Comparable to high
administrative
authority in RACF.
### Check if required and
monitored.
### OPERATIONS Broad dataset access
capabilities.
### Can expose data even
when normal permits
are absent.
### Should be rare and
closely audited.
### Review dataset access
risk.
### REVOKE Whether the account is
disabled for logon.
### Active privileged users
are higher risk than
revoked ones.
### Revocation affects
authentication but not
all ownership traces.
Confirm logon status.
### LAST-ACCESS Last recorded access
date/time.
### Useful for stale account
and recent activity
review.
### Real sites use
### RACF/SMF and
reporting tools for this.
### Compare against
expected use.
### C.2 SEARCH, RLIST and LISTDSD interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CLASS The RACF class being
searched or listed.
### Determines what kind
of resource is
protected.
### Classes such as
### DATASET, SURROGAT,
### FACILITY, OPERCMDS
and SERVAUTH have
different meanings.
### Pick the right follow-up
command.
### PROFILE The resource profile
name.
### Shows the protected
object or generic
pattern.
### Generic profiles can
protect broad resource
sets.
### Inspect with
RLIST/LISTDSD.
### UACC Universal access level. High UACC can expose
data to broad
populations.
### UACC is a central
access-control signal in
RACF.
### Report inappropriate
READ/UPDATE/ALTER.
### WARNING Access may be logged
but allowed.
### This is a high-value
security training
finding.
### RACF WARNING mode
is often used for testing
but risky if left in place.
### Validate whether
access is truly enforced.
### Access list Users/groups explicitly
permitted.
### Identifies who can
read, update or control
resources.
### Permits drive SAF
authorization
decisions.
### Check groups and
privileged IDs.
### C.3 SETROPTS LIST interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Password interval /
syntax
### Global password age
and syntax settings.
### Weak policy enables
credential attacks.
### RACF SETROPTS
controls system-wide
### Compare against
policy.


<!-- page 203 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
options.
### Failed logon controls Revocation or lockout
behaviour after
failures.
### Determines whether
brute force or spraying
is safe/in-scope.
### Failed attempts can
produce RACF/SMF
evidence.
### Prefer low-noise
testing.
### Class activation Whether resource
classes are active.
### Inactive classes do not
protect resources as
expected.
### SETROPTS
### CLASSACT/RACLIST
controls are key
hardening points.
### Review sensitive
classes.
### Auditing options Which events are
logged.
### Detection depends on
audit configuration.
### RACF auditing is
central to
accountability.
### Map to defender
evidence.
### C.4 SURROGAT interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
userid.SUBMIT A SURROGAT resource
naming an execution
user.
### It may allow another
user to submit batch
work as that ID.
### Controlled by RACF
### SURROGAT class and
checked at job
submission.
### Inspect with RLIST and
test only in scope.
USER= on JOB card The execution user
coded in JCL.
### This is where submit-as
becomes operational.
### If authorised, JES/RACF
may allow the job to
run under that user.
### Review job owner and
messages.
### C.5 APF interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### APF library A trusted load-module
library.
### Write access can
become privileged-code
injection risk.
### APF list is defined
through system
configuration such as
### PROGxx and displayed
by operator/SDSF
mechanisms.
### Review UPDATE/ALTER
permits.
### UPDATE/ALTER access Ability to modify or
replace content.
### Dangerous when
applied to trusted
libraries.
### Can undermine the
trusted computing base
if misconfigured.
Report as high risk.
### C.6 ISPF editor interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
Command ===> Primary command line. SAVE, END, CANCEL,
### FIND and CHANGE
belong here.
### ISPF Edit has its own
command language.
### Do not type these at
READY.
### Line-command area Left column beside
data lines.
### I, D, C, M, R and block
commands belong
here.
### Line commands change
the edit buffer and may
change JCL/REXX/config
content.
### SAVE or CANCEL
intentionally.


<!-- page 204 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Output / Symptom Meaning Why It Matters Follow-Up
### No output Copy succeeded by UNIX
convention.
### Students must validate target
rather than waiting for a
banner.
cat target or read dataset.
data set not found MVS dataset/member operand
cannot be read.
### May be spelling or access-path
issue.
### LISTCAT/ISPF 3.4 and quoted
operand check.
permission denied Dataset read/write authority
is blocked.
### This is security evidence. Review DATASET profile if
authorised.
unsupported source USS path absent or a
directory.
Copy did not run. ls -l and create source file.
### C.6a cp and USS/MVS copy interpretation
### C.7 SDSF/JES interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Job ID JES identifier assigned
to submitted work.
### Links submission to
spool output and
evidence.
### JES2 assigns and tracks
jobs through
queues/spool.
Open ST/O/H output.
### Return code Completion status for
job steps.
### RC 0000 is not always
security-safe; it only
means the job step
succeeded.
### Operations teams
review RC and
SYSOUT/JES messages.
### Inspect JESMSGLG,
JESJCL, JESYSMSG.
### C.8 CICS transaction states
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CONFIRMED The transaction or
region evidence
appears reachable.
### Candidate attack
surface or training
path.
### Real CICS transactions
are protected by
transaction security
and ESM integration.
### Check authority and
logs.
### DENIED The transaction exists
or is implied but access
is restricted.
### Good defensive signal
and useful
enumeration evidence.
### CICS/RACF transaction
security should reject
unauthorised use.
### Report protection and
verify scope.
### DISABLED The transaction exists
but is disabled.
### Configuration
evidence, not
immediate access.
### Disabled transactions
may become risk if
enabled later.
### Review change
controls.
### C.9 nmap-sim.py statuses
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CONFIRMED The simulated object
appears valid or
reachable.
### Candidate entry point
or confirmed surface.
### Real NSE-style probes
may create
connection/logon
evidence.
### Validate safely in
Gibson first.


<!-- page 205 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### INFERRED The response suggests
possible existence but
is ambiguous.
### Requires follow-up
before reporting.
### Ambiguous terminal
responses are common
in mainframe
enumeration.
### Gather corroborating
evidence.
### DENIED Access appears
restricted.
### Shows control exists
and object may still be
interesting.
### Real systems may log
the denial.
### Check defensive
evidence.
### UNAVAILABLE Object not found or not
exposed.
### Reduces the current
attack path.
### Absence of evidence is
not evidence of
absence across all
LPARs.
### Try scoped
alternatives.
### Correlation ID nmap-sim run
identifier.
### Links tool output to
forensic/training
evidence.
### Equivalent to keeping
traceability in a real
assessment.
Record in notes.
### C.10 Master Console / OPERLOG alert fields
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Timestamp When the event
occurred.
### Supports timeline
building.
### Real defenders
correlate
### SYSLOG/OPERLOG/SMF
times.
### Compare with
command time.
### User/session Identity or session
involved.
### Connects action to
accountability.
### RACF/SAF/SMF
evidence ties action to
IDs where configured.
Investigate privileges.
### Event type Logon, high-port,
command, API or demo
event.
### Shows what defensive
story the lab is
teaching.
### Real sites use logs,
consoles and SIEM
enrichment.
Write evidence line.
### C.13 ACF2 output interpretation
### Output Field Meaning Why It Matters Follow-Up
### SECURITY / NOSECURITY Whether Gibson treats the logonid
as an administrator-style identity.
### SECURITY is a high-value privilege
indicator.
### LIST the ID, review group/UID,
and test whether state-changing
commands are permitted.
### NON-CNCL Gibson shows a common ACF2-
style flag in logonid output.
### Students learn to read flags, not
only user names.
### Ask what operational effect the
flag would have on a real site.
### UID(n) Simulated OMVS/UID value or
ACF2 grouping value.
### UID 0 or broad UID grouping can
change privilege assumptions.
SHOW OMVS or LIST UID(n).
$KEY(key) Rule-set key for a data set or
resource rule.
### Shows the protected namespace
being evaluated.
### Use ACCESS or TEST to turn a rule
into an access decision.
### UID(id) SERVICE(x)
### ALLOW/PREVENT
### Rule line granting or denying a
service to a UID/logonid.
### This is the evidence line for access
review.
Test
### READ/UPDATE/DELETE/EXECUTE
where appropriate.
 Appendix D. Identity, Group and Privilege Reference
 Appendix E. Dataset and File Reference
 Appendix F. Services, Ports and Connection Reference


<!-- page 206 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
 Appendix G. RACF Profile Interpretation Guide
 Appendix H. Lab-to-Command and Command-to-Lab Index
### Appendix D. Identity, Group and
### Privilege Reference
Use this appendix when a lab mentions a user, group or privilege and you need to know why it
matters. Do not treat users as sample names only; in mainframe security, identity, default group
and special attributes often define the attack path.
### User / Group Role Privilege Signal What To Check Real z/OS
### Comparison Lab Reference
### IBMUSER Training/default
high-value ID
### Often privileged in
training
environments
### Check SPECIAL,
### OPERATIONS,
### AUDITOR and
revoke state
### Default system ID
concept; should be
protected/revoked
after build
### RACF/security labs
### GUEST Low-privilege
training ID
### Demonstrates
weak/default
access and
restricted
commands
### Check whether
login works and
what commands
are denied
### Guest/default IDs
are risky even
when limited
### Initial access labs
### SYSADM / RUARIV /
### CICSUSR
### Role-based
training IDs
### Used for admin,
### RACF or CICS
scenarios
depending on seed
state
### Check group
membership and
service access
### Privileged or
application IDs
need strong
control
### Security labs
### Appendix E. Dataset and File
### Reference
Use this appendix when a lab moves between datasets, members and USS files. Mainframe security
students must learn the difference between a sequential dataset, PDS/PDSE member, catalog entry
and USS path because each has different access controls and command contexts.
### Object Type Example Syntax Run From Why It Matters Security
### Relevance Lab Reference
Sequential dataset 'HLQ.DATA' TSO READY, ISPF,
### USS dataset path
where supported
### A named MVS data
object.
### Dataset profiles
may control
### READ/UPDATE/ALT
ER.
### LISTCAT, LISTDSD,
cp labs
PDS/PDSE member 'HLQ.PDS(MEMBE
R)'
### ISPF 3.4/member
list/editor, TSO
### EX/SUBMIT where
supported
### Stores JCL, REXX,
CLISTs or source.
### Edit access can
become execution
or configuration
risk.
### ISPF edit, JCL labs


<!-- page 207 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### USS file /u/user/file.txt OMVS/USS shell UNIX-side file in
z/OS UNIX.
### Permissions,
scripts and copied
data matter.
### OMVS labs
### MVS dataset path
in USS
//'HLQ.DATA' OMVS/USS shell
where supported
### Bridge between
### UNIX commands
and MVS datasets.
### Easy way to move
data/scripts
between worlds.
### USS copy labs
### Syntax Direction Run From What It Does What To
### Watch For
### Real z/OS
### Equivalent
### Security
### Relevance
cp source.txt
target.txt
### USS file to USS
file
### OMVS/USS shell Copies text
from a USS file
in the
simulated USS
tree to another
USS path.
### Returns no
output on
success.
cp: <source>:
unsupported
source when
source is absent
or a directory.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18A
cp
"//'IBMUSER.TE
ST.DATA'"
sample.txt
### MVS dataset to
### USS file
### OMVS/USS shell Reads the
simulated MVS
dataset/membe
r through
dataset services
and writes the
content into a
USS file.
cp: <source>:
data set not
found; cp:
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18B
cp from_uss.txt
"//'IBMUSER.TE
ST.COPY'"
### USS file to MVS
dataset
### OMVS/USS shell Reads the USS
file and writes
content into the
target MVS
dataset name.
unsupported
source if the
### USS path is
absent or a
directory;
permission
denied if
dataset write is
blocked.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18C
cp
"//'IBMUSER.A.D
ATA'"
"//'IBMUSER.B.D
ATA'"
### MVS dataset to
### MVS dataset
### OMVS/USS shell Reads one
simulated
dataset/membe
r and writes an
identical target
dataset/membe
r.
data set not
found;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document and
include in
reference;
optional lab
step.
cp
"//'IBMUSER.PD
S.CODE(TIME)'"
member.txt
### PDS/PDSE
member to USS
file
### OMVS/USS shell Reads the
named member
and writes a
USS file.
data set not
found if
member does
not exist.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18D
cp
new_member.t
xt
"//'IBMUSER.PD
### USS file to
### PDS/PDSE
member
### OMVS/USS shell Writes the USS
file contents
into the target
### PDS/PDSE
unsupported
source;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
### Add Lab 18D


<!-- page 208 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### S.CODE(NEWO
NE)'"
member. system has full
attributes/conv
ersion
considerations).
cp
//IBMUSER.TEST
.DATA file.txt
### Unquoted
dataset
notation
### OMVS/USS shell Parser accepts //
followed by a
dataset name,
but quoted
notation is safer
and is the
documented
teaching path.
### Shell quoting or
special
characters may
change the
operand before
### Gibson receives
it.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
supported/avoi
d unless simple.
cp -B or
conversion
options
### Binary/code-
page
conversion
### OMVS/USS shell Not
implemented.
### Gibson uses
### UTF-8/text style
content for
teaching.
### Options are not
parsed as
conversion
controls.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
real z/OS note
only.
Use this reference when a lab moves data between USS and traditional MVS datasets. The key
teaching point is context: these examples run from OMVS/USS, not from TSO READY or the ISPF
primary menu.
### E.5 USS/MVS Copy Syntax Reference
### Appendix F. Services, Ports and
### Connection Reference
Use this appendix when you need to connect to the right service. Ports are not just numbers in a
mainframe lab: each one represents an exposed subsystem, a client choice and a likely evidence
trail.
### Port Service Connect
With
### What It
### Exposes
### Offensive
Use
### Defensive
### Monitoring
### Gibson
### Behaviour
### Real z/OS
### Context
Lab
### Reference
2023 Gibson
### VTAM/TN3
270-style
terminal
nc, telnet,
c3270,
x3270,
nmap-
sim.py
### Front-door
application
s such as
### TSO/CICS/D
b2 where
configured
### Enumerate
### APPLIDs
and logon
paths
### Connection/
logon
events
### Primary
training
terminal
service
### TN3270/
### TN3270E to
VTAM
application
s
### Quick Start,
nmap-sim
8443 / 8082 Dashboard,
### Master
### Console or
web/API
endpoints
where
configured
### Browser,
curl
Web
control/visi
bility
surfaces
### Review
state and
API
exposure
### HTTP(S)
access logs,
dashboard
auth, event
streams
### Gibson web
training
surface
z/OSMF/z/
OS
### Connect/we
b interfaces
conceptuall
y
### Quick Start,
### API labs


<!-- page 209 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### FTP/JES
port where
configured
FTP
training
service
ftp client File
transfer
and
possible JES
workflow
Test
upload/dow
nload/JES
submission
if
supported
### FTP logs,
### JES records,
job output
### Source-
validated
only where
implement
ation
supports it
z/OS
### Communic
ations
### Server FTP
### FTP/JES
labs
### Appendix G. RACF Profile
### Interpretation Guide
Use this appendix when RACF output stops being obvious. A profile is not just a name; it tells you
what class is involved, what resource is protected, who owns it, whether WARNING mode is active
and which users or groups can access it.
### Class Profile UACC WARNING Access List
/ Permits
### What It
### Protects
### Why It
### Matters
### Inspect
With
Lab
### Reference
DATASET HLQ.** or
specific
dataset
NONE/
READ/
### UPDATE/
ALTER
### May be
active
### Users/
groups with
access
levels
MVS
datasets
and
members
### Weak UACC
or
### UPDATE/AL
### TER on
sensitive
datasets
can expose
data or
code paths.
### LISTDSD or
RLIST
### DATASET
### Dataset and
### WARNING
labs
### SURROGAT userid.SUB
MIT
### Usually
NONE
### Should be
controlled
### Submitters
allowed to
run batch
as target
user
Batch
submit-as
capability
Broad
permits
create
impersonat
ion and
privilege
escalation
paths.
### SEARCH
### CLASS(SUR
ROGAT);
RLIST
### SURROGAT
### SURROGAT
lab
### FACILITY Site-defined
facility
profile
### Varies Varies Users/
groups with
facility
access
### System/
service
capabilities
### Controls
access to
powerful
functions
outside
dataset
scope.
RLIST
### FACILITY
profile ALL
### RACF labs
### OPERCMDS Command
resource
### Varies Varies Operator
command
authorities
### MVS/JES/
operator
commands
### Can allow
display or
modificatio
n of system
state.
RLIST
### OPERCMDS
profile ALL
### Console/
### SDSF labs
### SERVAUTH Network/
resource
profile
### Varies Varies Network
access
permits
### TCP/IP
network
resources
### Important
for
controlling
who can
use specific
RLIST
### SERVAUTH
profile ALL
### Network/
security
labs


<!-- page 210 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
network
resources.
### Appendix H. Lab-to-Command
and Command-to-Lab Index
### Use this appendix to move between learning and reference. If you find a command here, you
should be able to locate the lab that teaches it. If a lab uses a command, you should be able to find
the reference and output interpretation.
### Lab ID / Title Commands / Tools
### Used Context Required Appendix
### References
### Output
### Interpretation
### Reference
### Cleanup Needed
### Lab QS-1: Install
### Gibson with a
virtual
environment
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-2: Start
### Gibson and
confirm services
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-3: Connect
with netcat
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-4: Connect
with c3270 or
x3270
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-5: Open the
browser console
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-6: Confirm
runtime mode
behaviour
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-7: Read the
event and alert
stream
### See lab command
table and context
block
Start from: Master
### Console or
browser
dashboard
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 01: Orient to
simulator
boundaries
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 02: Verify
ports and service
model
### See lab command
table and context
block
Start from: TSO
### READY for
### NETSTAT/PING or
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 211 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Linux host shell
for nmap-sim/nc
checks
command family
### Lab 03: Trace a
### READY command
to implementation
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 04: Review
### MFA and user state
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 05: Baseline
### READY commands
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 06: Create,
alter and review a
training user
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 07: Create a
resource profile
and permit access
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 08: Create and
inspect a dataset
profile
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 09: Launch
### ISPF and inspect
datasets
### See lab command
table and context
block
Start from: TSO
### READY, then enter
ISPF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 10: Review JES
state and SDSF
status panel
### See lab command
table and context
block
Start from: TSO
### READY or ISPF
menu path to SDSF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 11: Explore
### JES2 and NJE
commands
### See lab command
table and context
block
Start from: TSO
### READY or ISPF
menu path to SDSF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 12: Review
console metrics
and security
summary
commands
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 13: Respond to
### IPL WTOR
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 14: Explore
### CICS transaction
help
### See lab command
table and context
block
Start from:
### VTAM/front-door
or CICS entry point
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 212 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command family
### Lab 15: Run the
### GMVB banking
navigation path
### See lab command
table and context
block
Start from:
### VTAM/front-door
or CICS entry point
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 16: Enumerate
### Db2 catalog tables
### See lab command
table and context
block
Start from: Db2
command/query
context or Gibson
route documented
by the lab
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 17: Exercise
### SQL privilege-
oriented queries
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 18: Review
### OMVS shell and
identity commands
### See lab command
table and context
block
Start from: TSO
### READY then OMVS,
or an existing USS
shell
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 19: Bridge
### OMVS and TSO
commands
### See lab command
table and context
block
Start from: TSO
### READY then OMVS,
or an existing USS
shell
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 20: Enumerate
simulator TCP/IP
listeners
### See lab command
table and context
block
Start from: TSO
### READY for
### NETSTAT/PING or
### Linux host shell
for nmap-sim/nc
checks
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 21: Enter z/OS-
style FTP client
environment
### See lab command
table and context
block
Start from: FTP
session after
connecting from
host or Gibson FTP
client context
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 22: Map API
routes to training
workflows
### See lab command
table and context
block
Start from: Host-
side REST client or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 23: Exercise
### PassTicket API and
### TSO status
comparison
### See lab command
table and context
block
Start from: Host-
side REST client or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 24: Privilege
and exposure
triage
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 25: OPERLOG
and security event
review
### See lab command
table and context
block
Start from: Master
### Console or
browser
dashboard
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 26: Run a
capstone readiness
check
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 213 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command family
### H.2 Command-to-lab mapping
### Command / Tool Context Labs Using It Primary Learning
### Outcome
### Related Output
### Interpretation
### LISTUSER TSO READY / ISPF
option 6
### RACF and identity labs Interpret user profile
privilege and account
state
### C.1 LISTUSER fields
### SEARCH TSO READY / ISPF
option 6
### WARNING, SURROGAT
and dataset discovery
labs
### Find RACF profiles and
weak patterns
C.2
### SEARCH/RLIST/LISTDS
D
### SAVE / CANCEL / END ISPF editor ISPF edit labs Control whether edit-
buffer changes persist
### C.6 ISPF editor
SITE FILETYPE=JES FTP session FTP/JES labs Understand file-
transfer-to-execution
risk
### C.10 FTP/JES response
codes
nmap-sim.py Linux host shell nmap-sim security labs Practise bounded NSE-
style enumeration
### C.9 nmap-sim.py
statuses
### Lab Commands / Features Context Reference
09A I, D, SAVE, END ISPF editor A.8, A.9, C.6
09B CHANGE, CANCEL/PF12 ISPF editor A.8, C.6
09C FIND, RFIND, CHANGE,
### RCHANGE
### ISPF editor A.8, C.6
09D C, CC, M, MM, A, B, R, RR, D,
DD
### ISPF editor A.9, C.6
09E CAPS, HEX, PROFILE, TAB, ~,
### PF3, PF12
### ISPF editor A.8, C.6
09F EDIT, SAVE, SUBMIT, SDSF
review
### ISPF/TSO/SDSF contexts B, H, I
18A cp USS to USS OMVS/USS A.6, E.5, I
18B cp dataset to USS OMVS/USS A.6, E.5, I
18C cp USS to dataset OMVS/USS A.6, E.5, I
18D cp PDS member to/from USS OMVS/USS A.6, E.5, I
### H.6 Added cp and ISPF editor labs
### H.6 ACF2 lab-to-command mapping
### Lab Commands Learning Outcome
ACF2-1 ACF2, SHOW MODE, SHOW DDSN, LIST * Enter ACF2 mode and read identity/database
context
### ACF2-2 INSERT, CHANGE, LIST Understand state-changing logonid


<!-- page 214 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
administration
### ACF2-3 SET RULE, RECKEY, ACCESS, TEST Build and test a dataset access rule
### ACF2-4 SET RESOURCE(SUR), RECKEY, LIST, ACCESS,
TEST
### Understand resource-rule and submit-as risk
### ACF2-5 Evidence review Translate ACF2 output into a finding
 Appendix I. Real z/OS Comparison Reference


<!-- page 215 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix I. Real z/OS
### Comparison Reference
Use this appendix to keep Gibson honest. Gibson is a training simulator. It can teach the workflow,
the evidence and the risk, but a real z/OS system has RACF/SAF authority checks, JES and SDSF
controls, SMF records, OPERLOG/SYSLOG, site exits, parmlib configuration, network policy and
operational change controls.
### Area What Gibson
### Simulates What Real z/OS Adds Authority / Logging
### Consideration
### Defensive Evidence
### Mapping
### TSO/RACF commands RACF-style command
output and state
changes where
implemented
### Actual RACF database,
command processors,
class activation and
exits
### RACF authorities and
### SMF type 80/audit
policy may apply
### RACF reports, SMF,
console messages
### ISPF Panel navigation,
dataset
browsing/editing and
editor commands
where implemented
### Real ISPF dialog
services, dataset
allocation rules,
### ENQ/locks and site exits
### Dataset profiles and
### ISPF configuration
affect access
### Dataset access logs,
change records, job
output
### USS/OMVS UNIX-like shell and
dataset path simulation
where implemented
z/OS UNIX permissions,
### BPX authorities, code
page conversion and
dataset protection
### BPX.SUPERUSER,
filesystem permissions,
### RACF dataset profiles
### Shell history, audit
records, dataset access
logs
### JES/SDSF Job/spool concepts and
panel output
### JES2 queues, spool
datasets, SDSF SAF
controls and operator
commands
### JESSPOOL, OPERCMDS
and SDSF resources
govern access
### JESMSGLG, JESJCL,
### JESYSMSG, SDSF logs
### CICS Transaction exposure
and safe
denied/confirmed
states
### CICS regions, APPLID,
transaction security,
### ESM integration and
### CICS logs
### CICS transactions and
resources protected
through security
manager
### CICS security events,
### SMF, application logs
### Network/nmap-sim Safe local/offline
enumeration outcomes
### Real TN3270, FTP,
### DRDA, CICS web, z/OS
### Connect and firewall
policy
### SERVAUTH,
### NETACCESS, TLS and
daemon logs matter
### Network telemetry,
daemon logs, SIEM,
### OPERLOG
### I.6 USS/MVS cp and ISPF Edit Real z/OS Comparison
Real z/OS supports a richer version of both areas. IBM documents the z/OS UNIX cp command as
supporting copy operations to and from MVS data sets, while ISPF Edit and Edit Macros documents
the edit primary and line commands. Gibson implements a source-backed training subset. Where
Gibson lacks a real ISPF command, the manual marks it as real z/OS only rather than pretending it
works.
### Area Gibson Behaviour Real z/OS Behaviour Student Lesson
cp between USS and MVS Text-oriented copy using // Full z/OS UNIX and MVS Learn context and syntax


<!-- page 216 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
dataset operands. dataset integration, with
attributes and conversion
considerations.
first; understand production
has more controls.
### ISPF primary commands Training subset with
terminal-friendly focus
commands.
### Full ISPF primary command
set, macros and site profiles.
### Know what runs on
Command ===>.
### ISPF line commands I/D/C/M/R/A/B/P/O/X and block
forms.
### Much broader line-command
set.
### Know what belongs in the
line-command area.
### SAVE/END/CANCEL Simplified but safety-oriented. ISPF profiles and site
behaviour may vary.
### Never confuse exit, save and
cancel.


<!-- page 217 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix J. Code Interpreter
### Language Reference
Use this appendix when you know which language surface you are working with and need to check
what Gibson actually supports. The tables deliberately separate Gibson behaviour from real z/OS
meaning so students do not mistake a bounded training interpreter for a production compiler or
runtime.
### J.1 REXX supported statements and functions
### Statement /
function
### Syntax Gibson behaviour Real z/OS
meaning
Lab
### SAY SAY expression evaluates
expression and
writes line to
output
REXX
display/output
instruction
CI-1
### PARSE ARG PARSE ARG var1
var2
splits invocation
arguments into
variables
common TSO/E
### REXX argument
parsing
CI-1
### ARG(n) ARG(1) returns nth
invocation
argument
real REXX
argument access
concept
CI-1
### ADDRESS TSO ADDRESS TSO
command
routes command
to Gibson TSO
processor
### TSO/E REXX
external
command
environment
CI-2
EXECIO DISKR EXECIO * DISKR
dsn (STEM stem.
reads dataset
lines into stem
variables
reads z/OS
datasets in REXX
CI-2
EXECIO DISKW EXECIO * DISKW
dsn (STEM stem.
writes stem
variables to a
dataset
writes z/OS
datasets in REXX
### CI-2/CI-10
DO/END DO i = 1 TO 3 ...
END
bounded
counted/while
loops
### REXX looping CI-1
IF/THEN/ELSE IF expr THEN ...
ELSE ...
conditional
execution
### REXX branch
logic
CI-1
SYSVAR SYSVAR('SYSUID') returns simulated TSO/E system CI-1


<!-- page 218 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
system/user
values
variable query
TIME/DATE TIME(); DATE() returns current
time/date
### REXX time/date
functions
CI-1
### J.2 JCL supported statements, keywords and programs
### Statement /
program
### Syntax Gibson behaviour Real z/OS
meaning
Lab
### JOB //NAME JOB
(acct),'desc',CLAS
S=A,MSGCLASS=A
creates job
identity,
owner/class/mess
age class
defines batch job
to JES
CI-3
USER= USER(userid) submit-as identity
checked through
### SURROGAT
batch job
execution user
### CI-3/CI-10
### EXEC PGM //STEP EXEC
PGM=IEFBR14
extracts program
and simulates
supported PGMs
defines job step
program
CI-3
PARM PARM='value' operands
captured;
### BPXBATCH/TShOc
ker style parms
partly parsed
passes
parameters to
programs
CI-4
### DD //DDNAME DD ... inventory and
instream DD
capture
defines
input/output
datasets/devices
CI-4
SYSIN DD * //SYSIN DD * ... /* passes instream
block to program
simulation
inline program
control input
CI-4
SYSOUT=* //SYSPRINT DD
SYSOUT=*
routes program
output to JES
spool
writes output to
### JES SYSOUT
### CI-3/CI-4
### IEFBR14 EXEC
PGM=IEFBR14
no-op RC 0000
step
allocation/test
utility pattern
CI-3
### IEBGENER EXEC
PGM=IEBGENER
copies SYSUT1 to
### SYSUT2 where
possible
sequential copy
utility
CI-4
### IKJEFT01 EXEC
PGM=IKJEFT01;
runs TSO batch TSO batch driver CI-4


<!-- page 219 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SYSTSIN
commands
commands
### BPXBATCH EXEC
PGM=BPXBATCH
simulates z/OS
### UNIX command
processor
run UNIX
shell/program
from batch
CI-4
### J.3 COBOL supported simulation elements
### Element Syntax Gibson behaviour Real COBOL
meaning
Lab
### IDENTIFICATION
### DIVISION
### IDENTIFICATION
DIVISION.
required marker
for compile
simulation
real COBOL
identification
division
CI-5
### PROCEDURE
### DIVISION
### PROCEDURE
DIVISION.
required marker
for compile
simulation
real COBOL
executable
procedure
division
CI-5
DISPLAY DISPLAY 'text'. literal extraction
into SYSPRINT-
like output
COBOL
output/display
statement
CI-5
### EXEC CICS EXEC CICS ... END-
EXEC
recognised and
emits
informational
message
### CICS API call in
COBOL
CI-5
### EXEC SQL EXEC SQL ... END-
EXEC
recognised and
emits
precompiler-style
message
embedded SQL in
COBOL
CI-5
### J.4 HLASM status
### Element Gibson behaviour Real z/OS meaning Manual treatment
### HLASM assembler
runtime
### Not implemented Real HLASM
assembles, link-edits
and runs low-level
programs
### Conceptual / future
enhancement only
### J.5 ICSF and WTOR additions
### Area Syntax Gibson behaviour Security meaning Lab/section
### ICSF ICSF STATUS shows simulated detect control- ICSF-1


<!-- page 220 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ICSF control-
plane status
plane health and
access
### ICSF ICSF REFRESH
CKDS
refreshes
simulated key
dataset version
and audits
change should be
protected and
alerted
### ICSF-1
ICSF D ICSF; F
### ICSF,REFRESH,TK
DS
console control
path for ICSF
simulation
console actions
require strong
controls
### ICSF-1
### WTOR R 01,CLPA responds to IPL
### CLPA prompt
bootstrap order
and audit
evidence
WTOR
### WTOR R 02,U continues
### IPL/user step in
startup contract
ensures console
flow is complete
WTOR
### WTOR R 03,Y enables MFA PIN
prompt
### MFA policy
choice
WTOR
### WTOR R 04,1357 sets 4-digit MFA
### PIN for IPL
PIN+HHMM
token model
WTOR


<!-- page 221 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 222 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 223 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 224 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 225 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 226 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### J.6 ZREXX, ZSEC, ENUM and SEARCHRX Security Tool Reference
Use this reference when a lab moves from individual RACF commands into security-tool output.
The context remains TSO READY or ISPF option 6 unless a future tool specifically documents
another execution path.
I.7 Real z/OS comparison: zSecure-style reporting and REXX audit
automation
Real z/OS estates use RACF commands, SMF records, site REXX/CLIST tooling and products such as
IBM Security zSecure to analyse security posture. Gibson’s ZSEC and ENUM surfaces are training
simulators: they help students learn which questions to ask, but they do not replace live RACF
database analysis, SMF collection or zSecure reporting.


<!-- page 227 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Compact J.6 security-tool reference
ZSEC: run ZSEC or ZSEC <topic> from TSO READY or ISPF option 6. Use it to review simulated
posture reports for privilege, UID0, SURROGAT, APF, ICSF, SETROPTS, EVENTS and ALERTS. Labs:
ZS-1 and ZS-2.
ENUM: run ENUM SEC, ENUM APF or ENUM ALL from TSO READY or ISPF option 6. Use it for first-
pass security enumeration and follow-up prioritisation. Labs: EN-1, EN-2 and EN-3.
SEARCHRX: run SEARCHRX from TSO READY or ISPF option 6. Use it to organise WARNING,
dataset, BPX and SURROGAT leads into sections. Lab: SR-1.
ZREXX: external/future security-audit REXX package only in this build. No built-in Gibson ZREXX
command handler was found, so ZREXX is documented as conceptual/future integration rather
than a runnable lab.
### Appendix K. Implementation
### Completeness Notes
The final codebase audit also rechecked Gibson features that are easy to miss because they appear
in command dispatchers, tests or compatibility layers rather than in a single chapter file. The table
below records the main surfaces that were reviewed and either confirmed as already covered or
added to the reference proof package.
### Surface Status Why It Matters
ACF2 Added in this pass Alternative ESM model: logonids, UID strings,
rules and resource rules.
### SMPE Classified/referenced Maintenance workflows can expose software
inventory and exception handling.
NETACCESS/SERVAUTH Verified in command inventory Network zone controls shape who can reach
services.
RACDCERT/PTKTDATA/PassTicket Verified in command inventory Certificate, ring and passticket controls are
authentication-critical.
IKJTSO/PASSWORDPREPROMPT Verified in command inventory TSO logon prompting can affect enumeration
and authentication behaviour.
SECURITY RARE / reports Verified in command inventory Defensive reporting and frequency review
support audit triage.
IND$FILE, TRANSMIT, RECEIVE Verified in command inventory File-transfer paths matter for data movement
and evidence handling.
 Chapter 7. ISPF and Editor Workflows
 Code Interpreters
 Chapter 8. SDSF, JES, JCL, and NJE
 Chapter 9. Master Console and OPERLOG
 Chapter 10. CICS and Banking Lab


<!-- page 228 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
 Chapter 11. Db2 and SQL Simulation
 Chapter 12. OMVS/USS and Transfer Bridges
 Chapter 13. FTP, TCP/IP and Network Enumeration
 Chapter 14. REST API, Dashboard, and Web Interfaces
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to write the defensive validation first; that usually clarifies the finding.
### Instructor note
If the finding is vague, add the command, resource, user/group and observed field.
### Troubleshooting
Require students to provide a verification command for the fix, not just a recommendation.
### Defensive takeaway
Real mainframe findings must be reproducible, bounded, authorised and actionable for RACF,
system, database or network owners.
### On a real z/OS system
The output should be a concise finding that names the exact resource, command evidence and
recommended fix.
### What the output tells us
Choose one finding from Labs 24-28.
Write: Title, Evidence, Impact, Likelihood, Recommendation, Defensive Validation.
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
Use the previous labs as evidence sources. The command is the reporting workflow: evidence,
impact, likelihood, remediation and validation.
### What the commands do
### This final lab turns tool output into a finding. ENUM, SEARCHRX, SYS0WN, FTP/JES and SQL
evidence are only useful when they become clear risk statements and defensive actions.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context