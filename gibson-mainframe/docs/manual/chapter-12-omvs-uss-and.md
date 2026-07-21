## Chapter 12. OMVS/USS and
### Transfer Bridges
This section covers the USS shell command set, MVS/USS transfer commands, OGET, OPUT, OCOPY
and IND$FILE.
### Implementation evidence
### Area Source evidence
### OMVS shell gibson/apps/omvs.py
USS service gibson/services/uss_server.py
### Operational model
This USS chapter follows data as it moves between UNIX paths, MVS datasets and TSO command
bridges. The operational model is context-sensitive: cp belongs in OMVS, TSO commands need
tso/tsocmd or READY, and quoted dataset pathnames change the target world.
### Security relevance
The security value is movement. Scripts, JCL, configuration and evidence often cross between USS
and MVS datasets, and each copy operation should have a clear owner, permission check and audit
expectation.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### OMVS/USS transfer OMVS Launches the OMVS shell. gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OEDIT Edits a z/OS UNIX file using
ISPF File Edit.
gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OGET Copies a z/OS UNIX file into an
MVS data set.
gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OPUT Copies an MVS data set into a gibson/apps/tso.py


<!-- page 138 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
z/OS UNIX file. LEGACY_HELP
### OMVS/USS pwd cd ls cat echo touch
mkdir rm cp mv id whoami
hostname uname env export
extattr
shell command gibson/apps/omvs.py:397
OMVS/USS tso/tsocmd tso <cmd> gibson/apps/omvs.py:397
OMVS/USS oget/oput/ocopy oget dataset file | oput file
dataset | ocopy src dst
gibson/apps/omvs.py:397
### OMVS/USS su/sudo/python3/vi/ps/df/
clear/exit
command gibson/apps/omvs.py:397
### Section labs
### Lab 18: Review OMVS shell and identity commands
### Command context
Start from: TSO READY then OMVS, or an existing USS shell
Commands run from: OMVS/USS shell
Do not run these from: ISPF primary menu, ISPF editor, FTP or CICS
Why context matters: UNIX commands and MVS dataset pathname syntax are interpreted by USS,
not by ISPF panels.
### Why this lab matters
In this lab we’ll work through review omvs shell and identity commands as a practical evidence
exercise, not as a command checklist. The concept being taught is z/OS UNIX shell and USS/MVS
bridge. From a tester’s point of view, the aim is to produce a specific piece of evidence: current
directory, identity, hostname, copied file or dataset bridge output. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
OMVS: enters the z/OS UNIX style shell context. Commands after this point follow UNIX-style
assumptions rather than TSO command syntax.
pwd: prints the current USS working directory so the student knows where file operations will
happen.
id: shows the effective UNIX identity and group context.
whoami: prints the current user name, a simple but important identity check.
hostname: shows the host name, useful when correlating shell output with services and logs.
### Starting state


<!-- page 139 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Start from READY and enter OMVS when required. Keep track of whether you are typing UNIX-
style commands, TSO commands through the bridge, or dataset copy helpers.
### Lab steps
OMVS
pwd
id
whoami
hostname
### What the output tells us
For `OMVS`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
OMVS provides a z/OS UNIX shell. z/OS UNIX commands can work with HFS/zFS files and, through
supported syntax or utilities, move data to and from MVS datasets.
### Defensive takeaway
Monitor movement of scripts, JCL, data extracts and credentials between USS and MVS. Cross-
environment copy is operationally useful and attacker-useful.
### Troubleshooting
If a path fails, distinguish UNIX paths from MVS dataset names and confirm the object exists. Copy
failures are often syntax or permission problems.
### Instructor note
### Keep students aware of the boundary between USS paths and MVS dataset names. Many
mainframe file-handling mistakes begin at that boundary.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### OMVS Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
pwd Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
id Inspects the simulated pwd/id/whoami/ UNIX identity is a Evidence is the current


