## Chapter 7. ISPF and Editor
### Workflows
This section covers ISPF launcher behaviour, dataset listing/editing, member concepts and guided
editor-style workflows.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
ISPF is not a general shell; it is a panel and editor environment with its own command areas.
### Navigation commands, primary edit commands and line commands each belong in different
places, and Gibson uses that distinction to teach real mainframe habits.


<!-- page 90 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is change control. Editing source, JCL, REXX or configuration members can
change how work runs, so students should treat editor access as a security boundary, not just a
convenience.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 09: Launch ISPF and inspect datasets
### Command context
Start from: TSO READY, then enter ISPF
If you are currently in ISPF: Use =6 for TSO commands, =3.4 for dataset lists, and the editor
command line only after opening a member.
Commands run from: ISPF primary menu, ISPF 3.4, or ISPF editor depending on the step
Do not run these from: CICS, FTP or OMVS
Why context matters: ISPF is a panel environment. READY commands such as LISTCAT need
READY or option 6; editor commands such as SAVE need an open edit session.
### Why this lab matters
In this lab we’ll work through launch ispf and inspect datasets as a practical evidence exercise, not
as a command checklist. The concept being taught is interactive dataset navigation and edit access.
From a tester’s point of view, the aim is to produce a specific piece of evidence: panel entry,
dataset/member display, edit or browse state. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
ISPF: enters the panel environment. It marks a shift from command-line TSO thinking to panel-
driven dataset and utility workflows.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
VIEW IBMUSER.JCL.LAB: opens a dataset-like object in view mode. The distinction from edit
matters: view should let you inspect without changing state.
### Starting state
Start from READY and make sure the dataset named in the lab exists. Use view-oriented actions
first so you understand what you are looking at before attempting edits in later labs.


<!-- page 91 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
ISPF
### LISTCAT
### VIEW IBMUSER.JCL.LAB
### What the output tells us
For `ISPF`, look for the editor state change: inserted text, deleted lines, a saved member or a
discarded buffer. The edit is proven by the member content, not by the key press alone.
### On a real z/OS system
ISPF is the panel-driven workbench for TSO users. Edit primary commands, line commands and
DSLIST actions can change JCL, CLISTs, REXX and configuration members, so sites protect datasets
heavily.
### Defensive takeaway
Focus on who can browse or edit operational datasets, especially PROCLIB, PARMLIB, JCL libraries
and application control libraries.
### Troubleshooting
If ISPF navigation fails, confirm the option path, dataset name and whether you are in browse or
edit mode. Edit commands only make sense inside an edit panel.
### Instructor note
Have students say out loud whether they are browsing, viewing or editing before they press Enter.
The misconception to correct is that a panel is harmless simply because it looks like a menu.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### ISPF Enters the simulated
### ISPF menu
environment.
### No option is required
to reach the primary
menu.
### ISPF is the workbench
for data sets, members,
### JCL and edit workflows,
so the lab moves from
line commands into
screen-driven
operation.
### Evidence is the ISPF
primary option menu.
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
VIEW
### IBMUSER.JCL.LAB
### Opens a data set or
member in a read-
oriented view/edit-style
### The data set name
selects the target.
### Viewing before editing
is good assessment
discipline; you collect
### Evidence is the
displayed member or
data set content.


<!-- page 92 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
path. evidence before
changing state.
### Field Value
### Difficulty Beginner
### Estimated time 30 minutes
### Objective Use the TSO launcher and dataset catalog commands to prepare
for ISPF work.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Command What It Does Important Options Why It Matters Expected Evidence
### I / In Insert blank line(s). Optional count such as
I3.
### Creates room for new
content.
n LINE(S) INSERTED
### D / Dn Delete line(s). Optional count. Removes content
deliberately.
n LINE(S) DELETED
### SAVE Persist changes. None. Commits buffer to
dataset/member.
### DATA SAVED
### END / PF3 Leave edit when clean. PF3 maps to END. Exits after save. Editor exits or dirty
prompt
### Command What It Does Important Options Why It Matters Expected Evidence
### CHANGE Modify text in buffer. CHANGE old new. Creates a deliberate
unsaved change.
n OCCURRENCE(S)
### CHANGED
### CANCEL / PF12 Discard changes. CAN alias supported. Leaves without save. Original content
remains
### Command What It Does Important Options Why It Matters Expected Evidence
### FIND / F Search for text. FIND string. Locates evidence. CHARS string FOUND
### RFIND Repeat prior search. No operands. Moves through
evidence.
### FOUND/NOT FOUND
### CHANGE / C Replace text. CHANGE old new
[ALL].
### State-changing edit. n OCCURRENCE(S)
### CHANGED
### RCHANGE Repeat previous
change.
### No operands. Reuses last
replacement.
n OCCURRENCE(S)
### CHANGED
### Command What It Does Important Options Why It Matters Expected Evidence
### C / CC Copy line/block. C, Cn, CC...CC. Stages source lines. n LINE(S) COPIED
### M / MM Move line/block. M, Mn, MM...MM. Removes source and
stages it.
n LINE(S) MOVED
### A / B Place buffer. After/before target. Controls destination. n LINE(S) INSERTED
### R / RR Repeat line/block. R, Rn, RR...RR. Duplicates patterns. n LINE(S) REPEATED
### D / DD Delete line/block. D, Dn, DD...DD. Removes content. n LINE(S) DELETED
### Command What It Does Important Options Why It Matters Expected Evidence


