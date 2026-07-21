from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import json
import re
import shutil
from datetime import datetime

try:
    from gibson.core.sys1_library import SYS1_SYSTEM_DATASETS
except Exception:  # pragma: no cover - keep core usable if module is absent
    SYS1_SYSTEM_DATASETS = {}


@dataclass
class DatasetInfo:
    name: str
    org: str
    path: Path
    recfm: str = "FB"
    lrecl: int = 80
    blksize: int = 6160
    volume: str = "WORK01"


class DatasetSecurity:
    def __init__(self, dynamic_racf, racf_repo, audit_log=None, state=None):
        self.dynamic_racf = dynamic_racf
        self.racf_repo = racf_repo
        self.audit_log = audit_log
        self.state = state

    def _dataset_name(self, dsname: str) -> str:
        raw = (dsname or "").strip().strip("'").upper()
        m = re.fullmatch(r"(.+?)\(([^()]+)\)", raw)
        return m.group(1).strip() if m else raw

    def _hlq(self, dsname: str) -> str:
        name = self._dataset_name(dsname)
        return name.split(".", 1)[0] if name else ""

    def _audit_access(self, userid: str, dsn: str, required: str, result: str, detail: str, decision=None) -> None:
        extra = {
            "CLASS": "DATASET", "RESOURCE": dsn, "PROFILE": getattr(getattr(decision, "profile", None), "name", dsn),
            "SERVICE": "DATASET", "REQUIRED": required, "EFFECTIVE": getattr(decision, "effective", ""),
            "REASON": getattr(decision, "reason", ""), "WARNING": str(bool(getattr(decision, "warning", False))).upper(),
            "DETAIL": f"DATASET={dsn} ACCESS={required} {detail}",
        }
        if self.audit_log is not None:
            try:
                self.audit_log.record_smf80(userid, "DATASET ACCESS", f"DATASET={dsn} ACCESS={required} {detail}", result=result, extra=extra)
            except Exception:
                pass
        if self.state is not None:
            try:
                sev = "ALERT" if result.upper() in {"FAILURE", "WARNING"} else "INFO"
                if result.upper() == "WARNING":
                    msg = f"ICH408I WARNING MODE DATASET ACCESS PERMITTED USER({userid.upper()}) DATASET({dsn}) REQUIRED({required}) EFFECTIVE({getattr(decision, 'effective', '')})"
                    self.state.notify_console(msg, severity="ALERT")
                    self.state.raise_dashboard_alert(msg, severity="ALERT", event_type="WARNING_MODE")
                elif result.upper() == "FAILURE":
                    self.state.notify_console(f"ICH408I DATASET ACCESS DENIED USER({userid.upper()}) DATASET({dsn}) REQUIRED({required}) {detail}", severity="ALERT")
            except Exception:
                pass

    def authorize(self, userid: str, dsname: str, intent: str) -> None:
        dsn = self._dataset_name(dsname)
        if not dsn:
            return
        # v26.1 hardening: GUEST has simulated RACF ACCESS(NONE) to SYS1.* in
        # secure mode. A WARNING profile still permits access but is audited.
        try:
            from gibson.core.security_mode import is_secure_mode, is_noracf_mode
            if (self.state is not None and is_secure_mode(self.state) and not is_noracf_mode(self.state)
                    and (userid or '').upper() == 'GUEST' and dsn.startswith('SYS1.')):
                required_tmp = {"READ": "READ", "WRITE": "UPDATE", "UPDATE": "UPDATE", "ALTER": "ALTER", "ALLOCATE": "UPDATE"}.get(intent.upper(), "READ")
                prof_tmp = self.dynamic_racf._find_profile("DATASET", dsn)
                if not (prof_tmp is not None and getattr(prof_tmp, 'warning', False)):
                    class _Decision:
                        profile = prof_tmp; effective = 'NONE'; reason = 'GUEST_SYS1_NONE'; warning = False
                    self._audit_access(userid, dsn, required_tmp, "FAILURE", "GUEST ACCESS(NONE) TO SYS1.*", _Decision())
                    raise PermissionError(f"ICH408I USER({userid.upper()}) GROUP(STUDENT) DATASET({dsn}) CL(DATASET) INSUFFICIENT ACCESS AUTHORITY - ACCESS INTENT({required_tmp}) ACCESS ALLOWED(NONE)")
        except PermissionError:
            raise
        except Exception:
            pass
        try:
            from gibson.core.security_mode import is_noracf_mode
            if self.state is not None and is_noracf_mode(self.state):
                if self.audit_log is not None:
                    self.audit_log.record_smf80(userid, "NORACF DATASET BYPASS", f"DATASET={dsn} INTENT={intent.upper()} RACF=DISABLED", result="SUCCESS", extra={"EVENT":"NORACF", "RESOURCE":dsn, "SERVICE":"DATASET", "DETAIL":f"RACF DISABLED INTENT={intent.upper()}"})
                return
        except Exception:
            pass
        required = {"READ": "READ", "WRITE": "UPDATE", "UPDATE": "UPDATE", "ALTER": "ALTER", "ALLOCATE": "UPDATE"}.get(intent.upper(), "READ")
        decision = self.dynamic_racf.access_decision("DATASET", dsn, userid, required, self.racf_repo)
        if decision.allowed:
            if decision.warning:
                self._audit_access(userid, dsn, required, "WARNING", "WARNING MODE ACCESS ALLOWED: permitted only because profile is in WARNING MODE", decision)
            elif decision.reason == "SPECIAL":
                self._audit_access(userid, dsn, required, "SUCCESS", "SPECIAL BYPASS", decision)
            return
        self._audit_access(userid, dsn, required, "FAILURE", f"EFFECTIVE={decision.effective} REASON={decision.reason}", decision)
        if decision.profile is not None and decision.profile.warning:
            return
        raise PermissionError(f"ICH408I USER({userid.upper()}) NOT AUTHORIZED FOR DATASET {dsn} ACCESS({required})")

    def on_allocate(self, userid: str, dsname: str) -> None:
        dsn = self._dataset_name(dsname)
        if not dsn:
            return
        prof = self.dynamic_racf._find_profile("DATASET", dsn)
        created = prof is None
        if prof is None:
            owner = userid.upper()
            prof = self.dynamic_racf.define("DATASET", dsn, owner=owner, uacc="NONE", volume="WORK01")
            prof.permits[userid.upper()] = "ALTER"
            self.dynamic_racf.save()
        if created and self.audit_log is not None:
            try:
                owner = userid.upper()
                self.audit_log.record_smf80(userid, "DATASET CREATE", f"DATASET={dsn} OWNER={owner}")
            except Exception:
                pass


