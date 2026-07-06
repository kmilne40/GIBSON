# RACFDS Legacy-DES Fix Implementation

`RACFDB SEED LEGACY` marks the lab as seeded and materialises deterministic vulnerable users (`FIREID1`, `FIREID2`, `DUMONT`) as `ALG=LEGACY-DES` records in `SYS1.RACFDS(DATABASE)`. Secure/default users remain KDFAES/protected unless the vulnerable lab is explicitly enabled or the package is launched in vulnerable mode. `RACFDB VERIFY HASHES` reports John-compatible status.
