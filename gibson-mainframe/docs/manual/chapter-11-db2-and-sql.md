## Chapter 11. Db2 and SQL
### Simulation
This section covers DSN, SPUFI, RUN SQL, Db2 status commands, job submission from Db2 shell
and SQL training commands.
### Implementation evidence
### Area Source evidence
### Db2 app gibson/apps/db2.py
Db2 simulator gibson/apps/db2_sim.py
Db2 service gibson/services/db2_server.py
### Operational model
This Db2 chapter treats SQL and catalog visibility as a data-access workflow. Queries, REST paths
and simulated database roles show how application and database layers meet.
### Security relevance
The security value is data exposure. Catalog access, DDF/DRDA exposure and application SQL paths
can reveal structure and privileges that shape the next assessment step.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### Db2 DSN Starts simulated DB2
command processing.
gibson/apps/tso.py
LEGACY_HELP
### Db2 SPUFI Runs the simulated DB2/SPUFI
interface.
gibson/apps/tso.py
LEGACY_HELP
### Db2 RUN SQL Runs SQL through the
simulated DB2 engine.
gibson/apps/tso.py
LEGACY_HELP
Db2 HELP HELP gibson/apps/db2.py:171
### Db2 SHOW DBS/SHOW
### USERS/DISPLAY GROUP/OMVS
### STATUS/ID UID
command gibson/apps/db2.py:173
Db2 RUN SQL <query> RUN SQL SELECT ... gibson/apps/db2.py:185
### Db2 SUBMIT JOB / STATUS JOBS /
### CANCEL JOB
SUBMIT JOB name | STATUS
JOBS | CANCEL JOB id
gibson/apps/db2.py:187
### Db2 SQL SELECT/INSERT/UPDATE/
### DELETE/GRANT/REVOKE/
SQL text gibson/apps/db2.py:88


<!-- page 133 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### DISPLAY
### Section labs
### Lab 16: Enumerate Db2 catalog tables
### Command context
Start from: Db2 command/query context or Gibson route documented by the lab
Commands run from: Db2 simulation panel/API/query context
Do not run these from: ISPF editor or CICS unless the lab explicitly enters that bridge
Why context matters: Database commands require a database context; TSO and REST/API
examples must be kept separate.
### Why this lab matters
In this lab we’ll work through enumerate db2 catalog tables as a practical evidence exercise, not as
a command checklist. The concept being taught is Db2 catalog and privilege visibility. From a
tester’s point of view, the aim is to produce a specific piece of evidence: catalog table rows,
authority rows or query response. From a defender’s point of view, the same evidence explains
what should be controlled, logged or challenged before the activity becomes normalised. By the
end of the lab, you should be able to say why each command was used and what changed in your
understanding of the Gibson environment.
### What the commands do
DSN: enters the Db2 command/processor concept in the simulator. It marks the transition from
general TSO to database access.
SPUFI: represents SQL Processor Using File Input style interactive SQL. It is the teaching bridge to
on-host Db2 query workflows.
RUN SQL SELECT * FROM SYSIBM.SYSTABLES: queries the catalog map of table objects. It is
reconnaissance because catalog visibility often reveals where sensitive data lives.
### Starting state
### Start from the Db2-capable command path. The simulator catalog must be available, and SQL
commands should be entered exactly as shown because the SQL parser is training-oriented.
### Lab steps
DSN
SPUFI
RUN SQL SELECT * FROM SYSIBM.SYSTABLES
### What the output tells us
For `DSN`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.


<!-- page 134 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
Db2 catalog tables in DSNDB06 describe tables, columns, privileges, plans and packages. DDF/DRDA
and on-host tooling expose Db2 through different paths with RACF/SAF and Db2 authorities
shaping access.
### Defensive takeaway
Limit catalog visibility, review powerful authorities and monitor remote and on-host query paths.
Catalog enumeration can become a map of sensitive data.
### Troubleshooting
If SQL output is empty, check the simulated SQL syntax, catalog table name and whether the Db2
session/processor is active.
### Instructor note
Ask students which catalog row would drive their next test. The aim is to turn SQL output into a
target map, not merely to prove that SELECT works.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### DSN Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### SPUFI Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
RUN SQL SELECT *
FROM
### SYSIBM.SYSTABLES
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### Field Value
### Difficulty Beginner


<!-- page 135 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Estimated time 35 minutes
Objective Use DSN/SPUFI/RUN SQL to list simulator catalog entries.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 17: Exercise SQL privilege-oriented queries
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through exercise sql privilege-oriented queries as a practical evidence
exercise, not as a command checklist. The concept being taught is Db2 catalog and privilege
visibility. From a tester’s point of view, the aim is to produce a specific piece of evidence: catalog
table rows, authority rows or query response. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH: queries system-level Db2 authority information,
showing who has powerful database privileges.
RUN SQL SELECT * FROM SYSIBM.SYSDBAUTH: queries database-level authority information,
shifting from global authority to object/database-specific privilege.
### Starting state
### Start from the Db2-capable command path. The simulator catalog must be available, and SQL
commands should be entered exactly as shown because the SQL parser is training-oriented.
### Lab steps
RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH
RUN SQL SELECT * FROM SYSIBM.SYSDBAUTH
### What the output tells us


<!-- page 136 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
For `RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH`, identify the exact returned line, return
code, panel state or dataset change that proves the lab objective. If that item is not present, pause
and troubleshoot the current command context before continuing.
### On a real z/OS system
Db2 catalog tables in DSNDB06 describe tables, columns, privileges, plans and packages. DDF/DRDA
and on-host tooling expose Db2 through different paths with RACF/SAF and Db2 authorities
shaping access.
### Defensive takeaway
Limit catalog visibility, review powerful authorities and monitor remote and on-host query paths.
Catalog enumeration can become a map of sensitive data.
### Troubleshooting
If SQL output is empty, check the simulated SQL syntax, catalog table name and whether the Db2
session/processor is active.
### Instructor note
Ask students which catalog row would drive their next test. The aim is to turn SQL output into a
target map, not merely to prove that SELECT works.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
RUN SQL SELECT *
FROM
### SYSIBM.SYSUSERAUTH
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
RUN SQL SELECT *
FROM
### SYSIBM.SYSDBAUTH
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Run SQL commands against simulator tables and discuss


<!-- page 137 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
privilege/security relevance.
Prerequisites Db2 simulator available.
### Validation Runtime/static validated by SQL command family
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
