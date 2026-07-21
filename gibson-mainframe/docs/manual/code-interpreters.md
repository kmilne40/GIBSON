## Code Interpreters
### Why code matters on the mainframe
In this section we’ll move from using Gibson to interrogate a system into using Gibson to write,
submit and interpret code. That matters because real mainframes are not only login screens and
command prompts. They are programmable operating environments where JCL starts work, REXX
automates TSO and dataset activity, COBOL carries business logic, and assembler sits close to the
platform boundary. In Gibson, these capabilities are deliberately bounded so students can practise
the evidence trail without executing arbitrary host code.


<!-- page 100 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Gibson’s code execution model
Gibson supports REXX execution through a bounded interpreter, JCL/JES submission through a
parser and spool model, and COBOL source-aware compile simulation through the JES runner.
HLASM is included here as a real z/OS concept and a future enhancement: the source package does
not contain an HLASM interpreter or assembler runner. Code is normally written in ISPF edit or
copied through USS/MVS transfer paths, executed through TSO EX, SUBMIT, JES, FTP/JES or
supported simulator routes, and then reviewed through terminal output or SDSF/JES spool files.
### Interpreter Gibson status Primary entry
point
### Output to inspect Security lesson
### REXX Implemented
bounded
interpreter
### REXX, EXEC, EX
or %exec from
### TSO READY / ISPF
option 6
### SAY output, TSO
command output,
### EXECIO dataset
changes
### Automation can
inspect or change
state; script
libraries need
protection
### JCL/JES Implemented
parser and JES
runner
### SUBMIT
dataset(member),
### ISPF editor
### SUB/SUBMIT,
### FTP/JES where
enabled
### Job ID, RC,
### JESMSGLG,
### JESJCL,
### JESYSMSG,
### SYSOUT/SYSPRIN
T
### Batch is an
execution path;
### SURROGAT and
spool access
matter
### COBOL Implemented
compile
simulation, not a
full runtime
### JCL EXEC
PGM=IGYCRCTL
or COBOL with
SYSIN
### IGYCRCTL listing,
### DISPLAY text in
### SYSPRINT
### Source structure
and compiler
output teach
business-code
evidence
### HLASM Not implemented
as an interpreter
### Conceptual only /
future
enhancement
### N/A in Gibson Assembler is a
high-trust real
z/OS skill; do not
pretend Gibson
assembles code
### REXX interpreter
REXX is the most useful first programming language for Gibson students because it sits beside TSO.
A small exec can print variables, accept arguments, call TSO commands, and read or write datasets
through EXECIO. In a security lab, this turns a single command into repeatable evidence collection.
In a production z/OS environment, the same idea is powerful and therefore sensitive:
SYSEXEC/SYSPROC libraries, dataset write access and ADDRESS TSO use should be governed and
audited.
### REXX element Syntax Gibson behaviour Real z/OS
meaning
### Security /
learning value


