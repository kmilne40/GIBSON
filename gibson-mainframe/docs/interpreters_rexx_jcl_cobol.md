# Gibson REXX, JCL/JES, and COBOL simulation reference

This document records the interpreter features implemented in the v21 secure-entrypoint/interpreters package. Gibson implements bounded educational simulations; it does not execute arbitrary host code and it is not a complete z/OS language runtime.

## REXX interpreter

Implemented files/modules:

- `gibson/languages/rexx.py` - bounded `RexxInterpreter`.
- `gibson/apps/tso.py` - dispatches `REXX`, `EXEC`, `EX`, and `%exec` invocation forms through `_run_rexx()`.
- `gibson/core/training_shell.py` - bounded training-shell support for TShOcker-style REXX lab simulations.

Invocation forms:

```text
REXX execname
EXEC 'dataset(member)' EXEC
EX 'dataset(member)' 'arguments'
%execname arguments
```

Dataset/member execution is supported through the Gibson dataset catalog. Arguments are passed to `PARSE ARG` and `ARG(n)` style evaluation. If the requested exec cannot be read, Gibson returns a simulated “not found” REXX output rather than executing host code.

Supported REXX subset:

- comments and labels
- `SAY`
- assignment and simple expression evaluation
- variable substitution and compound variables
- `PARSE ARG`
- `PULL`
- `IF ... THEN ... ELSE`
- `DO ... END`, including counted loops, `DO var = start TO end BY step`, and `DO WHILE`
- `CALL label`, `CALL CHAROUT`, and `RETURN`
- `EXIT`
- `ADDRESS TSO` routed through the current TSO command processor
- limited `ADDRESS ISPEXEC` simulation including `VGET`, `VPUT`, `DISPLAY`, and `SELECT`
- `EXECIO n DISKR dataset (STEM stem.`
- `EXECIO n DISKW dataset (STEM stem.`
- `SYSVAR('SYSUID')`, `SYSVAR('SYSNAME')`, `SYSVAR('SYSNODE')`, `SYSVAR('SYSJES')`, `SYSVAR('SYSPLEX')`
- `TIME()` and `DATE()`
- `OUTTRAP`-style captured output through the interpreter stem model

Training toolkit paths:

- `SEARCHRX`
- `SYS0WN`
- `ENUM` with options such as `ALL`, `SEC`, `APF`, `SVC`, `WHO`, and `PATH`
- `ELV.SVC`
- `ELV.SELF`
- `ELV.APF`

Safety and limits:

- execution is bounded by `max_steps` to avoid infinite loops
- only a small safe expression evaluator is used
- host OS access is not exposed
- TShOcker-style listener simulations create bounded Gibson training shells only

Evidence:

- TSO command paths and selected training-shell launches emit Gibson console/security events where implemented.
- Dataset reads and writes through `EXECIO` use the central dataset catalog/evaluator.

## JCL/JES interpreter

Implemented files/modules:

- `gibson/languages/jcl.py` - lightweight JCL statement parser.
- `gibson/core/jes.py` - JES spool, job model, JCL step interpretation, and JES2-style command handling.
- `gibson/apps/tso.py` - `SUBMIT` and `JES` TSO command dispatch.
- `gibson/apps/sdsf.py` - SDSF job and output views.
- `gibson/services/ftp_server.py` - FTP JES mode submission path.

Submission commands and paths:

```text
SUBMIT 'dataset(member)'
SUBMIT 'dataset(member)' USER(userid)
JES STATUS
JES SUBMIT job-description
SDSF ST
SDSF O
SDSF H
SITE FILETYPE=JES
FTP STOR file.jcl
```

Supported JCL/JES features:

- JOB card parsing for job name, owner, class, and message class
- `USER=` on JOB cards
- SURROGAT access checks for submit-as behaviour
- `EXEC PGM=...` step extraction
- DD statement inventory and instream DD data collection
- `//ddname DD *` instream data terminated by `/*`
- `//*` comments ignored by the parser
- in-stream PROC/PEND expansion with simple symbolic substitution
- IF/ELSE/ENDIF flow records
- `COND=(code,operator)` handling for step skip simulation
- JES spool files such as `JESMSGLG`, `JESJCL`, `JESYSMSG`, and selected step output files
- JES2-style commands: `$D Q`, `$DQ`, `$D JOB(jobid)`, `$C JOB(jobid)`, `$P JOB(jobid)`, `$A JOB(jobid)`, `$H JOB(jobid)`

Implemented program simulations:

- `IEFBR14` - successful no-op step with RC 0000
- `IKJEFT01` / `IKJEFTxx` - TSO batch simulation using SYSTSIN commands
- `IDCAMS` - accepts SYSIN statements and reports function completion
- `IEBGENER` - copies SYSUT1 to SYSUT2 where possible and reports records written
- `SORT` / `ICEMAN` - DFSORT-style successful completion
- `BPXBATCH` - z/OS UNIX command processor simulation
- `DSNTEP2` / `DSNTIAD` - SQL processor simulation through Db2 formatter
- `IGYCRCTL` / `COBOL` - COBOL compiler simulation through `CobolSimulator`
- unknown programs - generic simulated execution with DD inventory

Evidence:

- `SUBMIT` records security/audit events for job submission.
- SDSF ST/O/H and spool panels show job status/output.
- FTP JES submissions create JES-spool evidence when enabled.

## COBOL simulation

Implemented files/modules:

- `gibson/languages/cobol.py` - `CobolSimulator`, a source-aware compile simulation.
- `gibson/core/jes.py` - calls the COBOL simulator for `EXEC PGM=IGYCRCTL` and `EXEC PGM=COBOL` steps.
- `gibson/apps/banking_lab.py` - COBOL-inspired banking application source snippets and trace explanations.
- `gibson/services/rest_gateway.py` - web/API lab pages that describe API/COBOL/Db2 trace flow.

Status:

Gibson does not currently implement a full COBOL interpreter or real COBOL runtime. It implements a COBOL source-aware compile simulation and COBOL-inspired banking/application traces.

Supported COBOL simulation features:

- validates presence of `IDENTIFICATION DIVISION` and `PROCEDURE DIVISION`
- reports missing required divisions with IGY-style messages and non-zero condition code
- extracts literal `DISPLAY 'text'` / `DISPLAY "text"` statements into display output
- recognises `EXEC CICS` statements and emits an informational compiler message
- recognises `EXEC SQL` statements and emits an informational Db2 precompiler-style message
- returns `MAXIMUM CONDITION CODE WAS n`

JCL use:

```text
//COBC    EXEC PGM=IGYCRCTL
//SYSIN   DD *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO FROM GIBSON'.
/*
```

Limitations:

- no real COBOL object code is produced
- no real compile/link-edit/load execution path exists
- no full COBOL syntax parser exists
- no arbitrary `EXEC CICS` or `EXEC SQL` runtime is executed from COBOL source
- banking/REST COBOL references are lab trace simulations, not a COBOL runtime

## Secure and vulnerable mode behaviour

The interpreter components are preserved in vulnerable mode for classroom workflows. In secure mode, surrounding security controls such as MFA, dataset access checks, SURROGAT checks, disabled plaintext services, and blocked vulnerable shortcuts apply according to the central Gibson security mode and RACF simulation.
