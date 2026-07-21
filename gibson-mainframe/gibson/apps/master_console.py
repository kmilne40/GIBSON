from __future__ import annotations

from collections import OrderedDict
import select
import sys
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Callable, Optional

from gibson.apps.autocomplete import TsoAutocomplete
from gibson.apps.tso import TsoCommandProcessor
from gibson.render import colors
from gibson.security import icsf
from gibson.apps.master_console_events import MasterConsoleEventPoller
from gibson.core import v26_features
from gibson.core import dvcapin


@dataclass
class ConsoleResult:
    text: str
    action: Optional[str] = None


@dataclass
class WtorRequest:
    reply_id: int
    message: str
    stage: str
    kind: str = "WTOR"

    def render(self) -> str:
        return f"R {self.reply_id:02d} {self.message}"


class MasterConsoleController:
    def __init__(self, state, userid: str = "IBMUSER"):
        self.state = state
        self.userid = userid.upper()
        self.processor = TsoCommandProcessor(state, self.userid)
        self.autocomplete = TsoAutocomplete(state)
        self._ensure_console_state()

    def _ensure_console_state(self) -> dict:
        state_obj = getattr(self.state, "master_console_state", None)
        if state_obj is None:
            state_obj = {
                "boot_complete": False,
                "next_reply_id": 1,
                "outstanding": OrderedDict(),
                "boot_history": [],
                "ipl_parms": None,
                "ieasys_member": None,
                "shutdown_confirm": False,
            }
            setattr(self.state, "master_console_state", state_obj)
            self._add_wtor("IEA101A SPECIFY SYSTEM PARAMETERS FOR RELEASE z/OS 02.05.00", "IPLPARM")
        return state_obj

    def _state_obj(self) -> dict:
        return self._ensure_console_state()

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H.%M.%S")

    def _add_wtor(self, message: str, stage: str, kind: str = "WTOR", reply_id: int | None = None) -> WtorRequest:
        st = self._state_obj()
        if reply_id is None:
            reply_id = int(st["next_reply_id"])
            while reply_id in st["outstanding"]:
                reply_id += 1
        st["next_reply_id"] = max(int(st["next_reply_id"]), int(reply_id) + 1)
        req = WtorRequest(reply_id=int(reply_id), message=message, stage=stage, kind=kind)
        st["outstanding"][int(reply_id)] = req
        return req

    def _pop_wtor(self, reply_id: int) -> Optional[WtorRequest]:
        return self._state_obj()["outstanding"].pop(reply_id, None)

    def _get_wtor(self, reply_id: int) -> Optional[WtorRequest]:
        return self._state_obj()["outstanding"].get(reply_id)


    def _status_box(self) -> list[str]:
        now = datetime.now()
        try:
            vols = sorted({getattr(r, "volume", "WORK01") for r in self.state.datasets.listcat(self.userid, prefix="")})
        except Exception:
            vols = ["SBSYS1", "WORK01"]
        mgr = getattr(self.state, "service_manager", None)
        started = 0
        total = 0
        if mgr is not None:
            rows = mgr.status_rows(); total = len(rows); started = sum(1 for _n, st, _p, _d in rows if st == "STARTED")
        warnings = len(getattr(self.state, "dashboard_alerts", []))
        processing = "PROCESSING" if getattr(self.state, "console_events", None) else "IDLE"
        return [
            "+---------------- GIBSON HERCULES-STYLE CONTROL ----------------+",
            f"| DATE {now.strftime('%Y-%m-%d')}  TIME {now.strftime('%H:%M')}     PROCESSING {processing:<10}|",
            f"| LOADED VOLUMES: {', '.join(vols[:5])[:43]:<43}|",
            f"| SERVICES STARTED: {started:02d}/{total:02d}    WARNINGS: {warnings:<3} POWER: ON  |",
            "| COMMANDS: POWER OFF / Z EOD for simulated shutdown             |",
            "+----------------------------------------------------------------+",
        ]

    def _boot_progress_lines(self) -> list[str]:
        now = datetime.now()
        jday = now.strftime("%Y.%j %H:%M:%S")
        return [
            f"IEA794I IBM Z/OS MASTER CONSOLE CONS01 ACTIVE FOR SYSTEM GIB1 AT {jday}",
            "IEA168I GIBSON IPL INITIATED - NUCLEUS INITIALIZATION PROGRAM ACTIVE",
        ]

    def boot_text(self) -> str:
        st = self._state_obj()
        lines = ["\x1b[2J\x1b[H"]
        lines.extend(self._status_box())
        lines.append("")
        lines.extend(self._boot_progress_lines())
        if st["boot_complete"]:
            lines.extend(self._boot_complete_lines())
        else:
            lines.append("")
            lines.append("IEE600I REPLY TO OUTSTANDING IPL REQUESTS WITH R nn,answer")
            lines.extend(self._format_request_lines("all"))
        lines.append("")
        lines.append("IEE600I ENTER ? FOR AVAILABLE COMMANDS")
        lines.append("")
        return "\n".join(lines)

    def _boot_complete_lines(self) -> list[str]:
        now = datetime.now()
        jday = now.strftime("%Y.%j %H:%M:%S")
        return [
            "IEA101I SYSTEM PARAMETERS ACCEPTED",
            "IEA347I IEASYS PARMLIB MEMBER SELECTION COMPLETE",
            "IEE254I IPLINFO DISPLAY",
            f" SYSTEM IPLED AT {jday}",
            " RELEASE z/OS 02.05.00 GIBSON TRAINING LPAR",
            "$HASP426 SPECIFY OPTIONS - HASP-II, VERSION SIMULATED",
            "$HASP373 JES2     STARTED",
            "IRR54001I RACF SUBSYSTEM INITIALIZED",
            "BPXM010I OMVS INITIALIZATION COMPLETE",
            "EZZ6035I TCPIP PROC STARTED",
            "IEA602I OPERATOR COMMAND PROCESSING ACTIVE",
            f"IEA630I SYSTEM NAME {getattr(self.state.network, 'hostname', 'GIBSON')}",
        ]

    def _format_request_lines(self, mode: str) -> list[str]:
        reqs = list(self._state_obj()["outstanding"].values())
        if mode == "reply":
            # Keep legacy D R,R contract clean after IPL while still allowing the
            # optional MFA PIN WTOR to be answered by its reply id.
            reqs = [r for r in reqs if r.kind == "WTOR" and r.stage != "MFAPIN"]
        if not reqs:
            return [f"IEE112I {self._timestamp()} NO OUTSTANDING REPLY REQUESTS"]
        lines = [f"IEE112I {self._timestamp()} PENDING REQUESTS"]
        lines.extend(req.render() for req in reqs)
        return lines

    def _display_services(self) -> str:
        mgr = getattr(self.state, "service_manager", None)
        lines = [
            "IEE457I DISPLAY SERVICE STATUS",
            "SERVICE   STATE     PORT   DESCRIPTION",
        ]
        if mgr is None:
            lines.append("NO SERVICE TABLE AVAILABLE")
            return "\n".join(lines)
        for name, state, port, desc in mgr.status_rows():
            lines.append(f"{name:<8}  {state:<8}  {port:<5}  {desc}")
        return "\n".join(lines)

    def _display_activity(self) -> str:
        lines = [
            "IEE114I 00.00.00 ACTIVITY DISPLAY",
            "JOBNAME  STATUS    TYPE  DETAIL",
            "JES2     STARTED   STC   JOB ENTRY SUBSYSTEM",
        ]
        mgr = getattr(self.state, "service_manager", None)
        if mgr is not None:
            for name, state, port, desc in mgr.status_rows():
                detail = f"PORT {port}" if port != "--" else desc[:18]
                lines.append(f"{name:<8} {state:<8} STC   {detail}")
        return "\n".join(lines)

    def _display_iplinfo(self) -> str:
        st = self._state_obj()
        try:
            from gibson.apps.parmlib.explorer import system_config_state
            info = system_config_state(self.state)["iplinfo"]
        except Exception:
            info = {}
        member = "IEASYS" + str(info.get("ieasys", st.get("ieasys_member", "00") or "00")).replace("IEASYS", "")
        if not member.startswith("IEASYS"):
            member = "IEASYS00"
        parms = st.get("ipl_parms") or "CLPA"
        now = datetime.now().strftime("%Y.%j %H:%M:%S")
        return "\n".join([
            "IEE254I IPLINFO DISPLAY",
            f" SYSTEM IPLED AT {now}",
            " RELEASE z/OS 02.05.00 GIBSON TRAINING LPAR",
            f" IEASYS MEMBER {member}",
            f" IPL PARAMETERS {parms}",
            f" IPL VOLUME {info.get('ipl_volume', 'SBSYS1')}",
            f" SYSTEM NAME {info.get('sysname', getattr(self.state.network, 'hostname', 'GIBSON'))}",
            " CLPA STATUS SIMULATED",
        ])

    def _display_parmlib_concat(self) -> str:
        """D PARMLIB - the PARMLIB concatenation actually read at IPL, sourced
        from the live LOADxx / dataset store."""
        try:
            from gibson.apps.parmlib.explorer import system_config_state
            cfg = system_config_state(self.state)
        except Exception:
            cfg = {"parmlib": {}, "iplinfo": {}}
        n = len(cfg.get("parmlib", {}))
        lines = ["IEE251I PARMLIB DISPLAY",
                 " ENTRY FLAGS VOLUME DATASET",
                 " 1     S      SBSYS1 SYS1.PARMLIB",
                 f" PARMLIB MEMBERS READ: {n}   IEASYM=00  LOAD=00"]
        return "\n".join(lines)

    def _display_symbols(self) -> str:
        """D SYMBOLS - resolved system symbols (from IEASYM00 / running system)."""
        host = str(getattr(self.state.network, "hostname", "GIBSON") or "GIBSON").upper()
        return "\n".join([
            "IEA007I STATIC SYSTEM SYMBOL VALUES",
            f"          &SYSNAME.  = \"{host}\"",
            f"          &SYSCLONE. = \"{host[:2]}\"",
            "          &SYSPLEX.  = \"GIBPLEX\"",
            "          &SYSR1.    = \"SBSYS1\"",
            "          &SYSNExt.  = \"00\"",
        ])

    def _display_prog_apf(self) -> str:
        """D PROG,APF - the APF list from the live PROG00 plus any runtime
        (escalation-lab) additions, with a writable-library flag."""
        try:
            from gibson.apps.parmlib.explorer import system_config_state
            apf = system_config_state(self.state)["apf"]
        except Exception:
            apf = list(getattr(self.state, "apf_libraries", []))
        lines = ["CSV470I APF FORMAT=DYNAMIC", " ENTRY VOLUME DSNAME"]
        for i, dsn in enumerate(apf, 1):
            vol = "SBSYS1"
            lines.append(f" {i:03d}   {vol} {dsn}")
        return "\n".join(lines)

    def _display_wlm(self, systems: bool = False) -> str:
        """D WLM,SYSTEMS / D WLM - active service policy and service classes."""
        host = str(getattr(self.state.network, "hostname", "GIBSON") or "GIBSON").upper()
        if systems:
            return "\n".join([
                "IWM025I  WLM DISPLAY",
                " ACTIVE WORKLOAD MANAGEMENT SERVICE POLICY NAME: WLMPOL",
                " ACTIVATED: 2026.180 06.27.55  BY: IBMUSER  FROM: GIBSON",
                " DESCRIPTION: GIBSON TRAINING SERVICE POLICY",
                " RELATED SERVICE DEFINITION NAME: GIBDEF",
                " INSTALLED:  2026.180 06.20.00  BY: IBMUSER",
                f" SYSTEM   WLM-STATE  MODE        POLICY",
                f" {host:<8} AVAILABLE  GOAL        WLMPOL",
            ])
        return "\n".join([
            "IWM025I  WLM SERVICE POLICY: WLMPOL  (GOAL MODE)",
            " SERVICE CLASS  GOAL                                     IMP  RESOURCE",
            " ------------   ------------------------------------     ---  --------",
            " SYSTEM         SYSTEM (no goal - SYSTEM work)             -   ",
            " SYSSTC         SYSTEM (no goal - started tasks)           -   ",
            " TSO            80% complete within 00:00:00.500          1   ",
            " ONLINE         90% complete within 00:00:01.000          2   CICS/DDF",
            " BATCHHI        EXECUTION VELOCITY 50                      3   ",
            " BATCHLO        EXECUTION VELOCITY 20                      5   ",
            " DDF            85% complete within 00:00:02.000          2   DB2DDF",
            " DISCRETN       DISCRETIONARY                              -   ",
        ])

    def _display_m_cpu(self) -> str:
        """D M=CPU - IEE889I CPU/CPC configuration."""
        return "\n".join([
            "IEE174I 14.02.55 DISPLAY M",
            "PROCESSOR STATUS",
            " ID  CPU    SERIAL",
            " 00  +       0AB1CD2097",
            " 01  +       0AB1CD2097",
            "CPC ND = 002097.E26.IBM.02.00000000AB1C",
            "CPC SI = 2097.710.IBM.02.0000000000AB1C",
            "         Model: E26   CPC S/N: 0AB1C",
            "CPC ID = 00",
            "CPC NAME = GIBCEC01",
            "LP NAME = GIBSON     LP ID = 0A",
            "CSS ID  = 00",
            "MIF ID  = A",
            "+ ONLINE    - OFFLINE    . DOES NOT EXIST    W WLM-MANAGED",
            "CPC ND/SI/ID describe the (simulated) central processor complex.",
        ])

    def _display_hzs(self, text: str = "") -> str:
        """HZSPRINT / F HZSPROC,DISPLAY CHECKS - health checker summary."""
        try:
            from gibson.core.healthcheck import get_healthchecker
            rows = get_healthchecker(self.state).rows()
        except Exception:
            rows = []
        out = ["HZS0200I HEALTH CHECKER SUMMARY",
               " CHECK(OWNER)              STATE      STATUS      SEV",
               " -----------------------   --------   ---------   ----"]
        for r in rows:
            out.append(f" {r.get('CHECK',''):<24}  ACTIVE(ENABLED)  "
                       f"{r.get('STATUS','ACTIVE'):<9}  {r.get('SEV','LOW')}")
        out.append(" IBMRACF,RACF_SENSITIVE_RESOURCES   ACTIVE(ENABLED)  EXCEPTION   HIGH")
        out.append(" IBMXCF,XCF_SYSPLEX_CDS_SPOF        ACTIVE(ENABLED)  EXCEPTION   MED")
        out.append("HZS0201I END OF HEALTH CHECK SUMMARY")
        return "\n".join(out)

    def _display_grs_contention(self) -> str:
        """D GRS,C - global resource serialization contention."""
        return "\n".join([
            "ISG343I 14.02.55 GRS STATUS",
            " NO ENQ CONTENTION EXISTS",
            " NO LATCH CONTENTION EXISTS",
            " GRS STAR MODE - LOCK STRUCTURE ISGLOCK ACTIVE",
        ])

    def _display_security_period(self, period: str) -> str:
        try:
            from gibson.core.security_summary import format_security_period
            return format_security_period(self.state, period)
        except Exception:
            alerts = list(getattr(self.state, "dashboard_alerts", []))
            count = len(alerts)
            return "\n".join([
                f"IEE887I SECURITY {period} SUMMARY",
                "SOURCE    COUNT  DESCRIPTION",
                f"ZSEC      {count:05d} SECURITY ALERTS IN CURRENT BUFFER",
                "RACF      00000  RACF EVENT SUMMARY AVAILABLE VIA ZSEC EVENTS",
                "SMF       00000  SIMULATED SMF EVENT BUFFER ACTIVE",
            ])


    def _host_metrics(self) -> dict:
        try:
            import psutil  # type: ignore
            cpu = psutil.cpu_percent(interval=0.0)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage(str(self.state.config.sim_root if hasattr(self, 'state') else '.')).percent
            return {'cpu': cpu, 'memory': mem, 'disk': disk, 'source': 'psutil'}
        except Exception:
            import os
            try:
                load = os.getloadavg()[0]
                cpu = min(100.0, load * 100.0 / max(1, os.cpu_count() or 1))
            except Exception:
                cpu = 0.0
            try:
                st = os.statvfs(str(self.state.config.sim_root if hasattr(self, 'state') else '.'))
                disk = (1.0 - (st.f_bavail / max(1, st.f_blocks))) * 100.0
            except Exception:
                disk = 0.0
            return {'cpu': cpu, 'memory': 0.0, 'disk': disk, 'source': 'fallback'}


    def _screen_log(self) -> list[str]:
        st = self._state_obj()
        log = st.setdefault("screen_log", [])
        return log

    def _remember_screen_text(self, text: str, limit: int = 80) -> None:
        if not text:
            return
        log = self._screen_log()
        for raw in str(text).splitlines():
            if raw.strip():
                log.append(raw[:140])
        del log[:-limit]

    def _bar(self, pct: float, width: int = 12) -> str:
        pct_i = max(0, min(100, int(round(float(pct or 0)))))
        filled = max(0, min(width, int(width * pct_i / 100)))
        return "#" * filled + "." * (width - filled)

    def _text_activity_rows(self, width: int = 28, rows: int = 7) -> list[str]:
        """Render an ANSI-safe separated activity field for non-curses consoles.

        This preserves the full Gibson Master Console layout in line-mode and
        telnet paths.  It intentionally uses separated cells rather than a
        joined red wall, and it changes a small number of cells even while idle.
        """
        st = self._state_obj()
        phase = int(st.get("text_activity_phase", 0)) + 1
        st["text_activity_phase"] = phase
        hot = 0.50 if st.pop("text_activity_burst", False) else 0.06
        total = max(1, width * rows)
        target = max(1, int(total * hot))
        cells: dict[tuple[int, int], str] = {}
        stride = 5 if width % 5 else 7
        attempts = 0
        cursor = (phase * 3) % total
        while len(cells) < target and attempts < total * 4:
            pos = (cursor + attempts * stride + attempts // max(1, rows)) % total
            r, c = divmod(pos, width)
            colour = "R" if hot >= 0.50 and attempts % 5 in {0, 3} else ("A" if attempts % 7 == 0 else "G")
            if colour == "R" and ((r, c - 1) in cells or (r, c + 1) in cells):
                attempts += 1
                continue
            cells[(r, c)] = colour
            attempts += 1
        out: list[str] = []
        for r in range(rows):
            chars = ["."] * width
            for (rr, cc), col in cells.items():
                if rr != r:
                    continue
                chars[cc] = "#" if col == "R" else ("+" if col == "A" else "*")
            out.append("".join(chars))
        return out

    def render_full_console(self, command_result: str | None = None, *, width: int = 132, height: int = 34) -> str:
        """Return the full text-mode Gibson Master Console panel.

        The master-console command path must never degrade into a simple
        command/reply transcript after R 05, R 06, or D DVCAPIN.  This renderer
        redraws the full panel after every command and places command results in
        the OPERLOG/ALERT STREAM area.
        """
        if command_result:
            self._remember_screen_text(command_result)
            # Commands should visibly trigger roughly half the processor block.
            self._state_obj()["text_activity_burst"] = True
        metrics = self._host_metrics()
        st = self._state_obj()
        log_lines = list(self._screen_log())
        if not log_lines:
            log_lines = self._boot_complete_lines() if st.get("boot_complete") else self._boot_progress_lines()
            if st.get("outstanding"):
                log_lines += self._format_request_lines("all")
        pending = len(st.get("outstanding", {}))
        hostname = getattr(getattr(self.state, "network", None), "hostname", None) or getattr(self.state, "system_hostname", "GIBSON1")
        mode = getattr(getattr(self.state, "config", None), "security_mode", "vuln")
        header1 = " GIBSON MASTER CONSOLE "
        host_disp = str(hostname).upper()
        # Layout maths must run on the *plain* hostname so the box borders stay
        # aligned; the glow escape sequence is injected after padding below.
        header2 = f" SYSNAME {host_disp:<8} LPAR GIB1  MODE {str(mode):<5} VERSION final-v1b  ALERTS {pending:03d} "
        right: list[str] = [
            "SYSTEM PROCESSING",
            "IPL       " + ("COMPLETE" if st.get("boot_complete") else "ACTIVE"),
            "JES2      ACTIVE",
            "VTAM      ACTIVE",
            "TSO       READY",
            "CICS      ACTIVE",
            "DB2       ACTIVE",
            "USS       ACTIVE",
            "",
            f"HOST CPU [{self._bar(metrics.get('cpu', 0), 12)}] {int(metrics.get('cpu', 0)):3d}%",
            f"HOST MEM [{self._bar(metrics.get('memory', 0), 12)}] {int(metrics.get('memory', 0)):3d}%",
            f"GIBSON FS[{self._bar(metrics.get('disk', 0), 12)}] {int(metrics.get('disk', 0)):3d}%",
            f"METRICS  {str(metrics.get('source', 'fallback')).upper()}",
            "",
            "DASD",
            "SYSRES01  ONLINE",
            "RACF001   ACTIVE",
            "SPOOL01   WRITING",
            "CKDS      PROTECTED",
            "",
            "PROCESSOR BLOCK ACTIVITY",
        ]
        right.extend(self._text_activity_rows(28, 7))
        left_width = 86
        right_width = 40
        body_rows = max(24, min(height - 7, 28))
        logs = log_lines[-body_rows:]
        out = ["\x1b[2J\x1b[H" + "┌" + "─" * (left_width + right_width + 3) + "┐"]
        out.append("│" + header1.center(left_width + right_width + 3) + "│")
        header2_padded = header2.ljust(left_width + right_width + 3)[:left_width + right_width + 3]
        # Inject the glow around the SYSNAME token only.  Padding/truncation has
        # already happened on plain text, so the (zero-width) escape codes do
        # not shift the right-hand border.  count=1 targets the SYSNAME field,
        # which always precedes any incidental match (e.g. "LPAR GIB1").
        if host_disp and host_disp in header2_padded:
            header2_padded = header2_padded.replace(host_disp, colors.glow(host_disp), 1)
        out.append("│" + header2_padded + "│")
        out.append("├" + "─" * left_width + "┬" + "─" * right_width + "┤")
        out.append("│" + " OPERLOG / ALERT STREAM ".center(left_width) + "│" + " SYSTEM PROCESSING ".center(right_width) + "│")
        for i in range(body_rows):
            l = logs[i] if i < len(logs) else ""
            r = right[i + 1] if i + 1 < len(right) else ""
            out.append("│" + l[:left_width].ljust(left_width) + "│" + r[:right_width].ljust(right_width) + "│")
        out.append("├" + "─" * (left_width + right_width + 3) + "┤")
        out.append("│ COMMAND ===> ".ljust(left_width + right_width + 4) + "│")
        out.append("└" + "─" * (left_width + right_width + 3) + "┘")
        return "\n".join(out)

    def _display_registers(self) -> str:
        import hashlib, time
        seed = f"{getattr(getattr(self, 'state', None), 'system_hostname', 'GIBSON')}:{int(time.time())//60}".encode()
        digest = hashlib.sha256(seed).hexdigest().upper()
        rows = ['IEE604I GIBSON REGISTER DISPLAY - SIMULATED 370/390 CONTEXT', 'PSW=070C1000 80000000  ASID=002A  TCB=00F4A120  MODE=PROBLEM']
        for i, r in enumerate('0123456789ABCDEF'):
            rows.append(f'R{r}={digest[i*8:i*8+8]}')
        rows.append('NOTE: REGISTER VALUES ARE SIMULATED EDUCATIONAL CONTEXT, NOT HOST CPU REGISTERS')
        return '\n'.join(rows)

    def _display_basic_metric(self, name: str) -> str:
        metrics = self._host_metrics()
        if name == "CPU":
            return f"IEE601I HOST CPU ACTIVITY {metrics['cpu']:05.1f} PERCENT - SOURCE({metrics['source']})"
        if name == "MEMORY":
            return f"IEE602I HOST MEMORY ACTIVITY {metrics['memory']:05.1f} PERCENT - SOURCE({metrics['source']})"
        if name == "DASD":
            return "\n".join([
                "IEE603I DASD ACTIVITY - GIBSON FILESYSTEM SPACE DISPLAY",
                f"  SIMROOT ONLINE  UTIL={metrics['disk']:05.1f}% SOURCE({metrics['source']})",
                "  NOTE: HOST FILESYSTEM SPACE, NOT REAL DASD VOLUME METRICS",
            ])
        return "IEE305I DISPLAY NOT AVAILABLE"

    def _master_help(self) -> str:
        return "\n".join([
            "IEE600I GIBSON MASTER CONSOLE COMMANDS",
            "COMMAND / SYNTAX",
            "  R nn,reply              Reply to outstanding WTOR",
            "  D R,L | D R,R           Display outstanding replies",
            "  D A,L                   Display active services/jobs",
            "  D IPLINFO               Display simulated IPL information",
            "  D SERVICES              Display Gibson managed services",
            "  D SECURITY,RARE         Display rare-event security summary",
            "  D SECURITY,DAILY        Display daily security summary",
            "  D SECURITY,WEEKLY       Display weekly security summary",
            "  D SECURITY,MONTHLY      Display monthly security summary",
            "  ZSEC RARE               Open zSecure rare-event report if available",
            "  STATUS | SERVICES       Display service status",
            "  CPU | MEMORY | DASD     Display host metrics (clearly labelled)",
            "  REGS | REGISTERS        Display simulated registers 0-F",
            "  CLEAR | REFRESH         Clear or refresh console display",
            "  QUIT | EXIT             Leave the master console",
        ])

    def _service_name(self, text: str) -> str:
        token = (text or "").strip().upper().replace(",", " ").split()
        if not token:
            return ""
        raw = token[0].lstrip("$")
        aliases = {
            "FTP": "FTPD",
            "FTPD": "FTPD",
            "RACF": "RACF",
            "OMVS": "OMVS",
            "USS": "OMVS",
            "JES2": "JES2",
            "JES": "JES2",
            "TCPIP": "TCPIP",
            "DB2DAS": "DB2DAS",
            "DB2WS": "DB2WS",
            "GIBDASH": "GIBDASH",
            "DASH": "GIBDASH",
        }
        return aliases.get(raw, raw)

    def _command_help(self, cmd: str) -> str:
        prefix = "" if cmd == "?" else cmd[:-1].strip()
        _completed, help_text = self.autocomplete.complete(prefix)
        return help_text

    def _shutdown_blockers(self) -> list[str]:
        mgr = getattr(self.state, "service_manager", None)
        if mgr is None:
            return []
        blockers = []
        for name in ("FTPD", "OMVS", "DB2DAS", "DB2WS", "TCPIP", "RACF", "JES2"):
            svc = mgr.get(name)
            if svc is not None and svc.state == "STARTED":
                blockers.append(name)
        return blockers

    def _handle_reply(self, raw: str) -> ConsoleResult:
        m = re.match(r"^(?:R|REPLY)\s+(\d{1,3})\s*,\s*(.+)$", raw.strip(), re.I)
        if not m:
            return ConsoleResult("IEE600I INVALID REPLY SYNTAX - USE R nn,reply")
        rid = int(m.group(1))
        value = m.group(2).strip()
        req = self._get_wtor(rid)
        if req is None:
            return ConsoleResult(f"IEE600I REPLY ID {rid:02d} NOT FOUND")
        self._pop_wtor(rid)
        st = self._state_obj()
        clog = getattr(self.state, "console_log", None)
        value_u = value.upper()
        lines: list[str] = []
        action: Optional[str] = None
        if req.stage == "IPLPARM":
            st["ipl_parms"] = value_u
            lines.append(f"IEA101I SYSTEM PARAMETERS SET TO {value_u}")
            nxt = self._add_wtor("IEA347A REPLY U TO USE DEFAULT IEASYS00 OR SPECIFY IEASYS MEMBER", "IEASYS")
            lines.append(nxt.render())
        elif req.stage == "IEASYS":
            member = "IEASYS00" if value_u == "U" else value_u
            st["ieasys_member"] = member
            lines.append(f"IEA347I IEASYS MEMBER {member} SELECTED")
            nxt = self._add_wtor("IEA102A REPLY Y TO CONTINUE GIBSON IPL", "IPLGO")
            lines.append(nxt.render())
        elif req.stage == "IPLGO":
            if value_u not in {"Y", "YES", "GO"}:
                lines.append("IEA102I IPL CONTINUE REPLY REJECTED - REPLY Y TO CONTINUE")
                nxt = self._add_wtor("IEA102A REPLY Y TO CONTINUE GIBSON IPL", "IPLGO")
                lines.append(nxt.render())
            else:
                # Always require reply 04 during the manual IPL path.  If a PIN
                # already exists, reply 04 confirms it; otherwise reply 04
                # defines it using the simulator training default rules.
                # Keep legacy boot-complete-looking console text visible after R 03,Y,
                # but leave boot_complete false until reply 04 validates.
                lines.extend(self._boot_complete_lines())
                lines.append("GIBSON MFA INITIALISATION")
                lines.append("*04 GIBSON MFA PIN REQUIRED FOR IPL CONTINUATION")
                nxt = self._add_wtor("DEFINE 4-DIGIT MFA PIN FOR THIS IPL - IEE600A REPLY 04 WITH MFA PIN", "MFAPIN", reply_id=4)
                lines.append(nxt.render())
        elif req.stage == "MFAPIN":
            try:
                if getattr(self.state, "mfa_pin_set", lambda: False)():
                    from gibson.security import mfa_pin as _mfa_pin
                    if not _mfa_pin._pin_matches(self.state, value):
                        raise ValueError("MFA PIN DOES NOT MATCH CONFIGURED IPL PIN")
                    lines.append("GIBSON MFA PIN ACCEPTED")
                    lines.append("SECURITY EVENT RECORDED")
                else:
                    msg = self.state.set_mfa_pin(value, self.userid)
                    lines.extend(msg.splitlines())
                lines.extend(self._boot_complete_lines())
                lines.append("*05 GIBSON HOSTNAME REQUIRED FOR IPL CONTINUATION")
                nxt = self._add_wtor("IEE600A REPLY 05 WITH SYSTEM HOSTNAME", "HOSTNAME", reply_id=5)
                lines.append(nxt.render())
            except ValueError as exc:
                lines.append(f"GIBSON MFA PIN REJECTED - {exc}")
                lines.append("*04 GIBSON MFA PIN REQUIRED FOR IPL CONTINUATION")
                # Keep the same pending reply id so R 04,xxxx remains the
                # operator workflow after an incorrect PIN.
                st["outstanding"][rid] = req
                lines.append(req.render())
        elif req.stage == "HOSTNAME":
            try:
                name = self.state.set_system_hostname(value, self.userid)
                lines.append(f"GIBHST005I HOSTNAME {name} ACCEPTED")
                lines.append(f"GIBHST006I SYSTEM IDENTITY SET TO {name}")
                lines.append(f"GIBHST007I LOCAL HOST ALIAS {name} -> 127.0.0.1 ACTIVE")
                lines.append("*06 GIBSON DVCA/CBSA/OMEN TRAINING PIN REQUIRED")
                nxt = self._add_wtor("DEFINE 4-DIGIT DVCAPIN OR SKIP - IEE600A REPLY 06 WITH DVCAPIN", "DVCAPIN", reply_id=6)
                lines.append(nxt.render())
            except ValueError as exc:
                lines.append(f"GIBHST105E INVALID HOSTNAME - {exc}")
                lines.append("*05 GIBSON HOSTNAME REQUIRED FOR IPL CONTINUATION")
                st["outstanding"][rid] = req
                lines.append(req.render())
        elif req.stage == "DVCAPIN":
            try:
                if value_u in {"SKIP", "N", "NO", "NONE"}:
                    lines.append("GIBPIN006I DVCAPIN CONFIGURATION SKIPPED")
                else:
                    m_pin = re.search(r"(?:DVCAPIN|PIN)\s*=\s*(\d{4})$", value, re.I)
                    pin = m_pin.group(1) if m_pin else value.strip()
                    msg = dvcapin.set_pin(self.state, pin, self.userid)
                    lines.append(f"GIBPIN006I {msg}")
                st["boot_complete"] = True
                lines.extend(self._boot_complete_lines())
            except ValueError as exc:
                lines.append(f"GIBPIN106E DVCAPIN REJECTED - {exc}")
                lines.append("*06 GIBSON DVCA/CBSA/OMEN TRAINING PIN REQUIRED")
                st["outstanding"][rid] = req
                lines.append(req.render())
        elif req.stage == "SHUTCONF":
            st["shutdown_confirm"] = False
            if value_u in {"Y", "YES", "GO"}:
                lines.append("IEE334I END OF DAY PROCESSING COMPLETE")
                lines.append("IEE600I SYSTEM SHUTDOWN IN PROGRESS")
                action = "shutdown"
            else:
                lines.append("IEE334I END OF DAY CANCELLED")
        else:
            lines.append(f"IEE600I REPLY {rid:02d} ACCEPTED")
        text = "\n".join(lines)
        if clog:
            clog.record(text)
        return ConsoleResult(text, action=action)

    def execute(self, cmd: str) -> ConsoleResult:
        raw = (cmd or "").rstrip()
        u = raw.upper().strip()
        if not u:
            return ConsoleResult("")
        clog = getattr(self.state, "console_log", None)
        if clog:
            clog.command(raw)
        if u.startswith("SPLITCON") or u in {"D SPLITCON", "DISPLAY SPLITCON"}:
            text = "IEE305I SPLITCON COMMAND NOT AVAILABLE IN THIS RELEASE"
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"REFRESH", "CLEAR", "CLS"}:
            return ConsoleResult("IEE600I CONSOLE DISPLAY REFRESHED" if u == "REFRESH" else "IEE600I CONSOLE MESSAGE PANE CLEARED")
        if u in {"HELP", "HELP CONSOLE", "?"}:
            text = self._master_help()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"STATUS", "SERVICES"}:
            text = self._display_services()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"CPU", "D CPU", "DISPLAY CPU"}:
            return ConsoleResult(self._display_basic_metric("CPU"))
        if u in {"MEMORY", "D MEMORY", "DISPLAY MEMORY"}:
            return ConsoleResult(self._display_basic_metric("MEMORY"))
        if u in {"DASD", "D DASD", "DISPLAY DASD"}:
            return ConsoleResult(self._display_basic_metric("DASD"))
        if u in {"REGS", "REGISTERS", "D REGS", "DISPLAY REGS", "D REGISTERS"}:
            return ConsoleResult(self._display_registers())
        if u in {"D IPLINFO", "DISPLAY IPLINFO"}:
            text = self._display_iplinfo()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"D PARMLIB", "DISPLAY PARMLIB"}:
            text = self._display_parmlib_concat()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"D SYMBOLS", "DISPLAY SYMBOLS", "D SYMBOL", "DISPLAY SYMBOL"}:
            text = self._display_symbols()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"D PROG,APF", "DISPLAY PROG,APF", "D PROG APF"}:
            text = self._display_prog_apf()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"D WLM,SYSTEMS", "DISPLAY WLM,SYSTEMS", "D WLM,SYSTEM"}:
            text = self._display_wlm(systems=True)
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"D WLM", "DISPLAY WLM", "D WLM,POLICY"}:
            text = self._display_wlm(systems=False)
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"D M=CPU", "DISPLAY M=CPU", "D M", "DISPLAY M"}:
            text = self._display_m_cpu()
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"HZSPRINT", "D HZS", "DISPLAY HZS"} or u.startswith("F HZSPROC"):
            text = self._display_hzs(raw)
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"D GRS,C", "DISPLAY GRS,C", "D GRS,CONTENTION", "D GRS"}:
            text = self._display_grs_contention()
            if clog: clog.record(text)
            return ConsoleResult(text)
        if u in {"D SECURITY,RARE", "DISPLAY SECURITY,RARE"}:
            return ConsoleResult(self._display_security_period("RARE"))
        if u in {"D SECURITY,DAILY", "DISPLAY SECURITY,DAILY"}:
            return ConsoleResult(self._display_security_period("DAILY"))
        if u in {"D SECURITY,WEEKLY", "DISPLAY SECURITY,WEEKLY"}:
            return ConsoleResult(self._display_security_period("WEEKLY"))
        if u in {"D SECURITY,MONTHLY", "DISPLAY SECURITY,MONTHLY"}:
            return ConsoleResult(self._display_security_period("MONTHLY"))
        if u in {"D DVCAPIN", "DISPLAY DVCAPIN", "DVCAPIN STATUS"}:
            text = f"DVCAPIN = {dvcapin.reveal_for_training(self.state)}" if dvcapin.is_set(self.state) else "DVCAPIN NOT SET"
            if clog: clog.record(text)
            return ConsoleResult(text)
        m_dvcapin = re.match(r"^(?:R|REPLY)\s*0?6\s*,\s*(?:(?:DVCAPIN|PIN)\s*=\s*)?(\d{4})$", raw.strip(), re.I)
        if m_dvcapin and self._get_wtor(6) is None:
            try:
                text = dvcapin.set_pin(self.state, m_dvcapin.group(1), self.userid)
            except ValueError as exc:
                text = f"IEE600I R 06,DVCAPIN REJECTED - {exc}"
            if clog: clog.record(text)
            return ConsoleResult(text)

        if raw == "?" or raw.endswith("?"):
            text = self._command_help(raw)
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in {"D ICSF", "DISPLAY ICSF"} or u.startswith("F ICSF,"):
            text = icsf.handle_console(self.state, self.userid, raw)
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if re.match(r"^(?:R|REPLY)\s+\d{1,3}\s*,", u):
            return self._handle_reply(raw)
        if u in ("QUIT", "EXIT"):
            text = "IEE600I MASTER CONSOLE SESSION END REQUEST ACCEPTED"
            if clog:
                clog.record(text)
            return ConsoleResult(text, action="quit")
        if u in ("LOGOFF",):
            text = "IEE600I LOGOFF NOT VALID FOR MASTER CONSOLE; USE QUIT OR Z EOD"
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in ("D R,L", "DISPLAY R,L", "D R,LONG", "DISPLAY R,LONG", "D R,L,CN=(ALL)", "DISPLAY R,L,CN=(ALL)"):
            text = "\n".join(self._format_request_lines("all"))
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in ("D R,R", "DISPLAY R,R", "D R,R,CN=(ALL)", "DISPLAY R,R,CN=(ALL)"):
            text = "\n".join(self._format_request_lines("reply"))
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in ("D SVC,L", "DISPLAY SVC,L", "D SERVICES", "DISPLAY SERVICES", "$D SERVICES", "$D SVC"):
            text = self._display_services()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u in ("D A,L", "DISPLAY A,L"):
            text = self._display_activity()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        if u.startswith(("S ", "START ")):
            name = self._service_name(raw.split(None, 1)[1] if " " in raw else "")
            allowed, denial = v26_features.operator_authorized(self.state, self.userid, f"MVS.START.STC.{name}")
            if not allowed: return ConsoleResult(denial)
            mgr = getattr(self.state, "service_manager", None)
            text = mgr.start(name)[1] if mgr is not None else f"IEE305I {name} NOT AVAILABLE"
            return ConsoleResult(text)
        if u.startswith(("P ", "STOP ", "PAUSE ", "RESUME ", "$P ")):
            op = u.split()[0].lstrip("$")
            name = self._service_name(raw.split(None, 1)[1] if " " in raw else "")
            resverb = "START" if op == "RESUME" else ("PAUSE" if op == "PAUSE" else "STOP")
            allowed, denial = v26_features.operator_authorized(self.state, self.userid, f"MVS.{resverb}.STC.{name}")
            if not allowed: return ConsoleResult(denial)
            mgr = getattr(self.state, "service_manager", None)
            if mgr is None:
                return ConsoleResult(f"IEE305I {name} NOT AVAILABLE")
            text = mgr.pause(name)[1] if op == "PAUSE" else (mgr.start(name)[1] if op == "RESUME" else mgr.stop(name)[1])
            return ConsoleResult(text)
        if u in ("POWER OFF", "POWEROFF", "Z EOD", "QUIESCE", "SHUTDOWN"):
            blockers = self._shutdown_blockers()
            if blockers:
                text = "IEE334I END-OF-DAY NOT ACCEPTED - ACTIVE SERVICES: " + ", ".join(blockers)
                if clog:
                    clog.record(text)
                return ConsoleResult(text)
            st = self._state_obj()
            if st.get("shutdown_confirm"):
                text = "IEE334I END-OF-DAY CONFIRMATION ALREADY PENDING"
                if clog:
                    clog.record(text)
                return ConsoleResult(text)
            st["shutdown_confirm"] = True
            req = self._add_wtor("IEE334A CONFIRM END OF DAY - REPLY Y TO CONTINUE", "SHUTCONF")
            text = req.render()
            if clog:
                clog.record(text)
            return ConsoleResult(text)
        out = self.processor.run(raw)
        if out.startswith("GIBSON-INTERACTIVE:"):
            text = f"IEE600I {raw} REQUIRES A LOGGED-ON TERMINAL SESSION; USE TN3270/USS CLIENT"
        else:
            text = out.rstrip("\n")
        if clog:
            clog.record(text)
        return ConsoleResult(text)


