# REXX Implementation Notes

- Added SELECT/WHEN/OTHERWISE block handling.
- Added PARSE VAR, PARSE VALUE and PARSE SOURCE support.
- Added DROP, UPPER and RETURN expression support.
- Added common string and utility built-ins: LEFT, RIGHT, SUBSTR, WORD, WORDS, STRIP, TRANSLATE, POS, LENGTH, DATATYPE, COPIES, SPACE, SUBWORD, DELWORD and RANDOM.
- Preserved existing ADDRESS TSO, ADDRESS ISPEXEC, EXECIO and OUTTRAP behaviour.

Known limitation: this is still a training interpreter, not a complete TSO/E REXX implementation.
