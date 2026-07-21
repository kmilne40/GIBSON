# RACFDS DES Materialisation Implementation

Implemented in `gibson/core/racf_database.py`.

Key changes:

- Added `RacfCredentialMaterial` metadata.
- Added policy helpers and commands.
- Added password-set materialisation for ADDUSER/ALTUSER.
- Added stale backup state.
- Preserved GACF.DB as authentication authority.
- Marked simulator fallback as simulator-only.
