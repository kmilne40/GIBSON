# IND$FILE Command-Mode Implementation

Implemented in `gibson/core/transfers.py` and `gibson/apps/tso.py`.

Supported examples:

```text
IND$FILE GET DSN(IBMUSER.DATA.TEXT) LOCAL(out.txt) MODE(ASCII)
IND$FILE PUT LOCAL(in.txt) DSN(IBMUSER.PDS(M1)) MODE(ASCII) EXIST(REPLACE)
IND$FILE GET DSN(SYS1.RACFDS) LOCAL(racfds.txt) MODE(ASCII)
```

Local paths are confined to the Gibson transfer root.
