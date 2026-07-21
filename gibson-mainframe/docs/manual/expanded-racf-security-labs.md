## Expanded RACF Security Labs
This RACF lab sequence comes before ACF2 because RACF is the clearest place to learn users,
groups, resource classes, profiles, UACC, access lists and policy posture. The later ACF2 labs
deliberately compare a different security-manager model against this RACF baseline.
### Lab RACF-1: Inspect your RACF identity with LISTUSER
### Command context
Run from TSO READY or ISPF option 6. Do not run LISTUSER from ISPF 3.4, the ISPF editor, FTP or
CICS.
### Why this lab matters
In this lab we turn a user ID into security evidence. LISTUSER is one of the first RACF commands a
tester uses because account state, group membership and special attributes can change the whole
assessment path.
### What the commands do
LISTUSER displays a simulated RACF user profile. The ALL form asks for the fuller view, including
attributes, default group, password/account state and group connections where Gibson exposes
them.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### LISTUSER IBMUSER ALL
### LISTUSER GUEST ALL
### What the output tells us
### Look for SPECIAL, OPERATIONS, AUDITOR, REVOKE, PROTECTED, default group and last-access
style fields. These fields tell you whether the ID is powerful, usable, disabled or intended as a
service account.
### On a real z/OS system
On real z/OS, LISTUSER queries RACF profile information through the RACF command processor.
Viewing privileged attributes may itself be restricted by site policy and can be audited depending
on configuration.
### Defensive takeaway


<!-- page 68 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should review privileged, stale and unexpected active accounts. A tester should treat
privileged usable IDs as high-value evidence requiring careful validation.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-2: Review group membership and inherited authority
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
Groups are where RACF privilege often becomes less obvious. A user may look ordinary until group
connections reveal inherited access to datasets, resources or operational functions.
### What the commands do
LISTGRP shows group-level information, while LISTUSER shows which groups a user is connected
to. Together they help explain inherited authority.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### LISTUSER IBMUSER ALL
### LISTGRP SYS1
### LISTGRP OPERATIONS
### What the output tells us
Look for connected groups and owner/authority relationships. The evidence is the link between a
user and the group that could carry access.
### On a real z/OS system


<!-- page 69 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Real RACF group structures are central to administration and delegation. Group-SPECIAL,
ownership and connect authority can materially change risk.
### Defensive takeaway
Defenders should review powerful groups, unexpected connects and stale group membership.
Group privilege is often easier to miss than direct user attributes.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-3: Discover RACF profiles with SEARCH
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
SEARCH changes the question from “what do I already know?” to “what protected resources can I
discover?”. It is a reconnaissance command for RACF profile space.
### What the commands do
SEARCH lists matching profiles in a RACF class. FILTER narrows the search so the learner can focus
on a dataset HLQ or resource family.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(DATASET) FILTER(IBMUSER.*)
SEARCH CLASS(FACILITY) FILTER(*)
### What the output tells us
Look for profile names, class names and whether generic patterns appear. The result tells you
where to use RLIST or LISTDSD next.


<!-- page 70 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
On real z/OS, SEARCH access and output may be controlled. Profile discovery can expose naming
conventions, sensitive resources and weak control boundaries.
### Defensive takeaway
Defenders should assume profile names can become reconnaissance evidence and should monitor
unusual broad searches in sensitive classes where auditing is enabled.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-4: Inspect a dataset profile with LISTDSD and RLIST
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
Dataset profiles turn a dataset name into an access-control decision. This lab teaches how UACC
and access lists explain who can read, update or alter data.
### What the commands do
LISTDSD and RLIST inspect dataset protection. LISTDSD is dataset-focused; RLIST gives a general
RACF resource-profile view where supported.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
LISTDSD DATASET('IBMUSER.JCL.LAB') ALL
### RLIST DATASET IBMUSER.JCL.LAB ALL
### What the output tells us


