## Chapter 15. Security Training
### Playbooks
This section combines attacker and defender workflows into coherent learning paths:
enumeration, privilege analysis, dataset exposure, CICS/Db2/FTP abuse, alert review and reporting.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This playbook chapter chains individual commands into assessment workflows. The operational
model is evidence-driven: enumerate, confirm, interpret, then decide whether the next step is
testing, reporting or defensive review.
### Security relevance
The security value is judgement. Students learn to turn command output into findings; defenders
learn which control should have prevented, detected or explained the activity.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.


<!-- page 158 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Section labs
Security Tooling: ZREXX, ZSEC,
### ENUM and SEARCHRX
This section turns the simulator into a security-analysis classroom. The goal is not to pretend that
Gibson is IBM zSecure or that every external REXX audit tool is built in. The goal is to show
students how to use supported training commands, recognise the difference between simulator
reports and real z/OS evidence, and turn enumeration output into defensible findings.
The workflow is deliberately simple: run the report from the right command context, identify the
high-value control point, validate the result with a more specific command where Gibson supports
it, and then explain what a real z/OS defender would review. This is the practical bridge between
command output and mainframe security judgement.
### ZREXX Security Automation
ZREXX is treated in this manual as security-automation material for TSO/E REXX. The uploaded
ZREXX material describes a hardened real z/OS REXX audit package, but the current Gibson source
tree does not contain a runnable ZREXX command handler or complete executable ZREXX source.
That distinction matters. In Gibson, REXX automation is taught through the Code Interpreters
section and through supported security-search commands such as SEARCHRX and ENUM. ZREXX
remains a conceptual and future-integration workflow unless the actual exec is supplied and
staged into a dataset or source member.
### Comman
d / Option
### Syntax Run
From
### What It
Does
### Output
To
### Review
### Security
### Question
### Answere
d
### Real z/OS
### Comparis
on
Lab
ZREXX
audit exec
EX
'HLQ.ZRE
XX' or
site-
specific
invocatio
n
### Conceptu
al / future
TSO
### READY or
ISPF
option 6
Would
run a
security-
audit
### REXX exec
when
executabl
e source is
available
### Finding
report
such as
IBMUSER.
### ZREXX.OU
T
Can
automatio
n
summaris
e
### RACF/secu
rity
weakness
es?
TSO/E
REXX
execs can
issue host
command
s and
produce
audit
reports if
authorise
d
### ZR-1/ZR-2
conceptua
l
### SEARCHR
X
### SEARCHR
X
TSO
### READY or
Runs
Gibson’s
### WARNING
, dataset,
Which
RACF
### A real
security
SR-1


<!-- page 159 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ISPF
option 6
supported
security-
search
workflow
### BPX and
### SURROGA
### T sections
search
leads
deserve
follow-
up?
### REXX exec
would
wrap
RACF
### SEARCH/R
### LIST/LIST
### DSD and
parse
output
### ZSEC and zSecure-Style Security Analysis
ZSEC is Gibson’s zSecure-style training interface. It is not IBM Security zSecure, and the manual
must say that clearly. The useful part for students is the reporting model: a single command can
summarise privileged users, UID(0) users, SURROGAT profiles, SERVAUTH controls, ICSF posture,
SETROPTS policy, CICS/Db2 exposure and event/alert evidence. On a real estate, those questions
would be answered through RACF, SMF, zSecure Admin/Audit, site policy and operational
evidence.
ZSEC
### Command /
### Option
### Syntax Run From Report
### Produced
### What To
### Look For
### Security
### Meaning
Lab
### Main menu ZSEC or
### ZSECURE
### TSO READY
or ISPF
option 6
### Training
topic list
### Available
report
categories
### Shows what
posture
reports can
be
requested
ZS-1
### Privilege
review
ZSEC
### PRIVILEGE
### TSO READY
or ISPF
option 6
### Privileged/
audit
attributes
### SPECIAL,
### OPERATION
### S, AUDITOR,
### ROAUDIT,
### UAUDIT
### Identifies
### IDs that
deserve
strict
ownership
and
monitoring
ZS-1
### UID(0)
review
### ZSEC UID0 TSO READY
or ISPF
option 6
OMVS
### UID(0) users
### UID 0 and
HOME
fields
### Finds UNIX
superuser-
equivalent
IDs
ZS-1
### SURROGAT
review
ZSEC
### SURROGAT
### TSO READY
or ISPF
option 6
### SURROGAT
profiles
userid.SUB
MIT
resources
### Highlights
batch
submit-as
risk
ZS-2
### ICSF review ZSEC ICSF TSO READY ICSF key CKDS/ Connects ZS-2