class MasterConsoleUI:
    def __init__(self, state, input_func: Callable[[str], str] = input, output_func: Callable[[str], None] = print, userid: str = "IBMUSER", poll_interval: float = 30.0):
        self.state = state
        self.input_func = input_func
        self.output_func = output_func
        self.controller = MasterConsoleController(state, userid)
        self.poll_interval = max(1.0, float(poll_interval or 30.0))
        self.event_poller = MasterConsoleEventPoller(state)

    def _format_event(self, severity: str, text: str) -> str:
        sev = (severity or "INFO").upper()
        payload = text.upper() if sev in {"ALERT", "EVENT"} else text
        if sev == "ALERT":
            return colors.RED + payload + colors.RESET
        if sev == "SUCCESS":
            return colors.GREEN + payload + colors.RESET
        return colors.YELLOW + payload + colors.RESET

    def _emit_pending_events(self) -> None:
        for event in self.event_poller.poll():
            self.output_func(self._format_event(event.severity, event.message))
        drain = getattr(self.state, "drain_console_events", None)
        if drain:
            for severity, text in drain():
                self.output_func(self._format_event(severity, text))

    def _run_polled_terminal(self) -> str:
        while True:
            self._emit_pending_events()
            ready, _, _ = select.select([sys.stdin], [], [], min(self.poll_interval, 1.0))
            if not ready:
                continue
            line = sys.stdin.readline()
            cmd = "QUIT" if line == "" else line.rstrip("\n")
            result = self.controller.execute(cmd)
            if result.text:
                self.output_func(self.controller.render_full_console(result.text))
            if result.action in {"quit", "shutdown"}:
                return result.action

    def run(self) -> str:
        boot = self.controller.render_full_console()
        if boot:
            self.output_func(boot)
            if getattr(self.state, "console_log", None):
                self.state.console_log.record(boot)
        if self.input_func is input and hasattr(sys.stdin, "fileno") and sys.stdin.isatty():
            return self._run_polled_terminal()
        while True:
            self._emit_pending_events()
            try:
                cmd = self.input_func("? ")
            except EOFError:
                cmd = "QUIT"
            result = self.controller.execute(cmd)
            if result.text:
                self.output_func(self.controller.render_full_console(result.text))
            if result.action in {"quit", "shutdown"}:
                return result.action
