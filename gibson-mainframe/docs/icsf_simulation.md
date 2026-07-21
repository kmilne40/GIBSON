# Gibson ICSF Simulation

Gibson v24 adds a simulated ICSF control-plane feature for administration and evidence labs. It does not implement real ICSF cryptography, real master-key registers, or real CKDS/PKDS/TKDS contents.

## Supported commands

TSO:

```text
ICSF
ICSF STATUS
ICSF DISPLAY STATUS
ICSF DISPLAY KEYSETS
ICSF REFRESH
ICSF REFRESH MASTERKEY
ICSF REFRESH CKDS
ICSF REFRESH PKDS
ICSF REFRESH TKDS
ICSF HELP
```

Console:

```text
D ICSF
F ICSF,STATUS
F ICSF,REFRESH
F ICSF,REFRESH,MASTERKEY
F ICSF,REFRESH,CKDS
F ICSF,REFRESH,PKDS
F ICSF,REFRESH,TKDS
F ICSF,DISPLAY
```

## RACF/FACILITY controls

Gibson gates simulated ICSF operations through FACILITY-style RACF resources:

| Resource | Purpose | Required access |
|---|---|---|
| CSF.STATUS | Display ICSF status | READ |
| CSF.REFRESH | Refresh all simulated key data sets | UPDATE |
| CSF.REFRESH.MASTERKEY | Refresh simulated master-key version | ALTER |
| CSF.REFRESH.CKDS | Refresh simulated CKDS version | UPDATE |
| CSF.REFRESH.PKDS | Refresh simulated PKDS version | UPDATE |
| CSF.REFRESH.TKDS | Refresh simulated TKDS version | UPDATE |
| CSF.ADMIN | Reserved simulator admin profile | ALTER |

IBMUSER/profile owner/SPECIAL recovery follows Gibson's existing RACF model and is audited.

## Evidence

Every ICSF status or refresh operation records SMF80-style evidence, console evidence, dashboard alerts where available, and audit-log entries. No real key material is generated, stored, displayed, or rotated.