<!-- page 160 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
or ISPF
option 6
dataset
posture
### PKDS/TKDS
and CSF
class
references
cryptograp
hic services
to RACF/SAF
protection
### Event/alert
review
ZSEC
### EVENTS /
### ZSEC SMF /
ZSEC
### ALERTS
### TSO READY
or ISPF
option 6
### Security
events and
alerts
User,
command/a
ction,
result,
severity
### Shows the
defensive
evidence
trail
ZS-1
### Report Category What It Checks Relevant RACF /
z/OS Area
### Evidence
### Produced
### Defensive
### Follow-Up
### Privilege Privileged and
audit attributes
### RACF user
profiles
### User IDs with
sensitive
attributes
### Review
ownership, need
and monitoring
### SURROGAT Submit-as and
surrogate profiles
### SURROGAT class /
### JES submission
### Profiles and
submit targets
Review USER=
usage and
permitted
submitters
### APF APF history and
library risk
APF,
### LINKLIST/LPA,
dataset profiles
### APF library
indicators
### Review write
access and
change controls
### ICSF Key dataset and
service posture
ICSF,
### CKDS/PKDS/TKDS,
### CSFKEYS/CSFSER
V
### Protected
dataset/service
indicators
### Alert on
refresh/change
and restrict key
dataset access
### Events/Alerts Security
telemetry
### SMF-like events,
### OPERLOG, alerts
### Recent events
and exceptions
### Triage, correlate
and report
### ENUM Mainframe Security Enumeration
ENUM gives students a compact way to run security enumeration checks before they drill down
with RACF commands. In Gibson, ENUM is implemented as a simulated security tool path that can
return focused views such as SEC, APF and ALL. The right teaching point is not that ENUM replaces
RACF commands. It gives audit leads: APF libraries to inspect, SURROGAT rules to verify,
WARNING profiles to test, and service controls to explain.
ENUM
### Mode /
### Option
### Syntax Run From What It
### Enumerate
s
### What To
### Look For
### Security
### Meaning
Lab
### SEC ENUM SEC TSO READY
or ISPF
option 6
### General
security
posture
### Warnings,
privileged
surfaces,
### A quick
first-pass
security
EN-1


<!-- page 161 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
leads policy hints triage
### APF ENUM APF TSO READY
or ISPF
option 6
### APF-related
exposure
### Authorized
library
references
and risky
update
paths
### APF write
access can
become
privileged
code
execution
risk
EN-2
### ALL ENUM ALL TSO READY
or ISPF
option 6
All
supported
sections
### Summary of
### SEC/APF/SV
### C/WHO/PAT
### H-style
results
### Prioritises
the next
manual
checks
EN-3
### SEARCHRX SEARCHRX TSO READY
or ISPF
option 6
### Prebuilt
security
search
report
### WARNING,
### BPX and
### SURROGAT
sections
### Turns RACF
search
output into
audit leads
SR-1
### Lab ZS-1: Run a ZSEC zSecure-style RACF report
### Command context
Start from: TSO READY.
If you are inside ISPF: use =6 first, then enter the ZSEC command.
Commands run from: TSO READY or ISPF option 6.
Do not run these from: ISPF 3.4, the ISPF editor, CICS, FTP or OMVS.
### Why this lab matters
In this lab we’ll use ZSEC as a training representation of a zSecure-style security review. The aim is
to move beyond individual commands and ask broader control questions: which users are
privileged, which IDs have UID(0), what events exist, and which posture areas deserve deeper
review.
### What the commands do
ZSEC opens the simulated security-analysis menu. ZSEC PRIVILEGE focuses on users with sensitive
attributes. ZSEC UID0 checks OMVS superuser-equivalent IDs. ZSEC SETROPTS brings
password/class policy into the same discussion. ZSEC EVENTS or ZSEC ALERTS connects the report
view to the defensive event stream.
### Starting state
Use a seeded Gibson training system with TSO READY available. If no security events exist yet, run
a harmless prior lab such as LISTUSER or NETSTAT first so the event views have context.
### Lab steps


