# Gibson v18 RACF dataset access

## Central evaluator

Gibson v18 uses the dynamic RACF dataset evaluator for dataset access decisions. The evaluator returns a structured decision with:

- allowed or denied
- effective access
- required access
- reason
- profile name
- WARNING mode use
- SPECIAL/owner bypass use
- user and group permit indicators

All dataset reads, writes, allocation updates, deletes, transfer paths, TSO `OGET`/`OPUT`, `IND$FILE`, FTP/REST paths that call the dataset catalog, and ISPF browse/edit/delete routes use this same dataset catalog security layer.

## Access levels

Gibson uses the ordered dataset authorities:

`NONE < READ < UPDATE < CONTROL < ALTER`

For v18 dataset operations:

- `READ` permits browse, view, list, read, OGET, GET, and download.
- `UPDATE` permits edit, write, update, PUT, upload, and member creation.
- `ALTER` permits update plus delete, rename, and profile/permit management semantics where implemented.
- `NONE` denies access unless owner, SPECIAL, group/user permit, UACC, WARNING mode, or a documented simulator rule permits it.

Dataset creators become owners and receive ALTER through ownership and an explicit owner permit for newly created profiles.

## Owner, SPECIAL, UACC, user permits, and group permits

The profile owner has ALTER-equivalent access. SPECIAL users have ALTER-equivalent access across datasets and are audited when they use the bypass. UACC supplies the baseline access for users who have no stronger user or group permit. User permits and group permits can grant `NONE`, `READ`, `UPDATE`, or `ALTER`.

Group commands supported in v18 include:

```text
ADDGROUP LABGRP
CONNECT GUEST GROUP(LABGRP)
REMOVE GUEST GROUP(LABGRP)
PERMIT GUEST.TEST.DATA CLASS(DATASET) ID(LABGRP) ACCESS(UPDATE)
LISTGRP LABGRP
LISTUSER GUEST
```

`RLIST DATASET profile ALL` and `LISTDSD DATASET(profile) ALL` show UACC, WARNING/NOWARNING state, and access-list entries, including group IDs.

## WARNING mode

WARNING mode is not a silent allow. If a profile is in WARNING and a request would otherwise be denied, Gibson permits the request and emits:

- a console alert
- an SMF80-style record
- a dashboard alert
- a SECEVENTS/security-log entry

Example:

```text
ALTDSD SYS1.PARMLIB WARNING
SETROPTS REFRESH
RLIST DATASET SYS1.PARMLIB ALL
```

The event details state that access was permitted only because WARNING MODE was active.

## Revocation and delete support

```text
PERMIT GUEST.TEST.DATA CLASS(DATASET) ID(GUEST) DELETE
REVOKE GUEST.TEST.DATA CLASS(DATASET) ID(LABGRP)
DELUSER TEMPUSR
DELETEUSER TEMPUSR
```

Revoking a user or group removes the access-list entry. Deleting a user removes the user from group membership and dataset access lists in the dynamic RACF store.

## SETROPTS REFRESH

```text
SETROPTS LIST
SETROPTS REFRESH
SETROPTS RACLIST(DATASET) REFRESH
SETROPTS RACLIST(TCICSTRN) REFRESH
SETROPTS RACLIST(FCICSFCT) REFRESH
```

If cache simulation is active for a class, `RACLIST(class) REFRESH` marks that class refreshed. If no cache is active, `SETROPTS REFRESH` still returns a realistic success response and emits an audit event.

## References

- IBM dataset access authorization levels: https://www.ibm.com/docs/en/zos/2.5.0?topic=authority-data-set-access-authorization-levels
- IBM RACF WARNING mode monitoring: https://www.ibm.com/docs/en/zvm/7.2.0?topic=writer-monitoring-access-attempts-in-warning-mode
- IBM CICS/RACF audit logging of WARNING to SMF: https://www.ibm.com/docs/en/cics-ts/5.6.0?topic=racf-logging-audit-messages-smf
- IBM RACF SMF type 80 records: https://www.ibm.com/docs/en/zos/3.1.0?topic=records-record-type-80-racf-processing-record
- IBM PERMIT access-list maintenance: https://www.ibm.com/docs/ro/SSB27U_7.2.0/com.ibm.zvm.v720.icha4/permit.htm
- IBM SETROPTS RACLIST refresh: https://www.ibm.com/docs/en/zos/2.5.0?topic=processing-refreshing-profiles-setropts-raclist
