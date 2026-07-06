"""M3a - DB2I (DB2 Interactive) in authentic EBCDIC 3270.

Phase-0 ``PanelSession``.  Reuses ``Db2Simulator`` for all behaviour
(``format_spufi`` for SPUFI execution, ``shell_command``/``display_group`` for
DB2 commands); this module is presentation + navigation only.

States: MENU -> SPUFI (SQL entry) -> OUT (result browse); MENU -> CMD (DB2 cmds).
"""
from __future__ import annotations

from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import Panel, Label, Field, PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.db2 import Db2Simulator

_MENU = "MENU"
_SPUFI = "SPUFI"
_OUT = "OUT"
_CMD = "CMD"
_DEFAULTS = "DEFAULTS"
_DCLGEN = "DCLGEN"
_PREP = "PREP"
_PRECOMP = "PRECOMP"
_BIND = "BIND"
_RUNP = "RUNP"
_UTIL = "UTIL"
_DSN = "DSN"

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_OUTPUT_ROWS = 20
_SQL_ROWS = 11  # SQL entry lines on the SPUFI panel

_MENU_OPTIONS = [
    ("1", "SPUFI", "Process SQL statements"),
    ("2", "DCLGEN", "Generate SQL and source declarations"),
    ("3", "PROGRAM PREP", "Prepare a DB2 application program"),
    ("4", "PRECOMPILE", "Invoke DB2 precompiler"),
    ("5", "BIND/REBIND/FREE", "BIND, REBIND, or FREE plans or packages"),
    ("6", "RUN", "RUN an SQL program"),
    ("7", "DB2 COMMANDS", "Issue DB2 commands"),
    ("8", "UTILITIES", "Invoke DB2 utilities"),
    ("DSN", "COMMAND PROC", "DSN line-mode DB2 command processor"),
    ("D", "DB2I DEFAULTS", "Set global parameters"),
    ("X", "EXIT", "Leave DB2I"),
]
_STUBBED = set()