<!-- page 162 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ZSEC
### ZSEC PRIVILEGE
### ZSEC UID0
### ZSEC SETROPTS
### ZSEC EVENTS
### ZSEC ALERTS
### What the output tells us
The evidence is the set of report headings and the rows under each heading. A privileged-user row
changes the question from “does the command work?” to “who owns this authority and why?” A
UID(0) row points to UNIX superuser risk. An event row shows that Gibson can tie actions to
defensive review.
### On a real z/OS system
On a real z/OS system, IBM Security zSecure and RACF reporting are used to analyse users, groups,
profiles, access and audit data. Gibson does not read a live RACF database; it teaches the reporting
questions a student should ask before touching production evidence.
### Defensive takeaway
Defenders should treat privileged attribute reports, UID(0) reports and alert/event reports as triage
inputs. The follow-up is ownership review, access justification, SMF/RACF evidence review and
change-control validation.
### Troubleshooting
If ZSEC returns the menu instead of a report, check the topic spelling. If EVENT or ALERT views are
empty, generate a safe event first or explain that the absence of rows is also a finding about current
simulator state.
### Instructor note
Ask students to pick one ZSEC report row and turn it into a follow-up question. The common
mistake is to copy the whole report without deciding which line actually changes risk.
### Cleanup
Read-only in Gibson. Leave generated events if the next lab uses them for reporting; otherwise
reset simulator state between classes.
### Validation status
### Source validated from Gibson TSO ZSEC handlers and v26 zSecure-style functions. Runtime
validation is recommended in the class profile used for delivery.
### Lab ZS-2: Review APF, SURROGAT and ICSF posture with ZSEC
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ZSEC topic commands.
Do not run these from: CICS, FTP or the ISPF editor.


<!-- page 163 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
This lab targets three high-value control points: APF-authorized code, SURROGAT submit-as
authority and ICSF key-service protection. These are different controls, but they share one security
lesson: a short report can reveal where a tester should spend the next hour validating authority
and evidence.
### What the commands do
ZSEC APF reviews APF-related history or risk where Gibson has state. ZSEC SURROGAT lists submit-
as style profiles. ZSEC ICSF summarises simulated CKDS/PKDS/TKDS protection and CSF class
review points.
### Starting state
Use the standard seeded state. The ICSF section is most useful after reading the ICSF Control-Plane
Protection and Alerting section.
### Lab steps
### ZSEC APF
### ZSEC SURROGAT
### ZSEC ICSF
### What the output tells us
For APF, look for authorized library references that would become serious if writable. For
SURROGAT, look for profile names ending in .SUBMIT. For ICSF, look for protected key dataset lines
and CSFKEYS/CSFSERV review prompts. Each line tells you what to validate next with more specific
commands or lab evidence.
### On a real z/OS system
On real z/OS, APF libraries define trusted code paths, SURROGAT controls submit-as authority and
ICSF protects cryptographic services and key datasets. These areas are usually protected by
RACF/SAF profiles, dataset rules, operational procedures and audit records.
### Defensive takeaway
### Defenders should baseline APF libraries, review SURROGAT access, protect CKDS/PKDS/TKDS
datasets and alert on refresh or control-plane changes. A report is not the control; it is the evidence
that tells you which control to check.
### Troubleshooting
If APF output is empty, check whether the APF lab/state has been exercised. If SURROGAT has no
rows, run the SURROGAT discovery lab or explain that no seeded profile is present. If ICSF output is
generic, cross-reference the ICSF command table.
### Instructor note
Teach this as prioritisation. Students should not treat APF, SURROGAT and ICSF as one topic; they
should explain why each one can change the security boundary in a different way.
### Cleanup
Read-only in Gibson. Do not reset events if the next reporting lab will use them.


<!-- page 164 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Validation status
Source validated from Gibson ZSEC and ICSF handlers. APF depth depends on the simulator state
available in the selected package.
### Lab EN-1: Run ENUM SEC for first-pass security triage
### Command context
Start from: TSO READY.
If you are inside ISPF: use =6 first.
Commands run from: TSO READY or ISPF option 6.
### Why this lab matters
ENUM SEC is a fast security-triage lab. The purpose is to teach the student how an audit helper can
collect leads without replacing interpretation. The output should tell you where to look next, not
what to blindly report.
### What the commands do
ENUM SEC asks Gibson to run the security-oriented enumeration mode. It is expected to produce a
compact view of relevant controls or weakness candidates. The follow-up is to validate each lead
with the specific RACF, APF, ICSF or dataset command that owns the evidence.
### Starting state
Use a TSO READY session with the security training state loaded.
### Lab steps
### ENUM SEC
### What the output tells us
The evidence is the SEC-mode section heading and the weakness candidates beneath it. A useful
result names a control point: a profile, dataset, attribute, APF surface or policy item. The student
should write down the top two items and identify the validating command.
### On a real z/OS system
On a real z/OS system, local REXX or CLIST audit helpers often wrap RACF, catalog, dataset and
system commands to speed up review. The helper is only as good as the commands it runs and the
authority of the user running it.
### Defensive takeaway
Defenders should know which local audit tools exist, who can run them and where their output
goes. Audit automation can expose sensitive security metadata, so reports need the same handling
as assessment evidence.
### Troubleshooting


