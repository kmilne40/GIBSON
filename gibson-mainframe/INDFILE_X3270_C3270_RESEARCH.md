# IND$FILE x3270/c3270/s3270 Research

x3270/c3270 expose file transfer through the `Transfer()` action and host-side IND$FILE expectations. The command-mode Gibson path supports NVT/ANSI/TN3270 text workflows. This package adds Transfer-style option parsing and staged native-compatibility modules.

Supported and tested in this package:

- command-mode `IND$FILE GET/PUT`;
- scripted terminal-style upload/download via typed commands;
- x3270/c3270-style option parsing for HOSTFILE, LOCALFILE, MODE, EXIST, CR, RECFM, LRECL.

Not claimed as fully validated:

- byte-perfect 3270 structured-field IND$FILE state machine compatibility with every x3270/c3270 Transfer() mode. Manual validation scripts are provided.
