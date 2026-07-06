# GIBSON --ctf : Operation Summer Guest

This GIBSON build adds a `--ctf` start flag and a fix for the NJE port-175 listener.

## Start in CTF mode
    sudo ./scripts/grant-port-capabilities.sh      # one-time: lets GIBSON bind 23, 21 AND 175
    python3 -m gibson --serve --with-ftp --ctf      # (add the flags you normally use)
    #   or: ./gibsonctl.sh start ... --ctf
On start you will see "GIBSON-CTF: ..." lines confirming each seeded item. Nothing
else needs setting up - users, clue datasets, the vulnerabilities and the crackable
DARVADER account are all injected automatically.

## What --ctf seeds (verified)
Users (logon-ready):
    IBMUSER  / SYS1      weak foothold (SPECIAL/OPERATIONS stripped)
    GUEST    / SUMMER26  more access, OMVS
    KEVIN01  / KEVIN01   the NJE contact
    SYSPROG  / SYSPROG   production sysprog (SPECIAL OPERATIONS)
    DARVADER / STARWARS  the master account / prize (SPECIAL OPERATIONS)
Datasets:
    IBMUSER.ACLUE.TEXT          stage-2 clue (browse in ISPF =3.4)
    SYS1.CLUELIB(GUEST)         stage-3 clue, WARNING mode (SEARCH ALL WARNING NOMASK)
    SYS2.CTF.APFLIB(ORACNOTE)   stage-4 writable APF library + ORAC/KEVIN01 clue
    GIBSON.WORDLIST             includes STARWARS so john cracks DARVADER
Vulnerabilities / config:
    SYS1.CLUELIB is fail-open (WARNING) so SEARCH ALL WARNING NOMASK lists it
    SYS2.CTF.APFLIB is on the APF list (D PROG,APF) and UACC(UPDATE) (writable finding)
    DARVADER is materialised into SYS1.RACFDS as a legacy-DES hash; racf2john + john
        recover STARWARS (tested: DARVADER:STARWARS)
    A win message "Well Done! It's Game over!" is queued for DARVADER and shows at logon
NJE node ORAC (003, password ORACPW) is native to this build.

## NJE port 175 fix
serve_nje() now guards the privileged-port bind exactly like TN3270 on 23: if the
process lacks the bind capability it fails LOUDLY with guidance instead of silently
printing "ACTIVE" while never binding. Grant the capability (above) and 175 binds
like 23/21. The NJE/TCP OPEN handshake (33-byte record, reason codes 0x00 ACK /
0x01 unknown OHOST / 0x04 bad RHOST) and the I-record node-password sign-on are
unchanged and verified against Chapter 10 (nodes GIBSON/HAL/ORAC).

## The two human roles (a co-instructor, or you)
- KEVIN01 (real account) answers a team's SEND (stage 5) with:
    'ORAC is node 003 on NJE. Node password ORACPW. Route your job with /*XEQ ORAC.'
- SYSPROG (real SPECIAL account) answers the NJE audit request (stage 6) and makes the
  RACF database available to the team, e.g. logged on as SYSPROG:
    racf2john SYS1.RACFDS > GUEST.HASHES
  then the team runs:  john --wordlist=GIBSON.WORDLIST GUEST.HASHES   ->  DARVADER:STARWARS

## Stages (full walk-through in the Solutions PDF)
    1 nmap 23 -> tso-enum -> logon IBMUSER/SYS1
    2 browse IBMUSER.ACLUE.TEXT
    3 SEARCH ALL WARNING NOMASK -> SYS1.CLUELIB -> GUEST/SUMMER26
    4 logon GUEST; FTP SITE FILETYPE=JES; D PROG,APF -> SYS2.CTF.APFLIB + ORAC clue
    5 SEND KEVIN01 -> ORAC details
    6 NJE /*XEQ ORAC job asks SYSPROG for the RACF DB (audit)
    7 racf2john + john -> DARVADER/STARWARS -> logon DARVADER -> "Well Done! It's Game over!"