class Db2i3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = (userid or "IBMUSER").upper()
        self.db2 = Db2Simulator(state)
        self._screen = _MENU
        self._message = ""
        self.lines: List[str] = []
        self._scroll: Optional[ScrollList] = None
        self._ssid = "DSN1"
        self._out_return = _SPUFI
        self._dsn_lines: List[str] = []

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        return self._menu_panel()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if self._screen == _MENU:
            return self._handle_menu(pi)
        if self._screen == _SPUFI:
            return self._handle_spufi(pi)
        if self._screen == _OUT:
            return self._handle_out(pi)
        if self._screen == _DCLGEN:
            return self._handle_dclgen(pi)
        if self._screen == _PREP:
            return self._handle_func(pi, self._gen_prep)
        if self._screen == _PRECOMP:
            return self._handle_func(pi, self._gen_precomp)
        if self._screen == _BIND:
            return self._handle_func(pi, self._gen_bind)
        if self._screen == _RUNP:
            return self._handle_func(pi, self._gen_runp)
        if self._screen == _UTIL:
            return self._handle_func(pi, self._gen_util)
        if self._screen == _CMD:
            return self._handle_cmd(pi)
        if self._screen == _DSN:
            return self._handle_dsn(pi)
        if self._screen == _DEFAULTS:
            if pi.key in ("PF3", "PF15") or pi.key == "ENTER":
                self._ssid = pi.stripped("SSID") or self._ssid
                self._screen = _MENU
                self._message = "DB2I defaults saved."
                return self._menu_panel()
            return self._defaults_panel()
        return None

    # --------------------------------------------------------------- MENU
    def _menu_panel(self) -> ScreenBuffer:
        p = Panel(title="DB2I PRIMARY OPTION MENU", cursor="OPTION")
        p.add(Label(3, 2, "Option  ===>", colors.GREEN))
        p.add(Field("OPTION", 3, 15, 4, colour=_TURQ))
        row = 5
        for num, name, desc in _MENU_OPTIONS:
            p.add(Label(row, 4, f"{num:>2}  {name:<18} {desc}", colors.TURQUOISE))
            row += 1
        p.add(Label(row + 1, 2, f"SSID ===> {self._ssid}", colors.GREEN))
        p.pfkeys = "F1=Help  F3=Exit  F7=Up  F8=Down  F10=Left  F11=Right  PA2=Reshow"
        if self._message:
            p.message = self._message
        return p.render()

    # ----------------------------------------------------- DSN PROCESSOR
    _DSN_BANNER = [
        "DSN SYSTEM(DB2A)",
        "DSN7100I -DB2A DB2 COMMAND PROCESSOR - GIBSON",
        "COMMANDS: HELP, DISPLAY GROUP, RUN SQL <statement>, SHOW DBS, SHOW USERS, LOGOUT",
    ]

    def _enter_dsn(self) -> ScreenBuffer:
        self._screen = _DSN
        self._message = ""
        self._dsn_lines = list(self._DSN_BANNER)
        return self._dsn_panel()

    def _dsn_run(self, cmd: str) -> List[str]:
        uc = cmd.upper().strip()
        try:
            if uc in ("HELP", "?"):
                return ["DB2 COMMAND PROCESSOR HELP",
                        "  DISPLAY GROUP       Display the Db2 data sharing group",
                        "  RUN SQL <sql>       Execute SQL through the simulator",
                        "  SHOW DBS            List databases",
                        "  SHOW USERS          List RACF/DB2 users",
                        "  LOGOUT              End the command processor"]
            if uc in ("DISPLAY GROUP", "-DISPLAY GROUP", "DIS GROUP", "-DIS GROUP"):
                return self.db2.display_group().split("\n")
            if uc.startswith("RUN SQL "):
                return self.db2.format_spufi(cmd[len("RUN SQL "):], self.userid).split("\n")
            if uc.split(" ", 1)[0] in ("SELECT", "INSERT", "UPDATE", "DELETE", "GRANT", "REVOKE"):
                return self.db2.format_spufi(cmd, self.userid).split("\n")
            return self.db2.shell_command(cmd, self.userid).split("\n")
        except Exception as exc:
            return [f"DSNE523I  COMMAND FAILED: {exc}"]

    def _dsn_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        self._scroll = ScrollList(self._dsn_lines, height=_OUTPUT_ROWS)
        self._scroll.to_bottom()
        self._scroll.render_into(s, 1, left=1, width=79, colour=colors.GREEN)
        s.put(22, 1, self._scroll.position_label.ljust(20), colors.BLUE)
        s.put(23, 1, "DSN SYSTEM(DB2A) ===>", colors.WHITE)
        s.add_field("CMD", 23, 23, 56, colour=_TURQ, role="command")
        s.put(24, 1, "F3=Exit to DB2I  F7=Up  F8=Down  LOGOUT=End  PA2=Reshow", colors.BLUE)
        s.set_cursor(23, 23)
        return s

    def _handle_dsn(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _MENU
            self._message = ""
            return self._menu_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self._dsn_lines, height=_OUTPUT_ROWS)
            self._scroll.scroll(pi.key)
            s = ScreenBuffer()
            s.extended_attributes = True
            self._scroll.render_into(s, 1, left=1, width=79, colour=colors.GREEN)
            s.put(22, 1, self._scroll.position_label.ljust(20), colors.BLUE)
            s.put(23, 1, "DSN SYSTEM(DB2A) ===>", colors.WHITE)
            s.add_field("CMD", 23, 23, 56, colour=_TURQ, role="command")
            s.put(24, 1, "F3=Exit to DB2I  F7=Up  F8=Down  LOGOUT=End  PA2=Reshow", colors.BLUE)
            s.set_cursor(23, 23)
            return s
        cmd = pi.stripped("CMD")
        if not cmd:
            return self._dsn_panel()
        self._dsn_lines.append("DSN SYSTEM(DB2A) ===> " + cmd)
        if cmd.upper().strip() in ("LOGOUT", "LOGOFF", "EXIT", "QUIT", "END"):
            self._dsn_lines.append("DSN9022I -DB2A DSN COMMAND PROCESSOR NORMAL COMPLETION")
            self._screen = _MENU
            self._message = "DSN command processor ended."
            return self._menu_panel()
        self._dsn_lines.extend(self._dsn_run(cmd))
        self._dsn_lines.append("")
        return self._dsn_panel()

    def _handle_menu(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            return None
        opt = pi.stripped("OPTION").upper()
        if opt in ("X", ""):
            return None if opt == "X" else self._menu_panel()
        if opt == "1":
            self._screen = _SPUFI
            return self._spufi_panel()
        if opt == "2":
            self._screen = _DCLGEN
            return self._dclgen_panel()
        if opt == "3":
            self._screen = _PREP
            return self._prep_panel()
        if opt == "4":
            self._screen = _PRECOMP
            return self._precomp_panel()
        if opt == "5":
            self._screen = _BIND
            return self._bind_panel()
        if opt == "6":
            self._screen = _RUNP
            return self._runp_panel()
        if opt == "8":
            self._screen = _UTIL
            return self._util_panel()
        if opt == "7":
            self._screen = _CMD
            return self._cmd_panel()
        if opt == "DSN":
            return self._enter_dsn()
        if opt == "D":
            self._screen = _DEFAULTS
            return self._defaults_panel()
        if opt in _STUBBED:
            self._message = f"DSNE???I OPTION {opt} IS NOT AVAILABLE ON THIS SYSTEM YET."
            return self._menu_panel()
        self._message = "DSNE391I INVALID OPTION - RE-ENTER"
        return self._menu_panel()

    # -------------------------------------------------------------- SPUFI
    def _spufi_panel(self) -> ScreenBuffer:
        p = Panel(title="SPUFI", cursor="SQL01")
        p.add(Label(3, 2, "Enter SQL statements below, then press ENTER to execute:", colors.GREEN))
        for i in range(_SQL_ROWS):
            p.add(Field(f"SQL{i+1:02d}", 5 + i, 2, 76, colour=_TURQ))
        p.pfkeys = "F1=Help  F3=Exit  F12=Cancel"
        if self._message:
            p.message = self._message
        return p.render()

    def _handle_spufi(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _MENU
            return self._menu_panel()
        parts = [pi.stripped(f"SQL{i+1:02d}") for i in range(_SQL_ROWS)]
        sql = " ".join(p for p in parts if p).strip()
        if not sql:
            self._message = "DSNE345I NO SQL STATEMENT ENTERED"
            return self._spufi_panel()
        try:
            out = self.db2.format_spufi(sql, self.userid)
        except Exception as exc:
            out = f"{exc}"
        self.lines = ["SPUFI  ---  SQL RESULTS", ""] + [l.rstrip() for l in text_to_lines(out)]
        self._out_return = _SPUFI
        self._screen = _OUT
        return self._out_panel(to_bottom=False)

    # -------------------------------------------------------------- DCLGEN
    def _dclgen_panel(self) -> ScreenBuffer:
        p = Panel(title="DCLGEN  (Declarations Generator)", cursor="TABLE")
        p.add(Label(3, 2, "Enter table information below:", colors.GREEN))
        p.add(Label(5, 4, "Table owner . . . .", colors.TURQUOISE))
        p.add(Field("OWNER", 5, 24, 18, value="GIBSON", colour=_TURQ))
        p.add(Label(6, 4, "Table name  . . . .", colors.TURQUOISE))
        p.add(Field("TABLE", 6, 24, 18, colour=_TURQ))
        p.add(Label(7, 4, "Language  . . . . .", colors.TURQUOISE))
        p.add(Field("LANG", 7, 24, 8, value="COBOL", colour=_TURQ))
        user_t = [t.split(".")[-1] for t in self.db2.tables() if not t.startswith("SYSIBM")]
        sys_t = [t.split(".")[-1] for t in self.db2.tables() if t.startswith("SYSIBM")]
        tbls = ", ".join((user_t + sys_t)[:8])
        p.add(Label(9, 2, ("Known tables: " + tbls)[:76], colors.BLUE))
        p.pfkeys = "F1=Help  F3=Exit  F12=Cancel"
        if self._message:
            p.message = self._message
        return p.render()

    def _handle_dclgen(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15", "PF12"):
            self._screen = _MENU
            return self._menu_panel()
        owner = (pi.stripped("OWNER") or "GIBSON").upper()
        table = pi.stripped("TABLE").upper()
        lang = (pi.stripped("LANG") or "COBOL").upper()
        if not table:
            self._message = "DSNE390I ENTER A TABLE NAME"
            return self._dclgen_panel()
        cols = self._table_columns(table)
        if not cols:
            self._message = f"DSNE391I TABLE {table} NOT FOUND IN CATALOG"
            return self._dclgen_panel()
        self.lines = self._build_dclgen(owner, table, lang, cols)
        self._out_return = _MENU
        self._screen = _OUT
        return self._out_panel(to_bottom=False)

    def _table_columns(self, table: str) -> List[dict]:
        try:
            cat = self.db2.catalog()
            cols = cat.get("SYSIBM.SYSCOLUMNS", [])
            return [c for c in cols if str(c.get("TBNAME", "")).upper() == table]
        except Exception:
            return []

    @staticmethod
    def _cobol_pic(coltype: str, length: str) -> str:
        t = (coltype or "").upper()
        try:
            n = int(length)
        except (TypeError, ValueError):
            n = 1
        if t in ("CHAR", "VARCHAR", "CHARACTER"):
            return f"PIC X({n})"
        if t == "INTEGER":
            return "PIC S9(9) USAGE COMP"
        if t == "SMALLINT":
            return "PIC S9(4) USAGE COMP"
        if t in ("DECIMAL", "NUMERIC"):
            return f"PIC S9({max(1, n)})V USAGE COMP-3"
        if t == "DATE":
            return "PIC X(10)"
        if t in ("TIMESTAMP",):
            return "PIC X(26)"
        return f"PIC X({n})"

    def _build_dclgen(self, owner: str, table: str, lang: str, cols: List[dict]) -> List[str]:
        out = [f"DCLGEN  ---  {owner}.{table}   ({lang})", ""]
        out.append("      EXEC SQL DECLARE " + f"{owner}.{table} TABLE")
        body = []
        for i, c in enumerate(cols):
            name = c.get("NAME", f"COL{i+1}")
            ctype = c.get("COLTYPE", "CHAR")
            length = c.get("LENGTH", "1")
            typ = f"{ctype}({length})" if ctype.upper() in ("CHAR", "VARCHAR", "DECIMAL", "NUMERIC") else ctype
            lead = "      (  " if i == 0 else "       , "
            body.append(f"{lead}{name:<18} {typ}")
        out.extend(body)
        out.append("      ) END-EXEC.")
        out.append("")
        out.append(f"* COBOL DECLARATION FOR TABLE {owner}.{table}")
        out.append(f"  01  DCL{table[:6]}.")
        for c in cols:
            name = c.get("NAME", "FIELD")
            pic = self._cobol_pic(c.get("COLTYPE", "CHAR"), c.get("LENGTH", "1"))
            out.append(f"      10  {name:<18} {pic}.")
        out.append("")
        out.append("DSNE905I  DCLGEN COMPLETE - " + f"{len(cols)} COLUMN(S) DECLARED")
        return out

    # --------------------------------------------------- function panels
    def _handle_func(self, pi: PanelInput, generator) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15", "PF12"):
            self._screen = _MENU
            return self._menu_panel()
        lines = generator(pi)
        if lines is None:
            return self._func_panel_for(self._screen)
        self.lines = lines
        self._out_return = _MENU
        self._screen = _OUT
        return self._out_panel(to_bottom=False)

    def _func_panel_for(self, screen: str) -> ScreenBuffer:
        return {
            _PREP: self._prep_panel, _PRECOMP: self._precomp_panel,
            _BIND: self._bind_panel, _RUNP: self._runp_panel,
            _UTIL: self._util_panel,
        }.get(screen, self._menu_panel)()

    def _func_frame(self, title: str, fields, cursor: str, hints=None) -> ScreenBuffer:
        p = Panel(title=title, cursor=cursor)
        row = 4
        for label, name, width, default in fields:
            p.add(Label(row, 4, label, colors.TURQUOISE))
            p.add(Field(name, row, 4 + len(label) + 1, width, value=default, colour=_TURQ))
            row += 2
        for h in (hints or []):
            p.add(Label(row, 4, h[:74], colors.GREEN))
            row += 1
        p.pfkeys = "F1=Help  F3=Exit  F12=Cancel"
        if self._message:
            p.message = self._message
        return p.render()

    # 3 - PROGRAM PREP
    def _prep_panel(self) -> ScreenBuffer:
        return self._func_frame("DB2I  ---  PROGRAM PREPARATION", [
            ("INPUT MEMBER  . . .", "MEMBER", 8, ""),
            ("SOURCE LIBRARY  . .", "LIB", 30, f"{self.userid}.SRC"),
            ("PRECOMPILE (Y/N)  .", "PC", 1, "Y"),
            ("COMPILE (Y/N) . . .", "CMP", 1, "Y"),
            ("BIND (Y/N)  . . . .", "BND", 1, "Y"),
            ("RUN (Y/N) . . . . .", "RUN", 1, "N"),
        ], "MEMBER")

    def _gen_prep(self, pi: PanelInput):
        member = pi.stripped("MEMBER").upper()
        if not member:
            self._message = "DSNE390I ENTER AN INPUT MEMBER NAME"
            return None
        lib = pi.stripped("LIB").upper() or f"{self.userid}.SRC"
        steps = [("PRECOMPILE", pi.stripped("PC")), ("COMPILE", pi.stripped("CMP")),
                 ("BIND", pi.stripped("BND")), ("RUN", pi.stripped("RUN"))]
        out = [f"DB2I PROGRAM PREPARATION  ---  {lib}({member})", ""]
        out.append("Generated batch job:  // " + f"{self.userid}P JOB ,'DB2 PREP',CLASS=A")
        out.append("                      //DSNH EXEC PGM=DSNH")
        rc = 0
        for name, flag in steps:
            if (flag or "Y").upper().startswith("Y"):
                out.append(f"   {name:<12} step generated for {member}")
        out.append("")
        out.append(f"DSNH740I  PREPARATION JOB FOR {member} BUILT - SSID {self._ssid}")
        out.append(f"DSNE905I  JOB {self.userid}P SUBMITTED - HIGHEST RC={rc:02d}")
        return out

    # 4 - PRECOMPILE
    def _precomp_panel(self) -> ScreenBuffer:
        return self._func_frame("DB2I  ---  PRECOMPILE", [
            ("INPUT MEMBER  . . .", "MEMBER", 8, ""),
            ("DBRM LIBRARY  . . .", "DBRM", 30, f"{self.userid}.DBRMLIB"),
            ("HOST LANGUAGE . . .", "LANG", 8, "COBOL"),
        ], "MEMBER")

    def _gen_precomp(self, pi: PanelInput):
        member = pi.stripped("MEMBER").upper()
        if not member:
            self._message = "DSNE390I ENTER AN INPUT MEMBER NAME"
            return None
        dbrm = pi.stripped("DBRM").upper() or f"{self.userid}.DBRMLIB"
        lang = pi.stripped("LANG").upper() or "COBOL"
        return [
            f"DB2I PRECOMPILE  ---  {member}   ({lang})", "",
            f"DSNH050I  DSNHPC PRECOMPILER ENTERED FOR {member}",
            "DSNH104I  SQL STATEMENTS PROCESSED",
            f"DSNH010I  DBRM MEMBER {member} STORED IN {dbrm}",
            "DSNH772I  HIGHEST RETURN CODE WAS 0",
            "", f"DSNE905I  PRECOMPILE OF {member} COMPLETE",
        ]

    # 5 - BIND / REBIND / FREE
    def _bind_panel(self) -> ScreenBuffer:
        return self._func_frame("DB2I  ---  BIND / REBIND / FREE", [
            ("ACTION (BIND/REBIND/FREE)", "ACT", 8, "BIND"),
            ("OBJECT (PLAN/PACKAGE) . .", "OBJ", 8, "PLAN"),
            ("NAME  . . . . . . . . . .", "NAME", 8, ""),
            ("OWNER . . . . . . . . . .", "OWNER", 8, ""),
            ("QUALIFIER . . . . . . . .", "QUAL", 8, ""),
        ], "NAME", hints=[
            "Catalog plans  : " + ", ".join(self.db2.plans()[:8]),
            "Catalog packages: " + ", ".join(self.db2.packages()[:8]),
        ])

    def _gen_bind(self, pi: PanelInput):
        act = (pi.stripped("ACT") or "BIND").upper()
        obj = (pi.stripped("OBJ") or "PLAN").upper()
        name = pi.stripped("NAME").upper()
        if not name:
            self._message = "DSNE390I ENTER A PLAN OR PACKAGE NAME"
            return None
        owner = pi.stripped("OWNER").upper() or self.userid
        known = self.db2.plans() if obj.startswith("PLAN") else self.db2.packages()
        known_up = {k.upper() for k in known}
        exists = name in known_up
        out = [f"DB2I {act}  ---  {obj} {name}", ""]
        if act == "FREE":
            if not exists:
                self._message = f"DSNT200I  {obj} {name} NOT FOUND IN CATALOG"
                return None
            out += [f"DSNT233I  {obj} {name} FREED",
                    f"DSNX150I  FREE FOR {name} SUCCESSFUL"]
        elif act == "REBIND":
            if not exists:
                self._message = f"DSNT200I  {obj} {name} NOT FOUND - CANNOT REBIND"
                return None
            out += [f"DSNT232I  {obj} {name} REBOUND - OWNER {owner}",
                    f"DSNX125I  REBIND FOR {name} SUCCESSFUL, RC=0"]
        else:
            verb = "REPLACED" if exists else "BOUND"
            out += [f"DSNT231I  {obj} {name} {verb} - OWNER {owner}",
                    f"DSNX100I  BIND FOR {name} SUCCESSFUL, RC=0"]
        out += ["", f"Catalog {obj.lower()}s: " + ", ".join(known[:8])]
        out += [f"DSNE905I  {act} COMPLETE - SSID {self._ssid}"]
        return out

    # 6 - RUN
    def _runp_panel(self) -> ScreenBuffer:
        return self._func_frame("DB2I  ---  RUN", [
            ("PROGRAM NAME  . . .", "PROG", 8, ""),
            ("PLAN NAME . . . . .", "PLAN", 8, ""),
            ("PARAMETERS  . . . .", "PARM", 30, ""),
        ], "PROG", hints=["Catalog plans  : " + ", ".join(self.db2.plans()[:8])])

    def _gen_runp(self, pi: PanelInput):
        prog = pi.stripped("PROG").upper()
        if not prog:
            self._message = "DSNE390I ENTER A PROGRAM NAME"
            return None
        plan = pi.stripped("PLAN").upper() or prog
        plans = self.db2.plans()
        if plan not in {p.upper() for p in plans}:
            self._message = (f"DSNE391I PLAN {plan} NOT IN CATALOG. KNOWN: "
                             + ", ".join(plans[:6]))[:78]
            return None
        return [
            f"DB2I RUN  ---  PROGRAM {prog}  PLAN {plan}", "",
            f"DSN SYSTEM({self._ssid})",
            f"RUN PROGRAM({prog}) PLAN({plan})",
            f"DSNE901I  PROGRAM {prog} RUNNING UNDER PLAN {plan}",
            f"DSNE902I  PROGRAM {prog} ENDED - RC=0",
            "", "DSN9022I  DSNTEP2 'RUN' NORMAL COMPLETION",
        ]

    # 8 - UTILITIES
    def _util_panel(self) -> ScreenBuffer:
        return self._func_frame("DB2I  ---  DB2 UTILITIES", [
            ("UTILITY (RUNSTATS/REORG/COPY/LOAD/CHECK)", "UTIL", 10, "RUNSTATS"),
            ("OBJECT TYPE (TABLESPACE/INDEX)  . . . . .", "OTYPE", 12, "TABLESPACE"),
            ("OBJECT NAME . . . . . . . . . . . . . . .", "ONAME", 20, "GIBDB.EMPLOYE"),
            ("UTILITY ID  . . . . . . . . . . . . . . .", "UID", 16, ""),
        ], "UTIL")

    def _gen_util(self, pi: PanelInput):
        util = (pi.stripped("UTIL") or "RUNSTATS").upper()
        otype = (pi.stripped("OTYPE") or "TABLESPACE").upper()
        oname = pi.stripped("ONAME").upper()
        if not oname:
            self._message = "DSNU050I  ENTER AN OBJECT NAME"
            return None
        uid = pi.stripped("UID").upper() or f"{self.userid}.{util[:4]}"
        valid = {"RUNSTATS", "REORG", "COPY", "LOAD", "CHECK", "QUIESCE", "RECOVER"}
        if util not in valid:
            self._message = f"DSNU050I  UNKNOWN UTILITY '{util}'"
            return None
        return [
            f"DB2 UTILITY  ---  {util}  {otype} {oname}", "",
            f"DSNU000I  DSNUGUTC - OUTPUT START FOR UTILITY, UTILID = {uid}",
            f"DSNU050I  DSNUGUTC - {util} {otype} {oname}",
            f"DSNU010I  DSNUGBAC - UTILITY EXECUTION COMPLETE, HIGHEST RETURN CODE=0",
            "", f"DSNE905I  {util} COMPLETE - SSID {self._ssid}",
        ]

    # ---------------------------------------------------------------- OUT
    def _out_panel(self, to_bottom: bool = False) -> ScreenBuffer:
        self._scroll = ScrollList(self.lines, height=_OUTPUT_ROWS)
        if to_bottom:
            self._scroll.to_bottom()
        return self._render_out()

    def _render_out(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        (self._scroll or ScrollList(self.lines, height=_OUTPUT_ROWS)).render_into(
            s, 1, left=1, width=79, colour=colors.GREEN)
        s.put(22, 1, (self._scroll.position_label if self._scroll else "").ljust(20), colors.BLUE)
        s.put(24, 1, "F1=Help  F3=Exit  F7=Up  F8=Down  F12=Cancel  PA2=Reshow", colors.BLUE)
        s.set_cursor(24, 1)
        return s

    def _handle_out(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = self._out_return
            return self._spufi_panel() if self._out_return == _SPUFI else self._menu_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self._scroll is None:
                self._scroll = ScrollList(self.lines, height=_OUTPUT_ROWS)
            self._scroll.scroll(pi.key)
            return self._render_out()
        return self._render_out()

    # ---------------------------------------------------------------- CMD
    def _cmd_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "DB2 COMMANDS", colors.WHITE)
        s.put(3, 2, "Enter a DB2 command (e.g. -DISPLAY GROUP), then press ENTER:", colors.GREEN)
        if self.lines:
            ScrollList(self.lines, height=14).render_into(s, 6, left=2, width=77, colour=colors.GREEN)
        s.put(22, 1, "-DB2 ===>", colors.WHITE)
        s.add_field("CMD", 22, 11, 66, colour=_TURQ, role="command")
        s.put(24, 1, "F1=Help  F3=Exit  F12=Cancel", colors.BLUE)
        s.set_cursor(22, 11)
        return s

    def _handle_cmd(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _MENU
            self.lines = []
            return self._menu_panel()
        cmd = pi.stripped("CMD")
        if cmd:
            up = cmd.upper().lstrip("-").strip()
            try:
                if up.startswith("DISPLAY GROUP"):
                    out = self.db2.display_group()
                else:
                    out = self.db2.shell_command(cmd, self.userid)
            except Exception as exc:
                out = f"DSNE???I {exc}"
            self.lines = [f"-{cmd}".rstrip()] + [l.rstrip() for l in text_to_lines(out)]
        return self._cmd_panel()

    # ------------------------------------------------------------ DEFAULTS
    def _defaults_panel(self) -> ScreenBuffer:
        p = Panel(title="DB2I DEFAULTS", cursor="SSID")
        p.add(Label(4, 2, "DB2 NAME (SSID)        ===>", colors.GREEN))
        p.add(Field("SSID", 4, 30, 4, value=self._ssid, colour=_TURQ))
        p.add(Label(6, 2, "SQL ID                 ===>", colors.GREEN))
        p.add(Field("SQLID", 6, 30, 8, value=self.userid, colour=_TURQ))
        p.pfkeys = "F1=Help  F3=Exit (saves)  F12=Cancel"
        return p.render()
