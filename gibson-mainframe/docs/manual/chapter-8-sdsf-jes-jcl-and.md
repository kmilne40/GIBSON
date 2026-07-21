## Chapter 8. SDSF, JES, JCL, and
NJE
This section covers job panels, JES queues, JES2 commands, NJE node/line controls and JCL-related
training flows.
### Implementation evidence
### Area Source evidence
### SDSF gibson/apps/sdsf.py
### JES gibson/core/jes.py
### NJE gibson/core/nje.py
### Operational model
This chapter connects submitted work to JES queues and SDSF-style output. The operational path is
job text to job ID to spool files to return code, with NJE/JES commands adding the operator and
network-job view.
### Security relevance
The security value is evidence handling. Spool output can expose commands, dataset names, return
codes and errors, while JES controls determine who can submit, cancel, hold, release or read other
users' work.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### JES/JCL/NJE TRANSMIT TRANSMIT userid
DA('dataset')
[OUTDSN('package')] - create a
simulated XMIT package.
gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE XMIT Alias of TRANSMIT. gibson/apps/tso.py
LEGACY_HELP
JES/JCL/NJE RECEIVE RECEIVE INDSN('package')
[DA('target')] - restore a
transmitted data set.
gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE SUBMIT Submits a JCL job. gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE JES Simulated Job Entry
Subsystem commands: JES
### STATUS, JES SUBMIT
gibson/apps/tso.py
LEGACY_HELP


<!-- page 115 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
<description>.
SDSF ST/DA/I/O/H/AD/AS SDSF panel command gibson/apps/sdsf.py:260
### SDSF LOG/SYSLOG/OPERLOG/
### SMF80/SMF7/ULOG/SR
SDSF panel command gibson/apps/sdsf.py:263
### SDSF JC/INIT/MAS/PR/PUN/RDR/
### PROC/JES/JG/J0/JRI/JRJ/RM/
### RMA/SO/SP
SDSF panel command gibson/apps/sdsf.py:276
SDSF PS/FS/BPXO SDSF panel command gibson/apps/sdsf.py:278
### SDSF SYS/SYM/APF/CK/DYNX/ENQ/
### ENQC/GT/LLS/LNK/LPA/LPD/
### PAG/PARM/PC/SSI/SVC/SYSP
SDSF panel command gibson/apps/sdsf.py:280
### SDSF FILTER/SORT/OWNER/
### PREFIX/SYSNAME/RESET/
### REFRESH
SDSF primary command gibson/apps/sdsf.py:623
JES2 $(D|C|P|A|H) JOB(jobid) JES2 operator command gibson/core/jes.py:481
This section has 13 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 10: Review JES state and SDSF status panel
### Command context
Start from: TSO READY or ISPF menu path to SDSF
Commands run from: SDSF panels and JES/spool output views
Do not run these from: FTP, CICS, OMVS or ISPF editor
Why context matters: SDSF reviews jobs and output; it is not the same context as FTP/JES
submission.
### Why this lab matters
In this lab we’ll work through review jes state and sdsf status panel as a practical evidence
exercise, not as a command checklist. The concept being taught is JES spool, job status and
operator-style visibility. From a tester’s point of view, the aim is to produce a specific piece of
evidence: job ID, return code, spool entry or JES2 display response. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
JES STATUS: summarises the simulated job-entry environment. It is the starting point before
creating or browsing job output.
JES SUBMIT MANUALJOB: submits a controlled training job and should produce a job identifier or
equivalent state change.


<!-- page 116 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
SDSF ST: opens the status-oriented SDSF view where job state, return codes and output availability
become visible.
### Starting state
Start from READY with JES/SDSF simulation available. If a job ID is referenced, either submit the
training job first or replace the ID with one that exists in your current state.
### Lab steps
### JES STATUS
### JES SUBMIT MANUALJOB
### SDSF ST
### What the output tells us
For `JES STATUS`, look for the JES job identifier, status, return code or spool entry that proves the
job or JES command was processed. Without job/spool evidence, you cannot explain what actually
ran.
### On a real z/OS system
SDSF sits over JES and operator functions. Access to job output can expose commands, dataset
names, errors and sometimes secrets; access is commonly governed by SDSF/SAF resources such as
JESSPOOL and panel controls.
### Defensive takeaway
Watch job submission, spool reads, operator commands and access to output owned by other users.
Spool access is often underestimated.
### Troubleshooting
If a job is not visible, check the job name/owner, whether it has completed and which panel/filter is
active.
### Instructor note
Point students to the job ID, owner and return code before they open output. Students often jump
straight to spool text without asking whether they should be allowed to see it.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### JES STATUS Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
### SDSF is where job
status and output
become evidence. It is
### Evidence is a job list,
output panel or JES
state summary.


<!-- page 117 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
where implemented. also where credentials
and system messages
often leak.
### JES SUBMIT
### MANUALJOB
### Submits a simulated
JES job.
### The job/member name
selects the JCL or
canned workload.
### Submission is how
batch work becomes
executable on z/OS;
attackers and admins
both care about what
runs and as whom.
### Evidence is a JOBID or
JES status entry.
### SDSF ST Enters or queries the
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
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Submit a simple simulator job and review JES/SDSF status.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 11: Explore JES2 and NJE commands
### Command context
Start from: TSO READY or ISPF menu path to SDSF
Commands run from: SDSF panels and JES/spool output views
Do not run these from: FTP, CICS, OMVS or ISPF editor
Why context matters: SDSF reviews jobs and output; it is not the same context as FTP/JES
submission.
### Why this lab matters
In this lab we’ll work through explore jes2 and nje commands as a practical evidence exercise, not
as a command checklist. The concept being taught is JES spool, job status and operator-style
visibility. From a tester’s point of view, the aim is to produce a specific piece of evidence: job ID,
return code, spool entry or JES2 display response. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do


<!-- page 118 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
$D NJEDEF: issues a JES2-style display of NJE definition information. It teaches operator-style
discovery of network job-entry configuration.
$D NODE: displays known JES2/NJE nodes, turning the question from “is NJE present?” into “who is
trusted or defined?”
$D JOB(JOB00001): queries a specific job by identifier. It teaches targeted job-status investigation
rather than broad spool browsing.
### Starting state
Start from READY with JES/SDSF simulation available. If a job ID is referenced, either submit the
training job first or replace the ID with one that exists in your current state.
### Lab steps
$D NJEDEF
$D NODE
$D JOB(JOB00001)
### What the output tells us
For `$D NJEDEF`, look for the JES job identifier, status, return code or spool entry that proves the
job or JES command was processed. Without job/spool evidence, you cannot explain what actually
ran.
### On a real z/OS system
SDSF sits over JES and operator functions. Access to job output can expose commands, dataset
names, errors and sometimes secrets; access is commonly governed by SDSF/SAF resources such as
JESSPOOL and panel controls.
### Defensive takeaway
Watch job submission, spool reads, operator commands and access to output owned by other users.
Spool access is often underestimated.
### Troubleshooting
If a job is not visible, check the job name/owner, whether it has completed and which panel/filter is
active.
### Instructor note
Point students to the job ID, owner and return code before they open output. Students often jump
straight to spool text without asking whether they should be allowed to see it.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence


<!-- page 119 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
$D NJEDEF Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
$D NODE Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
$D JOB(JOB00001) Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Identify operator-style JES2/NJE control commands and safe
display flows.
Prerequisites Source-validated command matrix.
Validation Source validated; runtime depends on interactive console
context
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
