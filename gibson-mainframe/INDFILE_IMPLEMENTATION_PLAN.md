# IND$FILE Implementation Plan

Completed:

1. Preserve command-mode IND$FILE.
2. Add option parsing and PDS/member support.
3. Add ASCII and binary transfer handling.
4. Add sensitive dataset alerting.
5. Add zSecure transfer view.
6. Add staged native Transfer() parsing helpers.

Future validation:

- live x3270/c3270 Transfer() testing against a real client;
- fuller structured-field protocol emulation if needed.