<!-- page 165 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If ENUM SEC is not recognised, confirm you are at READY or ISPF option 6 and that the Gibson
package includes the ENUM path. If it returns a generic response, record the mode as source-
inferred and use SEARCHRX or ZSEC for the supported lab path.
### Instructor note
Ask students to separate “lead” from “finding.” ENUM output creates leads. A finding requires
validation, risk statement and remediation.
### Cleanup
Read-only in Gibson.
### Validation status
### Source validated from Gibson TSO simulated REXX tool handling and seeded ENUM placeholder
material.
### Lab EN-2: Use ENUM APF to review authorized-library risk
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ENUM mode command.
### Why this lab matters
APF is one of the fastest ways to explain why source-library and program-library permissions
matter. If a user can update code that runs from an authorized path, the risk can move from data
access to control-plane compromise. ENUM APF gives a training view of that question.
### What the commands do
ENUM APF asks for the APF-focused section of the enumeration tool. In Gibson it is used as an
educational surface; on a real assessment the follow-up would include APF lists, dataset access
review, change history and program-library ownership.
### Starting state
Use the standard training state. Cross-reference the APF and ELV.APF privilege concept section if
present.
### Lab steps
### ENUM APF
### What the output tells us
The evidence is any APF library reference, history line or risk note. The useful interpretation is not
“APF exists”; it is whether the library is writable, who owns it, and whether changes are monitored.
### On a real z/OS system
On real z/OS, APF authorization is defined through system configuration such as PROGxx and is
visible through operator/system display paths. Dataset protection determines whether users can
alter authorized libraries.


<!-- page 166 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Defenders should monitor APF library lists and protect those datasets with strict UPDATE/ALTER
controls. Any change to an APF library should be treated as security-sensitive.
### Troubleshooting
If the ENUM APF output is sparse, confirm whether APF state exists in this Gibson build and use
ZSEC APF as a comparison command.
### Instructor note
Ask students why read-only visibility of APF is still valuable to an attacker and why write access
changes the severity.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from ENUM/ZSEC APF command paths where present; real-world depth requires
live APF dataset evidence.
### Lab EN-3: Run ENUM ALL and prioritise follow-up
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ENUM mode command.
### Why this lab matters
ENUM ALL is useful because it creates too much information on purpose. That is the teaching
point: mainframe security review is not just running tools; it is prioritising what the tool tells you.
### What the commands do
### ENUM ALL requests every supported enumeration section. The student should identify which
sections represent identity risk, dataset risk, APF risk, service risk and operational evidence.
### Starting state
Use a clean training state or a state where earlier labs have generated security evidence.
### Lab steps
### ENUM ALL
### What the output tells us
The evidence is the set of section headings and summary lines. A good student answer should
identify the highest-risk line and the command that would validate it next, such as RLIST, LISTDSD,
ZSEC, ICSF DISPLAY or NETSTAT.
### On a real z/OS system


<!-- page 167 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
On a real z/OS system, broad audit scripts can quickly create long reports. Experienced assessors
triage by control impact: privileged IDs, writable trusted code, SURROGAT, weak dataset controls,
exposed services and missing audit coverage first.
### Defensive takeaway
Defenders should require audit reports to be actionable. A report that does not identify owner,
control, evidence and remediation is just noise.
### Troubleshooting
### If ENUM ALL is too short, run ENUM SEC and ENUM APF separately to confirm which modes are
supported in this build.
### Instructor note
Teach prioritisation. Ask students to choose only three follow-up items and defend their choice.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from Gibson ENUM handling; exact sections depend on package state.
### Lab SR-1: Use SEARCHRX to turn RACF searches into audit leads
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: SEARCHRX simulated REXX workflow.
### Why this lab matters
### SEARCHRX is the bridge between raw RACF search commands and a security-audit thought
process. Instead of asking the student to remember every SEARCH command, the lab shows how an
automation helper can organise WARNING mode, dataset, BPX and SURROGAT leads.
### What the commands do
SEARCHRX runs Gibson’s supported simulated REXX search workflow. It calls into the same ideas
as SEARCH ALL WARNING NOMASK and SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT), then
presents the output as sections the student can review.
### Starting state
Use TSO READY or ISPF option 6. If you have not run any RACF profile labs yet, the report may still
show seeded examples.
### Lab steps
### SEARCHRX
### What the output tells us


