from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import itertools
import re

from gibson.core.training_shell import start_training_shell


class JobStatus(str, Enum):
    INPUT = "INPUT"
    CONVERSION = "CONVERSION"
    EXECUTION = "EXECUTION"
    ACTIVE = "ACTIVE"
    OUTPUT = "OUTPUT"
    HELD = "HELD"
    PURGED = "PURGED"
    FAILED = "FAILED"


@dataclass
class SpoolFile:
    ddname: str
    content: str


@dataclass
class Job:
    jobid: str
    jobname: str
    owner: str
    jcl: str
    status: JobStatus = JobStatus.INPUT
    submitted: datetime = field(default_factory=datetime.now)
    ended: Optional[datetime] = None
    rc: int = 0
    spool: List[SpoolFile] = field(default_factory=list)
    submitter: str = ""
    message_class: str = "A"
    job_class: str = "A"
    training_endpoint: str = ""
    summary: str = ""

    @property
    def records(self) -> int:
        return sum(len(s.content.splitlines()) for s in self.spool)


class JesSpool:
    def __init__(self):
        self._counter = itertools.count(1)
        self.jobs: Dict[str, Job] = {}

    def next_jobid(self) -> str:
        return f"JOB{next(self._counter):05d}"

    def parse_job_card(self, jcl: str, fallback_owner: str = "IBMUSER") -> dict[str, str]:
        info = {
            "jobname": fallback_owner[:8].upper() or "JOB",
            "owner": fallback_owner.upper(),
            "class": "A",
            "msgclass": "A",
        }
        for line in jcl.splitlines():
            if line.startswith("//") and " JOB" in line.upper():
                body = line[2:]
                info["jobname"] = re.sub(r"[^A-Z0-9#$@]", "", body.split()[0].upper())[:8] or info["jobname"]
                m_user = re.search(r"\bUSER\s*=\s*([A-Z0-9#$@]+)", line, re.I)
                if m_user:
                    info["owner"] = m_user.group(1).upper()
                m_cls = re.search(r"\bCLASS\s*=\s*([A-Z0-9])", line, re.I)
                if m_cls:
                    info["class"] = m_cls.group(1).upper()
                m_msg = re.search(r"\bMSGCLASS\s*=\s*([A-Z0-9])", line, re.I)
                if m_msg:
                    info["msgclass"] = m_msg.group(1).upper()
                break
        return info

    def submit(
        self,
        jcl: str,
        owner: str,
        runner: Optional[Callable[[str], str]] = None,
        sql_runner: Optional[Callable[[str], str]] = None,
        cobol_runner: Optional[Callable[[str], tuple[int, str, List[str]]]] = None,
        submitter: Optional[str] = None,
    ) -> Job:
        jobid = self.next_jobid()
        card = self.parse_job_card(jcl, fallback_owner=owner)
        job = Job(
            jobid,
            card["jobname"],
            card["owner"],
            jcl,
            submitter=(submitter or owner).upper(),
            message_class=card["msgclass"],
            job_class=card["class"],
        )
        self.jobs[jobid] = job
        self.run(jobid, runner=runner, sql_runner=sql_runner, cobol_runner=cobol_runner)
        return job

    def _convert_jcl(self, jcl: str) -> tuple[list[str], list[str], Optional[str]]:
        """Pre-execution JCL conversion pass.

        Returns (converter_msgs, jecl_msgs, jcl_error). ``jcl_error`` is None for
        clean JCL; otherwise a short reason and the job fails in conversion
        (no step is executed), the way real z/OS rejects bad JCL before run.

        Detection is deliberately high-precision so valid JCL is never flagged:
        only an invalid label (IEFC662I) or a dangling continuation comma with
        no continuation line (IEFC621I) trip an error. Recognised JECL
        statements are acknowledged.
        """
        conv: list[str] = []
        jecl: list[str] = []
        error: Optional[str] = None
        lines = jcl.splitlines()
        JECL = ("/*JOBPARM", "/*ROUTE", "/*OUTPUT", "/*MESSAGE", "/*NOTIFY",
                "/*PRIORITY", "/*SETUP", "/*NETACCT", "/*SIGNON", "/*JECL")
        stmt_no = 0
        for i, raw in enumerate(lines):
            s = raw.rstrip()
            u = s.upper()
            # JECL statements (/* in cols 1-2) - acknowledge, don't number as JCL
            if u.startswith("/*") and any(u.startswith(j) for j in JECL):
                kw = u.split()[0]
                if kw == "/*JOBPARM":
                    jecl.append("IEFC001I JES2 JECL STATEMENT /*JOBPARM ACCEPTED")
                elif kw == "/*ROUTE":
                    dest = s.split(None, 2)[2] if len(s.split(None, 2)) > 2 else ""
                    sub = s.split()[1].upper() if len(s.split()) > 1 else "PRINT"
                    jecl.append(f"$HASP000 JECL /*ROUTE {sub} {dest}".rstrip() + " ACCEPTED")
                elif kw == "/*OUTPUT":
                    jecl.append("IEFC001I JES2 JECL STATEMENT /*OUTPUT PROCESSED")
                elif kw == "/*MESSAGE":
                    jecl.append(f"$HASP000 {s[9:].strip()}")
                elif kw == "/*NOTIFY":
                    jecl.append("$HASP000 JECL /*NOTIFY ACCEPTED")
                else:
                    jecl.append(f"$HASP000 JECL {kw} ACCEPTED")
                continue
            # delimiter (/*), comments (//*), null statement (//), in-stream data
            if u.startswith("//*") or s.strip() in ("/*", "//") or not u.startswith("//"):
                continue
            body = s[2:]
            # continuation line: column 3 is blank
            if body[:1] in (" ", "\t"):
                continue
            stmt_no += 1
            name = re.split(r"[ \t]", body, 1)[0]
            # IEFC662I invalid label: bad chars or > 8 characters
            if name and (len(name) > 8 or not re.match(r"^[A-Z#$@][A-Z0-9#$@]*$", name.upper())):
                msg = f"IEFC662I {stmt_no:>5}  INVALID LABEL - {name[:14]}"
                conv.append(msg)
                error = error or f"IEFC662I INVALID LABEL {name[:8]}"
                continue
            # IEFC621I expected continuation: parameter field ends with a comma
            # but the next line is not a continuation (col 3 not blank) / is EOF.
            if s.endswith(","):
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                is_cont = nxt[:2] == "//" and nxt[2:3] in (" ", "\t")
                if not is_cont:
                    conv.append(f"IEFC621I {stmt_no:>5}  EXPECTED CONTINUATION NOT RECEIVED")
                    error = error or "IEFC621I EXPECTED CONTINUATION NOT RECEIVED"
        return conv, jecl, error

    def run(self, jobid: str, runner=None, sql_runner=None, cobol_runner=None) -> None:
        job = self.jobs[jobid]
        job.status = JobStatus.CONVERSION
        conv_msgs, jecl_msgs, jcl_error = self._convert_jcl(job.jcl)
        if jcl_error:
            # Job fails in conversion - no step runs (authentic z/OS behaviour).
            msglog = [
                f"$HASP100 {job.jobname} ON READER",
                f"IRR010I USERID {job.owner} IS ASSIGNED TO THIS JOB.",
            ] + jecl_msgs + conv_msgs + [
                f"IEFC452I {job.jobname} - JOB NOT RUN - JCL ERROR",
                f"$HASP165 {job.jobname} ENDED - JCL ERROR",
            ]
            job.spool.append(SpoolFile("JESMSGLG", "\n".join(msglog) + "\n"))
            job.spool.append(SpoolFile("JESJCL", job.jcl))
            job.spool.append(SpoolFile("JESYSMSG",
                             "\n".join(conv_msgs) + f"\n IEFC452I {job.jobname} JCL ERROR\n"))
            job.rc = 8
            job.summary = jcl_error
            job.status = JobStatus.FAILED
            job.ended = datetime.now()
            return
        job.status = JobStatus.EXECUTION
        jesmsglg = [
            f"$HASP100 {job.jobname} ON READER",
            f"IRR010I USERID {job.owner} IS ASSIGNED TO THIS JOB.",
        ]
        jesmsglg.extend(jecl_msgs)
        jesmsglg.extend([
            f"$HASP373 {job.jobname} STARTED - INIT 1 - CLASS {job.job_class}",
            f"IEF403I {job.jobname} - STARTED - TIME={job.submitted.strftime('%H.%M.%S')}",
        ])
        if job.submitter and job.submitter != job.owner:
            jesmsglg.append(f"ICH70002I JOB SUBMITTED BY {job.submitter} FOR EXECUTION AS {job.owner} USING SURROGAT ACCESS")
        job.spool.append(SpoolFile("JESMSGLG", "\n".join(jesmsglg) + "\n"))
        job.spool.append(SpoolFile("JESJCL", job.jcl))
        output, rc, extra_spool, summary = self._interpret_steps(job, runner=runner, sql_runner=sql_runner, cobol_runner=cobol_runner)
        job.rc = rc
        job.summary = summary
        job.spool.extend(extra_spool)
        sysmsg = output + f"\nIEF404I {job.jobname} - ENDED - TIME={datetime.now().strftime('%H.%M.%S')}\n$HASP395 {job.jobname} ENDED - RC={rc:04d}\n"
        job.spool.append(SpoolFile("JESYSMSG", sysmsg))
        job.status = JobStatus.OUTPUT if rc < 8 else JobStatus.FAILED
        job.ended = datetime.now()

    def _collect_instream(self, lines: List[str]) -> Dict[str, str]:
        blocks: Dict[str, List[str]] = {}
        current: Optional[str] = None
        for line in lines:
            u = line.upper()
            m = re.match(r"^//([A-Z0-9#$@]+)\s+DD\s+\*", u)
            if m:
                current = m.group(1)
                blocks[current] = []
                continue
            if current and u.startswith("/*"):
                current = None
                continue
            if current:
                blocks[current].append(line.rstrip("\n"))
        return {k: "\n".join(v) for k, v in blocks.items()}

    def _dd_dsn(self, lines: List[str], ddname: str) -> str:
        """Resolve a DD name to its DSN= from the (expanded) JCL lines."""
        pat = re.compile(rf"^//{re.escape(ddname.upper())}\s+DD\b(.*)$", re.I)
        for ln in lines:
            m = pat.match(ln.strip())
            if m:
                mm = re.search(r"DSN(?:AME)?\s*=\s*([^,\s]+)", m.group(1), re.I)
                if mm:
                    return mm.group(1).strip().strip("'")
        return ""

    def _store_records(self, state, user: str, dsn: str, data: str) -> None:
        """Write records to a dataset, preserving a VSAM (VS) org marking that
        a prior DEFINE CLUSTER may have set (allocate would otherwise reset it)."""
        prior_org = None
        try:
            meta = state.datasets.meta(user, dsn)
            prior_org = (meta or {}).get("ORG")
        except Exception:
            prior_org = None
        state.datasets.allocate(user, dsn, org="PS")
        state.datasets.write(user, dsn, data)
        if prior_org == "VS":
            try:
                p = state.datasets.ds_path(user, dsn)
                state.datasets._write_meta(p, org="VS", recfm="VB", lrecl=80)
            except Exception:
                pass

    def _dfsort(self, records: List[str], sysin: str, out: List[str]) -> List[str]:
        """Apply a SORT FIELDS= (or COPY) control statement to records.

        Supports multi-field keys ``FIELDS=(pos,len,fmt,order,...)`` with CH
        (character) and numeric (ZD/PD/FI/BI) formats and A/D ordering, plus
        ``FIELDS=COPY``.  Stable multi-key behaviour is achieved by sorting from
        the least- to most-significant key.
        """
        if re.search(r"\bSORT\s+FIELDS\s*=\s*COPY", sysin, re.I):
            return list(records)
        m = re.search(r"\bSORT\s+FIELDS\s*=\s*\(([^)]*)\)", sysin, re.I)
        if not m:
            return list(records)
        toks = [t.strip().upper() for t in m.group(1).split(",") if t.strip()]
        gfmt = ""
        gf = re.search(r"\bFORMAT\s*=\s*([A-Z]{2})", sysin, re.I)
        if gf:
            gfmt = gf.group(1).upper()
        specs = []
        i = 0
        while i + 1 < len(toks):
            try:
                pos = int(toks[i]); length = int(toks[i + 1])
            except ValueError:
                break
            j = i + 2
            fmt = gfmt or "CH"
            order = "A"
            if j < len(toks) and toks[j] in ("CH", "ZD", "PD", "FI", "BI", "AC", "FL"):
                fmt = toks[j]; j += 1
            if j < len(toks) and toks[j] in ("A", "D"):
                order = toks[j]; j += 1
            specs.append((pos, length, fmt, order))
            i = j
        result = list(records)
        for pos, length, fmt, order in reversed(specs):
            def key(rec, pos=pos, length=length, fmt=fmt):
                seg = rec[pos - 1:pos - 1 + length]
                if fmt in ("ZD", "PD", "FI", "BI"):
                    try:
                        return (0, int(seg.strip() or "0"))
                    except ValueError:
                        return (0, 0)
                return (1, seg)
            result.sort(key=key, reverse=(order == "D"))
        out.append(f"ICE201I 0 RECORD TYPE IS F - DFSORT SORTED {len(specs)} KEY FIELD(S)")
        return result

    def _idcams_source(self, cmd: str, lines, blocks, state, user) -> str:
        """Resolve REPRO/PRINT input: INFILE(dd) or INDATASET('dsn')."""
        f = re.search(r"\b(?:INFILE|IFILE)\s*\(([^)]+)\)", cmd, re.I)
        if f:
            return self._read_dd(lines, blocks, f.group(1).strip(), state, user)
        d = re.search(r"\b(?:INDATASET|INDS|IDS)\s*\(([^)]+)\)", cmd, re.I)
        if d and state is not None:
            try:
                return state.datasets.read(user, d.group(1).strip().strip("'"))
            except Exception:
                return ""
        return ""

    def _idcams_target(self, cmd: str, lines) -> str:
        """Resolve REPRO output: OUTFILE(dd)->DSN or OUTDATASET('dsn')."""
        f = re.search(r"\b(?:OUTFILE|OFILE)\s*\(([^)]+)\)", cmd, re.I)
        if f:
            return self._dd_dsn(lines, f.group(1).strip())
        d = re.search(r"\b(?:OUTDATASET|OUTDS|ODS)\s*\(([^)]+)\)", cmd, re.I)
        if d:
            return d.group(1).strip().strip("'")
        return ""

    def _read_dd(self, lines: List[str], blocks: Dict[str, str], ddname: str,
                 state, user: str) -> str:
        """Return the data behind a DD: instream (DD *) first, else its DSN."""
        ddname = ddname.upper()
        if ddname in blocks and blocks[ddname]:
            return blocks[ddname]
        dsn = self._dd_dsn(lines, ddname)
        if dsn and state is not None:
            try:
                return state.datasets.read(user, dsn)
            except Exception:
                return ""
        return ""

    def _extract_steps(self, lines: List[str]) -> list[tuple[str, str, str]]:
        steps: list[tuple[str, str, str]] = []
        for line in lines:
            if not line.startswith("//") or line.startswith("//*"):
                continue
            m = re.match(r"^//([A-Z0-9#$@]+)\s+EXEC\s+(.*)$", line, re.I)
            if not m:
                continue
            stepname = m.group(1).upper()
            operands = m.group(2).strip()
            pgm = ""
            if "PGM=" in operands.upper():
                m_pgm = re.search(r"PGM\s*=\s*([^,\s]+)", operands, re.I)
                if m_pgm:
                    pgm = m_pgm.group(1).strip().strip("'").upper()
            elif operands.upper().startswith("PROC"):
                pgm = "PROC"
            steps.append((stepname, pgm, operands))
        return steps

    def _extract_tshocker_mode(self, job: Job) -> tuple[str | None, str | None, int | None]:
        jcl = job.jcl
        m = re.search(r"PARM\s*=\s*'%'?([A-Z0-9#$@]+)\s+([LR])\s+([^']+)'", jcl, re.I)
        if not m:
            return None, None, None
        mode = m.group(2).upper()
        rest = m.group(3).strip().split()
        if mode == "L":
            port = int(rest[-1]) if rest and rest[-1].isdigit() else None
            return mode, None, port
        if len(rest) >= 2 and rest[-1].isdigit():
            return mode, rest[0], int(rest[-1])
        return mode, None, None

    def _expand_procs(self, lines: List[str]) -> List[str]:
        procs: dict[str, tuple[dict[str, str], list[str]]] = {}
        out: list[str] = []
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            m = re.match(r"^//([A-Z0-9#$@]+)\s+PROC\s*(.*)$", line, re.I)
            if m:
                name = m.group(1).upper()
                defaults: dict[str, str] = {}
                for key, value in re.findall(r"([A-Z0-9#$@]+)\s*=\s*([^,\s]+)", m.group(2), re.I):
                    defaults[key.upper()] = value.strip().strip("'")
                body: list[str] = []
                idx += 1
                while idx < len(lines):
                    cur = lines[idx]
                    if re.match(r"^//\s*PEND\b", cur, re.I):
                        break
                    body.append(cur)
                    idx += 1
                procs[name] = (defaults, body)
                idx += 1
                continue
            m_exec = re.match(r"^//([A-Z0-9#$@]+)\s+EXEC\s+([A-Z0-9#$@]+)(.*)$", line, re.I)
            if m_exec and "PGM=" not in m_exec.group(2).upper() and m_exec.group(2).upper() in procs:
                stepname, procname, parms = m_exec.group(1).upper(), m_exec.group(2).upper(), m_exec.group(3)
                defaults, body = procs[procname]
                symbols = defaults.copy()
                for key, value in re.findall(r"([A-Z0-9#$@]+)\s*=\s*([^,\s]+)", parms, re.I):
                    symbols[key.upper()] = value.strip().strip("'")
                for bidx, raw in enumerate(body, 1):
                    rep = raw
                    if bidx == 1 and rep.startswith("//"):
                        rep = f"//{stepname} " + rep[2:].split(None, 1)[1]
                    for key, value in symbols.items():
                        rep = rep.replace(f"&{key}", value)
                    out.append(rep)
                idx += 1
                continue
            out.append(line)
            idx += 1
        return out

    def _extract_flow(self, lines: List[str]) -> list[tuple[str, str, str]]:
        flow: list[tuple[str, str, str]] = []
        for line in lines:
            if not line.startswith("//") or line.startswith("//*"):
                continue
            u = line.upper().strip()
            if re.match(r"^//\s*IF\s+", u):
                flow.append(("IF", "IF", line[2:].strip()))
                continue
            if re.match(r"^//\s*ELSE\b", u):
                flow.append(("ELSE", "ELSE", ""))
                continue
            if re.match(r"^//\s*ENDIF\b", u):
                flow.append(("ENDIF", "ENDIF", ""))
                continue
            m = re.match(r"^//([A-Z0-9#$@]+)\s+EXEC\s+(.*)$", line, re.I)
            if not m:
                continue
            stepname = m.group(1).upper()
            operands = m.group(2).strip()
            pgm = ""
            if "PGM=" in operands.upper():
                m_pgm = re.search(r"PGM\s*=\s*([^,\s]+)", operands, re.I)
                if m_pgm:
                    pgm = m_pgm.group(1).strip().strip("'").upper()
            flow.append((stepname, pgm, operands))
        return flow

    def _eval_if_expr(self, expr: str, *, last_rc: int, step_rcs: dict[str, int]) -> bool:
        work = expr.upper()
        work = re.sub(r"^IF\s+", "", work)
        work = re.sub(r"\s+THEN$", "", work)
        for step, rc in step_rcs.items():
            work = work.replace(f"{step}.RC", str(rc))
        work = re.sub(r"\bRC\b", str(last_rc), work)
        work = work.replace("=", "==")
        work = work.replace(">===", ">=").replace("<===", "<=").replace("!==", "!=")
        work = work.replace("<>", "!=")
        work = work.replace(" AND ", " and ").replace(" OR ", " or ")
        try:
            return bool(eval(work, {"__builtins__": {}}, {}))
        except Exception:
            return False

    def _cond_skip(self, operands: str, *, last_rc: int) -> bool:
        m = re.search(r"COND\s*=\s*\(([^)]+)\)", operands, re.I)
        if not m:
            return False
        parts = [p.strip().upper() for p in m.group(1).split(",") if p.strip()]
        if not parts:
            return False
        try:
            code = int(parts[0])
        except Exception:
            code = 0
        op = parts[1] if len(parts) > 1 else "NE"
        return {
            "GT": last_rc > code,
            "GE": last_rc >= code,
            "LT": last_rc < code,
            "LE": last_rc <= code,
            "EQ": last_rc == code,
            "NE": last_rc != code,
        }.get(op, False)

    def _interpret_steps(self, job: Job, runner=None, sql_runner=None, cobol_runner=None) -> tuple[str, int, list[SpoolFile], str]:
        lines = self._expand_procs(job.jcl.splitlines())
        blocks = self._collect_instream(lines)
        steps = self._extract_flow(lines)
        out: List[str] = []
        extra_spool: list[SpoolFile] = []
        rc = 0
        last_rc = 0
        step_rcs: dict[str, int] = {}
        if_stack: list[bool] = []
        summary = "JOB PROCESSED BY GIBSON JES2 SIMULATOR"

        for raw in lines:
            if raw.upper().startswith("/*XEQ"):
                node = raw.split(maxsplit=1)[1].strip().upper() if len(raw.split(maxsplit=1)) > 1 else "UNKNOWN"
                extra_spool.append(SpoolFile("JESNJE", f"$HASP000 JOB ROUTED TO NJE NODE {node} BY /*XEQ\n"))
                break

        for stepname, pgm, operands in steps:
            if stepname == "IF":
                if_stack.append(self._eval_if_expr(operands, last_rc=last_rc, step_rcs=step_rcs))
                continue
            if stepname == "ELSE":
                if if_stack:
                    if_stack[-1] = not if_stack[-1]
                continue
            if stepname == "ENDIF":
                if if_stack:
                    if_stack.pop()
                continue
            if False in if_stack or self._cond_skip(operands, last_rc=last_rc):
                out.append(f"IEF202I {job.jobname} {stepname} - STEP WAS NOT EXECUTED")
                step_rcs[stepname] = 0
                continue
            out.append(f"IEF236I ALLOC. FOR {job.jobname} {stepname}")
            upgm = pgm.upper()
            if upgm == "IEFBR14":
                expanded_jcl = "\n".join(lines)
                proc = runner.__self__ if hasattr(runner, "__self__") else None
                state = getattr(proc, "state", None)
                user = getattr(proc, "userid", job.owner)
                for m_dd in re.finditer(r"^//[A-Z0-9#$@]+\s+DD\s+DSN=([^,\s]+).*?DISP=\(([^)]*)\)", expanded_jcl, re.I | re.M):
                    dsn = m_dd.group(1).strip().strip("'")
                    disp = m_dd.group(2).upper()
                    if state is not None and "NEW" in disp:
                        try:
                            state.datasets.allocate(user, dsn, org="PS")
                            out.append(f"IEF285I {dsn.upper()} CATALOGED")
                        except Exception as exc:
                            rc = max(rc, 8); last_rc = 8
                            out.append(f"IEC141I {dsn.upper()} ALLOCATION FAILED - {exc}")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
                last_rc = max(last_rc, 0)
            elif upgm.startswith("IKJEFT"):
                out.append(f"IKJEFT01 TSO BATCH STARTED FOR STEP {stepname}")
                mode, host, port = self._extract_tshocker_mode(job)
                if mode == "L":
                    try:
                        from gibson.apps.tso import TsoCommandProcessor
                        _srv, actual_port = start_training_shell(
                            runner.__self__.state if hasattr(runner, '__self__') and hasattr(runner.__self__, 'state') else None or getattr(runner, '__self__', None).state,  # type: ignore[attr-defined]
                            job.owner,
                            lambda uid: TsoCommandProcessor(runner.__self__.state, uid).run,  # type: ignore[attr-defined]
                            port=port or 0,
                            ttl=300,
                            shell_id=job.jobid,
                        )
                        job.training_endpoint = f"{actual_port}"
                        out.append(f"IRX9000I TSHOCKER LISTENER SIMULATION STARTED ON PORT {actual_port}")
                        out.append("IRX9001I CONNECT WITH NETCAT OR A SIMPLE TCP CLIENT BEFORE TTL EXPIRY")
                        summary = f"TShOcker listener available on port {actual_port}"
                    except Exception as exc:
                        rc = max(rc, 8)
                        out.append(f"IRX9010E TSHOCKER LISTENER SIMULATION FAILED: {exc}")
                elif mode == "R":
                    out.append(f"IRX9002I TSHOCKER REVERSE CALLBACK SIMULATED TO {host}:{port}")
                    summary = f"TShOcker reverse callback simulated to {host}:{port}"
                systsin = blocks.get("SYSTSIN", "")
                if systsin.strip():
                    for cmd in systsin.splitlines():
                        if cmd.strip():
                            out.append(runner(cmd.strip()) if runner else f"READY\n{cmd}\nIKJ56500I COMMAND {cmd} NOT FOUND")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {rc:04d}")
                last_rc = rc
            elif upgm == "IDCAMS":
                out.append("IDCAMS  SYSTEM SERVICES")
                sysin = blocks.get("SYSIN", "")
                proc = runner.__self__ if hasattr(runner, "__self__") else None
                state = getattr(proc, "state", None)
                user = getattr(proc, "userid", job.owner)
                for rawcmd in sysin.splitlines():
                    cmd = rawcmd.strip()
                    if not cmd:
                        continue
                    ucmd = cmd.upper()
                    try:
                        if ucmd.startswith("DEFINE"):
                            m = re.search(r"NAME\s*\(([^)]+)\)", cmd, re.I)
                            dsn = (m.group(1).strip() if m else f"{job.owner}.IDCAMS.DEFINE")
                            if re.search(r"\bNUMBERED\b", cmd, re.I):
                                vtype = "RRDS"
                            elif re.search(r"\bNONINDEXED\b", cmd, re.I):
                                vtype = "ESDS"
                            elif re.search(r"\bINDEXED\b", cmd, re.I) or re.search(r"\bKEYS\b", cmd, re.I):
                                vtype = "KSDS"
                            else:
                                vtype = "ESDS"
                            keys = re.search(r"KEYS\s*\(([^)]+)\)", cmd, re.I)
                            if state is not None:
                                state.datasets.allocate(user, dsn, org="PS")
                                try:
                                    p = state.datasets.ds_path(user, dsn)
                                    state.datasets._write_meta(p, org="VS", recfm="VB", lrecl=80,
                                                               VSAMTYPE=vtype)
                                except Exception:
                                    pass
                            out.append(f"IDC0508I DATA SET {dsn.upper()} DEFINED")
                            keytxt = f" KEYS({keys.group(1).strip()})" if keys else ""
                            out.append(f"IDC0181I VSAM {vtype} CLUSTER DEFINED{keytxt}")
                        elif ucmd.startswith("DELETE"):
                            m = re.search(r"DELETE\s+('?[^'\s]+'?|\S+)", cmd, re.I)
                            dsn = (m.group(1).strip("'") if m else "")
                            if state is not None and dsn:
                                out.append(state.datasets.delete(user, dsn))
                            else:
                                out.append(f"IDC0550I ENTRY {dsn.upper()} SUCCESSFULLY DELETED")
                        elif ucmd.startswith("REPRO"):
                            data = self._idcams_source(cmd, lines, blocks, state, user)
                            tdsn = self._idcams_target(cmd, lines)
                            if tdsn and state is not None:
                                self._store_records(state, user, tdsn, data)
                            n = len(data.splitlines()) if data else 0
                            out.append(f"IDC0005I NUMBER OF RECORDS PROCESSED WAS {n}")
                            out.append("IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0")
                        elif ucmd.startswith("PRINT"):
                            data = self._idcams_source(cmd, lines, blocks, state, user)
                            out.append("IDCAMS  PRINT")
                            for i, row in enumerate(data.splitlines()[:50], 1):
                                out.append(f"  RECORD {i:08d} - {row}")
                            out.append(f"IDC0005I NUMBER OF RECORDS PROCESSED WAS {len(data.splitlines())}")
                        elif ucmd.startswith("LISTCAT"):
                            out.append("IDCAMS LISTCAT ENTRIES")
                            if state is not None:
                                for info in state.datasets.listcat(user, None)[:20]:
                                    kind = "CLUSTER" if info.org == "VS" else info.org
                                    out.append(f"  {kind:<8} {info.name:<44} {info.volume}")
                        else:
                            out.append(f"IDC0001I FUNCTION COMPLETED, HIGHEST CONDITION CODE WAS 0 - {cmd}")
                    except Exception as exc:
                        rc = max(rc, 8); last_rc = 8
                        out.append(f"IDC3009I IDCAMS COMMAND FAILED - {cmd} - {exc}")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            elif upgm == "IEBGENER":
                out.append("IEBGENER DATA SET COPY UTILITY SIMULATION")
                expanded_jcl = "\n".join(lines)
                proc = runner.__self__ if hasattr(runner, "__self__") else None
                state = getattr(proc, "state", None)
                user = getattr(proc, "userid", job.owner)
                data = blocks.get("SYSUT1", "")
                m_in = re.search(r"^//SYSUT1\s+DD\s+DSN=([^,\s]+)", expanded_jcl, re.I | re.M)
                if m_in and state is not None and not data:
                    try:
                        data = state.datasets.read(user, m_in.group(1))
                    except Exception as exc:
                        rc = max(rc, 8); last_rc = 8
                        out.append(f"IEC141I SYSUT1 OPEN FAILED - {exc}")
                count = max(1, len(data.splitlines())) if data else 0
                m_out = re.search(r"^//SYSUT2\s+DD\s+DSN=([^,\s]+)", expanded_jcl, re.I | re.M)
                if m_out and state is not None and last_rc < 8:
                    try:
                        state.datasets.allocate(user, m_out.group(1), org="PS")
                        state.datasets.write(user, m_out.group(1), data)
                    except Exception as exc:
                        rc = max(rc, 8); last_rc = 8
                        out.append(f"IEC141I SYSUT2 OPEN FAILED - {exc}")
                out.append(f"IEB144I THERE ARE {count:08d} RECORDS IN THE OUTPUT DATA SET")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            elif upgm in {"SORT", "ICEMAN"}:
                proc = runner.__self__ if hasattr(runner, "__self__") else None
                state = getattr(proc, "state", None)
                user = getattr(proc, "userid", job.owner)
                sysin = blocks.get("SYSIN", "")
                sortin = self._read_dd(lines, blocks, "SORTIN", state, user)
                records = sortin.splitlines() if sortin else []
                n_in = len(records)
                out.append("ICE143I 0 BLOCKSET SORT TECHNIQUE SELECTED")
                out.append("ICE000I 0 - CONTROL STATEMENTS PROCESSED")
                sorted_recs = self._dfsort(records, sysin, out)
                outdsn = self._dd_dsn(lines, "SORTOUT")
                if outdsn and state is not None:
                    try:
                        self._store_records(state, user, outdsn, "\n".join(sorted_recs) + ("\n" if sorted_recs else ""))
                    except Exception as exc:
                        rc = max(rc, 8); last_rc = 8
                        out.append(f"ICE083A 0 SORTOUT OPEN FAILED - {exc}")
                out.append(f"ICE054I 0 RECORDS - IN: {n_in}, OUT: {len(sorted_recs)}")
                out.append("ICE052I 0 END OF DFSORT")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            elif upgm == "BPXBATCH":
                parms = blocks.get("STDPARM", "") or blocks.get("STDIN", "")
                out.append("BPXBATCH UNIX COMMAND PROCESSOR STARTED")
                if "ID" in parms.upper():
                    out.append(f"uid=190000585({job.owner}) gid=1100000209(TEST)")
                else:
                    out.append("BPXBATCH completed RC=0000")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE 0000")
                last_rc = 0
            elif upgm in {"DSNTEP2", "DSNTIAD"} or "RUN PROGRAM(DSNTEP2" in operands.upper():
                sql = blocks.get("SYSIN", "") or blocks.get("SYSTSIN", "")
                out.append("DSNTEP2 SQL PROCESSOR STARTED")
                sql_out = sql_runner(sql) if sql_runner else "DSNE610I NUMBER OF ROWS DISPLAYED IS 0"
                out.append(sql_out)
                extra_spool.append(SpoolFile("SYSOUT", sql_out))
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE 0000")
                summary = "SQL executed through DSNTEP2 simulation"
                last_rc = 0
            elif upgm in {"IGYCRCTL", "COBOL"}:
                src = blocks.get("SYSIN", "")
                out.append("IGYCRCTL COBOL COMPILER STARTED")
                if cobol_runner:
                    crc, listing, displays = cobol_runner(src)
                    rc = max(rc, crc)
                    last_rc = crc
                    out.append(listing)
                    if displays:
                        extra_spool.append(SpoolFile("SYSPRINT", "\n".join(displays)))
                else:
                    out.append("MAXIMUM CONDITION CODE WAS 0")
                    last_rc = 0
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            elif upgm in {"ASMA90", "ASMAHL"}:
                src = blocks.get("SYSIN", "")
                out.append(f"{upgm} HIGH LEVEL ASSEMBLER STARTED")
                try:
                    from gibson.languages.hlasm import HlasmSimulator
                    hres = HlasmSimulator().assemble(src)
                    rc = max(rc, hres.rc); last_rc = hres.rc
                    out.append(hres.listing)
                    extra_spool.append(SpoolFile("SYSPRINT", hres.listing))
                    extra_spool.append(SpoolFile("SYSLIN", f"OBJECT MODULE SIMULATED FOR {job.jobname}.{stepname}\n"))
                except Exception as exc:
                    rc = max(rc, 8); last_rc = 8
                    out.append(f"ASMA999E ASSEMBLER SIMULATION FAILED: {exc}")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            elif upgm in {"IEWL", "HEWL", "IEWBLINK"}:
                out.append("IEWL LINKAGE EDITOR SIMULATION STARTED")
                expanded_jcl = "\n".join(lines)
                proc = runner.__self__ if hasattr(runner, "__self__") else None
                state = getattr(proc, "state", None)
                user = getattr(proc, "userid", job.owner)
                m_out = re.search(r"^//SYSLMOD\s+DD\s+DSN=([^,\s]+)", expanded_jcl, re.I | re.M)
                if m_out and state is not None:
                    try:
                        state.datasets.allocate(user, m_out.group(1), org="PS")
                        state.datasets.write(user, m_out.group(1), f"SIMULATED LOAD MODULE FOR {job.jobname}\n")
                        out.append(f"IEW2454I LOAD MODULE WRITTEN TO {m_out.group(1).upper()}")
                    except Exception as exc:
                        rc = max(rc, 8); last_rc = 8
                        out.append(f"IEW999E LINK EDIT FAILED: {exc}")
                else:
                    out.append("IEW2454I LOAD MODULE CREATED IN TEMPORARY SYSLMOD")
                out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE {last_rc:04d}")
            else:
                # Deliberate abend-demonstration programs for the ABENDS APPENDIX
                # lab: distinctive names that force a specific, repeatable abend
                # so students can read the resulting SYSUDUMP. Real shops keep
                # equivalent "force-abend" test modules. Only these exact names
                # abend; every other unrecognised PGM behaves as before.
                _ABEND_DEMOS = {
                    "ABEND0C7": "S0C7", "BADDEC": "S0C7", "PAYBADD": "S0C7", "ABENDDEC": "S0C7",
                    "ABEND806": "S806", "MISSMOD": "S806", "NOTFOUND": "S806",
                    "ABEND913": "S913", "RACFDENY": "S913",
                    "ABEND0C4": "S0C4", "BADADDR": "S0C4",
                    "ABEND322": "S322", "ABENDB37": "B37", "ABENDS37": "B37",
                }
                acode = _ABEND_DEMOS.get(upgm)
                if acode:
                    from gibson.core.abend import abend_block
                    if acode == "S913":
                        out.append(f"ICH408I USER({job.owner}) GROUP(SYS1) NAME({job.owner})")
                        out.append(f"  SYS1.RACFDS CL(DATASET)")
                        out.append("  INSUFFICIENT ACCESS AUTHORITY")
                        out.append("  ACCESS INTENT(UPDATE)  ACCESS ALLOWED(NONE)")
                    pname = {"S0C7": "PAYCALC", "S806": "MISSMOD", "S913": "IFG0194E",
                             "S0C4": "BNKUPD"}.get(acode, stepname[:8])
                    out.append(abend_block(acode, jobname=job.jobname, stepname=stepname,
                                           progname=pname))
                    out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS NOT EXECUTED - "
                               f"ABEND {acode}")
                    out.append(f"IEF472I {job.jobname} {stepname} - COMPLETION CODE - SYSTEM={acode[1:]}")
                    rc = max(rc, 12); last_rc = 12
                    summary = f"ABEND {acode} IN STEP {stepname} (ABENDS APPENDIX DEMO)"
                else:
                    ddnames = [m.group(1).upper() for m in (re.match(r"^//([A-Z0-9#$@]+)\s+DD\s+", ln, re.I) for ln in lines) if m]
                    out.append(f"IEF237I STEP {stepname} EXEC PGM={upgm or 'UNKNOWN'} PARM(SIMULATED)")
                    if ddnames:
                        out.append("IEF285I DD STATEMENTS PRESENT: " + ", ".join(sorted(set(ddnames))[:8]))
                    out.append(f"IEF142I {job.jobname} {stepname} - STEP WAS EXECUTED - COND CODE 0000")
                    last_rc = 0
            step_rcs[stepname] = last_rc
        if not out:
            out.append(summary)
        return "\n".join(out), rc, extra_spool, summary

    def list_jobs(self, owner: Optional[str] = None) -> List[Job]:
        jobs = list(self.jobs.values())
        if owner:
            jobs = [j for j in jobs if j.owner == owner.upper() or j.submitter == owner.upper()]
        return sorted(jobs, key=lambda j: j.submitted)

    def purge(self, jobid: str) -> bool:
        job = self.jobs.get(jobid.upper())
        if not job:
            return False
        job.status = JobStatus.PURGED
        return True

    def cancel(self, jobid: str) -> bool:
        job = self.jobs.get(jobid.upper())
        if not job:
            return False
        job.status = JobStatus.FAILED
        job.rc = max(job.rc, 8)
        job.spool.append(SpoolFile("JESYSMSG", f"$HASP395 {job.jobname} CANCELLED BY OPERATOR\n"))
        return True

    def hold(self, jobid: str) -> bool:
        job = self.jobs.get(jobid.upper())
        if not job:
            return False
        job.status = JobStatus.HELD
        return True

    def release(self, jobid: str) -> bool:
        job = self.jobs.get(jobid.upper())
        if not job:
            return False
        if job.status == JobStatus.HELD:
            job.status = JobStatus.OUTPUT
        return True

    def _jes2_display_from_parm(self, kind: str) -> str:
        """Render $D NODE / $D SOCKET / $D SPOOL from the live
        SYS1.PARMLIB(JES2PARM) deck so the console reflects the real member."""
        deck = ""
        try:
            deck = self.state.datasets.read("IBMUSER", "SYS1.PARMLIB(JES2PARM)")
        except Exception:
            deck = ""
        lines_in = deck.splitlines()

        def _val(stmt: str, key: str, default: str = "") -> str:
            for ln in lines_in:
                s = ln.strip()
                if s.upper().startswith(stmt.upper()) and key.upper() + "=" in s.upper():
                    try:
                        return s.upper().split(key.upper() + "=", 1)[1].split(",", 1)[0].split(")", 1)[0].strip()
                    except Exception:
                        return default
            return default

        if kind == "NODE":
            nodes = []
            for ln in lines_in:
                s = ln.strip()
                if s.upper().startswith("NODE(") and "NAME=" in s.upper():
                    num = s.split("(", 1)[1].split(")", 1)[0]
                    name = s.upper().split("NAME=", 1)[1].split(",", 1)[0].strip()
                    nodes.append((num, name))
            own = _val("NJEDEF", "OWNNODE", "1")
            out = ["$HASP826 NODE DISPLAY"]
            for num, name in nodes or [("1", "GIBSON")]:
                role = "OWNNODE" if num == own else "ADJACENT"
                out.append(f"$HASP826 NODE({num}) NAME={name},STATUS=ACTIVE,{role}")
            return "\n".join(out)

        if kind == "INIT":
            return self._jes2_init_display(lines_in)
        if kind == "PRT":
            return self._jes2_prt_display(lines_in)
        if kind == "SOCKET":
            socks = []
            for ln in lines_in:
                s = ln.strip()
                if s.upper().startswith("SOCKET("):
                    name = s.split("(", 1)[1].split(")", 1)[0]
                    ip = _val("SOCKET", "IPADDR", "0.0.0.0")
                    port = _val("SOCKET", "PORTNAME", "VMNET")
                    socks.append((name, ip, port))
            out = ["$HASP897 SOCKET DISPLAY"]
            for name, ip, port in socks or [("LOCAL", "192.168.0.97", "VMNET")]:
                out.append(f"$HASP897 SOCKET({name}) IPADDR={ip} PORTNAME={port} STATUS=ACTIVE")
            return "\n".join(out)

        # SPOOL
        vol = _val("SPOOLDEF", "VOLUME", "SBSPL")
        tg = _val("SPOOLDEF", "TGSPACE", "MAX=16288")
        return "\n".join([
            "$HASP646 0.0000 PERCENT SPOOL UTILIZATION",
            f"$HASP893 VOLUME({vol}) STATUS=ACTIVE,TGSPACE=({tg})",
        ])

    def _jes2_display_active(self) -> str:
        """$DA - active jobs/started tasks JES2 knows about."""
        out = ["$HASP890 ACTIVE JOBS DISPLAY"]
        active = [j for j in self.list_jobs()
                  if j.status in (JobStatus.EXECUTION, JobStatus.ACTIVE)]
        for j in active:
            out.append(f"$HASP890 {j.jobid} {j.jobname:<8} OWNER={j.owner} "
                       f"CLASS={j.job_class} STATUS=ACTIVE INIT=1")
        if not active:
            out.append("$HASP890 NO ACTIVE JES2 JOBS (started tasks run under MSTR)")
        return "\n".join(out)

    def _jes2_init_display(self, lines_in: list[str]) -> str:
        """$D INIT(S) - initiators from the live JES2PARM INIT(n)/INITDEF."""
        inits = []
        for ln in lines_in:
            s = ln.strip()
            if s.upper().startswith("INIT(") and "CLASS=" in s.upper():
                num = s.split("(", 1)[1].split(")", 1)[0]
                klass = s.upper().split("CLASS=", 1)[1].split(",", 1)[0].strip()
                name = (s.upper().split("NAME=", 1)[1].split(",", 1)[0].strip()
                        if "NAME=" in s.upper() else f"INIT{num}")
                inits.append((num, name, klass))
        out = ["$HASP892 INITIATOR DISPLAY"]
        for num, name, klass in inits or [("1", "INIT1", "ABS")]:
            out.append(f"$HASP892 INIT({num}) NAME={name},CLASS={klass},STATUS=INACTIVE")
        return "\n".join(out)

    def _jes2_prt_display(self, lines_in: list[str]) -> str:
        prts = []
        for ln in lines_in:
            s = ln.strip()
            if s.upper().startswith("PRT(") and ")" in s:
                num = s.split("(", 1)[1].split(")", 1)[0]
                klass = (s.upper().split("CLASS=", 1)[1].split(",", 1)[0].strip()
                         if "CLASS=" in s.upper() else "A")
                prts.append((num, klass))
        out = ["$HASP890 PRINTER DISPLAY"]
        for num, klass in prts or [("1", "A")]:
            out.append(f"$HASP890 PRT({num}) CLASS={klass},STATUS=DRAINED,ROUTECDE=LOCAL")
        return "\n".join(out)

    def jes2_command(self, cmd: str) -> str | None:
        u = cmd.strip().upper()
        if u in ("$D NODE", "$DNODE", "$D NODE(*)", "$D U,NODES"):
            return self._jes2_display_from_parm("NODE")
        if u in ("$D SOCKET", "$DSOCKET", "$D SOCKET(*)", "$D NETSRV", "$D NETSRV(*)"):
            return self._jes2_display_from_parm("SOCKET")
        if u in ("$D SPOOL", "$DSPOOL", "$HASP646"):
            return self._jes2_display_from_parm("SPOOL")
        if u in ("$DA", "$D A", "$DA,A", "$D A,A", "$DA,ALL"):
            return self._jes2_display_active()
        if u in ("$D INIT", "$DINIT", "$D INITS", "$DI", "$D I"):
            return self._jes2_display_from_parm("INIT")
        if u in ("$D PRT", "$DPRT", "$D PRT(*)", "$D U,PRT", "$D PRINTER"):
            return self._jes2_display_from_parm("PRT")
        if u in ("$P JES2", "$PJES2"):
            return "\n".join([
                "$HASP623 JES2 TERMINATION IS IN PROGRESS",
                "$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE",
                "(simulated - JES2 not actually stopped on the training range)",
            ])
        if u in ("$S JES2", "$SJES2"):
            return "$HASP492 JES2 INITIALIZATION COMPLETE"
        m_prt = re.match(r"\$(P|S|E)\s*PRT\(?(\d+)\)?", u)
        if m_prt:
            op, n = m_prt.group(1), m_prt.group(2)
            verb = {"P": "DRAINED", "S": "STARTED", "E": "RESTARTED"}[op]
            return f"$HASP160 PRT{n} INACTIVE - {verb}" if op == "P" else f"$HASP100 PRT{n} {verb}"
        m_t = re.match(r"\$T\s+(INIT|PRT|JOBCLASS|SPOOLDEF)\(?([A-Z0-9]*)\)?\s*,?(.*)", u)
        if m_t:
            res, sel, rest = m_t.group(1), m_t.group(2), m_t.group(3).strip()
            tag = f"{res}({sel})" if sel else res
            return f"$HASP000 OK - {tag} SET {rest}" if rest else f"$HASP000 OK - {tag} (no change specified)"
        if u in ("$D Q", "$DQ", "$D JOBQ", "$D JOBQ") :
            lines = ["$HASP890 JOB QUEUE DISPLAY", "JOBID     JOBNAME   OWNER    STATUS  RC"]
            for job in self.list_jobs():
                lines.append(f"{job.jobid:<9} {job.jobname:<8} {job.owner:<8} {job.status.value:<7} {job.rc:04d}")
            return "\n".join(lines)
        if u in ("$D JOB", "$DJOB"):
            return self.jes2_command("$D Q")
        m = re.match(r"\$(D|C|P|A|H)\s+JOB\(?([A-Z0-9]+)\)?", u) or re.match(r"(CANCEL|PURGE|HOLD|RELEASE)\s+([A-Z0-9]+)", u)
        if not m:
            return None
        op, jobid = m.group(1), m.group(2)
        op = {"CANCEL":"C", "PURGE":"P", "HOLD":"H", "RELEASE":"A"}.get(op, op)
        if op == "D":
            job = self.jobs.get(jobid)
            return f"$HASP890 {jobid} NOT FOUND" if not job else f"$HASP890 {job.jobid} {job.jobname} OWNER={job.owner} STATUS={job.status.value} RC={job.rc:04d}"
        if op == "C":
            return f"$HASP395 {jobid} CANCELLED" if self.cancel(jobid) else f"$HASP890 {jobid} NOT FOUND"
        if op == "P":
            return f"$HASP250 {jobid} PURGED" if self.purge(jobid) else f"$HASP890 {jobid} NOT FOUND"
        if op == "A":
            return f"$HASP250 {jobid} RELEASED" if self.release(jobid) else f"$HASP890 {jobid} NOT FOUND"
        if op == "H":
            return f"$HASP250 {jobid} HELD" if self.hold(jobid) else f"$HASP890 {jobid} NOT FOUND"
        return None