<!-- page 140 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
z/OS UNIX shell identity
or environment.
hostname report
location, UID/name and
host identity.
separate but connected
part of the mainframe
security model.
path, userid/UID or
host name.
whoami Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
hostname Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Launch OMVS and run safe identity/navigation commands.
Prerequisites User with OMVS segment such as IBMUSER.
Validation Source validated; interactive OMVS shell required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 19: Bridge OMVS and TSO commands
### Command context
Start from: TSO READY then OMVS, or an existing USS shell
Commands run from: OMVS/USS shell
Do not run these from: ISPF primary menu, ISPF editor, FTP or CICS
Why context matters: UNIX commands and MVS dataset pathname syntax are interpreted by USS,
not by ISPF panels.
### Why this lab matters
In this lab we’ll work through bridge omvs and tso commands as a practical evidence exercise, not
as a command checklist. The concept being taught is z/OS UNIX shell and USS/MVS bridge. From a
tester’s point of view, the aim is to produce a specific piece of evidence: current directory, identity,
hostname, copied file or dataset bridge output. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
tso LISTCAT: runs a TSO-style command from the OMVS bridge, proving the simulator can cross
command environments.


<!-- page 141 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
oget IBMUSER.JCL.LAB /tmp/lab.txt: copies a dataset-like object into USS space so students can see
host data moving into a UNIX path.
oput /tmp/lab.txt IBMUSER.JCL.LAB: copies a USS file back into dataset space. This is operationally
useful and security-sensitive.
### Starting state
### Start from READY and enter OMVS when required. Keep track of whether you are typing UNIX-
style commands, TSO commands through the bridge, or dataset copy helpers.
### Lab steps
tso LISTCAT
oget IBMUSER.JCL.LAB /tmp/lab.txt
oput /tmp/lab.txt IBMUSER.JCL.LAB
### What the output tells us
For `tso LISTCAT`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
OMVS provides a z/OS UNIX shell. z/OS UNIX commands can work with HFS/zFS files and, through
supported syntax or utilities, move data to and from MVS datasets.
### Defensive takeaway
Monitor movement of scripts, JCL, data extracts and credentials between USS and MVS. Cross-
environment copy is operationally useful and attacker-useful.
### Troubleshooting
If a path fails, distinguish UNIX paths from MVS dataset names and confirm the object exists. Copy
failures are often syntax or permission problems.
### Instructor note
### Keep students aware of the boundary between USS paths and MVS dataset names. Many
mainframe file-handling mistakes begin at that boundary.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
tso LISTCAT Lists cataloged data
sets known to the
### A high-level qualifier
may narrow results
### Catalog enumeration
tells you what objects
### Evidence is a list of
data set names and


<!-- page 142 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
simulator. where implemented. exist before you test
RACF or edit paths.
attributes.
oget
### IBMUSER.JCL.LAB
/tmp/lab.txt
### Moves data between
the simulated UNIX and
TSO/MVS-style worlds.
### Source and target
identify whether data
flows from USS to data
set or data set to USS.
### File movement is
operationally normal
but security-significant:
scripts, JCL, keys and
data often cross this
bridge.
### Evidence is a created
file/data set or
successful copy
message.
oput /tmp/lab.txt
### IBMUSER.JCL.LAB
### Moves data between
the simulated UNIX and
TSO/MVS-style worlds.
### Source and target
identify whether data
flows from USS to data
set or data set to USS.
### File movement is
operationally normal
but security-significant:
scripts, JCL, keys and
data often cross this
bridge.
### Evidence is a created
file/data set or
successful copy
message.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Use tso/tsocmd from the USS command set and review dataset
transfer patterns.
Prerequisites OMVS shell.
Validation Source validated; transfer requires interactive shell state
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Command What It Does Important Options Why It Matters Expected Evidence
cp Copy file. cp source target. Proves USS file copy. No output on success
cat Display target. cat target. Verifies content. Copied text
### Command What It Does Important Options Why It Matters Expected Evidence
cp Dataset to USS. cp "//'DSN'" file. Bridges MVS to USS. No output on success
cat Display USS copy. cat file. Verifies moved content. Dataset text appears
### Command What It Does Important Options Why It Matters Expected Evidence
cp USS to dataset. cp file "//'DSN'". Writes into MVS. No output on success
cat Read target dataset. cat "//'DSN'". Verifies MVS target. Copied text appears
### Command What It Does Important Options Why It Matters Expected Evidence
cp Member to USS. cp "//'PDS(MEM)'" file. Extracts member. No output on success
cp USS to member. cp file
"//'PDS(NEWMEM)'".
### Creates/replaces
member.
### No output on success
cat Verify content. cat file or cat //
operand.
### Checks both sides. Expected text
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.