<!-- page 71 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Look for UACC, WARNING, OWNER and access list entries. UPDATE or ALTER on source, JCL, REXX
or APF-related libraries is the evidence that matters.
### On a real z/OS system
Real RACF DATASET profiles protect MVS datasets. Generic profiles, discrete profiles and access
lists are core to real mainframe security reviews.
### Defensive takeaway
Defenders should baseline sensitive HLQs, review ID(*) access, and investigate broad
UPDATE/ALTER grants on executable or configuration libraries.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-5: Find WARNING mode profiles
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
WARNING mode is useful during staged policy rollout, but forgotten WARNING profiles can allow
access while only recording that access would have failed. This lab teaches why “logged but
allowed” is still a risk.
### What the commands do
### SEARCH ALL WARNING NOMASK looks for profiles marked WARNING. RLIST then confirms the
profile and shows access details.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps


<!-- page 72 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SEARCH ALL WARNING NOMASK
### RLIST DATASET IBMUSER.WARN.LIB ALL
### What the output tells us
### Look for the WARNING attribute and any access entries that would otherwise be denied. The
profile is important because it may train users, jobs or applications around a control that is not
actually enforcing.
### On a real z/OS system
On real RACF, WARNING can log access that would fail without denying it. Sites use it carefully
during migration or policy testing, but it requires review and expiry discipline.
### Defensive takeaway
Defenders should track WARNING profiles, owners and expiry plans. WARNING on sensitive data
or executable libraries should be treated as a finding until justified.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-6: Review SURROGAT submit-as exposure
### Command context
Run from TSO READY or ISPF option 6 for RACF review. JCL submission happens later from READY,
ISPF edit or FTP/JES depending on the lab.
### Why this lab matters
SURROGAT controls whether one user can submit work as another. From a tester’s point of view
this can become a batch impersonation path; from a defender’s point of view it is a high-value
control class.
### What the commands do
### SEARCH locates submit-as profiles. RLIST shows who is permitted to the specific SURROGAT
resource.
### Starting state


<!-- page 73 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)
### RLIST SURROGAT IBMUSER.SUBMIT ALL
### What the output tells us
Look for <userid>.SUBMIT profiles and the access list. A permitted submitter can become
operationally significant if the target ID owns privileged batch workflows.
### On a real z/OS system
Real JES/RACF checks SURROGAT when USER= appears on a JOB card or when submit-as behaviour
is requested. The job output often records acceptance or rejection evidence.
### Defensive takeaway
Defenders should review SURROGAT permits, especially to privileged IDs, and monitor submitted
jobs that specify USER= or unexpected submitter/owner combinations.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-7: Review SERVAUTH, FACILITY and OPERCMDS exposure
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
### Not all mainframe risk is in datasets. FACILITY, SERVAUTH and OPERCMDS protect sensitive
services, network access and operator functions. This lab teaches students to look beyond users
and data.
### What the commands do


<!-- page 74 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
These SEARCH commands enumerate profiles in classes that often gate sensitive system, network
or operator capabilities.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(FACILITY) FILTER(*)
SEARCH CLASS(SERVAUTH) FILTER(*)
SEARCH CLASS(OPERCMDS) FILTER(*)
### What the output tells us
Look for broad profiles, ID(*) access, weak UACC and names that map to operator commands,
network zones or privileged services.
### On a real z/OS system
On real z/OS, these classes are part of SAF/RACF control for sensitive functions. Poorly controlled
FACILITY, SERVAUTH or OPERCMDS profiles can expose powerful capabilities.
### Defensive takeaway
Defenders should treat broad access in these classes as high priority and review whether each
permit aligns with a documented operational need.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-8: Review SETROPTS policy posture
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters


