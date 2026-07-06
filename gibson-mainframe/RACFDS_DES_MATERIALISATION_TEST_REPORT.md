# RACFDS DES Materialisation Test Report

Covered by `tests/test_racfds_indfile_v1.py` and existing RACFDS tests.

Validated:

- legacy-all policy creates crackable RACFDS records for new ADDUSER passwords;
- ALTUSER updates RACFDS hash material;
- protected policy keeps users non-crackable;
- backup stale/current behaviour works;
- john cracks new and changed users when the password is in the wordlist.