<!-- page 168 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The evidence is the sectioned report. WARNING mode lines indicate profiles that may log but still
allow access. BPX/FACILITY lines point to UNIX-related controls. SURROGAT lines point to submit-
as authority. Each section should map to a manual follow-up command.
### On a real z/OS system
### On real z/OS, security REXX execs are often used to standardise RACF searches and produce
reports. The exec itself requires authority to see the data and should be controlled as a security
tool.
### Defensive takeaway
Defenders should control who can run audit execs and where output is stored. The content can
reveal high-value datasets, classes and privilege relationships.
### Troubleshooting
If SEARCHRX is not recognised, confirm command context and package version. If output is empty,
validate the underlying RACF commands manually.
### Instructor note
Ask students to pick one SEARCHRX section and turn it into a specific RACF follow-up command.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from Gibson TSO simulated REXX tool handler.
### Lab REP-1: Turn ZSEC, ENUM and SEARCHRX evidence into a finding
### Command context
Start from: the outputs generated in the ZSEC, ENUM or SEARCHRX labs.
Commands run from: none required unless re-running evidence commands at TSO READY.
### Why this lab matters
This lab closes the loop. A technical report is not complete because a tool printed a line. The learner
must explain the evidence, impact, likelihood, control failure and remediation in language a
technical manager can act on.
### What the commands do
ZSEC, ENUM and SEARCHRX provide the evidence source. The student’s job is to select one line,
validate it where possible, and write the finding in a short professional format.
### Starting state
Complete at least one of the ZSEC, ENUM or SEARCHRX labs first.
### Lab steps


<!-- page 169 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Review one ZSEC/ENUM/SEARCHRX output line.
Identify the affected control.
Write: Evidence, Impact, Likelihood, Remediation, Defensive validation.
### What the output tells us
The evidence is the written finding. It should cite the command, output line, affected control and
recommended next step. A weak answer repeats the tool output. A strong answer explains why the
line matters.
### On a real z/OS system
On real z/OS, findings should be backed by RACF profile output, SMF/audit records, dataset access
listings, system display output or product reports such as zSecure. The principle is the same: tool
output must become evidence-backed risk.
### Defensive takeaway
Defenders should be able to validate the finding independently and identify which owner or
control process must change.
### Troubleshooting
If students cannot explain impact, require them to return to the relevant command section: APF,
SURROGAT, ICSF, SETROPTS, dataset access or user privilege.
### Instructor note
Teach report discipline. The common mistake is to paste a tool line without explaining affected
asset, control and remediation.
### Cleanup
No cleanup required.
### Validation status
Manual exercise; source validated through the commands used in prior labs.
### Lab 24: ENUM security enumeration
 Chapter 15. Security Training Playbooks
 Security Tooling: ZREXX, ZSEC, ENUM and SEARCHRX
### Lab 25: SEARCHRX security search workflow
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to choose one ENUM line and name the exact verification command.


