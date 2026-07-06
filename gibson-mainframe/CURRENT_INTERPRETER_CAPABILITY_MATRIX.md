# Current Interpreter Capability Matrix

| Runtime | Implemented in v1 | Remaining future work |
|---|---|---|
| COBOL | Working-Storage, PIC/value, MOVE, DISPLAY vars, ADD/SUBTRACT/COMPUTE, IF, EVALUATE, PERFORM, EXEC CICS/SQL recognition | Multi-line IF blocks, full file I/O, COPY expansion, real CICS/Db2 execution |
| JCL/JES | Job/step/DD AST, DD *, DISP basics, IEFBR14 allocation, IEBGENER, IDCAMS, IKJEFT01 preservation, ASMA90/ASMAHL, IEWL | GDG, full catalog rules, INCLUDE/JCLLIB, IEBCOPY depth |
| REXX | SELECT, PARSE VAR/VALUE/SOURCE, DROP, UPPER, common string functions, EXECIO preservation | Full PROCEDURE EXPOSE, SIGNAL ON ERROR, complete REXX expression semantics |
| HLASM | Parser, CSECT/DSECT/USING/DROP/DC/DS, LA/L/ST/MVC/compare/branch simulation, listing | Macro expansion, full instruction set, linkage editor symbol resolution |
