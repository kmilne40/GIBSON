# ISPF Coordinate Test Report

New tests added in `tests/test_ispf_coordinate_editor_fix_v1.py` verify:
- zero-based and one-based coordinate helper behaviour;
- DSLIST command-row constants;
- title width safety with two-digit row counts;
- editor cursor conversion without the old row-plus-two correction.
