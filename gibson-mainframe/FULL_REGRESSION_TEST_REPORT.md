# Full Regression Test Report

Full `pytest -q` was not run due to prior environment timeout constraints. The targeted suites covering the affected ISPF/editor paths and previously modified subsystems were run successfully.

Results:
- `python -m compileall -q gibson`: passed.
- ISPF/editor targeted suite: 21 passed.
- Prior terminal/ZSEC/IND$FILE/RACFDS/core targeted suite: 32 passed, 11 existing CBSA datetime warnings.
- Master Console/CBSA/language/SMF targeted suite: 22 passed, 109 existing CBSA datetime warnings.
