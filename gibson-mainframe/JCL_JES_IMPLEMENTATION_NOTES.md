# JCL/JES Implementation Notes

- `JclParser.parse_job()` now builds `JclJob`, `JclStep` and `JclDD` structures.
- In-stream DD blocks are captured for `DD *` and `DD DATA`.
- JES now simulates IEFBR14 dataset allocation for DISP NEW/CATLG DDs.
- IDCAMS supports DEFINE, DELETE and LISTCAT-style output using Gibson dataset state.
- IEBGENER can copy in-stream or dataset SYSUT1 to SYSUT2.
- ASMA90/ASMAHL invokes the new HLASM simulator.
- IEWL creates a simulated load module in a Gibson dataset when SYSLMOD is provided.