<!-- page 170 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Instructor note
If ENUM syntax requires EX form in your package, run the equivalent exec path documented in
Appendix A.
### Troubleshooting
Do not stop at the summary. Follow up with RLIST, LISTDSD, ZSEC, SYS0WN or SDSF depending on
what ENUM reports.
### Defensive takeaway
Real estates often use local REXX/CLIST tools or commercial products to summarise RACF and
system posture. ENUM is the Gibson training equivalent.
### On a real z/OS system
Look for APF candidates, SURROGAT-style exposure, weak dataset/profile signals and summary
lines that point to follow-up commands.
### What the output tells us
### ENUM SEC
### ENUM APF
### ENUM ALL
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
ENUM SEC checks security posture. ENUM APF focuses on APF libraries. ENUM ALL collects the
broad simulator view.
### What the commands do
ENUM gives students a fast triage view before they drill down into individual RACF profiles. Use it
to decide what deserves deeper review.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 26: SYS0WN APF and ownership review
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 171 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students how SEARCHRX differs from a single SEARCH command.
### Instructor note
If the exec is missing, confirm the dataset/member name or use the direct SEARCH commands.
### Troubleshooting
Review who can run and modify audit execs; a broken search script can hide risk or create false
confidence.
### Defensive takeaway
Real sites often use REXX/CLIST automation to standardise RACF searches and evidence collection.
The script itself needs change control.
### On a real z/OS system
The evidence is the grouped report output: warning-mode datasets, submit-as profiles and other
candidates that need a RACF follow-up command.
### What the output tells us
EX 'IBMUSER.SEARCHRX.RX'
### SEARCH ALL WARNING NOMASK
SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
### EX IBMUSER.SEARCHRX.RX runs the SEARCHRX exec where implemented. It commonly wraps
WARNING, SURROGAT, APF and dataset searches into a repeatable report.
### What the commands do
SEARCHRX sits between raw RACF SEARCH output and security reporting. It teaches students how
to turn several searches into audit leads.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 27: FTP JES submission with QUOTE SITE FILETYPE=JES
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 172 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to prove both trust and writeability before calling it high risk.
### Instructor note
If SYS0WN is not available, run D PROG,APF and ENUM APF as the supported alternative.
### Troubleshooting
Alert on APF list changes and broad UPDATE/ALTER to authorised libraries. Review owner/group
relationships as carefully as permits.
### Defensive takeaway
### Real APF/library ownership review combines APF list, PROGxx/SETPROG state, RACF dataset
profiles and change-control evidence.
### On a real z/OS system
The evidence is an APF library or execution path paired with risky ownership or update authority.
### What the output tells us
### D PROG,APF
### EX SYS0WN.RX
### ENUM APF
### ZSEC APF
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
### EX SYS0WN.RX reviews APF, execution-path or ownership style exposure where Gibson
implements the training exec. D PROG,APF and ENUM APF provide corroborating evidence.
### What the commands do
SYS0WN teaches a privilege-escalation thought process safely: find trusted paths, then check
whether the wrong users can update them.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 28: SQL and TSh0cker-style workflow in Gibson
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 173 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to separate submission evidence from execution evidence.
### Instructor note
If the server does not accept JES mode, confirm the FTP service profile and port.
### Troubleshooting
Monitor FTP logins, SITE FILETYPE=JES usage, submitted USER= values and job output retrieval
from network sessions.
### Defensive takeaway
Real z/OS FTP can support FILETYPE=JES where configured, allowing job submission and output
retrieval through FTP. It must be tightly controlled.
### On a real z/OS system
The evidence is the FTP 226-style completion message and the JES job/spool entry. The FTP prompt
proves submission path; SDSF proves JES processed it.
### What the output tells us
ftp 127.0.0.1 2022
quote site filetype=jes
put job.jcl
quit
### SDSF ST
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
QUOTE SITE FILETYPE=JES switches the FTP session into JES submission mode. PUT/STOR submits
the JCL. SDSF/JES review happens after the upload path completes.
### What the commands do
FTP/JES matters because file transfer can become job submission. The lab teaches why an ordinary
network service can cross into batch execution.
### Why this lab matters
Start from the FTP prompt. FTP commands run at ftp>. Verify results later in SDSF/JES. Do not type
SDSF commands inside FTP.
### Command context
### Lab 29: Security evidence to finding
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.


<!-- page 174 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
Ask students what Gibson proves and what would still need a real authorised test environment.
### Instructor note
### If TSh0cker is not implemented, keep the lab conceptual and use supported RUN SQL/FTP
SQL/banking SQLi paths only.
### Troubleshooting
### Monitor SQL execution routes, FTP SQL mode, CICS/REST query inputs and privileged catalog
queries.
### Defensive takeaway
Real TShOcker-style discussions involve abusing service paths and SQL execution context. Gibson
should teach the reasoning and evidence safely.
### On a real z/OS system
### The evidence is SQL output, SQLCODE/SQLSTATE, or the banking/API trace showing the unsafe
branch. Unsupported TSh0cker behaviour must be called conceptual.
### What the output tells us
### RUN SQL SELECT CURRENT SQLID FROM SYSIBM.SYSDUMMY1
### RUN SQL SELECT USERID, AUTHORITY FROM SYSIBM.SYSUSERAUTH
# If FTP SQL mode is enabled:
quote site filetype=sql
put whoadm.sql
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
RUN SQL executes simulator SQL. FTP SITE FILETYPE=SQL processes uploaded SQL where enabled.
The banking lab includes SQL-like unsafe input branches for education.
### What the commands do
This lab teaches SQL/TSh0cker-style risk as a bounded Gibson workflow. The goal is to show how
unsafe SQL paths and FTP SQL processing can change data or reveal authority in a lab, not to fake
production exploitation.
### Why this lab matters
### Start from the Db2/SQL simulator, CICS banking lab, REST SQL gateway or FTP SQL mode
depending on which path is enabled. Do not claim a real exploit unless the simulator explicitly
supports it.
### Command context


<!-- page 175 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Missing and Conceptual Security Tool Capabilities
The current Gibson package supports ZSEC, ENUM, SEARCHRX and SYS0WN-style training surfaces,
but a complete executable ZREXX package is not present in the Gibson source tree. The uploaded
ZREXX material is valuable as a hardening and design reference, but it is not enough to claim a
built-in ZREXX command. The manual therefore treats ZREXX as security-automation concept and
future integration until source is supplied.
 Chapter 16. Instructor Guide and Assessment
 Appendix A. Command Reference by Execution Context