class DatasetCatalog:
    SYSTEM_DATASETS = {
        "SYS1.PARMLIB": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {
                "IEASYS00": "CMD=00\nOPI=YES\nOMVS=00\nPROG=00\nCONSOL=00\n",
                "COMMND00": "S JES2\nS TCPIP\nS FTPD\nS OMVS\n",
                "PROG00": "APF ADD DSNAME(SYS1.LINKLIB) VOLUME(SBSYS1)\nAPF ADD DSNAME(SYS1.PROCLIB) VOLUME(SBSYS1)\n",
                "SMFPRM00": "ACTIVE\n  RECORDING(DATASET)\n  DSNAME(SYS1.MANA,SYS1.MANB,SYS1.MANC)\n  SYS(TYPE(7,30,80,83,92,100,101,102,110,119,123))\n",
                "LOAD00": "IEASYM00\nNUCLST00\n",
                "BPXPRM00": "ROOT=/\nMOUNT FILESYSTEM('OMVS.ZFS.ROOT') TYPE(ZFS) MODE(RDWR) MOUNTPOINT('/')\n",
                "CONSOL00": "DEFAULT ROUTCODE(ALL)\nDEFAULT LEVEL(1,2,3,4,5)\n",
            },
        },
        "SYS1.RACFDS": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"DATABASE": "SIMULATED RACF PRIMARY DATABASE - TRAINING ONLY\n"}},
        "SYS1.RACFDS.BACKUP": {"ORG": "PS", "VOLUME": "SBRES1", "content": "SIMULATED RACF BACKUP DATABASE - TRAINING ONLY\n"},
        "SYS1.MANA": {"ORG": "PS", "VOLUME": "SBSMF1", "content": "GIBSON SIMULATED SMF MAN DATA SET A - TRAINING ONLY\n"},
        "SYS1.MANB": {"ORG": "PS", "VOLUME": "SBSMF1", "content": "GIBSON SIMULATED SMF MAN DATA SET B - TRAINING ONLY\n"},
        "SYS1.MANC": {"ORG": "PS", "VOLUME": "SBSMF1", "content": "GIBSON SIMULATED SMF MAN DATA SET C - TRAINING ONLY\n"},
        "SYS1.PROCLIB": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {
                "FTPD1": "//FTPD1 PROC\n//FTPD EXEC PGM=FTPD,REGION=0M\n",
                "DB2START": "//DB2START PROC\n//DB2MSTR EXEC PGM=DSN3MSTR\n",
                "CICSSTART": "//CICSSTART PROC\n//CICS EXEC PGM=DFHSIP\n",
            },
        },
        "SYS1.LINKLIB": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {
                "IEFBR14": "LOAD MODULE PLACEHOLDER\n",
                "IKJEFT01": "LOAD MODULE PLACEHOLDER\n",
            },
        },
        "SYS1.SISPEXEC": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {"ISR@PRIM": "/* ISPF PRIMARY OPTION MENU */\n"},
        },
        "SYS1.SISPCLIB": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {"ISRUTIL": "PROC 0\nEXIT 0\n"},
        },
        "SYS1.VTAMLST": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {
                "ATCSTR00": "SSCPID=GIB1\nNETID=GIBNET\n",
                "APPLS00": "TSO     APPL AUTH=(ACQ,PASS)\nCICS    APPL AUTH=(ACQ,PASS)\n",
            },
        },
        "SYS1.MACLIB": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {"IKJTSOEV": "MACRO\nMEND\n"},
        },
        "SYS1.TCPPARMS": {
            "ORG": "PO",
            "VOLUME": "SBSYS1",
            "members": {
                "PROFILE": "HOME 127.0.0.1 LINK ETH0\n",
                "TCPDATA": "DOMAINORIGIN GIBSON.LOCAL\n",
            },
        },
        "SYS1.LPALIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IEAVINIT": "SIMULATED LPA MODULE DIRECTORY ENTRY\n", "CSVLLA": "SIMULATED LIBRARY LOOKASIDE MODULE\n"}},
        "SYS1.SVCLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IEFSSN00": "SUBSYS SUBNAME(JES2)\nSUBSYS SUBNAME(RACF)\n", "IEASVC00": "SIMULATED SVC TABLE MEMBER\n"}},
        "SYS1.NUCLEUS": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IEANUC01": "SIMULATED NUCLEUS DIRECTORY ENTRY - TRAINING ONLY\n", "IEAVNP00": "SIMULATED NIP PARAMETER MODULE\n"}},
        "SYS1.MODGEN": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IFASMFR": "SMF RECORD MAPPING MACRO PLACEHOLDER\n", "IKJTCB": "TCB MAPPING MACRO PLACEHOLDER\n"}},
        "SYS1.SAMPLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"RACFNOTE": "RACF TRAINING NOTES - NO REAL SECRETS\n", "DB2NOTE": "DB2 TRAINING NOTES - SAFE SAMPLE TEXT\n", "CICSNOTE": "CICS TRAINING NOTES - SAFE SAMPLE TEXT\n", "FTPNOTE": "FTP FILE/JES/SQL MODE TRAINING NOTES\n", "JCLNOTE": "JCL SAMPLE NOTES - USE IEFBR14 FOR SAFE JOBS\n"}},
        "SYS1.CLIST": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"LOGON": "PROC 0\nWRITE GIBSON LOGON CLIST SAMPLE\n", "ISPF": "PROC 0\nISPEXEC SELECT PANEL(ISR@PRIM)\n", "SDSF": "PROC 0\nWRITE ENTER SDSF\n", "DB2I": "PROC 0\nWRITE ENTER DB2I\n"}},
        "SYS1.REXX": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"HELLO": "/* REXX */\nSAY 'HELLO FROM SYS1.REXX'\n", "SECAUDIT": "/* REXX */\nADDRESS TSO 'SECEVENTS'\n", "DSNLOOK": "/* REXX */\nADDRESS TSO 'LISTCAT'\n", "USERCHK": "/* REXX */\nADDRESS TSO 'LISTUSER'\n"}},
        "SYS1.JCLLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IEFBR14": "//GIBBR14 JOB (ACCT),'SAFE'\n//STEP1 EXEC PGM=IEFBR14\n", "LISTCAT": "//LISTCAT JOB (ACCT),'IDCAMS'\n//STEP1 EXEC PGM=IDCAMS\n//SYSIN DD *\n LISTCAT\n/*\n", "DB2SPUFI": "//DB2SPUF JOB (ACCT),'DB2'\n//STEP1 EXEC PGM=DSNTEP2\n", "CICSSTRT": "//CICSSTRT JOB (ACCT),'CICS'\n//STEP1 EXEC PGM=IEFBR14\n"}},
        "SYS1.UADS": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"IBMUSER": "TSO USER ATTRIBUTE SAMPLE\n", "GUEST": "TSO USER ATTRIBUTE SAMPLE\n"}},
        "SYS1.BRODCAST": {"ORG": "PS", "VOLUME": "SBSYS1", "content": "GIBSON BROADCAST DATA SET - TRAINING MESSAGES ONLY\n"},
        "SYS1.MIGLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"HASMIG00": "SIMULATED MIGRATION LIBRARY MEMBER\n"}},
        "SYS1.CSSLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"CSVQUERY": "SIMULATED COMMON SERVICES SAMPLE\n"}},
        "SYS1.SERBLINK": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ERBSCAN": "SIMULATED RMF/SERB LINK MODULE PLACEHOLDER\n"}},
        "SYS1.SISPLPA": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISPLPA": "ISPF LPA TRAINING PLACEHOLDER\n"}},
        "SYS1.SISPMENU": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISR@PRIM": "ISPF PRIMARY MENU TRAINING MEMBER\n", "ISRUTIL": "ISPF UTILITIES MENU TRAINING MEMBER\n"}},
        "SYS1.SISPPLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISREDIT": "ISPF EDIT PANEL TRAINING MEMBER\n", "ISRDSNL": "ISPF DSLIST PANEL TRAINING MEMBER\n"}},
        "SYS1.SISPSENU": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISRSENU": "ISPF ENGLISH MESSAGE TRAINING MEMBER\n"}},
        "SYS1.SISTCLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISPF": "ISPF TSO CLIST PLACEHOLDER\n", "ISRSTART": "ISPF STARTUP CLIST PLACEHOLDER\n"}},
        "SYS1.SDSF": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"ISFPARMS": "SDSF PARAMETER SAMPLE - TRAINING ONLY\n", "ISFPRM00": "SDSF SERVER PARAMETER SAMPLE\n"}},
        "SYS1.DB2.PROCLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"DB2MSTR": "//DB2MSTR PROC\n//MSTR EXEC PGM=DSN3MSTR\n", "DB2DIST": "//DB2DIST PROC\n//DIST EXEC PGM=DSNDIST\n"}},
        "SYS1.CICS.PROCLIB": {"ORG": "PO", "VOLUME": "SBSYS1", "members": {"CICS": "//CICS PROC\n//DFHSIP EXEC PGM=DFHSIP\n", "CICSAOR": "//CICSAOR PROC\n//AOR EXEC PGM=DFHSIP\n"}},
    }

    # Override the thin SYS1 placeholders with authentic sysprog-grade content
    # (and add the system libraries that were missing). New entries win.
    SYSTEM_DATASETS = {**SYSTEM_DATASETS, **SYS1_SYSTEM_DATASETS}

    def __init__(self, files_root: Path):
        self.files_root = Path(files_root)
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.security: Optional[DatasetSecurity] = None

    def user_home(self, userid: str) -> Path:
        p = self.files_root / userid.upper()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def split_name(self, dsname: str) -> tuple[str, str | None]:
        raw = (dsname or "").strip().strip("'").upper()
        m = re.fullmatch(r"(.+?)\(([^()]+)\)", raw)
        if m:
            return m.group(1).strip(), m.group(2).strip().upper()
        return raw, None

    def ds_path(self, userid: str, dsname: str) -> Path:
        dataset, member = self.split_name(dsname)
        parts = [p for p in dataset.split(".") if p]
        if not parts:
            parts = [userid.upper()]
        hlq = parts[0].upper()
        rel_parts = parts[1:] if len(parts) > 1 else parts
        base = self.files_root / hlq
        base.mkdir(parents=True, exist_ok=True)
        p = base.joinpath(*rel_parts) if rel_parts else base
        return (p / member) if member else p

    def meta_path(self, path: Path) -> Path:
        return Path(str(path) + ".meta")

    def _ensure_pds_parent(self, parent: Path, dataset: str, member: str) -> None:
        """Ensure ``parent`` is a directory able to hold a PDS member.

        Fixes the PS/PO collision behind the raw "[Errno 17] File exists" error:
        if a *sequential* data set already occupies the path, an empty stub is
        promoted to a partitioned data set, while a non-empty sequential data set
        raises a clean error the editor renders as a readable message.
        """
        if parent.exists() and not parent.is_dir():
            try:
                empty = parent.stat().st_size == 0
            except OSError:
                empty = False
            if empty:
                parent.unlink()
                self.meta_path(parent).unlink(missing_ok=True)
            else:
                raise NotADirectoryError(
                    f"{dataset} is a sequential data set; member {member} not allowed")
        parent.mkdir(parents=True, exist_ok=True)

    def _write_meta(self, path: Path, org: str = "PS", recfm: str = "FB", lrecl: int = 80, *, volume: str = "WORK01", blksize: int = 6160, cataloged: bool = True, **extra) -> None:
        old = {}
        mp = self.meta_path(path)
        if mp.exists():
            try:
                old = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        now = datetime.now().isoformat(timespec="seconds")
        meta = {
            "ORG": org, "RECFM": recfm, "LRECL": int(lrecl), "BLKSIZE": int(blksize), "VOLUME": volume,
            "CATALOGED": bool(cataloged),
            "CREATED": old.get("CREATED", now), "CHANGED": extra.get("changed", old.get("CHANGED", now)),
            "REFERENCED": extra.get("referenced", old.get("REFERENCED", now)),
            "OWNER": extra.get("owner", old.get("OWNER", "")),
            "MGMTCLAS": extra.get("mgmtclas", old.get("MGMTCLAS", "")),
            "STORCLAS": extra.get("storclas", old.get("STORCLAS", "")),
            "DATACLAS": extra.get("dataclas", old.get("DATACLAS", "")),
            "SPACE_UNITS": extra.get("space_units", old.get("SPACE_UNITS", "TRKS")),
            "PRIMARY": str(extra.get("primary", old.get("PRIMARY", "1"))),
            "SECONDARY": str(extra.get("secondary", old.get("SECONDARY", "1"))),
            "DIRBLKS": str(extra.get("dirblks", old.get("DIRBLKS", "0"))),
            "DEVICE": extra.get("device", old.get("DEVICE", "3390")),
            "LASTUSER": extra.get("lastuser", old.get("LASTUSER", "")),
        }
        mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def seed_defaults(self) -> None:
        for dsn, spec in self.SYSTEM_DATASETS.items():
            path = self.ds_path("IBMUSER", dsn)
            org = str(spec.get("ORG", "PO")).upper()
            volume = str(spec.get("VOLUME", "SBSYS1")).upper()
            # Static system libraries (PARMLIB/PROCLIB/VTAMLST/TCPPARMS/...) carry
            # refresh=True so a re-seed upgrades any stale placeholder member to
            # the canonical content. Dynamic data sets (RACFDS, MANx, ...) have no
            # refresh flag and stay create-if-missing so runtime data is kept.
            refresh = bool(spec.get("refresh", False))
            if org == "PO":
                path.mkdir(parents=True, exist_ok=True)
                if not self.meta_path(path).exists():
                    self._write_meta(path, org="PO", volume=volume)
                for member, content in (spec.get("members") or {}).items():
                    member_path = path / member.upper()
                    if refresh or not member_path.exists():
                        member_path.write_text(str(content), encoding="utf-8")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(str(spec.get("content", "")), encoding="utf-8")
                if not self.meta_path(path).exists():
                    self._write_meta(path, org="PS", volume=volume)


    def seed_user_training(self, userid: str) -> None:
        u = userid.upper()
        samples = {
            f"{u}.PDS.CODE": {
                "ORG": "PO",
                "members": {
                    "TIME": """/* REXX SCRIPT */
SAY 'HELLO IT IS ' TIME()
SAY 'YOUR USER-ID IS ' SYSVAR('SYSUID')
SAY 'The location of RACF is below'
SAY '-----------------------------'
ADDRESS TSO 'RVARY'
""",
                    "ENUM": """/* TRAINING PLACEHOLDER - EX 'HLQ.ENUM' 'APF' */
""",
                },
            },
            f"{u}.SQL.LAB": {
                "ORG": "PO",
                "members": {
                    "WHOADM": """SELECT USERID, AUTHORITY FROM SYSIBM.SYSUSERAUTH WHERE AUTHORITY = 'SYSADM';
""",
                    "SYSTABS": """SELECT NAME, CREATOR, TYPE FROM SYSIBM.SYSTABLES;
""",
                    "ADDARCHR": """INSERT INTO SYSIBM.SYSUSERAUTH (USERID, AUTHORITY) VALUES ('SARCHER','SYSADM');
""",
                },
            },
            f"{u}.4CHAR.PIN": {"ORG": "PS", "content": "0000\n0001\n1111\n1234\n9999\n"},
            f"{u}.JCL.LAB": {
                "ORG": "PO",
                "members": {
                    "TSHOCK": f"""//{u[:7]}J JOB (ACCT),'TSHOCKER',CLASS=A,MSGCLASS=A
//STEP1 EXEC PGM=IKJEFT01,PARM='%CATSO L 40002'
//SYSTSIN DD DUMMY
""",
                    "SURRJOB": """//SURRJOB JOB (ACCT),'SURROGAT',CLASS=A,MSGCLASS=A,USER=IBMUSER
//STEP1 EXEC PGM=IEFBR14
""",
                    "PROCDEMO": """//PROCJOB JOB (ACCT),'PROC DEMO',CLASS=A,MSGCLASS=A
//MYPROC  PROC WHO=IBMUSER
//STEPA   EXEC PGM=IKJEFT01
//SYSTSIN DD *
LISTUSER &WHO
/*
//        PEND
//RUN1    EXEC MYPROC,WHO=IBMUSER
""",
                },
            },
            f"{u}.COBOL.LAB": {
                "ORG": "PO",
                "members": {
                    "HELLO": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO FROM GIBSON COBOL LAB'.
           STOP RUN.
""",
                    "ACCTRPT": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTRPT.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-USERID      PIC X(8)  VALUE 'IBMUSER'.
       01  WS-BALANCE     PIC 9(7)V99 VALUE 0001234.56.
       PROCEDURE DIVISION.
           DISPLAY 'ACCOUNT REPORT FOR ' WS-USERID.
           DISPLAY 'CURRENT BALANCE: ' WS-BALANCE.
           STOP RUN.
""",
                    "READCARD": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. READCARD.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CARD-FILE ASSIGN TO SYSIN.
       DATA DIVISION.
       FILE SECTION.
       FD  CARD-FILE.
       01  CARD-REC       PIC X(80).
       WORKING-STORAGE SECTION.
       01  WS-EOF         PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           OPEN INPUT CARD-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ CARD-FILE
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END DISPLAY CARD-REC
               END-READ
           END-PERFORM.
           CLOSE CARD-FILE.
           STOP RUN.
""",
                },
            },
            f"{u}.REXX.LAB": {
                "ORG": "PO",
                "members": {
                    "HELLO": """/* REXX - simple greeting */
SAY 'HELLO' SYSVAR('SYSUID') '- IT IS' TIME()
SAY 'WELCOME TO THE GIBSON REXX LAB'
EXIT 0
""",
                    "WHOAMI": """/* REXX - show who and where I am */
SAY 'USERID  :' SYSVAR('SYSUID')
SAY 'TIME    :' TIME()
SAY 'DATE    :' DATE()
ADDRESS TSO 'LISTUSER' SYSVAR('SYSUID')
EXIT 0
""",
                    "LISTDS": """/* REXX - list a data set's attributes */
ARG DSN
IF DSN = '' THEN DSN = SYSVAR('SYSUID')".COBOL.LAB"
X = LISTDSI("'"DSN"'")
SAY 'DATASET :' DSN
SAY 'RECFM   :' SYSRECFM
SAY 'LRECL   :' SYSLRECL
SAY 'DSORG   :' SYSDSORG
EXIT 0
""",
                },
            },
        }
        for dsn, spec in samples.items():
            path = self.ds_path(u, dsn)
            if str(spec.get("ORG", "PO")).upper() == "PO":
                path.mkdir(parents=True, exist_ok=True)
                if not self.meta_path(path).exists():
                    self._write_meta(path, org="PO")
                for member, content in (spec.get("members") or {}).items():
                    member_path = path / member.upper()
                    if not member_path.exists():
                        member_path.write_text(str(content), encoding="utf-8")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(str(spec.get("content", "")), encoding="utf-8")
                if not self.meta_path(path).exists():
                    self._write_meta(path, org="PS")

    def allocate(self, userid: str, dsname: str, org: str = "PS", recfm: str = "FB",
                 lrecl: int = 80, *, blksize: int | None = None, volume: str | None = None,
                 space_units: str | None = None, primary=None, secondary=None,
                 dirblks=None, device: str | None = None, mgmtclas: str | None = None,
                 storclas: str | None = None, dataclas: str | None = None,
                 dsntype: str | None = None) -> DatasetInfo:
        dataset, member = self.split_name(dsname)
        p = self.ds_path(userid, dsname)
        exists = p.exists() or (member is not None and self.ds_path(userid, dataset).exists())
        if self.security is not None and exists:
            self.security.authorize(userid, dsname, "ALLOCATE")
        if member:
            parent = self.ds_path(userid, dataset)
            self._ensure_pds_parent(parent, dataset, member)
            p.touch(exist_ok=True)
            self._write_meta(parent, org="PO", recfm=recfm, lrecl=lrecl)
            if self.security is not None:
                self.security.on_allocate(userid, f"{dataset}({member})")
            return DatasetInfo(f"{dataset}({member})".upper(), "PO", p, recfm, lrecl)
        if dsntype and dsntype.upper() in ("LIBRARY", "PDS", "PDSE"):
            org = "PO"
        elif dirblks not in (None, "") and str(dirblks).isdigit() and int(dirblks) > 0:
            org = "PO"
        meta_kw: dict = {}
        for key, val in (("space_units", space_units), ("primary", primary),
                         ("secondary", secondary), ("dirblks", dirblks), ("device", device),
                         ("mgmtclas", mgmtclas), ("storclas", storclas), ("dataclas", dataclas)):
            if val not in (None, ""):
                meta_kw[key] = val
        if volume:
            meta_kw["volume"] = volume
        if blksize is not None:
            meta_kw["blksize"] = blksize
        if org.upper() in ("PO", "PDS"):
            p.mkdir(parents=True, exist_ok=True)
            org = "PO"
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            org = "PS"
        self._write_meta(p, org=org, recfm=recfm, lrecl=lrecl, **meta_kw)
        if self.security is not None:
            self.security.on_allocate(userid, dsname)
        return DatasetInfo(dsname.upper(), org, p, recfm, lrecl,
                           blksize=blksize if blksize is not None else 6160,
                           volume=volume or "WORK01")

    def _iter_dataset_infos(self) -> List[DatasetInfo]:
        rows: List[DatasetInfo] = []
        seen: set[str] = set()
        pds_dirs: set[Path] = set()
        for mp in sorted(self.files_root.rglob("*.meta")):
            base = Path(str(mp)[:-5])
            if not base.exists():
                continue
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
            rel = base.relative_to(self.files_root)
            dsn = ".".join(part.upper() for part in rel.parts)
            org = str(meta.get("ORG", "PO" if base.is_dir() else "PS")).upper()
            info = DatasetInfo(
                dsn,
                org,
                base,
                str(meta.get("RECFM", "FB")).upper(),
                int(meta.get("LRECL", 80)),
                int(meta.get("BLKSIZE", 6160)),
                str(meta.get("VOLUME", "WORK01")).upper(),
            )
            rows.append(info)
            seen.add(str(base.resolve()))
            if base.is_dir() and org == "PO":
                pds_dirs.add(base.resolve())
        # Legacy fallback: surface only leaf sequential files that lack metadata.
        # Do not expose intermediate qualifier directories such as HLQ.TEST as if they
        # were real PO data sets. Dataset allocation and seeding write metadata for the
        # actual dataset object; qualifier directories are just backing-store scaffolding.
        for path in sorted(self.files_root.rglob("*")):
            if path.name.endswith(".meta"):
                continue
            resolved = path.resolve()
            if str(resolved) in seen:
                continue
            if any(parent.resolve() in pds_dirs for parent in path.parents):
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(self.files_root)
            dsn = ".".join(part.upper() for part in rel.parts)
            rows.append(DatasetInfo(dsn, "PS", path))
        rows.sort(key=lambda r: r.name)
        return rows

    def listcat(self, userid: str, prefix: Optional[str] = None) -> List[DatasetInfo]:
        filt = (prefix or userid or "").strip().strip("'").upper()
        rows = []
        for info in self._iter_dataset_infos():
            meta = self.meta(userid, info.name)
            if meta and meta.get("CATALOGED") is False:
                continue
            if not filt or info.name.startswith(filt):
                rows.append(info)
        return rows

    def read(self, userid: str, dsname: str) -> str:
        if self.security is not None:
            self.security.authorize(userid, dsname, "READ")
        p = self.ds_path(userid, dsname)
        if p.is_dir():
            meta=self.meta(userid, dsname); self._write_meta(p, org=meta.get("ORG","PO"), recfm=meta.get("RECFM","FB"), lrecl=int(meta.get("LRECL",80)), volume=meta.get("VOLUME","WORK01"), blksize=int(meta.get("BLKSIZE",6160)), cataloged=meta.get("CATALOGED", True), referenced=datetime.now().isoformat(timespec="seconds"), lastuser=userid.upper())
            return "\n".join(sorted(x.name for x in p.iterdir() if not x.name.endswith(".meta")))
        if not p.exists():
            raise FileNotFoundError(dsname)
        meta=self.meta(userid, dsname); self._write_meta(p, org=meta.get("ORG","PS"), recfm=meta.get("RECFM","FB"), lrecl=int(meta.get("LRECL",80)), volume=meta.get("VOLUME","WORK01"), blksize=int(meta.get("BLKSIZE",6160)), cataloged=meta.get("CATALOGED", True), referenced=datetime.now().isoformat(timespec="seconds"), lastuser=userid.upper())
        return p.read_text(encoding="utf-8", errors="ignore")

    def write(self, userid: str, dsname: str, text: str) -> None:
        if self.security is not None:
            self.security.authorize(userid, dsname, "UPDATE")
        dataset, member = self.split_name(dsname)
        p = self.ds_path(userid, dsname)
        if member:
            parent = self.ds_path(userid, dataset)
            self._ensure_pds_parent(parent, dataset, member)
            mp = self.meta_path(parent)
            if not mp.exists():
                self._write_meta(parent, org="PO", recfm="FB", lrecl=80)
                if self.security is not None:
                    self.security.on_allocate(userid, dataset)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        target_meta_path = self.meta_path(parent if member else p)
        if member is None and not self.meta_path(p).exists():
            self._write_meta(p, owner=userid.upper(), lastuser=userid.upper())
        else:
            base = parent if member else p
            meta=self.meta(userid, dataset if member else dsname)
            if base.exists():
                self._write_meta(base, org=meta.get("ORG", "PO" if member else "PS"), recfm=meta.get("RECFM","FB"), lrecl=int(meta.get("LRECL",80)), volume=meta.get("VOLUME","WORK01"), blksize=int(meta.get("BLKSIZE",6160)), cataloged=meta.get("CATALOGED", True), changed=datetime.now().isoformat(timespec="seconds"), lastuser=userid.upper())
        if self.security is not None:
            self.security.on_allocate(userid, dsname)


    def meta(self, userid: str, dsname: str) -> dict:
        p = self.ds_path(userid, self.split_name(dsname)[0])
        mp = self.meta_path(p)
        if mp.exists():
            try:
                return json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def members(self, userid: str, dsname: str) -> List[str]:
        if self.security is not None:
            self.security.authorize(userid, dsname, "READ")
        dataset, _ = self.split_name(dsname)
        p = self.ds_path(userid, dataset)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(dsname)
        return sorted(x.name.upper() for x in p.iterdir() if x.is_file() and not x.name.endswith(".meta"))

    def catalog(self, userid: str, dsname: str) -> str:
        if self.security is not None:
            self.security.authorize(userid, dsname, "ALTER")
        p = self.ds_path(userid, self.split_name(dsname)[0])
        if not p.exists():
            return f"IDC3012I ENTRY {dsname.upper()} NOT FOUND"
        meta = self.meta(userid, dsname)
        self._write_meta(p, org=meta.get("ORG", "PO" if p.is_dir() else "PS"), recfm=meta.get("RECFM", "FB"), lrecl=int(meta.get("LRECL", 80)), volume=meta.get("VOLUME", "WORK01"), blksize=int(meta.get("BLKSIZE", 6160)), cataloged=True)
        return f"IDC0001I FUNCTION COMPLETED, DATA SET {dsname.upper()} CATALOGED"

    def uncatalog(self, userid: str, dsname: str) -> str:
        if self.security is not None:
            self.security.authorize(userid, dsname, "ALTER")
        p = self.ds_path(userid, self.split_name(dsname)[0])
        if not p.exists():
            return f"IDC3012I ENTRY {dsname.upper()} NOT FOUND"
        meta = self.meta(userid, dsname)
        self._write_meta(p, org=meta.get("ORG", "PO" if p.is_dir() else "PS"), recfm=meta.get("RECFM", "FB"), lrecl=int(meta.get("LRECL", 80)), volume=meta.get("VOLUME", "WORK01"), blksize=int(meta.get("BLKSIZE", 6160)), cataloged=False)
        return f"IDC0001I FUNCTION COMPLETED, DATA SET {dsname.upper()} UNCATALOGED"

    def delete(self, userid: str, dsname: str) -> str:
        if self.security is not None:
            self.security.authorize(userid, dsname, "ALTER")
        p = self.ds_path(userid, dsname)
        if not p.exists():
            return f"IDC3012I ENTRY {dsname.upper()} NOT FOUND"
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        mp = self.meta_path(p)
        if mp.exists():
            mp.unlink()
        return f"IDC0550I ENTRY {dsname.upper()} SUCCESSFULLY DELETED"
