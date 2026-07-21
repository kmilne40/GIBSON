# racf2john / john Implementation

Implemented in `gibson/tools/racf2john_sim.py`.

- `racf2john` extracts all legacy records from SYS1.RACFDS/SYS1.RACFDS(DATABASE)/SYS1.RACFDS.BACKUP.
- `john` attempts all hashes against the selected wordlist.
- Cracked results are stored in Gibson-local state for `john --show`.
- Host paths are rejected.
- SMF, console, zSecure and CTI evidence is emitted.