<!-- page 101 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SAY SAY expression evaluates
expression and
writes line to
output
REXX
display/output
instruction
helps prove exec
ran and exposes
automation
output
### PARSE ARG PARSE ARG var1
var2
splits invocation
arguments into
variables
common TSO/E
### REXX argument
parsing
teaches
parameterised
tooling
### ARG(n) ARG(1) returns nth
invocation
argument
real REXX
argument access
concept
reduces hard-
coded scripts
### ADDRESS TSO ADDRESS TSO
command
routes command
to Gibson TSO
processor
### TSO/E REXX
external
command
environment
automation can
list users/datasets
or submit jobs
EXECIO DISKR EXECIO * DISKR
dsn (STEM stem.
reads dataset
lines into stem
variables
reads z/OS
datasets in REXX
evidence
collection and
dataset review
EXECIO DISKW EXECIO * DISKW
dsn (STEM stem.
writes stem
variables to a
dataset
writes z/OS
datasets in REXX
state-changing
automation risk
DO/END DO i = 1 TO 3 ...
END
bounded
counted/while
loops
### REXX looping automation and
repeated checks
IF/THEN/ELSE IF expr THEN ...
ELSE ...
conditional
execution
### REXX branch
logic
risk decisions in
scripts
SYSVAR SYSVAR('SYSUID') returns simulated
system/user
values
### TSO/E system
variable query
identity-aware
scripts
TIME/DATE TIME(); DATE() returns current
time/date
### REXX time/date
functions
audit/time
stamping in
scripts
### JCL interpreter and JES runner
JCL is how batch work is described. In Gibson, the parser reads JOB, EXEC and DD statements, JES
creates a job ID and spool, and the runner simulates selected programs such as IEFBR14,
IEBGENER, IKJEFT01, BPXBATCH, DSNTEP2/DSNTIAD and IGYCRCTL. The important habit is to read
the job as a set of security decisions: who owns it, what program runs, what datasets are read or
written, what SYSIN says, and what output appears in spool.
### JCL Syntax Gibson behaviour Real z/OS Security /


<!-- page 102 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
statement/keywor
d
meaning learning value
### JOB //NAME JOB
(acct),'desc',CLAS
S=A,MSGCLASS=A
creates job
identity,
owner/class/mess
age class
defines batch job
to JES
job owner and
### SURROGAT risk
USER= USER(userid) submit-as identity
checked through
### SURROGAT
batch job
execution user
impersonation/
privilege risk
### EXEC PGM //STEP EXEC
PGM=IEFBR14
extracts program
and simulates
supported PGMs
defines job step
program
program choice
determines
impact
PARM PARM='value' operands
captured;
### BPXBATCH/TShOc
ker style parms
partly parsed
passes
parameters to
programs
parameters can
alter run
behaviour
### DD //DDNAME DD ... inventory and
instream DD
capture
defines
input/output
datasets/devices
### DDs can
expose/write
datasets
SYSIN DD * //SYSIN DD * ... /* passes instream
block to program
simulation
inline program
control input
what you send to
utilities matters
SYSOUT=* //SYSPRINT DD
SYSOUT=*
routes program
output to JES
spool
writes output to
### JES SYSOUT
spool may leak
sensitive data
### Program Purpose Gibson
behaviour
### Inputs Outputs Security
relevance
### IEFBR14 Safe no-op
step
### Returns RC
0000
### JCL step JESYSMSG/
### JESMSGLG
### Baseline job
submission
and spool
review
### IEBGENER Copy utility
simulation
### Copies SYSUT1
to SYSUT2
where
possible
### SYSUT1/
### SYSUT2 DDs
### IEB144I
records
written
### Dataset copy
paths can
expose or
alter data
### IKJEFT01 /
### IKJEFTxx
### TSO batch
driver
### Runs SYSTSIN
commands
through TSO
processor
### SYSTSIN TSO command
output in
spool
### Batch can
automate
privileged
commands


<!-- page 103 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BPXBATCH USS batch
bridge
### Simulates
UNIX
processor and
selected
output
### STDPARM/
STDIN
### BPXBATCH
messages
### Batch-to-USS
bridge needs
strong
controls
### DSNTEP2 /
### DSNTIAD
### SQL processor
simulation
### Formats Db2
query output
### SYSIN/
### SYSTSIN SQL
### SQL output
spool
### Database
enumeration
evidence
### IGYCRCTL /
COBOL
COBOL
compile
simulation
### Validates
divisions and
extracts
### DISPLAY lines
### SYSIN COBOL
source
### Compile
listing and
### SYSPRINT
### Business-code
evidence
without
runtime
execution
### COBOL compile simulation
Gibson does not run arbitrary COBOL. It simulates the compiler evidence that a beginner needs to
understand: required divisions, DISPLAY output, condition code and informational recognition of
EXEC CICS or EXEC SQL. That distinction matters. A student can learn what a compile listing
proves, but should not claim that Gibson has executed a COBOL load module.
### COBOL element Syntax Gibson behaviour Real COBOL
meaning
### Security /
learning value
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
shows source
structure
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
where program
logic lives
DISPLAY DISPLAY 'text'. literal extraction
into SYSPRINT-
like output
COBOL
output/display
statement
proves program
path and data
disclosure
### EXEC CICS EXEC CICS ... END-
EXEC
recognised and
emits
informational
message
### CICS API call in
COBOL
teaches
transaction-tier
linkage without
execution
### EXEC SQL EXEC SQL ... END-
EXEC
recognised and
emits
precompiler-style
message
embedded SQL in
COBOL
teaches Db2
linkage without
execution


<!-- page 104 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### HLASM status and real-system context
HLASM is documented here because students will encounter assembler in real mainframe security
work, especially around exits, authorised programs, SVCs and low-level utilities. Gibson does not
currently implement an HLASM interpreter, assembler, link-editor or runtime. Treat HLASM
examples in this manual as real z/OS context and future enhancement material only unless a later
Gibson package adds a source-backed runner.
### HLASM element Gibson status Real z/OS meaning Manual treatment
### START / CSECT / USING
/ END
### Not implemented Program organisation
and addressability in
HLASM
### Conceptual only
### STM / LM / LR / LA / L /
### ST / MVC / CLI /
branches
### Not implemented Machine-level register,
storage and branch
logic
### Future enhancement
### WTO macros and
assembler exits
### Not implemented Operator messages
and low-level system
interfaces
### Conceptual security
discussion only
### Editing, storing and running code
A typical Gibson coding workflow is deliberately mainframe-shaped: create or open a PDS member
in ISPF edit, enter REXX, JCL or COBOL source, SAVE or END the member, then execute it from the
correct context. REXX runs from TSO READY or ISPF option 6 using EX/EXEC/REXX. JCL is submitted
from READY, ISPF editor SUB/SUBMIT or FTP/JES. COBOL source is normally compiled through a
JCL step using IGYCRCTL or COBOL. USS cp can move source files between UNIX-style paths and
MVS dataset members, but the execution context still matters.
### Security implications of code execution
Code execution is one of the places where mainframe security stops being theoretical. Write access
to a REXX, JCL, COBOL or PROC library can change what future work does. SUBMIT authority can
turn a dataset member into running work. SURROGAT can make that work run as another user.
SDSF and JES controls decide who can read the evidence. In Gibson, these behaviours are bounded,
but the teaching point is real: source libraries, execution libraries, JES submission and spool
visibility are all security boundaries.
### Lab CI-1: Write and run a simple REXX program
### Command context
Start from: TSO READY or ISPF option 6; use ISPF editor first if creating the member. Do not run
these commands from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX
execution belongs at READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT
or FTP/JES where enabled; spool review belongs in SDSF/JES output.


<!-- page 105 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. SAY, PARSE ARG and SYSVAR
prove that the exec ran, accepted input and knew the current user.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
EX 'IBMUSER.REXX.TEST(HELLO)' 'GIBSON'
### What the output tells us
The evidence is the SAY output. If the argument appears in the output, PARSE ARG worked; if
SYSUID appears, the exec is running under the expected simulator identity.
### On a real z/OS system
On real z/OS, TSO/E REXX is often used for administration, reporting and automation.
SYSEXEC/SYSPROC libraries and dataset writes deserve the same attention as shell scripts on
distributed systems.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status


<!-- page 106 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-2: Use REXX to issue a TSO command
### Command context
Start from: TSO READY or ISPF option 6. Do not run these commands from unrelated contexts. Code
creation belongs in ISPF edit or USS; REXX execution belongs at READY/option 6; JCL submission
belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where enabled; spool review belongs in
SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. ADDRESS TSO is the bridge from
script logic into TSO command processing. In Gibson it routes the command back through the
current TSO processor.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
EX 'IBMUSER.REXX.TEST(TSOCMD)'
### What the output tells us
The evidence is both the REXX output and the TSO command response. If REXX starts but LISTCAT
or LISTUSER output is absent, the script ran but the command bridge did not return the expected
evidence.
### On a real z/OS system
### On real z/OS, ADDRESS TSO can automate powerful commands. A defender cares where the exec
came from, which user ran it, and what TSO commands were issued.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting


<!-- page 107 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-3: Submit simple JCL and read spool output
### Command context
Start from: Create or edit a JCL member in ISPF; submit from READY, ISPF editor SUB/SUBMIT, or
option 6 as documented. Do not run these commands from unrelated contexts. Code creation
belongs in ISPF edit or USS; REXX execution belongs at READY/option 6; JCL submission belongs at
READY, ISPF editor SUB/SUBMIT or FTP/JES where enabled; spool review belongs in SDSF/JES
output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. JOB, EXEC and DD are the core
language of batch work. IEFBR14 gives a safe baseline job with a clean RC.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(BR14)'
SDSF
ST
### What the output tells us


<!-- page 108 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The evidence is the JOB ID, RC 0000 and JES spool files. This proves that JES accepted the job and
that the simulated step completed cleanly.
### On a real z/OS system
On real z/OS, JCL submission creates JES evidence and may allocate or change datasets. Submit
authority and SDSF output access are security controls.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-4: Use JCL with SYSIN and SYSOUT
### Command context
Start from: JCL member submitted through READY or ISPF editor. Do not run these commands
from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. SYSIN provides input to a
program and SYSOUT/SYSPRINT routes output to spool. IEBGENER and IKJEFT01 demonstrate two
different styles: utility copy and TSO batch.
### What the commands do


<!-- page 109 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(GENER)'
SDSF
O
### What the output tells us
The evidence is the utility message, records-written count or TSO batch output in spool. If SYSOUT
is missing, check DD names and instream input.
### On a real z/OS system
### On real z/OS, SYSIN and SYSOUT show what control data was supplied and what the program
produced. They are often where assessment evidence and sensitive leakage appear.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.


<!-- page 110 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab CI-5: Compile a small COBOL source member
### Command context
Start from: JCL member with EXEC PGM=IGYCRCTL or COBOL. Do not run these commands from
unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. The COBOL simulation checks
required divisions and extracts DISPLAY literals. It teaches compiler evidence rather than runtime
execution.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(COBOLJ)'
SDSF
O
### What the output tells us
The evidence is the IGYCRCTL listing, maximum condition code and SYSPRINT DISPLAY line.
Missing required divisions produce IGY-style errors and a higher condition code.
### On a real z/OS system
On real z/OS, COBOL compilation would produce object code and normally feed link-edit and load
libraries. Gibson stops at compile simulation, so do not claim load-module execution.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note


<!-- page 111 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-6: Copy source code between USS and MVS datasets
### Command context
Start from: OMVS/USS shell for cp; ISPF/TSO for later edit or execute. Do not run these commands
from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. This lab connects the previous
cp work to code. Moving source between USS and MVS is operationally useful and security-relevant
when scripts, JCL or evidence cross subsystem boundaries.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
cp rexxdemo.rexx "//'IBMUSER.REXX.TEST(REXXCP)'"
cp "//'IBMUSER.JCL.TEST(BR14)'" br14.jcl
### What the output tells us
The evidence is the target file/member content after the copy. For source movement, success is not
just the copy message; it is the ability to open and understand the destination.
### On a real z/OS system
On real z/OS, USS-to-MVS copy uses dataset pathnames and is controlled by UNIX permissions,
dataset profiles and site policy. Moving code into executable libraries should be controlled.


<!-- page 112 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-7: Security impact of editable source and JCL
### Command context
Start from: ISPF editor for source change; TSO READY or ISPF editor for submit. Do not run these
commands from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution
belongs at READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES
where enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. This lab shows why edit
authority is a finding. A small change to source or JCL can alter what future execution does and
what evidence appears in spool.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.


<!-- page 113 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
ISPF
=3.4
### E IBMUSER.JCL.TEST(BR14)
### CHANGE IEFBR14 IEBGENER
SAVE
SUB
### What the output tells us
The evidence is the changed source member and the new job output. If the member changed but
the job output did not, the wrong member may have been submitted.
### On a real z/OS system
On real z/OS, source/JCL libraries are often protected by RACF DATASET profiles and change
control. Defenders should monitor update access, submits and spool access together.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.


<!-- page 114 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
