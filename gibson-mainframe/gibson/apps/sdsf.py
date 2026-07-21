from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from gibson.core.jes import Job, JobStatus
from gibson.core.state import GibsonState
from gibson.core.healthcheck import get_healthchecker
from gibson.render import colors


@dataclass(frozen=True)
class SdsfMenuItem:
    command: str
    description: str
    group: str
    status: str = ""


@dataclass
class SdsfRow:
    cells: Dict[str, str]
    target: Optional[str] = None


@dataclass
class SdsfPanel:
    command: str
    title: str
    group: str
    columns: Sequence[str]
    rows: Sequence[SdsfRow]
    action_help: str = "ACTION=S-Select  ?-Show  P-Purge  C-Cancel  A-Release  /-Values"


class SdsfApp:
    """SDSF V2R5-style panel engine for Gibson.

    The goal is to reproduce the interaction model and visual grammar of SDSF:
    a main menu of panel commands, an NP action column, scrollable tabular
    panels, PREFIX/OWNER/DEST/SYSNAME filters, and JES-backed ST/I/O/H/DA
    panels.  Panels that do not have deep Gibson state yet render realistic
    display-only rows so the V2R5 command inventory is present.
    """

    MENU_ITEMS: Tuple[SdsfMenuItem, ...] = (
        # Jobs
        SdsfMenuItem("AD", "Active users, including started tasks", "Jobs"),
        SdsfMenuItem("AS", "Address spaces", "Jobs"),
        SdsfMenuItem("DA", "Display active users", "Jobs"),
        SdsfMenuItem("I", "Input queue", "Jobs"),
        SdsfMenuItem("ST", "Status of jobs", "Jobs"),
        # Output
        SdsfMenuItem("O", "Output queue", "Output"),
        SdsfMenuItem("H", "Held output queue", "Output"),
        # JES
        SdsfMenuItem("INIT", "Initiators", "JES"),
        SdsfMenuItem("JC", "Job classes", "JES"),
        SdsfMenuItem("JES", "JES2 system information", "JES"),
        SdsfMenuItem("JG", "Job groups", "JES"),
        SdsfMenuItem("J0", "Job zero", "JES"),
        SdsfMenuItem("JRI", "JES resources - initiators", "JES"),
        SdsfMenuItem("JRJ", "JES resources - jobs", "JES"),
        SdsfMenuItem("MAS", "Multi-access spool members", "JES"),
        SdsfMenuItem("PR", "Printers", "JES"),
        SdsfMenuItem("PROC", "Proclib concatenation", "JES"),
        SdsfMenuItem("PUN", "Punches", "JES"),
        SdsfMenuItem("RDR", "Readers", "JES"),
        SdsfMenuItem("RM", "Resource monitors", "JES"),
        SdsfMenuItem("RMA", "Resource monitor alerts", "JES"),
        SdsfMenuItem("SO", "Spool offload", "JES"),
        SdsfMenuItem("SP", "Spool volumes", "JES"),
        # Log
        SdsfMenuItem("LOG", "System log", "Log"),
        SdsfMenuItem("OPERLOG", "Operations log", "Log"),
        SdsfMenuItem("SMF80", "RACF security events (SMF type 80)", "Log"),
        SdsfMenuItem("SMF30", "Job/session activity events (SMF type 30)", "Log"),
        SdsfMenuItem("SMF101", "Db2 activity events (SMF type 101)", "Log"),
        SdsfMenuItem("SMF110", "CICS activity events (SMF type 110)", "Log"),
        SdsfMenuItem("SMF119", "TCP/IP activity events (SMF type 119)", "Log"),
        SdsfMenuItem("SMF7", "SMF data-lost records (type 7)", "Log"),
        SdsfMenuItem("SR", "System requests", "Log"),
        SdsfMenuItem("ULOG", "User session log", "Log"),
        # Devices
        SdsfMenuItem("DEV", "Devices", "Devices"),
        SdsfMenuItem("SMSG", "SMS storage groups", "Devices"),
        SdsfMenuItem("SMSV", "SMS volumes", "Devices"),
        # Memory
        SdsfMenuItem("CS", "Common storage", "Memory"),
        SdsfMenuItem("CSR", "Common storage remaining", "Memory"),
        SdsfMenuItem("MEM", "Memory objects", "Memory"),
        SdsfMenuItem("VMAP", "Virtual storage map", "Memory"),
        # Network
        SdsfMenuItem("LINE", "JES lines", "Network"),
        SdsfMenuItem("NA", "Network activity", "Network"),
        SdsfMenuItem("NC", "Network connections", "Network"),
        SdsfMenuItem("NODE", "JES nodes", "Network"),
        SdsfMenuItem("NS", "Network servers", "Network"),
        # OMVS
        SdsfMenuItem("BPXO", "OMVS BPXOINIT address space", "OMVS"),
        SdsfMenuItem("FS", "File systems", "OMVS"),
        SdsfMenuItem("PS", "Processes", "OMVS"),
        # Sysplex
        SdsfMenuItem("CFC", "Coupling facility connections", "Sysplex"),
        SdsfMenuItem("CFD", "Coupling facility details", "Sysplex"),
        SdsfMenuItem("CFS", "Coupling facility structures", "Sysplex"),
        SdsfMenuItem("EMCS", "Extended MCS consoles", "Sysplex"),
        SdsfMenuItem("ENQD", "ENQ contention detail", "Sysplex"),
        SdsfMenuItem("XCFM", "XCF members", "Sysplex"),
        # System
        SdsfMenuItem("APF", "APF libraries", "System"),
        SdsfMenuItem("CK", "Health checks", "System"),
        SdsfMenuItem("DYNX", "Dynamic exits", "System"),
        SdsfMenuItem("ENQ", "Enqueues", "System"),
        SdsfMenuItem("ENQC", "Enqueue contention", "System"),
        SdsfMenuItem("GT", "Generic trackers", "System"),
        SdsfMenuItem("LLS", "Library lookaside", "System"),
        SdsfMenuItem("LNK", "Link list", "System"),
        SdsfMenuItem("LPA", "Link pack area", "System"),
        SdsfMenuItem("LPD", "LPAR details", "System"),
        SdsfMenuItem("PAG", "Page data sets", "System"),
        SdsfMenuItem("PARM", "Parmlib members", "System"),
        SdsfMenuItem("PC", "Program call table", "System"),
        SdsfMenuItem("SSI", "Subsystem interface", "System"),
        SdsfMenuItem("SVC", "SVC table", "System"),
        SdsfMenuItem("SYM", "System symbols", "System"),
        SdsfMenuItem("SYS", "System information", "System"),
        SdsfMenuItem("SYSP", "System properties", "System"),
        # WLM
        SdsfMenuItem("ENC", "Enclaves", "WLM"),
        SdsfMenuItem("REPC", "Report classes", "WLM"),
        SdsfMenuItem("RES", "Resources", "WLM"),
        SdsfMenuItem("RGRP", "Resource groups", "WLM"),
        SdsfMenuItem("SE", "Scheduling environments", "WLM"),
        SdsfMenuItem("SRVC", "Service classes", "WLM"),
        SdsfMenuItem("WKLD", "Workloads", "WLM"),
        SdsfMenuItem("WLM", "Workload manager policy", "WLM"),
        SdsfMenuItem("VER", "SDSF version information", "System"),
    )

    PAGE_SIZE = 16
    PANEL_PAGE_SIZE = 15

    def __init__(self, state: GibsonState, userid: str):
        self.state = state
        self.userid = userid.upper()
        self.prefix = "*"
        self.dest = "(ALL)"
        self.owner = "*"
        self.sysname = ""
        self.filter_text = ""
        self.sort_column = ""
        self.message = ""

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _header(self, title: str, line_range: str = "") -> List[str]:
        now = datetime.now().strftime("%H:%M:%S")
        range_text = line_range or "LINE 1-1 (1)"
        return [
            colors.CLEAR + colors.BLUE + "Display  Filter  View  Print  Options  Search  Help" + colors.RESET,
            colors.HLINE,
            f"{colors.WHITE}{title:<22}{colors.TURQUOISE} GIBPLEX  MVSC {now:<8}{colors.WHITE}{range_text:>20}{colors.RESET}",
            f"{colors.BLUE}COMMAND INPUT ===>{colors.RED} {colors.BLUE}{'':<34}SCROLL ===>{colors.WHITE} CSR{colors.RESET}",
            f"{colors.TURQUOISE}PREFIX={self.prefix:<8} DEST={self.dest:<8} OWNER={self.owner:<8} SYSNAME={self.sysname}{colors.RESET}",
        ]

    def _footer(self, message: str = "") -> List[str]:
        msg = message or self.message
        return [
            colors.BLUE + "PF1=Help PF3=End PF7=Up PF8=Down  WHO  SET ACTION  SORT  FILTER" + colors.RESET,
            (colors.YELLOW + msg + colors.RESET) if msg else "",
        ]

    def _format_row(self, columns: Sequence[str], row: SdsfRow, index: int) -> str:
        widths = self._widths(columns)
        parts: List[str] = []
        for col in columns:
            val = row.cells.get(col, "")
            if col == "NP":
                val = ""
            parts.append(f"{val:<{widths[col]}}"[: widths[col]])
        # Prefix with a synthetic numeric reference in NP visual area without
        # replacing the authentic NP action field.
        return f"{colors.WHITE}{index:>2}{colors.RESET} " + " ".join(parts)

    def _widths(self, columns: Sequence[str]) -> Dict[str, int]:
        default = {
            "NP": 3, "NAME": 8, "Description": 30, "Group": 10, "Status": 10,
            "JOBNAME": 8, "JobID": 8, "Owner": 8, "Prty": 4, "Queue": 8,
            "C": 1, "Pos": 4, "SAff": 5, "ASys": 6, "RC": 6, "Lines": 6,
            "DDNAME": 8, "StepName": 8, "ProcStep": 8, "ByteCount": 9,
            "SYSNAME": 8, "MEMBER": 8, "TYPE": 8, "STATE": 10, "VALUE": 20,
            "USERID": 8, "GROUP": 8, "EVENT": 16, "RESULT": 8, "TIME": 8, "DATE": 10, "SYSTEM": 6, "JOBNAME": 8, "RESOURCE": 18, "PROFILE": 14,
            "APPLID": 7, "TRANSID": 7, "TERMID": 7, "REGION": 10, "CORRID": 13,
            "CLASS": 5, "ACTIVE": 6, "HELD": 6, "DESC": 34, "VOLUME": 8,
            "UNIT": 8, "USE": 8, "PATH": 32, "PID": 7, "PPID": 7, "USER": 8,
            "CPU": 5, "COMMAND": 18, "ADDRSPACE": 8, "SERVICE": 12,
            "DSNAME": 34, "VolSer": 6, "SMS": 4, "Members": 7, "Status": 8,
            "Source": 12, "APFAttr": 8,
        }
        return {c: default.get(c, max(8, min(18, len(c) + 2))) for c in columns}

    def render_main(self, page: int = 0, message: str = "") -> str:
        items = list(self.MENU_ITEMS)
        total = len(items)
        page = max(0, min(page, max(0, (total - 1) // self.PAGE_SIZE)))
        start = page * self.PAGE_SIZE
        end = min(total, start + self.PAGE_SIZE)
        rows = [SdsfRow({"NP": "", "NAME": i.command, "Description": i.description, "Group": i.group, "Status": i.status}) for i in items[start:end]]
        out = self._header("SDSF MENU V2R5M0", f"LINE {start+1}-{end} ({total})")
        out.append(colors.TURQUOISE + "ACTION=S-Select" + colors.RESET)
        columns = ["NP", "NAME", "Description", "Group", "Status"]
        out.append(self._column_header(columns))
        for idx, row in enumerate(rows, start + 1):
            out.append(self._format_row(columns, row, idx))
        out.extend(self._footer(message))
        return "\n".join([x for x in out if x != ""])

    def _column_header(self, columns: Sequence[str]) -> str:
        widths = self._widths(columns)
        return colors.TURQUOISE + "   " + " ".join(f"{c:<{widths[c]}}"[: widths[c]] for c in columns) + colors.RESET

    def render_panel(self, command: str, page: int = 0, message: str = "") -> str:
        panel = self.build_panel(command)
        rows = self._apply_filters(panel.rows, panel.columns)
        if self.sort_column and self.sort_column in panel.columns:
            rows = sorted(rows, key=lambda r: r.cells.get(self.sort_column, ""), reverse=bool(getattr(self, "sort_desc", False)))
        total = len(rows)
        page = max(0, min(page, max(0, (total - 1) // self.PANEL_PAGE_SIZE))) if total else 0
        start = page * self.PANEL_PAGE_SIZE
        end = min(total, start + self.PANEL_PAGE_SIZE)
        out = self._header(f"SDSF {panel.title}", f"LINE {start+1 if total else 0}-{end} ({total})")
        out.append(colors.TURQUOISE + panel.action_help + colors.RESET)
        out.append(self._column_header(panel.columns))
        if rows[start:end]:
            for idx, row in enumerate(rows[start:end], start + 1):
                out.append(self._format_row(panel.columns, row, idx))
        else:
            out.append("   NO ROWS TO DISPLAY")
        out.extend(self._footer(message))
        return "\n".join([x for x in out if x != ""])

    def _apply_filters(self, rows: Sequence[SdsfRow], columns: Sequence[str]) -> List[SdsfRow]:
        result = list(rows)
        if self.owner and self.owner != "*" and "Owner" in columns:
            result = [r for r in result if r.cells.get("Owner", "").upper() == self.owner.upper()]
        if self.prefix and self.prefix != "*" and "JOBNAME" in columns:
            p = self.prefix.rstrip("*").upper()
            result = [r for r in result if r.cells.get("JOBNAME", "").upper().startswith(p)]
        if self.sysname and "ASys" in columns:
            result = [r for r in result if r.cells.get("ASys", "").upper() == self.sysname.upper()]
        if self.filter_text:
            f = self.filter_text.upper()
            result = [r for r in result if any(f in v.upper() for v in r.cells.values())]
        return result

    # ------------------------------------------------------------------
    # Panel sources
    # ------------------------------------------------------------------
    def build_panel(self, command: str) -> SdsfPanel:
        c = command.upper().strip()
        if c in ("ST", "DA", "I", "O", "H", "AD", "AS"):
            return self._jobs_panel(c)
        if c in {"LOG", "SYSLOG"}:
            return self._log_panel()
        if c == "OPERLOG":
            return self._operlog_panel()
        if c == "SMF80":
            return self._smf80_panel()
        if c in {"SMF30", "SMF101", "SMF110", "SMF119"}:
            return self._generic_smf_panel(c[3:])
        if c == "SMF7":
            return self._smf7_panel()
        if c == "ULOG":
            return self._ulog_panel()
        if c == "SR":
            return self._requests_panel()
        if c in ("JC", "INIT", "MAS", "PR", "PUN", "RDR", "PROC", "JES", "JG", "J0", "JRI", "JRJ", "RM", "RMA", "SO", "SP"):
            return self._jes_resource_panel(c)
        if c in ("PS", "FS", "BPXO"):
            return self._omvs_panel(c)
        if c in ("SYS", "SYM", "APF", "CK", "DYNX", "ENQ", "ENQC", "GT", "LLS", "LNK", "LPA", "LPD", "PAG", "PARM", "PC", "SSI", "SVC", "SYSP"):
            return self._system_panel(c)
        if c == "VER":
            return self._version_panel()
        if c in ("ENC", "REPC", "RES", "RGRP", "SE", "SRVC", "WKLD", "WLM"):
            return self._wlm_panel(c)
        if c in ("DEV", "SMSG", "SMSV"):
            return self._devices_panel(c)
        if c in ("LINE", "NA", "NC", "NODE", "NS"):
            return self._network_panel(c)
        if c in ("CFC", "CFD", "CFS", "EMCS", "ENQD", "XCFM"):
            return self._sysplex_panel(c)
        return SdsfPanel(c, f"{c} DISPLAY", "Other", ["NP", "NAME", "Description", "Status"], [SdsfRow({"NAME": c, "Description": "Panel available in Gibson display-only mode", "Status": "ACTIVE"})])

    def _authorised_jobs(self) -> List[Job]:
        user = self.state.racf.get(self.userid)
        if user and user.special:
            return self.state.jes.list_jobs()
        return self.state.jes.list_jobs(owner=self.userid)

    def _jobs_panel(self, command: str) -> SdsfPanel:
        jobs = [j for j in self._authorised_jobs() if j.status != JobStatus.PURGED]
        if command == "I":
            jobs = [j for j in jobs if j.status == JobStatus.INPUT]
            title = "INPUT QUEUE"
        elif command == "O":
            jobs = [j for j in jobs if j.status in (JobStatus.OUTPUT, JobStatus.FAILED)]
            title = "OUTPUT QUEUE"
        elif command == "H":
            jobs = [j for j in jobs if j.status == JobStatus.HELD]
            title = "HELD OUTPUT QUEUE"
        elif command in ("DA", "AD", "AS"):
            title = "DISPLAY ACTIVE USERS"
        else:
            title = "STATUS OF JOBS"
        rows = [self._job_row(j) for j in jobs]
        # DA should include current TSO users as rows as well; use separate
        # ADDRSPACE-style rows while preserving SDSF job-like columns.
        if command in ("DA", "AD", "AS"):
            for sess in self.state.sessions.sessions.values():
                if sess.connected:
                    rows.append(SdsfRow({
                        "NP": "", "JOBNAME": sess.userid[:8], "JobID": "TSU00001", "Owner": sess.userid,
                        "Prty": "15", "Queue": "EXECUTION", "C": "A", "Pos": "", "SAff": "", "ASys": "MVSC",
                        "Status": "ACTIVE", "RC": "", "Lines": "0",
                    }, target="TSU00001"))
        return SdsfPanel(command, title, "Jobs", ["NP", "JOBNAME", "JobID", "Owner", "Prty", "Queue", "C", "Pos", "SAff", "ASys", "Status", "RC", "Lines"], rows)

    def _job_row(self, job: Job) -> SdsfRow:
        return SdsfRow({
            "NP": "", "JOBNAME": job.jobname[:8], "JobID": job.jobid, "Owner": job.owner[:8],
            "Prty": "1", "Queue": job.status.value, "C": "A", "Pos": "1", "SAff": "", "ASys": "MVSC",
            "Status": job.status.value, "RC": f"RC={job.rc:04d}" if job.ended else "", "Lines": str(job.records),
        }, target=job.jobid)

    def _log_panel(self) -> SdsfPanel:
        lines: List[SdsfRow] = []
        now = datetime.now().strftime("%H.%M.%S")
        base = [
            f"{now} MVSC $HASP000 GIBSON JES2 SUBSYSTEM ACTIVE",
            f"{now} MVSC IEE042I SYSTEM LOG DATA SET ACTIVE",
        ]
        for job in self.state.jes.list_jobs()[-10:]:
            base.append(f"{now} MVSC $HASP395 {job.jobname} ENDED - RC={job.rc:04d}")
        for i, text in enumerate(base, 1):
            lines.append(SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "WTO", "VALUE": text}, target=str(i)))
        return SdsfPanel("LOG", "SYSTEM LOG", "Log", ["NP", "SYSNAME", "TYPE", "VALUE"], lines, "ACTION=S-Browse  FIND string")

    def _smf7_panel(self) -> SdsfPanel:
        events = [e for e in self.state.audit.events if e.component == "SMF7"][-60:] if self.state.audit is not None else []
        rows = []
        for idx, ev in enumerate(events, 1):
            x = ev.extra or {}
            rows.append(SdsfRow({"NP":"", "USERID": ev.userid, "EVENT": x.get("EVENT", "SMF DATA LOST"), "RESULT": x.get("SEVERITY", "WARNING"), "TIME": x.get("TIME", ev.ts.strftime("%H:%M:%S")), "DATE": x.get("DATE", ev.ts.strftime("%Y-%m-%d")), "RESOURCE": x.get("SERVICE", "SMF"), "PROFILE": x.get("REASON", "DATA LOST")}, target=f"SMF7-{idx}"))
        return SdsfPanel("SMF7", "SMF TYPE 7 DATA LOST EVENTS", "Log", ["NP", "USERID", "EVENT", "RESULT", "TIME", "DATE", "RESOURCE", "PROFILE"], rows, action_help="ACTION=S-Detail")

    def _ulog_panel(self) -> SdsfPanel:
        rows = [SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "USER", "VALUE": f"{self.userid} ENTERED SDSF"}, target="ULOG")]
        return SdsfPanel("ULOG", "USER SESSION LOG", "Log", ["NP", "SYSNAME", "TYPE", "VALUE"], rows, "ACTION=S-Browse")

    def _operlog_panel(self) -> SdsfPanel:
        rows: list[SdsfRow] = []
        try:
            lines = self.state.console_log.operlog_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
        except Exception:
            lines = []
        for idx, text in enumerate(lines, 1):
            rows.append(SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "OPERLOG", "VALUE": text}, target=f"OPER{idx}"))
        if not rows:
            rows = [SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "OPERLOG", "VALUE": "OPERLOG IS EMPTY"})]
        return SdsfPanel("OPERLOG", "OPERATIONS LOG", "Log", ["NP", "SYSNAME", "TYPE", "VALUE"], rows, "ACTION=S-Browse  FIND string")


    def _generic_smf_panel(self, record_type: str) -> SdsfPanel:
        comp = f"SMF{record_type}"
        events = [e for e in self.state.audit.events if e.component == comp][-60:] if self.state.audit is not None else []
        rows: list[SdsfRow] = []
        for idx, ev in enumerate(events, 1):
            x = ev.extra or {}
            rows.append(SdsfRow({
                "NP": "",
                "USERID": ev.userid,
                "EVENT": x.get("EVENT", ev.command.replace(f"SMF TYPE {record_type} ", "")),
                "RESULT": x.get("RESULT", "SUCCESS"),
                "TIME": x.get("TIME", ev.ts.strftime("%H:%M:%S")),
                "DATE": x.get("DATE", ev.ts.strftime("%Y-%m-%d")),
                "RESOURCE": x.get("RESOURCE", x.get("TABLE", x.get("TRANSACTION", x.get("SERVICE", "")))),
                "PROFILE": x.get("PROFILE", x.get("DETAIL", ev.result))[:40],
            }, target=f"SMF{record_type}-{idx}"))
        if not rows:
            rows = [SdsfRow({"NP":"", "USERID":"", "EVENT":"", "RESULT":"", "TIME":"", "DATE":"", "RESOURCE":"", "PROFILE":f"NO SMF TYPE {record_type} RECORDS AVAILABLE"})]
        return SdsfPanel(f"SMF{record_type}", f"SMF TYPE {record_type} EVENT LOG", "Log", ["NP", "USERID", "EVENT", "RESULT", "TIME", "DATE", "RESOURCE", "PROFILE"], rows, action_help="ACTION=S-Browse  FIND string")

    def _smf80_panel(self) -> SdsfPanel:
        rows: list[SdsfRow] = []
        events = [e for e in self.state.audit.events if e.component == "SMF80" and not ("SYS1.UADS" in (getattr(e, "command", "") + " " + getattr(e, "result", "") + " " + str(getattr(e, "extra", {}))))][-60:]
        for idx, evt in enumerate(events, 1):
            row = self.state.audit.smf80_row(evt, system=getattr(self.state.network, "hostname", "MVSC").upper())
            rows.append(SdsfRow({
                "NP": "",
                "USERID": row["USERID"],
                "GROUP": row["GROUP"],
                "EVENT": row["EVENT"],
                "RESULT": row["RESULT"],
                "TIME": row["TIME"],
                "DATE": row["DATE"],
                "SYSTEM": row["SYSTEM"],
                "JOBNAME": row["JOBNAME"],
                "CLASS": row["CLASS"],
                "RESOURCE": row["RESOURCE"],
                "PROFILE": row["PROFILE"],
                "APPLID": row.get("APPLID", ""),
                "TRANSID": row.get("TRANSID", ""),
                "TERMID": row.get("TERMID", ""),
                "CORRID": row.get("CORRID", ""),
            }, target=f"SMF80-{idx}"))
        if not rows:
            rows = [SdsfRow({
                "NP": "",
                "USERID": "",
                "GROUP": "",
                "EVENT": "",
                "RESULT": "",
                "TIME": "",
                "DATE": "",
                "SYSTEM": "MVSC",
                "JOBNAME": "",
                "CLASS": "",
                "RESOURCE": "",
                "PROFILE": "NO SMF TYPE 80 SECURITY RECORDS AVAILABLE",
                "APPLID": "",
                "TRANSID": "",
                "TERMID": "",
                "CORRID": "",
            })]
        return SdsfPanel(
            "SMF80",
            "SMF TYPE 80 SECURITY LOG",
            "Log",
            ["NP", "USERID", "GROUP", "EVENT", "RESULT", "TIME", "DATE", "SYSTEM", "JOBNAME", "CLASS", "RESOURCE", "PROFILE", "APPLID", "TRANSID", "TERMID", "CORRID"],
            rows,
            "ACTION=S-Browse  FIND string  SORT USERID|EVENT|TIME",
        )

    def _requests_panel(self) -> SdsfPanel:
        rows = [SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "WTOR", "VALUE": "NO OUTSTANDING SYSTEM REQUESTS"})]
        return SdsfPanel("SR", "SYSTEM REQUESTS", "Log", ["NP", "SYSNAME", "TYPE", "VALUE"], rows)

    def _jes_resource_panel(self, cmd: str) -> SdsfPanel:
        if cmd == "JC":
            rows = [SdsfRow({"NP": "", "CLASS": c, "ACTIVE": "YES", "HELD": "NO", "DESC": "GIBSON JES2 JOB CLASS"}) for c in "ABCDEFGH"]
            return SdsfPanel(cmd, "JOB CLASSES", "JES", ["NP", "CLASS", "ACTIVE", "HELD", "DESC"], rows)
        if cmd == "INIT":
            rows = [SdsfRow({"NP": "", "NAME": f"INIT{i}", "CLASS": "A", "STATE": "ACTIVE", "JOBNAME": "", "ASys": "MVSC"}) for i in range(1, 5)]
            return SdsfPanel(cmd, "INITIATORS", "JES", ["NP", "NAME", "CLASS", "STATE", "JOBNAME", "ASys"], rows)
        if cmd == "MAS":
            rows = [SdsfRow({"NP": "", "MEMBER": "MVSC", "SYSNAME": "MVSC", "STATE": "ACTIVE", "TYPE": "JES2"})]
            return SdsfPanel(cmd, "MAS MEMBERS", "JES", ["NP", "MEMBER", "SYSNAME", "STATE", "TYPE"], rows)
        if cmd in ("PR", "PUN", "RDR"):
            rows = [SdsfRow({"NP": "", "NAME": f"{cmd}{i}", "CLASS": "A", "STATE": "DRAINED" if i > 1 else "STARTED", "ASys": "MVSC"}) for i in range(1, 4)]
            return SdsfPanel(cmd, f"{cmd} DEVICES", "JES", ["NP", "NAME", "CLASS", "STATE", "ASys"], rows)
        if cmd == "PROC":
            rows = [SdsfRow({"NP": "", "NAME": "SYS1.PROCLIB", "VOLUME": "MVSRES", "UNIT": "3390", "STATE": "ACTIVE"})]
            return SdsfPanel(cmd, "PROCLIB", "JES", ["NP", "NAME", "VOLUME", "UNIT", "STATE"], rows)
        if cmd == "SP":
            rows = [SdsfRow({"NP": "", "VOLUME": "SPOOL1", "UNIT": "3390", "USE": "12%", "STATE": "ACTIVE"})]
            return SdsfPanel(cmd, "SPOOL VOLUMES", "JES", ["NP", "VOLUME", "UNIT", "USE", "STATE"], rows)
        rows = [SdsfRow({"NP": "", "NAME": cmd, "Description": f"{cmd} information", "Status": "ACTIVE"})]
        return SdsfPanel(cmd, f"{cmd} DISPLAY", "JES", ["NP", "NAME", "Description", "Status"], rows)

    def _omvs_panel(self, cmd: str) -> SdsfPanel:
        if cmd == "PS":
            rows = [
                SdsfRow({"NP": "", "PID": "1", "PPID": "0", "USER": "OMVSKERN", "CPU": "0.1", "COMMAND": "BPXOINIT"}),
                SdsfRow({"NP": "", "PID": "1042", "PPID": "1", "USER": self.userid, "CPU": "0.0", "COMMAND": "sh"}),
            ]
            return SdsfPanel(cmd, "OMVS PROCESSES", "OMVS", ["NP", "PID", "PPID", "USER", "CPU", "COMMAND"], rows)
        if cmd == "FS":
            rows = [SdsfRow({"NP": "", "NAME": "ZFSROOT", "PATH": "/", "USE": "24%", "STATE": "MOUNTED"}), SdsfRow({"NP": "", "NAME": "USERZFS", "PATH": "/u", "USE": "11%", "STATE": "MOUNTED"})]
            return SdsfPanel(cmd, "FILE SYSTEMS", "OMVS", ["NP", "NAME", "PATH", "USE", "STATE"], rows)
        return SdsfPanel(cmd, "BPXO ADDRESS SPACE", "OMVS", ["NP", "ADDRSPACE", "STATE", "ASys"], [SdsfRow({"NP": "", "ADDRSPACE": "BPXOINIT", "STATE": "ACTIVE", "ASys": "MVSC"})])

    def _version_panel(self) -> SdsfPanel:
        rows = [
            SdsfRow({"NP": "", "NAME": "SDSF", "VALUE": "V2R5M0 (Gibson simulated)"}),
            SdsfRow({"NP": "", "NAME": "z/OS", "VALUE": "03.01"}),
            SdsfRow({"NP": "", "NAME": "JES2", "VALUE": "HASP 3.1 compatible surface"}),
        ]
        return SdsfPanel("VER", "SDSF VERSION INFORMATION", "System", ["NP", "NAME", "VALUE"], rows, "ACTION=S-Display")

    def _system_panel(self, cmd: str) -> SdsfPanel:
        if cmd == "APF":
            rows = []
            for idx, lib in enumerate(getattr(self.state, "apf_libraries", []), 1):
                vol = "WORK01" if "VULN" in lib or lib.startswith("RUARIV") else "MVSRES"
                rows.append(SdsfRow({
                    "NP": "", "DSNAME": lib, "Seq": str(idx), "VolSer": vol, "Status": "OK",
                    "BlkSize": "32760", "Extent": "1", "SMS": "NO", "LRecL": "0", "DSOrg": "PO"
                }, target=lib))
            return SdsfPanel(
                cmd,
                "APF DISPLAY  GIB1     GIB1      EXT",
                "System",
                ["NP", "DSNAME", "Seq", "VolSer", "Status", "BlkSize", "Extent", "SMS", "LRecL", "DSOrg"],
                rows,
                "ACTION=S-Display  /-Popup command  SORT DSNAME  FIND string",
            )
        if cmd == "CK":
            rows = [SdsfRow({"NP": "", "CHECK": row["CHECK"], "NAME": row["NAME"], "SEV": row["SEV"], "STATUS": row["STATUS"], "FINDING": row["FINDING"]}, target=row["CHECK"]) for row in get_healthchecker(self.state).rows()]
            return SdsfPanel(cmd, "HEALTH CHECKS", "System", ["NP", "CHECK", "NAME", "SEV", "STATUS", "FINDING"], rows, "ACTION=S-Display  REFRESH  START chk  STOP chk")
        if cmd == "SYM":
            rows = [SdsfRow({"NP": "", "NAME": "&SYSNAME", "VALUE": "MVSC"}), SdsfRow({"NP": "", "NAME": "&SYSCLONE", "VALUE": "SC"})]
            return SdsfPanel(cmd, "SYSTEM SYMBOLS", "System", ["NP", "NAME", "VALUE"], rows)
        if cmd == "SYS":
            rows = [SdsfRow({"NP": "", "SYSNAME": "MVSC", "TYPE": "z/OS", "STATE": "ACTIVE", "VALUE": "GIBSON z/OS 3.1 TRAINING"})]
            return SdsfPanel(cmd, "SYSTEM INFORMATION", "System", ["NP", "SYSNAME", "TYPE", "STATE", "VALUE"], rows)
        rows = [SdsfRow({"NP": "", "NAME": cmd, "Description": f"{cmd} system resource display", "Status": "ACTIVE"})]
        return SdsfPanel(cmd, f"{cmd} DISPLAY", "System", ["NP", "NAME", "Description", "Status"], rows)

    def _wlm_panel(self, cmd: str) -> SdsfPanel:
        rows = [SdsfRow({"NP": "", "NAME": "SYSSTC", "SERVICE": "HIGH", "STATE": "ACTIVE", "Description": "System service class"}), SdsfRow({"NP": "", "NAME": "TSO", "SERVICE": "MEDIUM", "STATE": "ACTIVE", "Description": "Interactive TSO"})]
        return SdsfPanel(cmd, f"{cmd} WLM DISPLAY", "WLM", ["NP", "NAME", "SERVICE", "STATE", "Description"], rows)

    def _devices_panel(self, cmd: str) -> SdsfPanel:
        rows = [SdsfRow({"NP": "", "NAME": "3390-1", "UNIT": "3390", "VOLUME": "MVSRES", "STATE": "ONLINE"}), SdsfRow({"NP": "", "NAME": "3390-2", "UNIT": "3390", "VOLUME": "WORK01", "STATE": "ONLINE"})]
        return SdsfPanel(cmd, f"{cmd} DEVICE DISPLAY", "Devices", ["NP", "NAME", "UNIT", "VOLUME", "STATE"], rows)

    def _network_panel(self, cmd: str) -> SdsfPanel:
        c = cmd.upper()
        if c == "NODE":
            rows = [SdsfRow({"NP": "", "Node": n.name, "Status": n.status, "Local": "YES" if n.local else "NO", "Description": "Gibson JES2 NJE node"}) for n in self.state.nje.nodes.values()]
            return SdsfPanel(cmd, "NJE NODES", "Network", ["NP", "Node", "Status", "Local", "Description"], rows)
        if c == "LINE":
            rows = [SdsfRow({"NP": "", "Line": l.name, "Node": l.node, "Status": l.status.value, "Type": "TCP", "Port": "175"}) for l in self.state.nje.lines.values()]
            return SdsfPanel(cmd, "NJE LINES", "Network", ["NP", "Line", "Node", "Status", "Type", "Port"], rows)
        rows = [SdsfRow({"NP": "", "NAME": l.name, "TYPE": l.proto, "STATE": l.state, "Description": l.description}) for l in self.state.network.listeners]
        return SdsfPanel(cmd, f"{cmd} NETWORK DISPLAY", "Network", ["NP", "NAME", "TYPE", "STATE", "Description"], rows)

    def _sysplex_panel(self, cmd: str) -> SdsfPanel:
        rows = [SdsfRow({"NP": "", "NAME": "GIBPLEX", "MEMBER": "MVSC", "STATE": "ACTIVE", "Description": "Single-system simulated sysplex"})]
        return SdsfPanel(cmd, f"{cmd} SYSPLEX DISPLAY", "Sysplex", ["NP", "NAME", "MEMBER", "STATE", "Description"], rows)

    # ------------------------------------------------------------------
    # Actions and command handling
    # ------------------------------------------------------------------
    def find_menu_command_by_number(self, number: int) -> Optional[str]:
        if 1 <= number <= len(self.MENU_ITEMS):
            return self.MENU_ITEMS[number - 1].command
        return None

    def row_target(self, panel_cmd: str, row_number: int) -> Optional[str]:
        panel = self.build_panel(panel_cmd)
        rows = self._apply_filters(panel.rows, panel.columns)
        if self.sort_column and self.sort_column in panel.columns:
            rows = sorted(rows, key=lambda r: r.cells.get(self.sort_column, ""), reverse=bool(getattr(self, "sort_desc", False)))
        if 1 <= row_number <= len(rows):
            return rows[row_number - 1].target
        return None

    def job_dataset_panel(self, jobid: str) -> str:
        job = self.state.jes.jobs.get(jobid.upper())
        if not job:
            return self._message_screen(f"ISF754I JOB {jobid.upper()} NOT FOUND")
        columns = ["NP", "DDNAME", "StepName", "ProcStep", "ByteCount", "Lines"]
        out = self._header(f"SDSF JOB DATA SETS {job.jobid}", f"LINE 1-{len(job.spool)} ({len(job.spool)})")
        out.append(colors.TURQUOISE + "ACTION=S-Browse" + colors.RESET)
        out.append(self._column_header(columns))
        widths = self._widths(columns)
        for idx, sf in enumerate(job.spool, 1):
            cells = {
                "NP": "", "DDNAME": sf.ddname, "StepName": "JES2", "ProcStep": "", "ByteCount": str(len(sf.content.encode())), "Lines": str(len(sf.content.splitlines()))
            }
            out.append(f"{colors.WHITE}{idx:>2}{colors.RESET} " + " ".join(f"{cells.get(c,''):<{widths[c]}}"[: widths[c]] for c in columns))
        out.extend(self._footer("Use S n to browse a data set, PF3 to return"))
        return "\n".join([x for x in out if x])

    def browse_job(self, jobid: str, dd_index: Optional[int] = None) -> str:
        job = self.state.jes.jobs.get(jobid.upper())
        if not job:
            return self._message_screen(f"ISF754I JOB {jobid.upper()} NOT FOUND")
        spool = job.spool
        if dd_index is not None and 1 <= dd_index <= len(spool):
            spool = [spool[dd_index - 1]]
        out = [colors.CLEAR + colors.WHITE + f"SDSF OUTPUT DISPLAY {job.jobname} {job.jobid}" + colors.RESET]
        out.append(colors.BLUE + "COMMAND INPUT ===>" + colors.RED + " " + colors.BLUE + "SCROLL ===> CSR" + colors.RESET)
        line = 1
        for sf in spool:
            out.append(colors.BLUE + f"--- {sf.ddname} " + "-" * max(1, 65 - len(sf.ddname)) + colors.RESET)
            for text in sf.content.splitlines():
                out.append(f"{colors.TURQUOISE}{line:06d}{colors.RESET} {text}")
                line += 1
        out.extend(self._footer("PF3 to return  FIND string"))
        return "\n".join([x for x in out if x])

    def perform_action(self, panel_cmd: str, action: str, row: int) -> Tuple[Optional[str], str]:
        action = action.upper()
        target = self.row_target(panel_cmd, row)
        if not target:
            return None, "ISF754I ROW NOT FOUND"
        if panel_cmd.upper() == "SMF80":
            events = [e for e in self.state.audit.events if e.component == "SMF80" and not ("SYS1.UADS" in (getattr(e, "command", "") + " " + getattr(e, "result", "") + " " + str(getattr(e, "extra", {}))))][-60:]
            if target.startswith("SMF80-"):
                try:
                    idx = int(target.split("-", 1)[1]) - 1
                except Exception:
                    idx = -1
                if 0 <= idx < len(events) and action in {"S", "?"}:
                    detail = self.state.audit.smf80_detail_lines(events[idx], system=getattr(self.state.network, "hostname", "MVSC").upper())
                    return self._message_screen("\n".join(detail)), ""
        if panel_cmd.upper() == "SMF7":
            events = [e for e in self.state.audit.events if e.component == "SMF7"][-60:]
            if target and target.startswith("SMF7-"):
                try: idx = int(target.split("-",1)[1]) - 1
                except Exception: idx = -1
                if 0 <= idx < len(events) and action in {"S", "?"}:
                    return self._message_screen("\n".join(self.state.audit.smf7_detail_lines(events[idx]))), ""
        if action == "?":
            return self.job_dataset_panel(target), ""
        if action == "S":
            return self.browse_job(target), ""
        if action == "P":
            if self.state.jes.purge(target):
                return None, f"ISF452I {target} PURGED"
            return None, f"ISF754I JOB {target} NOT FOUND"
        if action == "C":
            job = self.state.jes.jobs.get(target.upper())
            if job:
                job.status = JobStatus.FAILED
                return None, f"ISF458I {target} CANCELLED"
            return None, f"ISF754I JOB {target} NOT FOUND"
        if action == "A":
            job = self.state.jes.jobs.get(target.upper())
            if job and job.status == JobStatus.HELD:
                job.status = JobStatus.OUTPUT
                return None, f"ISF452I {target} RELEASED"
            return None, f"ISF754I {target} NOT HELD"
        if action == "/":
            job = self.state.jes.jobs.get(target.upper())
            if job:
                return self._message_screen("\n".join(f"{k} = {v}" for k, v in self._job_row(job).cells.items())), ""
        if action.startswith("%"):
            return None, f"ISF000I REXX ACTION {action} ACCEPTED FOR {target} (SIMULATED)"
        return None, f"ISF000I ACTION {action} NOT SUPPORTED ON {panel_cmd}"

    def apply_sdsf_command(self, text: str) -> Tuple[Optional[str], str]:
        """Apply non-panel-changing SDSF commands.

        Returns (new_panel_command, message).  new_panel_command is None when
        the caller should keep the existing panel.
        """
        t = text.strip()
        if not t:
            return None, ""
        u = t.upper()
        if ";" in u:
            # SDSF supports stacked commands.  For the simulator, apply all
            # settings and let the last panel command win.
            panel = None
            msg = ""
            for part in [p.strip() for p in t.split(";") if p.strip()]:
                p, m = self.apply_sdsf_command(part)
                panel = p or panel
                msg = m or msg
            return panel, msg
        for keyword in ("PREFIX", "OWNER", "DEST", "SYSNAME"):
            if u.startswith(keyword):
                value = t.split(None, 1)[1] if " " in t else t.split("=", 1)[1] if "=" in t else "*"
                value = value.strip().strip("'")
                if keyword == "PREFIX": self.prefix = value or "*"
                elif keyword == "OWNER": self.owner = value or "*"
                elif keyword == "DEST": self.dest = value or "(ALL)"
                elif keyword == "SYSNAME": self.sysname = value
                return None, f"ISF031I {keyword} SET TO {value}"
        if u.startswith("FILTER"):
            self.filter_text = t.split(None, 1)[1] if " " in t else ""
            return None, f"ISF031I FILTER SET TO {self.filter_text or 'NONE'}"
        if u.startswith("SORT"):
            parts = t.split()
            self.sort_column = parts[1].strip() if len(parts) >= 2 else ""
            self.sort_desc = len(parts) >= 3 and parts[2].upper().startswith("D")
            return None, f"ISF031I SORT FIELD SET TO {self.sort_column or 'NONE'} {'DESC' if getattr(self, 'sort_desc', False) else 'ASC'}"
        if u in ("COLS", "COLSHELP"):
            cols = sorted({c for item in self.MENU_ITEMS for c in ["JOBNAME","JobID","Owner","Queue","RC","Lines","USERID","EVENT","RESULT","TIME","DATE","RESOURCE","DSNAME","VolSer","Status","STATE","SERVICE"]})
            return None, "SDSF COLUMN HELP\n" + "\n".join(f"  {c:<12} Simulated SDSF column" for c in cols)
        if u == "RESET":
            self.prefix="*"; self.owner="*"; self.dest="(ALL)"; self.sysname=""; self.filter_text=""; self.sort_column=""
            return None, "ISF031I SDSF FILTERS RESET"
        if u in ("WHO", "SET ACTION", "SET SCREEN", "SET MENU") or u.startswith("SET "):
            return None, f"ISF000I {u} ACTIVE FOR USER {self.userid}"
        if u.startswith("REFRESH") and hasattr(self.state, "refresh_health_checks"):
            self.state.refresh_health_checks()
            return None, "ISF031I PANEL DATA REFRESHED"
        if u == "/":
            return None, "ISF000I SDSF COMMAND POP-UP ACTIVE - ENTER OPERATOR COMMAND"
        if u.startswith(("SETPROG ", "D ", "DISPLAY ", "S ", "P ", "START ", "STOP ", "F ")):
            from gibson.apps.tso import TsoCommandProcessor
            return None, TsoCommandProcessor(self.state, self.userid).run(t)
        cmds = {i.command for i in self.MENU_ITEMS}
        if u in cmds:
            return u, ""
        if u.startswith("S "):
            sel = u.split(None, 1)[1]
            if sel.isdigit():
                cmd = self.find_menu_command_by_number(int(sel))
                if cmd:
                    return cmd, ""
            if sel in cmds:
                return sel, ""
        return None, f"ISF753I COMMAND {t} NOT RECOGNIZED"

    def _message_screen(self, message: str) -> str:
        return "\n".join([colors.CLEAR + colors.WHITE + "SDSF MESSAGE" + colors.RESET, "", message, "", colors.BLUE + "PF3 to return" + colors.RESET])
