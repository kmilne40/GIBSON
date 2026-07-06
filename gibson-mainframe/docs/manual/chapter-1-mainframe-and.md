## Chapter 1. Mainframe and
### Gibson Foundations
This section gives the conceptual foundation required to use Gibson without mistaking it for a
production mainframe. It explains z/OS-like concepts, training boundaries, safe use, and the
simulator model.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This foundation chapter introduces the boundary between Gibson training behaviour and real z/OS
operations. The useful model is simple: identify the environment, prove where a command runs,
and keep track of whether the action reads state, changes simulator state, or demonstrates a
controlled weakness.


<!-- page 35 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value here is orientation. Students learn to separate simulator proof from production
claims; defenders learn to ask what evidence a real system would create before trusting a finding.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
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
### Searches for
a string and
### INVALID
EDIT
### Source-
backed in
### ISPF edit
primary
### Lab 09C


<!-- page 36 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
===> or PF
key
positions the
cursor on a
match.
### COMMAND,
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
### RFIND RFIND ISPF editor
### Command
===> or PF
key
### Repeats the
previous
FIND.
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


<!-- page 37 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BROWSE/VIE
### W as appli
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
### Toggles null
display/profil
e state.
### INVALID
EDIT
### COMMAND,
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
### Reference


<!-- page 38 -->

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
TABS TABS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles tab
profile state.
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


<!-- page 39 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### W as appli
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
### Lab 09E


<!-- page 40 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command
and text
fields in the
interactive
editor.
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
concept; see
### IBM ISPF Edit
docs
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
### Second
marker
### MM Implement
ed
### Real ISPF
equivalent
or marked
### Lab 09D


<!-- page 41 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
the buffer. real-only
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
### No S/F/L No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab


<!-- page 42 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
only.
shift
commands
((, )), <, >
(, ), <, > real ISPF
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
### No (, No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab
### Feature Type Behaviour Where Used Gibson
### Behaviour
### Real ISPF
### Behaviour
### Common
### Mistake
### PF3 / F3 PF key Maps to END. Editor session Warns on dirty
data.
### Common ISPF
exit/end key.
### Assuming PF3
always saves.
### PF12 / F12 PF key Maps to
CANCEL.
### Editor session Discards
changes.
### Often CANCEL
depending
panel/keylist.
### Cancelling
useful work.
### TAB UI behaviour Cycles field
focus.
### Interactive
editor
### Terminal-
friendly field
cycling.
3270 fields are
cursor-
addressable.
### Typing line
commands into
text.
~ Special
command
### Returns to
command field.
### Interactive
editor
### Gibson
convenience
command.
### Not a standard
ISPF command.
### Treating it as
real z/OS
syntax.
### CAPS/HEX/
### PROFILE
### Switches Show or alter
profile state.
Command ===> Simulated
profile state.
### Real ISPF
profile settings.
### Not checking
profile before
interpreting
behaviour.
PROFILE, CAPS, HEX, RESET, TAB, PF3, PF12 and the Gibson-specific ~ focus command are included
here because they control how editing feels. The safety lesson is simple: know whether you are
changing data, saving data, exiting cleanly or cancelling a bad edit.
### ISPF Editor Switches, PF Keys and Special Behaviour
Line commands are the part of ISPF that make the editor feel different from a normal shell. They
are typed beside a line, not at READY. Gibson also supports command-line fallbacks such as LC 5 I
or I3 5 for terminal sessions where cursor placement is awkward. Teach both the concept and the
fallback, but always explain the real ISPF line-command area.
### ISPF Editor Line Commands
From a mainframe security point of view, ISPF edit is where authority becomes practical. If you
can edit JCL, REXX, CLISTs, PROCs or configuration members, you may be able to change what later
executes. Gibson gives you a safe editor subset so that students learn the workflow before touching
a real system.
ISPF edit is its own command environment. A student who types LISTUSER at the ISPF primary
menu is in the wrong place; a student who types SAVE at TSO READY is also in the wrong place. In
this section we'll keep the contexts separate: primary commands run on the editor Command ===>


<!-- page 43 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
line, line commands run in the left line-command area, and TSO/RACF commands belong at READY
or ISPF option 6.
### ISPF Editor Primary Commands
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
### S.CODE(NEWO
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
system has full
### Add Lab 18D


<!-- page 44 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
NE)'" member. attributes/conv
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
### Symptom Likely Cause Check Fix
cp: source: data set not found Dataset/member name is
wrong.
### LISTCAT or ISPF 3.4. Correct the quoted dataset
name.
cp: permission denied Dataset read/write is blocked. Inspect DATASET profile if
authorised.
### Use a permitted training
object.
cp: source: unsupported
source
### Source path missing or
directory.
ls -l source. Create file or choose
supported source.
No output UNIX success convention. cat target or read dataset. Verify the target rather than
expecting a success banner.
### Common cp Failures and What They Teach
The important syntax is the double-slash dataset operand. A USS file looks like sample.txt or
/u/ibmuser/sample.txt. An MVS dataset operand is written as //'HLQ.DATASET'. A PDS or PDSE
member adds parentheses inside the dataset name, for example //'IBMUSER.REXX(ENUM)'. In the
labs, quote the operand because it teaches the safest habit and avoids shell parsing surprises.
In this section we'll use Gibson to practise one of the most useful bridge skills in z/OS: moving data
between UNIX System Services and traditional MVS datasets. On a real system, this is how scripts,
JCL, reports, configuration snippets and evidence often move between the UNIX and TSO worlds.
### Copying Between USS and MVS Data Sets with cp
### Section labs
### Lab 01: Orient to simulator boundaries
### Command context
Start from: Context stated in the lab prerequisite


<!-- page 45 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through orient to simulator boundaries as a practical evidence exercise, not
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
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### NETSTAT PORTLIST
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


<!-- page 46 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach orient to simulator boundaries by asking students to explain the purpose of each command
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
### Field Value
### Difficulty Beginner
### Estimated time 25 minutes
### Objective Identify simulator components and distinguish Gibson
behaviour from production z/OS.
Prerequisites Package extracted and service inventory available.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 47 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
