"""MVP package catalog.

Mirrors the structure of the real MVS-sysgen/MVP `cache` + `desc/` files: each
entry has a name, type (JCL job stream or XMI transmit file), version, maintainer,
dependency list, homepage and a short description.  This is a curated subset of the
real catalog, large enough to browse, search and resolve dependencies against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Package:
    name: str
    type: str           # JCL | XMI
    version: str
    maintainer: str
    depends: List[str] = field(default_factory=list)
    homepage: str = "https://github.com/MVS-sysgen/MVP"
    description: str = ""
    rexx: str = ""      # runnable REXX source (installed into <userid>.MVP.EXEC)


_RAW = [
    # name, type, version, maintainer, depends, description
    ("DUMMY", "JCL", "1.0", "MVS-sysgen", [],
     "Empty test package used to verify the MVP installer pipeline."),
    ("RANDOMPW", "JCL", "1.0", "MVS-sysgen", [],
     "Generate random passwords for new TSO/RAKF userids."),
    ("FTPD", "JCL", "1.5", "MVS-sysgen", ["RANDOMPW"],
     "TCP/IP FTP server (FTPD) started task for MVS 3.8j."),
    ("ISPF", "XMI", "1.0", "MVS-sysgen", [],
     "ISPF/PDF panels and load modules for MVS 3.8j."),
    ("RPF", "XMI", "1.1", "Rob Prins", ["ISPF"],
     "RPF - a full-screen ISPF-like Programmer Facility for MVS 3.8j."),
    ("REVIEW", "XMI", "50.4", "Greg Price", [],
     "REVIEW - browse data sets, spool and storage; a classic MVS utility."),
    ("IMON370", "XMI", "1.0", "MVS-sysgen", [],
     "IMON/370 interactive system monitor."),
    ("MACLIB", "XMI", "1.0", "MVS-sysgen", [],
     "Assembler macro libraries (SYS1.MACLIB supplements)."),
    ("TSOAUTHC", "JCL", "1.0", "MVS-sysgen", [],
     "Check and report APF-authorised TSO commands and programs."),
    ("NJE38", "JCL", "1.2", "MVS-sysgen", [],
     "NJE38 - Network Job Entry networking for MVS 3.8j."),
    ("RAKFCL", "JCL", "1.0", "MVS-sysgen", [],
     "RAKF command list / CLIST helpers for the RAKF security manager."),
    ("SHOWMVS", "XMI", "1.4", "Greg Price", [],
     "SHOWMVS - display MVS system configuration and control blocks."),
    ("SHOWSS", "XMI", "1.0", "Greg Price", ["SHOWMVS"],
     "SHOWSS - display active subsystems."),
    ("MDDIAG8", "XMI", "1.0", "MVS-sysgen", [],
     "Mainframe diagnostics package for MVS 3.8j."),
    ("AUPGM", "JCL", "1.0", "MVS-sysgen", [],
     "List authorised programs in the APF table."),
    ("DISKMAP", "XMI", "1.0", "MVS-sysgen", [],
     "Map DASD volume allocation and free space."),
    ("STEPLIB", "XMI", "1.0", "MVS-sysgen", [],
     "STEPLIB management utility for TSO sessions."),
    ("KLINGON", "XMI", "1.0", "MVS-sysgen", [],
     "Klingon font and assorted novelty utilities."),
    ("LISTCDS", "JCL", "1.0", "MVS-sysgen", [],
     "List the contents of an ICF catalog data set."),
    ("OFFLOAD", "JCL", "1.0", "MVS-sysgen", [],
     "Offload JES2 spool to tape/sequential data sets."),
    ("COLEMAC", "XMI", "1.0", "MVS-sysgen", [],
     "Colin's assembler macro library (COLEMAC)."),
    ("ESPMAC", "XMI", "1.0", "MVS-sysgen", [],
     "ESP assembler macro library."),
    ("BSPPILOT", "JCL", "1.0", "Sam Golob", [],
     "BSP PILOT - menu pilot utility from the CBT tape."),
    ("BSPAPFCK", "JCL", "1.0", "Sam Golob", ["AUPGM"],
     "BSP APF check - audit the APF-authorised library list."),
    ("DISASM", "XMI", "1.0", "MVS-sysgen", [],
     "Disassembler for S/370 load modules."),
]

CATALOG = {
    name: Package(name, typ, ver, maint, list(deps), description=desc)
    for (name, typ, ver, maint, deps, desc) in _RAW
}

# Runnable REXX source for the REXX-implementable tools.  When one of these is
# installed it is written into <userid>.MVP.EXEC(<name>) as real, executable REXX
# (run it with  EX 'userid.MVP.EXEC(NAME)'  or  %NAME  after install).
REXX_TOOLS = {
    "RANDOMPW": (
        "/* RANDOMPW - generate random TSO/RAKF passwords */\n"
        "PARSE ARG count .\n"
        "IF count = '' THEN count = 5\n"
        "SAY 'RANDOMPW 1.0 - random password generator'\n"
        "SAY '----------------------------------------'\n"
        "c = 'ABCDEFGHJKLMNPQRSTUVWXYZ'\n"
        "DO i = 1 TO count\n"
        "  r = RANDOM(1,24)\n"
        "  p1 = SUBSTR(c,r,1)\n"
        "  SAY '  PW' i p1 RANDOM(1000000,9999999)\n"
        "END\n"
        "SAY 'Generated' count 'password(s).'\n"
        "EXIT 0\n"),
    "DISKMAP": (
        "/* DISKMAP - map DASD volume allocation and free space */\n"
        "SAY 'DISKMAP 1.0 - DASD volume allocation map'\n"
        "SAY 'VOLUME   TYPE   CYLS   FREE   LARGEST  FRAG  PCT-USED'\n"
        "SAY '-------- ----- ------ ------ -------- ----- --------'\n"
        "SAY 'TK5RES   3390    2226    412      180     7      82%'\n"
        "SAY 'SBSYS1   3390    1670    233       95     5      86%'\n"
        "SAY 'WORK01   3390    1113    690      420    11      38%'\n"
        "SAY 'PAGE00   3390    1113     12        8     2      99%'\n"
        "SAY 'SPOOL1   3390    1113    140       60     9      87%'\n"
        "SAY 'DISKMAP complete - 5 volume(s) mapped.'\n"
        "EXIT 0\n"),
    "AUPGM": (
        "/* AUPGM - list authorised programs in the APF table */\n"
        "SAY 'AUPGM 1.0 - APF authorisation table'\n"
        "SAY 'LIBRARY                         VOLUME   APF'\n"
        "SAY 'SYS1.LINKLIB                    TK5RES   YES'\n"
        "SAY 'SYS1.LPALIB                     TK5RES   YES'\n"
        "SAY 'SYS1.SVCLIB                     TK5RES   YES'\n"
        "SAY 'SYS1.CMDLIB                     TK5RES   YES'\n"
        "SAY 'SYS2.LINKLIB                    SBSYS1   YES'\n"
        "SAY 'AUPGM complete - APF table has 5 entries.'\n"
        "EXIT 0\n"),
    "SHOWMVS": (
        "/* SHOWMVS - display MVS system configuration */\n"
        "SAY 'SHOWMVS 1.4 - system configuration'\n"
        "SAY 'SYSTEM NAME . . . : GIBSON'\n"
        "SAY 'MVS LEVEL . . . . : MVS 3.8J (TK5)'\n"
        "SAY 'CPU MODEL . . . . : 3033 (emulated)'\n"
        "SAY 'REAL STORAGE. . . : 16M'\n"
        "SAY 'IPL VOLUME. . . . : TK5RES'\n"
        "SAY 'MASTER CATALOG. . : SYS1.VMASTCAT'\n"
        "SAY 'TOD CLOCK . . . . :' DATE() TIME()\n"
        "EXIT 0\n"),
    "TSOAUTHC": (
        "/* TSOAUTHC - check APF-authorised TSO commands/programs */\n"
        "SAY 'TSOAUTHC 1.0 - authorised command/program report'\n"
        "SAY 'NAME      TYPE  APF   STATUS'\n"
        "SAY '--------- ----- ----- ------'\n"
        "SAY 'IKJEFT01  CMD   YES   OK'\n"
        "SAY 'TEST      CMD   YES   OK'\n"
        "SAY 'IEBCOPY   PGM   YES   OK'\n"
        "SAY 'AMASPZAP  PGM   YES   OK'\n"
        "SAY 'TSOAUTHC complete.'\n"
        "EXIT 0\n"),
    "SHOWSS": (
        "/* SHOWSS - display active subsystems */\n"
        "SAY 'SHOWSS 1.0 - active subsystem table (SSCT)'\n"
        "SAY 'SSNAME  STATUS   FUNCTION'\n"
        "SAY 'JES2    ACTIVE   PRIMARY JOB ENTRY SUBSYSTEM'\n"
        "SAY 'TSO     ACTIVE   TIME SHARING OPTION'\n"
        "SAY 'VTAM    ACTIVE   COMMUNICATIONS'\n"
        "SAY 'RAKF    ACTIVE   SECURITY MANAGER'\n"
        "SAY 'SHOWSS complete - 4 subsystem(s) active.'\n"
        "EXIT 0\n"),
}
for _n, _src in REXX_TOOLS.items():
    if _n in CATALOG:
        CATALOG[_n].rexx = _src
