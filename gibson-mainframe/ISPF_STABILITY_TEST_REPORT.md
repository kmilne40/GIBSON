# ISPF Stability Test Report

New targeted tests were added in `tests/test_ispf_stability_fix_v1.py`.

Validated:

- DSLIST `E 1` preserves raw typed text and does not crash.
- DSLIST reads from the visible `Command ===>` row.
- Common DSLIST commands `B 1`, `V 1`, `S 1`, `M 1`, `D 1`, `R 1`, `SORT`, `REFRESH` and invalid input remain stable.
- PF/caret sequences are consumed as logical commands and do not pollute the DSLIST field.
- The panel input helper preserves typed text while mapping PF keys cleanly.