### Lab 30: Privilege and exposure triage
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through privilege and exposure triage as a practical evidence exercise, not as
a command checklist. The concept being taught is identity, class, profile and authority analysis.
From a tester’s point of view, the aim is to produce a specific piece of evidence: user attributes,
profile class, UACC, access list, WARNING or audit fields. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do
LISTUSER IBMUSER ALL: asks for the fuller identity view. In a real RACF workflow, the ALL-style
view is where default group, attributes, revoke/protected state and audit-relevant details become
visible.
LISTGRP *: lists group information. Group membership often explains access inherited by users.
SETROPTS LIST: lists RACF-wide options and class status. It shows whether classes are active and
whether profile decisions are cached or enforced.
RLIST DATASET SYS1.PARMLIB: reviews a high-value dataset profile. SYS1.PARMLIB is security-
relevant because it holds system configuration on real z/OS.
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
### Starting state


<!-- page 176 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### LISTUSER IBMUSER ALL
LISTGRP *
### SETROPTS LIST
### RLIST DATASET SYS1.PARMLIB
### NETSTAT PORTLIST
### What the output tells us
For `LISTUSER IBMUSER ALL`, look for the RACF field that answers the security question: attribute,
class, profile, UACC, WARNING, access list or policy setting. That field is the evidence you would cite
in a finding.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### LISTUSER IBMUSER
ALL
### Displays a simulated
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


<!-- page 177 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
LISTGRP * Lists RACF group
information.
* requests a broader
inventory where
supported by Gibson.
### Groups are how many
z/OS environments
delegate authority, so
group membership
often explains
unexpected access.
### Evidence is a group list,
owner data or
connected users.
### SETROPTS LIST Displays or alters
simulated RACF
system-wide settings.
### LIST reports effective
options;
### CLASSACT/RACLIST/RE
### FRESH style operands
model class activation
and caching.
### SETROPTS explains the
security manager
posture, not just a
single user or profile.
### Evidence is a policy
summary or
activation/refresh
message.
### RLIST DATASET
### SYS1.PARMLIB
### Displays a simulated
### RACF general resource
profile.
### CLASS identifies the
resource class; AUTH
or ALL asks for access
list and authority
detail.
### RLIST converts a
profile name into
evidence: owner, UACC,
warning state and
access list.
### Evidence is the profile
detail and any explicit
permits.
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
### Difficulty Intermediate
### Estimated time 60 minutes
### Objective Build a security snapshot from users, groups, SETROPTS,
dataset profiles and listeners.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 31: OPERLOG and security event review
### Command context
Start from: Master Console or browser dashboard
Commands run from: Master Console/dashboard controls, or from the subsystem that triggers the
event
Do not run these from: ISPF editor, FTP or CICS unless generating the event intentionally
Why context matters: Detection labs separate activity generation from defender observation.
### Why this lab matters
In this lab we’ll work through operlog and security event review as a practical evidence exercise,
not as a command checklist. The concept being taught is operator console, event stream and


<!-- page 178 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
system-state evidence. From a tester’s point of view, the aim is to produce a specific piece of
evidence: console display output, WTOR state, event line or security summary. From a defender’s
point of view, the same evidence explains what should be controlled, logged or challenged before
the activity becomes normalised. By the end of the lab, you should be able to say why each
command was used and what changed in your understanding of the Gibson environment.
### What the commands do
SECEVENTS: shows simulator security events so students can connect actions to event evidence.
SDSF OPERLOG: opens the OPERLOG view through SDSF-style workflow, providing console/security
event context.
D SECURITY,DAILY: shows the simulator security summary view. Its value is tying technical actions
to security reporting.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
### SECEVENTS
### SDSF OPERLOG
### D SECURITY,DAILY
### What the output tells us
For `SECEVENTS`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
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
### Teach operlog and security event review by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup


<!-- page 179 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### SECEVENTS Reviews simulated
security events or
OPERLOG-style output.
### The panel or command
selects event/log
visibility.
### Logs are where proof
becomes defensible.
### They also show
whether the simulator
raises the right signals.
### Evidence is an event
line, command audit
record or console log
entry.
### SDSF OPERLOG Enters or queries the
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
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Review security events and determine what activities should be
reported.
Prerequisites IBMUSER session.
### Validation Runtime/static plus source panel validation
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### ICSF Control-Plane Protection and Alerting
ICSF matters because cryptography on z/OS is not just an application feature; it is a platform
service. Real sites protect callable services, key labels and key data sets such as CKDS, PKDS and
TKDS with RACF classes and strict operational controls. Gibson does not hold real keys, but it gives
students a safe control-plane model: display status, inspect CKDS/PKDS/TKDS state, attempt refresh
actions, and verify that the action created audit or console evidence.
### Command Run from Gibson behaviour Real z/OS concept Defensive focus
### ICSF STATUS / TSO READY or Displays ICSF operational Who can view


