# Gibson v18 IND$FILE transfer

## Overview

Gibson v18 implements simulated IND$FILE GET and PUT for host/workstation-style transfers. TSO and REST routes use the shared transfer manager and the central dataset access evaluator.

## Commands

```text
IND$FILE GET DSN(SYS1.PARMLIB(IEASYS00)) LOCAL(ieasys00.txt)
IND$FILE PUT DSN(IBMUSER.UPLOAD.TEST) LOCAL(upload.txt)
IND$FILE GET SYS1.PARMLIB(IEASYS00) ieasys00.txt
IND$FILE PUT upload.txt IBMUSER.UPLOAD.TEST
```

REST compatibility remains:

```text
GET  /indfile/download
POST /indfile/upload
```

## Access checks

- GET requires READ.
- PUT requires UPDATE for an existing dataset.
- PUT to a new dataset creates a dataset owned by the user with ALTER.
- SPECIAL can transfer to and from all datasets.
- Group permits are honoured.
- Denied and WARNING-mode transfers are auditable.

## Transfer root and filename safety

Local files are restricted to the configured transfer root:

```text
GIBSON_TRANSFER_ROOT=/path/to/safe/transfers
```

If unset, Gibson uses `~/mfsim/transfers` or the simulator root’s `transfers` directory. Absolute paths and path traversal such as `../../etc/passwd` are rejected. Filenames are sanitised before use.

## References

- IBM Host On-Demand host file transfer overview: https://www.ibm.com/docs/en/host-on-demand/14.0?topic=ee-host-file-transfer
- Rocket Software IND$FILE receive documentation: https://docs.rocketsoftware.com/bundle/extraxtreme_ug_97_html/page/file-transfer-receive-file-use-ind-cs.htm
- IND$FILE GET/PUT terminology overview: https://ldapwiki.com/wiki/Wiki.jsp?page=IND%24FILE