<!-- page 75 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
SETROPTS LIST gives the policy backdrop for the profile evidence gathered so far. It helps students
understand which classes are active and which password/audit controls are in force.
### What the commands do
SETROPTS LIST displays global RACF options such as class activity, generics, password controls and
other security posture indicators where Gibson simulates them.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### SETROPTS LIST
### What the output tells us
Look for active classes, audit-related settings and password policy indicators. A profile in an
inactive class may not protect what students think it protects.
### On a real z/OS system
Real RACF SETROPTS controls global RACF behaviour. It is administrative and sensitive; output
interpretation requires care and site context.
### Defensive takeaway
Defenders should baseline SETROPTS output and review changes through change control, because
a single global setting can alter enforcement across many resources.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-9: Protect ICSF-related resources
### Command context
Run from TSO READY or ISPF option 6 for RACF commands, and use the Master Console/ICSF lab
where the manual directs you.


<!-- page 76 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
ICSF key-store datasets and control-plane functions are critical. This lab links RACF thinking to
cryptographic service protection and alerting.
### What the commands do
### The RLIST commands review simulated CKDS, PKDS and TKDS dataset protection. ZSEC ICSF
provides the training summary where implemented.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RLIST DATASET SYS1.CSF.CKDS ALL
### RLIST DATASET SYS1.CSF.PKDS ALL
### RLIST DATASET SYS1.CSF.TKDS ALL
### ZSEC ICSF
### What the output tells us
Look for broad READ, UPDATE or ALTER access and for alert/event output when ICSF refresh or
key-store activity is simulated.
### On a real z/OS system
On real z/OS, ICSF uses datasets such as CKDS, PKDS and TKDS and is tightly integrated with
RACF/SAF controls. Poor protection can become a serious cryptographic-control weakness.
### Defensive takeaway
### Defenders should monitor key-store access, refresh commands and unexpected changes. ICSF
dataset protection should be part of privileged access review.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.


<!-- page 77 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab RACF-10: Add an APF library with UACC UPDATE for training review
### Command context
### Run from TSO READY or ISPF option 6. This is a Gibson-only misconfiguration exercise in a
disposable training state.
### Why this lab matters
APF-authorized libraries are trusted code paths. Giving everyone UPDATE to an APF library is the
kind of configuration that turns ordinary dataset access into a privilege-escalation concern.
### What the commands do
The commands create or inspect a training APF-library exposure, grant broad UPDATE access, then
review the evidence using RACF and security-tool views.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RDEFINE DATASET GIBSON.APF.LIB UACC(UPDATE)
PERMIT 'GIBSON.APF.LIB' ID(*) ACCESS(UPDATE)
### RLIST DATASET GIBSON.APF.LIB ALL
### ENUM APF
### SYS0WN
### What the output tells us
Look for UACC(UPDATE), ID(*) UPDATE or an equivalent broad permit on the APF-related library.
That is the evidence that the trusted code boundary is exposed.
### On a real z/OS system
On real z/OS, APF libraries are controlled through system configuration such as PROGxx/SETPROG
and protected by dataset access controls. UPDATE to APF libraries is a high-risk finding.
### Defensive takeaway
Defenders should restrict APF library update access to tightly controlled build/deploy IDs and alert
on APF list changes or broad access to APF datasets.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup


<!-- page 78 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Remove the training profile/permit or reset Gibson before continuing. Never treat this lab as
production change guidance.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-11: Create a WARNING-mode library
### Command context
Run from TSO READY or ISPF option 6. This is a Gibson-only controlled misconfiguration exercise.
### Why this lab matters
This lab creates a profile that illustrates WARNING mode. The point is to show how an apparently
protected resource may still allow access while producing warning/audit evidence.
### What the commands do
RDEFINE creates a training dataset profile with WARNING. RLIST confirms the profile. SEARCH
ALL WARNING NOMASK finds WARNING profiles for follow-up.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RDEFINE DATASET GIBSON.WARN.LIB UACC(NONE) WARNING
### RLIST DATASET GIBSON.WARN.LIB ALL
### SEARCH ALL WARNING NOMASK
### What the output tells us
Look for the WARNING attribute. If Gibson simulates an access test, look for evidence that the
access would have failed but was allowed because the profile is in WARNING.
### On a real z/OS system
Real RACF WARNING mode is used for staged control rollout and testing. It should not remain
indefinitely on sensitive datasets because enforcement is not hard denial.
### Defensive takeaway
### Defenders should maintain an owner, reason and expiry for every WARNING profile and alert
when sensitive libraries are left in WARNING mode.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note