<!-- page 93 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### PROFILE Display settings. None. Shows active editor
state.
### Profile message
### CAPS Toggle uppercase. ON/OFF. Explains case
behaviour.
### CAPS ON/OFF
### HEX Toggle hex state. ON/OFF. Introduces byte-level
thinking.
### HEX ON/OFF
### RESET Clear excluded state. RESET X. Restores display. n LINE(S) RESET
~ / TAB Change focus. Gibson helper / key. Prevents wrong-field
errors.
### COMMAND FIELD or
focus movement
### PF3 / PF12 END/CANCEL. PF keys. Safe exit choices. END/CANCEL
behaviour
### Command What It Does Important Options Why It Matters Expected Evidence
### EDIT / E Open member in edit. ISPF 3.4 action. Confirms update path. Editor opens
### SAVE Persist member. None. Commits change. DATA SAVED
### SUB / SUBMIT Submit current JCL
where configured.
### Editor or READY
context.
### Connects edit to
execution.
### JOB SUBMITTED/job
output
### SDSF ST/H/O Review output. SDSF context. Confirms execution
evidence.
### Spool output
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If SUBMIT fails, separate the problems: did the member save, is it valid JCL, and are you submitting
from the right context?
### Troubleshooting
Review UPDATE/ALTER to executable libraries and correlate member changes with JES execution
evidence.
### Defensive takeaway
On real z/OS, libraries in SYSPROC, SYSEXEC, PROCLIB, JCLLIB or scheduler paths can be trusted by
humans or automation. RACF DATASET controls and SMF/JES evidence matter.
### On a real z/OS system
The evidence chain is edit authority -> saved content -> optional execution evidence. That is a
security workflow, not just an editor workflow.
### What the output tells us


<!-- page 94 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
1. Open a safe scratch JCL or REXX member.
2. Add a harmless comment or display statement.
3. SAVE.
4. If safe JCL and submitter are configured, SUBMIT.
5. Review output in SDSF/JES context.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll connect ISPF editing to mainframe security. UPDATE access to JCL, REXX, CLIST or
PROC libraries can become an execution path when another user, scheduler or started task trusts
that content.
### Why this lab matters
Start in ISPF edit on a scratch JCL/REXX member. Run TSO commands from READY or option 6;
review jobs from SDSF/JES, not inside the editor.
### Command context
### Lab 09F: Security impact of edit access to JCL or REXX
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If text appears in the member, you were in the data field. Use ~ or TAB to return to command focus.
### Troubleshooting
Reliable evidence requires reliable editing. If a student cannot prove whether they saved, cancelled
or simply changed focus, their assessment notes will be weak.
### Defensive takeaway
Real ISPF profiles and keylists are site-customisable. Gibson simplifies them but preserves the
training lesson: know your profile and key behaviour.
### On a real z/OS system
The output tells you the editor's state and where your next input will go. That matters because
wrong-field typing is a common 3270 learning failure.


<!-- page 95 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### What the output tells us
1. Run PROFILE.
2. Toggle CAPS OFF and ON.
3. Toggle HEX ON and OFF.
4. Exclude a line with X, then run RESET.
5. Use TAB or ~ to return to command focus.
6. Use PF3/PF12 only when you know whether you want END or CANCEL.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll focus on editor state. The command may be correct, but if the cursor is in the
wrong field or the profile behaves differently, the learner will misread the result.
### Why this lab matters
Start in ISPF edit. PROFILE, CAPS, HEX, RESET, TAB and ~ are editor behaviours. PF3 maps to END
and PF12 maps to CANCEL.
### Command context
### Lab 09E: ISPF editor switches and PF keys
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
### If A or B says NO COPIED/MOVED LINES, copy or move first. If a block command says BLOCK
STARTED, mark the second boundary line.
### Troubleshooting
Watch for unauthorised or unreviewed changes to libraries where block edits can alter execution
paths.
### Defensive takeaway
Real ISPF block editing is daily mainframe work. It is powerful enough to duplicate EXEC steps,
remove DD statements or change job behaviour if used carelessly.
### On a real z/OS system


