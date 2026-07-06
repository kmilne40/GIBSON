# IBM Language Runtime Research Notes

This implementation follows a bounded educational-simulator model rather than attempting to reproduce IBM compilers/interpreters exactly.

## JCL/JES

The implemented target follows core z/OS JCL concepts: JOB, EXEC and DD statements, in-stream data, PROC-style expansion, conditional step execution and utility execution with JES spool output.

## COBOL

The COBOL uplift targets the familiar Enterprise COBOL training subset: IDENTIFICATION, DATA and PROCEDURE divisions, Working-Storage items, DISPLAY, MOVE, arithmetic, IF, EVALUATE and PERFORM.

## TSO/E REXX

The REXX uplift targets safe training use of common TSO/E REXX constructs: SAY, PARSE, SELECT, DO/END, ADDRESS, OUTTRAP, EXECIO, stems and string built-ins.

## HLASM

The HLASM foundation targets parser/listing and tiny instruction simulation for CSECT/DSECT/USING/DC/DS and simple register/storage operations.
