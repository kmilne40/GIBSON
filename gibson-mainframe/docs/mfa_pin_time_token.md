# Gibson MFA PIN + HHMM Token Model

Gibson v24 enhances simulator MFA with an IPL-defined 4-digit PIN. When MFA is ON and a PIN has been set, the required token is:

```text
<PIN><HHMM>
```

Example:

```text
PIN: 1234
Host time: 09:05
Token: 12340905
```

## IPL setup

During the simulated master-console IPL flow, after `R 03,Y`, Gibson asks for a 4-digit PIN:

```text
GIBSON MFA INITIALISATION
DEFINE 4-DIGIT MFA PIN FOR THIS IPL:
```

The PIN must be exactly four numeric digits. The PIN is not printed back and the token is never logged.

## Compatibility

Existing commands remain:

```text
MFA
MFA ON
MFA OFF
MFA STATUS
```

If a PIN has not yet been configured, Gibson preserves the legacy HHMM-only MFA token behaviour for compatibility with existing labs. Once a PIN is set, the PIN+HHMM 8-digit token is required.

## Time window

The default simulator tolerance accepts the current minute plus/minus one minute to avoid lab usability problems. The correct token is never displayed.

## IBMUSER recovery

IBMUSER remains a recovery account according to Gibson's existing break-glass model. Any IBMUSER MFA recovery/bypass behaviour is audited.
