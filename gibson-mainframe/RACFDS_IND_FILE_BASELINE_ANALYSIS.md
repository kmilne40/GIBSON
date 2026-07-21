# RACFDS and IND$FILE Baseline Analysis

The source package already contained a RACFDS materialisation layer, seeded legacy lab users, racf2john and john simulators, and a command-mode IND$FILE implementation. The gaps were:

- legacy-DES materialisation was limited to seeded users only;
- ADDUSER/ALTUSER did not make arbitrary new vulnerable-mode users crackable;
- SYS1.RACFDS.BACKUP did not model stale/current state;
- racf2john did not distinguish real DES versus simulator-only material;
- john did not explicitly report attempted-but-not-cracked;
- IND$FILE option parsing was minimal and did not support enough x3270-style semantics;
- sensitive IND$FILE transfers lacked a focused zSecure transfer view.

This package resolves those issues while preserving GACF.DB as the login authority.
