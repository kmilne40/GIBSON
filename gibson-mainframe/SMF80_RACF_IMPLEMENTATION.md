# SMF80 RACF Implementation

Added `Smf80RacfRecord`-style constructors through `gibson/core/smf/records/type80.py`.

The model supports event name, event code, qualifier, user, job, class, resource, profile, requested/allowed access, result, reason, APPLID, terminal, source IP and correlation ID.

`GibsonState.record_security_event()` now mirrors security events into structured Type 80 records while preserving the existing audit log.