<!-- page 79 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Delete the training profile or reset Gibson after the lab if the next class section expects a clean
RACF state.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-12: Create a SURROGAT submit-as path and submit JCL
### Command context
Run RACF setup from TSO READY or ISPF option 6. Submit JCL from READY or ISPF edit. Review
output in SDSF/JES.
### Why this lab matters
### This lab joins RACF, SURROGAT and JES. It teaches that batch submission can become an
impersonation path when one ID is permitted to submit work as another.
### What the commands do
### The RACF commands establish a training submit-as path. The SUBMIT command starts a simple
job, and SDSF/JES review provides the evidence of how the job was accepted or rejected.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### ADDUSER SUBMITR DFLTGRP(SYS1)
### RDEFINE SURROGAT IBMUSER.SUBMIT UACC(NONE)
### PERMIT IBMUSER.SUBMIT CLASS(SURROGAT) ID(SUBMITR) ACCESS(READ)
SUBMIT 'IBMUSER.JCL(SURRJOB)'
### SDSF ST
### What the output tells us
Look for the SURROGAT profile, the submitter permit, the JOB USER= target and the resulting job
ID/return code or rejection message.
### On a real z/OS system
On real z/OS, SURROGAT controls submit-as behaviour for batch. JES and RACF evidence can show
who submitted the job and which user the job ran as.
### Defensive takeaway
Defenders should review SURROGAT permits to privileged IDs and monitor jobs where submitter
and execution user differ unexpectedly.


<!-- page 80 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Remove the training SURROGAT permit/profile and training user, or reset Gibson before returning
to the baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-13: Convert RACF evidence into a security finding
### Command context
Use evidence from the previous RACF labs. This is a reporting exercise, not a configuration step.
### Why this lab matters
### A penetration test does not end with a command. This lab teaches students to convert RACF
evidence into a finding with impact, proof and remediation.
### What the commands do
The “command” here is the reporting workflow: select evidence, explain why it matters and
propose a defensible remediation.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### Review evidence from RACF-1 through RACF-12
Write: Title, Evidence, Impact, Likelihood, Remediation, Defensive validation
### What the output tells us
A good finding names the resource, shows the risky field or permit, explains the impact and gives
the owner a practical validation step.
### On a real z/OS system
Real mainframe findings must distinguish discovery from exploitability and must map evidence to
RACF, JES, APF or operational control points.
### Defensive takeaway


<!-- page 81 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should be able to reproduce the evidence, confirm whether access is required, and apply
or verify the corrective control.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### From RACF to ACF2
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to defend their severity rating with the output, not opinion.
### Instructor note
If the finding sounds generic, add the resource name, class, user/group and access level.
### Troubleshooting
Defenders should be able to validate the fix by rerunning the same command or report and seeing
the risky condition removed.
### Defensive takeaway
Real assessment reports should separate evidence, impact, exploitability and remediation, with
enough detail for administrators to reproduce and fix the issue.
### On a real z/OS system
A good answer links an exact command output line to a control failure and a remediation. For
example, APF UACC UPDATE is stronger evidence than “APF looks bad.”
### What the output tells us
Choose one previous RACF lab result.
Write: Evidence, Impact, Likelihood, Recommendation, Defensive Validation.


<!-- page 82 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
Use LISTUSER, RLIST, LISTDSD, SEARCH, ZSEC, ENUM and JES/SDSF evidence from previous labs to
write a concise finding.
### What the commands do
This capstone forces students to turn RACF evidence into a finding. The value is in explaining
impact, not collecting another page of output.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
