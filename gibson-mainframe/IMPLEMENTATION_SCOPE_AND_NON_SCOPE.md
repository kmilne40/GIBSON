# Implementation Scope and Non-Scope

Implemented:
- ISPF coordinate helper contract.
- DSLIST command-field placement and title width safety.
- Editor zero-based cursor mapping and no-wrap clamp.
- Regression tests covering DSLIST placement and editor no-wrap behaviour.

Not implemented:
- No Option 5 / Batch / compiler-workbench enhancements.
- No changes to COBOL, JCL, REXX or HLASM runtimes.
- No CTI/RSS/RACFDS/ZSEC/SMF/IND$FILE redesign.
- No native x3270/c3270 Transfer() work.