<!-- page 143 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If the member is not found, check the containing PDS and member spelling.
### Troubleshooting
Monitor updates to executable libraries and member additions in JCL/REXX/CLIST paths.
### Defensive takeaway
PDS/PDSE members are how z/OS stores many operational artefacts. Member write access can be
an execution-path risk.
### On a real z/OS system
The evidence is the same content moving across the USS/MVS boundary at member level.
### What the output tells us
1. Use or create IBMUSER.PDS.CODE.
2. Run cp "//'IBMUSER.PDS.CODE(TIME)'" time.rexx.
3. Create new_member.txt.
4. Run cp new_member.txt "//'IBMUSER.PDS.CODE(NEWONE)'".
5. Verify the new member.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll practise member-level movement, which is the useful case for JCL, REXX, CLIST and
source libraries.
### Why this lab matters
Start from OMVS/USS shell. Put the member in parentheses inside the quoted dataset operand.
### Command context
### Lab 18D: Copy a PDS member between USS and MVS
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup


<!-- page 144 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If target verification fails, check quotes and exact dataset name.
### Troubleshooting
Review who can write to datasets from multiple access paths: ISPF, OMVS, FTP and batch.
### Defensive takeaway
Real z/OS checks dataset authority and attributes when writing MVS data from USS.
### On a real z/OS system
A successful copy means UNIX-side content became an MVS dataset object. That is useful and
security-sensitive.
### What the output tells us
1. Create from_uss.txt.
2. Run cp from_uss.txt "//'IBMUSER.TEST.CATCOPY'".
3. Run cat "//'IBMUSER.TEST.CATCOPY'".
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll write a USS file back to MVS. This is the direction that becomes sensitive when the
target is a JCL, REXX or configuration dataset.
### Why this lab matters
Start from OMVS/USS shell. Source is USS; target is a quoted // dataset operand.
### Command context
### Lab 18C: Copy a USS file into an MVS dataset
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
Quote the dataset operand and verify the HLQ/member spelling.


<!-- page 145 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
Dataset reads followed by USS file creation can be legitimate or suspicious staging. Defenders need
context and audit evidence.
### Defensive takeaway
IBM documents z/OS shell copying to and from MVS datasets. RACF DATASET profiles and dataset
attributes govern real access.
### On a real z/OS system
The evidence is MVS dataset text now visible as a USS file. Failure usually means name or access
issue.
### What the output tells us
1. Confirm a safe training dataset exists.
2. Run cp "//'IBMUSER.TEST.DATA'" sample_from_ds.txt.
3. Run cat sample_from_ds.txt.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll pull MVS content into USS. This is how dataset evidence becomes searchable and
portable with UNIX-style tools.
### Why this lab matters
Start from OMVS/USS shell. Use a quoted //'HLQ.DATA' operand.
### Command context
### Lab 18B: Copy an MVS dataset into USS
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
Use pwd and ls -l if cp reports unsupported source.
### Troubleshooting
Monitor unusual file staging in USS home, tmp or executable directories.


<!-- page 146 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
On real z/OS UNIX, cp behaves like a UNIX command for UNIX files, subject to permissions and
filesystem controls.
### On a real z/OS system
No output from cp is normal. The proof is the target file content.
### What the output tells us
1. Create source.txt in OMVS.
2. Run cp source.txt target.txt.
3. Run cat target.txt.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll prove the ordinary UNIX side of cp first. That gives students a clean baseline before
adding MVS dataset operands.
### Why this lab matters
Start from OMVS/USS shell. Run cp at the USS prompt only.
### Command context
### Lab 18A: Copy a USS file to another USS file
