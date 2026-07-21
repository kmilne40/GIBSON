# RACFDS Legacy DES Policy Design

RACFDS credential policy is intentionally separate from Gibson login authentication.

Policies:

- `protected`: all users are represented in RACFDS as KDFAES/protected/non-crackable.
- `legacy-lab`: seeded and explicitly marked lab users are crackable.
- `legacy-all-vuln`: any user created or password-changed with plaintext through ADDUSER/ALTUSER becomes legacy-DES or simulator-DES.

The plaintext password is used only at password-set time to generate RACFDS material and is then discarded. Existing unknown GACF.DB hashes are never converted into DES.