<!-- page 180 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ICSF DISPLAY
### STATUS
### ISPF option 6 simulated ICSF
status
status and control
plane
cryptographic
service state
### ICSF DISPLAY
### CKDS/PKDS/TKDS
### TSO READY or
### ISPF option 6
### Displays
simulated key
dataset status
messages
### CKDS/PKDS/TKDS
contain sensitive
key/token
material or
metadata in real
systems
### Dataset and key-
label access
should be tightly
controlled
### ICSF REFRESH
### CKDS/PKDS/TKDS
### TSO READY or
### ISPF option 6
### Simulates refresh
and records
### SMF80-style
evidence
### Operational
refresh of key
data set state
### Any refresh
should be
authorised,
change-controlled
and alerted
### D ICSF / F
### ICSF,REFRESH,TK
DS
### Master Console Displays or
modifies ICSF
state through
console path
### Operator
command path
for ICSF control
### Console
commands need
separation of
duties and
monitoring
### ZSEC ICSF TSO READY Shows posture
summary for ICSF
protection
### Security posture
review of
cryptographic
services
Check
### CSFSERV/CSFKEY
### S-like controls
and dataset
protection
### Lab ICSF-1: Protect simulated ICSF datasets and alert on refresh activity
### Command context
Start from TSO READY or ISPF option 6 for TSO commands. Use the Master Console for D/F ICSF
commands. Do not run ICSF REFRESH from CICS, FTP, OMVS or ISPF 3.4. Review alerts in the
Master Console or OPERLOG after the action.
### Why this lab matters
In this lab we’ll use Gibson to practise the defensive question that matters around ICSF: who can
see or change cryptographic control-plane state, and does a change leave evidence? The lab is safe
because Gibson does not store real key material, but the risk model is real.
### What the commands do
### ICSF STATUS establishes the baseline. ICSF DISPLAY CKDS/PKDS/TKDS shows the simulated
protected key dataset surfaces. ICSF REFRESH CKDS tests whether the current user can perform a
change-like operation. D ICSF and F ICSF,REFRESH,TKDS show the console path for the same
control-plane idea. ZSEC ICSF gives a security posture view.
### Starting state


<!-- page 181 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Use a lab user such as IBMUSER for the authorised path, then repeat the refresh attempt as a lower-
privilege user if available. The Master Console should be available so that alerts and audit evidence
can be reviewed.
### Lab steps
### ICSF STATUS
### ICSF DISPLAY CKDS
### ICSF DISPLAY PKDS
### ICSF DISPLAY TKDS
### ZSEC ICSF
### ICSF REFRESH CKDS
### D ICSF
### F ICSF,REFRESH,TKDS
### What the output tells us
The baseline commands should show simulated ICSF status and key dataset surfaces. The refresh
command should produce a clear status or denial and should create audit/console evidence. If the
display succeeds but refresh is denied, the simulator is teaching read versus update authority. If a
refresh succeeds silently, the defensive control path is incomplete and should be treated as a
documentation or product issue.
### On a real z/OS system
Real ICSF protects callable services and key material through RACF/SAF controls such as CSFSERV,
CSFKEYS and related cryptographic classes, plus dataset protection for CKDS, PKDS and TKDS. Real
key stores and master-key operations are highly sensitive and normally require strict separation of
duties, change records and operational logging.
### Defensive takeaway
Defenders should baseline who can display ICSF status, who can refresh key data sets, who can
access key labels, and whether refresh/change attempts create timely alerts. Protect the datasets,
protect the callable services, and alert on any unexpected display or refresh activity.
### Troubleshooting
If ICSF commands are not recognised, confirm you are at TSO READY or ISPF option 6. If console
commands fail, confirm you are in the Master Console path. If refresh appears to succeed but no
alert appears, check OPERLOG, dashboard alert polling and SMF80-style audit entries.
### Instructor note
Teach this as a control-plane lab, not a key-management lab. The point is not to show keys; the
point is to show why key services, key datasets and refresh commands need access control and
monitoring.
### Cleanup
No real keys are changed. If the lab increments a simulated key dataset version or creates an alert,
leave it as evidence for the detection discussion or reset Gibson to the chapter baseline before the
next cohort.
### Validation status


<!-- page 182 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Source validated from Gibson ICSF documentation, TSO handlers, console handlers and v24 tests.
Runtime validation is recommended in the selected classroom profile.