<!-- page 96 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Line-count messages and the new member layout prove what happened. Students should be able to
identify source lines, buffered lines and target placement.
### What the output tells us
1. Copy one line with C and place it with A.
2. Copy a block with CC at first and last line, then place with B.
3. Move a line with M and place it with A.
4. Repeat a line with R3.
5. Delete a block with DD at first and last line.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll use the commands that make ISPF editing efficient: copy, move, repeat and block
delete. These are the commands students need before editing JCL safely.
### Why this lab matters
Start in ISPF edit. Use the line-command area or Gibson fallbacks. A and B are placement targets;
they are not standalone copy commands.
### Command context
### Lab 09D: ISPF copy, move, repeat and block line-command workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If RFIND says NO PRIOR FIND, run FIND first. If CHANGE is blocked, you are in browse/view or lack
edit authority.
### Troubleshooting
Review UPDATE/ALTER access to executable and configuration libraries. Diffs to JCL, PROCs and
REXX are evidence defenders should preserve.
### Defensive takeaway
Real ISPF FIND/CHANGE is central to JCL/config review. Changing a PROC, REXX or RACF-command
member can alter system behaviour.


<!-- page 97 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
FIND proves where the evidence is; CHANGE proves you can alter it. The distinction between read
evidence and write capability is the security lesson.
### What the output tells us
1. Open a member containing repeated words.
2. Run FIND USER.
3. Run RFIND.
4. Run CHANGE 'USER' 'STUDENT'.
5. Run RCHANGE or CHANGE 'USER' 'STUDENT' ALL.
6. SAVE only if using a scratch member.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll search and replace within a member. Mainframe security work often means
quickly finding user IDs, dataset names, program names, ports or control statements in long
JCL/REXX/config members.
### Why this lab matters
Start in ISPF edit. FIND, RFIND, CHANGE and RCHANGE run on Command ===>. They are not
READY commands.
### Command context
### Lab 09C: ISPF FIND and CHANGE workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If the change persists, the student probably saved it. Reset the scratch member and repeat.
### Troubleshooting
Teach students to prove edit authority without unnecessarily changing state. A cancelled edit can
be a safer proof-of-access during training.
### Defensive takeaway


<!-- page 98 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
On real z/OS, CANCEL is a practical safety mechanism when you realise you are in the wrong
member or about to save a bad edit.
### On a real z/OS system
The proof is negative evidence: the change should not be there after reopening. That tells the
student CANCEL restored the original buffer.
### What the output tells us
1. Open a safe member.
2. Run CHANGE 'OLD' 'NEW' or insert a test line.
3. Type CANCEL or press PF12.
4. Reopen the same member and confirm the change is gone.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll prove that CANCEL discards an unsafe or unwanted edit. The goal is to understand
the difference between a dirty edit buffer and a committed dataset change.
### Why this lab matters
Start in ISPF edit. CANCEL and PF12 are editor actions. Do not treat CANCEL as a TSO command.
### Command context
### Lab 09B: ISPF edit cancel/no-save workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If I or D appears as text, your cursor is in the data field. Use the line-command area or Gibson's LC
n command fallback.
### Troubleshooting
### Edit access to JCL/REXX/config libraries is sensitive. Defenders should know who has
UPDATE/ALTER access and who changed executable members.
### Defensive takeaway


<!-- page 99 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Real ISPF separates primary commands from line commands. Dataset profiles, library
management and ENQ/locking decide whether a save is allowed.
### On a real z/OS system
The useful evidence is the line-count message and DATA SAVED. That proves the editor processed
line commands and then wrote the result.
### What the output tells us
1. Open a safe training member in ISPF edit.
2. Insert a blank line with I or LC n I.
3. Add a harmless comment line.
4. Delete a scratch line with D.
5. Type SAVE.
6. Type END or press PF3.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll use Gibson to practise the core edit loop: insert a line, delete a line and save
deliberately. This is the same foundation students need before editing JCL, REXX or configuration
members.
### Why this lab matters
Start in ISPF edit. Primary commands go on Command ===>. Line commands go in the line-
command area or through Gibson fallbacks such as LC 5 I. Do not run I, D or SAVE at TSO READY.
### Command context
### Lab 09A: ISPF edit insert/delete/save workflow
