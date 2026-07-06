# Language Runtime Baseline Analysis

## Baseline observations

- `gibson/languages/cobol.py` was a small compile simulator that checked required divisions, extracted literal DISPLAY statements, and recognised EXEC CICS/EXEC SQL text.
- `gibson/languages/jcl.py` was only a statement splitter and did not produce a structured job model.
- `gibson/core/jes.py` was the strongest existing foundation and already supported JOB/EXEC/DD handling, PROC/PEND, IF/ELSE/ENDIF, COND and several utilities.
- `gibson/languages/rexx.py` had a useful bounded interpreter with SAY, CALL, ADDRESS TSO, ADDRESS ISPEXEC, OUTTRAP and EXECIO basics.
- No HLASM simulator module was present.

## Baseline tests

- `python -m compileall -q gibson` passed after implementation.
- `pytest -q tests/test_core.py` passed.
