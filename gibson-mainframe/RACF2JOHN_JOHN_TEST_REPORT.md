# racf2john / john Test Report

Validated:

- extraction from SYS1.RACFDS;
- extraction includes newly created users;
- `$racf$*USER*HASH` output shape;
- john attempts all hashes;
- john cracks matching wordlist entries;
- john reports attempted-but-not-cracked when applicable;
- SMF/console/CTI evidence is emitted.
