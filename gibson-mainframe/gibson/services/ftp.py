from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Callable

from gibson.apps.db2_sim import Db2Simulator
from gibson.core.state import GibsonState


@dataclass
class SqlProcessResult:
    outfile: str
    outtext: str
    jobid: Optional[str] = None


class GibsonFtpAdapter:
    """Shared-state hooks for the FTP service.

    Supports FILE/JES/SQL modes plus a TShOcker-style training lab flow:
    - JES uploads become JES jobs visible in SDSF and retrievable via FTP in JES mode.
    - SQL uploads create a DB2-style text output file and a matching JES spool entry.
    - Special SYSIBM.SYSUSERAUTH/SARCHER lab SQL updates the training RACF DB.
    """

    def __init__(self, state: GibsonState):
        self.state = state

    def stor_jes(self, userid: str, filename: str, content: bytes, tso_runner: Optional[Callable[[str], str]] = None) -> str:
        text = content.decode("utf-8", errors="ignore")
        job = self.state.jes.submit(
            text,
            userid,
            runner=tso_runner,
            sql_runner=lambda sql: Db2Simulator(self.state).format_spufi(sql, userid),
            submitter=userid,
        )
        # z/OS FTP internal-reader response. The job id is the real, incrementing
        # id assigned by JES, and the job is retrievable with GET <jobid>.
        lines = [f"250-It is known to JES as {job.jobid}"]
        if job.training_endpoint:
            lines.append(f"250-Training shell (tshocker) listening on port {job.training_endpoint}")
        lines.append("250 Transfer completed successfully.")
        return "\r\n".join(lines)

    def _ensure_sarcher_exact(self) -> None:
        self.state.racf.load(merge=True)
        self.state.racf.adduser("SARCHER", "$1$UW46ARLk$MJtsT0nRnPwgYGvSRYyiY.", special=True, omvs=True)

    def process_sql(self, userid: str, sql: str) -> SqlProcessResult:
        norm = " ".join(sql.replace("\r", " ").replace("\n", " ").split()).upper()
        lines: list[str] = []

        def footer(ok: bool = True) -> None:
            if ok:
                lines.extend([
                    "DSNE601I SQLSTAT = 00000",
                    "DSNE617I DSN UTILITIES STARTED SUCCESSFULLY",
                    "DSNE618I END OF SQL STATEMENT PROCESSING",
                ])
            else:
                lines.extend([
                    "DSNE601I SQLSTAT = 38553",
                    "DSNE617I DSN UTILITIES STARTED WITH WARNINGS",
                    "DSNE618I END OF SQL STATEMENT PROCESSING",
                ])

        if "INSERT INTO SYSIBM.SYSUSERAUTH" in norm and "SARCHER" in norm:
            outfile = "JOBADD_ARCHER.txt"
            lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
            lines.append("USERID               AUTHORITY")
            lines.append("SARCHER              SYSADM")
            footer(True)
            try:
                self._ensure_sarcher_exact()
            except Exception as exc:
                lines.append(f"-- NOTE: Failed to update GACF.DB: {exc}")
            lines.append("")
            lines.append("SARCHER added - check default SYSADM password for access.")
        elif ("FROM SYSIBM.SYSUSERAUTH" in norm and "AUTHORITY = 'SYSADM'" in norm) or ("FROM SYSIBM.SYSUSERAUTH" in norm and "WHERE SYSADMAUTH = 'Y'" in norm):
            outfile = "JOBWHO_HAS_SYSADM.txt"
            lines.append("DSNE616I NUMBER OF ROWS DISPLAYED IS 2")
            lines.append("USERID               AUTHORITY")
            lines.append("DBAUSER1             SYSADM")
            lines.append("SECUSER2             SYSADM")
            footer(True)
        elif "FROM SYSIBM.SYSTABLES" in norm:
            outfile = "JOBSHOW_SYSTABLES.txt"
            lines.append("NAME                 CREATOR     TYPE")
            lines.append("SYSTABLES            SYSIBM      T")
            lines.append("SYSUSERAUTH          SYSIBM      V")
            lines.append("SYSINDEXES           SYSIBM      X")
            footer(True)
        elif norm.startswith("INSERT "):
            outfile = "JOBINSERT_GENERIC.txt"
            lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
            footer(True)
        elif norm.startswith("UPDATE "):
            outfile = "JOBUPDATE_GENERIC.txt"
            lines.append("DSNE615I NUMBER OF ROWS AFFECTED IS 1")
            footer(True)
        else:
            outfile = "JOBSQL_GENERIC.txt"
            lines.append("-- Statement processed for training; no rows returned")
            footer(True)
        return SqlProcessResult(outfile=outfile, outtext="\n".join(lines))

    def stor_sql(self, userid: str, filename: str, content: bytes) -> str:
        sql = content.decode("utf-8", errors="ignore")
        self.state.datasets.write(userid, filename, sql)
        result = self.process_sql(userid, sql)
        self.state.datasets.write(userid, result.outfile, result.outtext)
        # Also create a JES spool entry so the lab can inspect SQL output in SDSF/O panels.
        jcl = (
            f"//SQLFTP   JOB (ACCT),'FTP SQL',CLASS=A,MSGCLASS=A,USER={userid.upper()}\n"
            "//STEP1    EXEC PGM=DSNTEP2\n"
            "//SYSIN    DD *\n"
            f"{sql.rstrip()}\n"
            "/*\n"
        )
        job = self.state.jes.submit(
            jcl,
            userid,
            sql_runner=lambda _sql: result.outtext,
            submitter=userid,
        )
        return f"226 SQL processed; output in {result.outfile}; job={job.jobid}"

    def list_jes(self, userid: str) -> str:
        lines = ["JOBID     JOBNAME   OWNER    STATUS   RC"]
        for job in self.state.jes.list_jobs(owner=userid):
            lines.append(f"{job.jobid:<9} {job.jobname:<8} {job.owner:<8} {job.status.value:<8} {job.rc:04d}")
        return "\n".join(lines)

    def retr_jes(self, userid: str, jobid: str) -> str:
        job = self.state.jes.jobs.get(jobid.upper())
        if not job:
            raise FileNotFoundError(jobid)
        allowed = {job.owner.upper(), (job.submitter or "").upper(), userid.upper()}
        if userid.upper() not in allowed:
            raise PermissionError(f"JES spool access denied for {jobid.upper()}")
        parts = [f"----- {sf.ddname} -----\n{sf.content}" for sf in job.spool]
        return "\n\n".join(parts)
