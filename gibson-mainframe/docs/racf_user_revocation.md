# RACF User Revocation and Deletion

Gibson v19 adds RACF-style user lifecycle controls.

## ALTUSER REVOKE

```text
ALTUSER TEMPUSR REVOKE
```

Expected output:

```text
ICH10006I ALTUSER TEMPUSR REVOKE COMPLETE
SECURITY EVENT RECORDED
```

A revoked user cannot log on. LISTUSER displays the revoked state:

```text
ATTRIBUTES=REVOKED
REVOKE DATE=YES
```

## ALTUSER RESUME

```text
ALTUSER TEMPUSR RESUME
```

Expected output:

```text
ICH10007I ALTUSER TEMPUSR RESUME COMPLETE
SECURITY EVENT RECORDED
```

## DELUSER

```text
DELUSER TEMPUSR
```

DELUSER removes the user from the RACF user store and cleans up group and permit references where Gibson can safely do so. DELUSER requires SPECIAL authority.

## IBMUSER protection in secure mode

In `--secure` mode, IBMUSER is protected as a break-glass account:

```text
ALTUSER IBMUSER REVOKE
DELUSER IBMUSER
```

Expected result: the request is rejected and audited.
