# Gibson v17 MFA Mode

v17 adds a simulator-only MFA mode controlled by `IBMUSER` from TSO.

## Commands

```text
MFA
MFA ON
MFA OFF
MFA STATUS
```

`MFA` without arguments is equivalent to `MFA ON`. Only `IBMUSER` can toggle MFA mode.

## Logon behaviour

When MFA mode is enabled, every non-IBMUSER user must enter an additional token after the correct password. The token is the Linux host local time in `HHMM` format. For example, if the host time is 22:57, the token is `2257`; if the host time is 09:04, the token is `0904`.

`IBMUSER` can log on without MFA even when MFA mode is enabled so the class can recover the system.

## Evidence

Successful and failed MFA attempts are recorded as simulator security events so they can be reviewed through SECEVENTS, SDSF SMF80-style views, dashboard audit views, or audit logs where those paths are enabled.
