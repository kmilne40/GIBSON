# OMVS Nmap Implementation Guide

Supported examples include:

```sh
nmap mainframe -p- -T4 --open
nmap mainframe -p21 --script ftp-anon -sV
nmap mainframe -p2023 --script vtam-enum
nmap mainframe -p2023 --script tso-enum --script-args userdb=tso_users.txt
nmap mainframe -p2023 --script cics-enum
nmap mainframe -p50000 --script db2-das-info -sV
nmap -oN scan.txt mainframe
```

The implementation uses deterministic Gibson fixtures and the existing `nmap-sim.py` compatibility engine. It does not perform arbitrary internet scanning.
