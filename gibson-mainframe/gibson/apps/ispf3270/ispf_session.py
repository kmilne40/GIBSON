"""M4 - ISPF core in authentic EBCDIC 3270.

Phase-0 ``PanelSession``.  Stage A: dialog spine (primary menu, jump ``=x``,
PF3 navigation, scroll, message line), Settings (0), Command (6).  Stage B:
Utilities (3) -> Data Set List 3.4 with line commands, PDS member lists, and a
read-only Browse with FIND/LOCATE.

Storage is reused (``state.datasets``: ``listcat`` / ``read``); the TSO command
engine is reused for option 6.  This module is presentation + navigation only.
"""
from __future__ import annotations

import re
from typing import List, Optional

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import Panel, Label, Field, PanelInput, PanelSession, ScrollList, text_to_lines
from gibson.apps.tso import TsoCommandProcessor

_PRIMARY = "PRIMARY"
_SETTINGS = "SETTINGS"
_COMMAND = "COMMAND"
_CMDOUT = "CMDOUT"
_EDIT_ENTRY = "EDIT_ENTRY"
_UTIL = "UTIL"
_DSL_ENTRY = "DSL_ENTRY"
_DSLIST = "DSLIST"
_MEMBERS = "MEMBERS"
_BROWSE = "BROWSE"
_RSSREAD = "RSSREAD"
_LYNX = "LYNX"
_OUTLIST = "OUTLIST"
_DSUTIL = "DSUTIL"
_DSALLOC = "DSALLOC"
_MOVECOPY = "MOVECOPY"
_RACF = "RACF"
_ZSEC = "ZSEC"
_ENDV = "ENDV"
_IMSP = "IMSP"
_MGMT = "MGMT"
_ENDVFG = "ENDVFG"
_LANGPROC = "LANGPROC"

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)


def _endv_line_colour(line: str) -> str:
    """Colour an Endevor body line the way an authentic ISPF/Endevor panel would:
    white titles, blue column headers, green menu options, turquoise data rows,
    yellow informational messages, red errors."""
    s = line.rstrip()
    u = s.strip().upper()
    if not u:
        return colors.GREEN
    # errors / denials
    if any(w in u for w in ("ERROR", "INVALID", "NOT FOUND", "FAILED", "DENIED", "E  ", "0000E")):
        if u[:1].isalpha() and ("E " in u or "ERROR" in u or "INVALID" in u or "FAILED" in u or "DENIED" in u):
            return colors.RED
    # C1 informational messages (C1nnnnI / *** ... ***) -> yellow
    if re.match(r"^C1[A-Z]?\d", u) or (u.startswith("***") and u.endswith("***")):
        return colors.YELLOW
    # titles / banners
    if "ENDEVOR" in u and ("OPTION" in u or "SCM" in u or "MENU" in u):
        return colors.WHITE
    # menu option rows: a 1-2 char option code then a label
    if re.match(r"^\s*[0-9]{1,2}\s+\S", s) or re.match(r"^\s*[A-Z]\s{2,}\S", s):
        return colors.GREEN
    # column-header rows: all-caps, several columns separated by 2+ spaces
    if re.match(r"^[A-Z0-9 #/_\-\.]+$", s) and "  " in s and len(s.split()) >= 3:
        return colors.BLUE
    # default: data rows
    return _TURQ
_LIST_ROWS = 15
_BROWSE_ROWS = 18

# Authentic ISPF function-key legends (two lines, rows 23-24, like real z/OS).
_PF_MENU = ("F1=Help  F2=Split  F3=Exit  F7=Up  F8=Down  F9=Swap\n"
            "F10=Actions  F12=Cancel")
_PF_SCROLL = ("F1=Help  F2=Split  F3=Exit  F5=Rfind  F7=Up  F8=Down  F9=Swap\n"
              "F10=Left  F11=Right  F12=Cancel")
_PF_SIMPLE = "F1=Help  F2=Split  F3=Exit  F9=Swap  F12=Cancel"


def _scroll_primary(scroll, cmd: str) -> bool:
    """Handle ISPF/SDSF scroll primary commands (TOP/BOTTOM/MAX). Returns True if handled."""
    if scroll is None:
        return False
    u = (cmd or "").strip().upper()
    if u in ("TOP", "T", "U MAX", "UP MAX", "MAX UP", "M UP"):
        scroll.to_top(); return True
    if u in ("BOTTOM", "BOT", "BO", "D MAX", "DOWN MAX", "MAX DOWN", "M DOWN", "MAX", "M"):
        scroll.to_bottom(); return True
    return False


def _put_pfkeys(s, legend: str) -> None:
    """Render a one- or two-line F-key legend on rows 23-24."""
    parts = legend.split("\n")
    if len(parts) == 1:
        s.put(24, 1, parts[0][:79], colors.BLUE)
    else:
        s.put(23, 1, parts[0][:79], colors.BLUE)
        s.put(24, 1, parts[1][:79], colors.BLUE)

_PRIMARY_OPTIONS = [
    ("0", "Settings", "Terminal and user parameters"),
    ("1", "View", "Display source data or listings"),
    ("2", "Edit", "Create or change source data"),
    ("3", "Utilities", "Perform utility functions"),
    ("4", "Foreground", "Interactive language processing"),
    ("5", "Batch", "Submit job for language processing"),
    ("6", "Command", "Enter TSO or Workstation commands"),
    ("7", "Dialog Test", "Perform dialog testing"),
    ("8", "Outlist", "Display, delete, or print held job output"),
    ("S", "SDSF", "System Display and Search Facility"),
    ("12", "DB2", "DB2I primary option menu / SPUFI"),
    ("R", "RACF", "Security administration panels"),
    ("M", "Management", "zSecure, SMP/E, SYSVIEW, Endevor, EZRecon"),
    ("I", "IMS", "IMS Connect / OTMA security lab"),
    ("X", "Exit", "Terminate ISPF using log/list defaults"),
]
# Compact descriptions used when the right-hand information panel is shown.
_PRIMARY_SHORT = {
    "0": "Terminal and user params", "1": "Display source data/listings",
    "2": "Create or change source", "3": "Perform utility functions",
    "4": "Interactive lang proc", "5": "Submit job for processing",
    "6": "Enter TSO/Workstation cmds", "7": "Perform dialog testing",
    "8": "Display/print held output", "S": "System Display and Search",
    "12": "DB2I primary menu / SPUFI", "R": "Security admin panels",
    "M": "Management menu", "E": "CA Endevor SCM", "I": "IMS Connect / OTMA", "X": "Terminate ISPF",
}
_RACF_MENU = [
    ("1", "DATA SET PROFILES"),
    ("2", "GENERAL RESOURCE PROFILES"),
    ("3", "GROUP PROFILES AND USER-TO-GROUP CONNECTIONS"),
    ("4", "USER PROFILES AND YOUR OWN PASSWORD"),
    ("5", "SYSTEM OPTIONS"),
    ("6", "REMOTE SHARING FACILITY"),
    ("7", "DIGITAL CERTIFICATES, KEY RINGS, AND TOKENS"),
]
_ZSEC_MENU = [
    ("AU",   "Audit - Status Audit",    "Status audit report (concerns by priority)", "AUDIT"),
    ("RA.S", "RACF - SETROPTS",         "System options, password and class settings", "SETROPTS"),
    ("AU.P", "Audit - Privileged",      "SPECIAL / OPERATIONS / AUDITOR holders",      "PRIVILEGE"),
    ("AU.U", "Audit - UID(0)",          "z/OS UNIX superuser (UID 0) holders",         "UID0"),
    ("EV",   "Events - SMF",            "SMF type-80 security events",                  "EVENTS"),
    ("CO",   "Compliance",              "Compliance / drift summary",                  "COMPLIANCE"),
    ("SE",   "Setup",                   "Input files (CKFREEZE / UNLOAD / live)",      "SETUP"),
]


def _racf_user_cmd(opt, f):
    uid = f.get("USERID", ""); pw = f.get("PASSWORD", ""); name = f.get("NAME", ""); attr = f.get("ATTR", "")
    if not uid:
        return None
    if opt in ("", "L"):
        return f"LISTUSER {uid} ALL"
    if opt == "A":
        cmd = f"ADDUSER {uid}"
        if pw:
            cmd += f" PASSWORD({pw})"
        if name:
            cmd += f" NAME('{name}')"
        if attr:
            cmd += f" {attr}"
        return cmd
    if opt == "C":
        return f"ALTUSER {uid} {attr}".strip()
    if opt == "D":
        return f"DELUSER {uid}"
    if opt == "P":
        return f"ALTUSER {uid} PASSWORD({pw or 'TEMP0000'})"
    if opt == "R":
        return f"ALTUSER {uid} REVOKE"
    if opt == "E":
        return f"ALTUSER {uid} RESUME"
    return None


def _racf_group_cmd(opt, f):
    grp = f.get("GROUP", ""); uid = f.get("USERID", "")
    if not grp:
        return None
    if opt in ("", "L"):
        return f"LISTGRP {grp}"
    if opt == "A":
        return f"ADDGROUP {grp}"
    if opt == "D":
        return f"DELGROUP {grp}"
    if opt == "CO":
        return f"CONNECT {uid} GROUP({grp})"
    if opt == "RE":
        return f"REMOVE {uid} GROUP({grp})"
    return None


def _racf_dsd_cmd(opt, f):
    prof = f.get("PROFILE", ""); uacc = f.get("UACC", "NONE"); idv = f.get("ID", ""); acc = f.get("ACCESS", "READ")
    if not prof:
        return None
    if opt in ("", "L"):
        return f"LISTDSD DATASET('{prof}') ALL"
    if opt == "A":
        return f"ADDSD '{prof}' UACC({uacc})"
    if opt == "C":
        return f"ALTDSD '{prof}' UACC({uacc})"
    if opt == "P":
        return f"PERMIT '{prof}' ID({idv}) ACCESS({acc})"
    return None


def _racf_genres_cmd(opt, f):
    cls = f.get("CLASS", ""); prof = f.get("PROFILE", ""); uacc = f.get("UACC", "NONE")
    idv = f.get("ID", ""); acc = f.get("ACCESS", "READ")
    if not cls or not prof:
        return None
    if opt in ("", "L"):
        return f"RLIST {cls} {prof} ALL"
    if opt == "A":
        return f"RDEFINE {cls} {prof} UACC({uacc})"
    if opt == "C":
        return f"RALTER {cls} {prof} UACC({uacc})"
    if opt == "P":
        return f"PERMIT {prof} CLASS({cls}) ID({idv}) ACCESS({acc})"
    return None


def _racf_search_cmd(opt, f):
    cls = f.get("CLASS", "USER"); mask = f.get("MASK", "")
    if mask:
        return f"SEARCH CLASS({cls}) MASK({mask})"
    return f"SEARCH CLASS({cls})"


# view -> (title, action legend, [(field,label,width,default)], builder)
_RACF_VIEWS = {
    "USER": ("RACF User Profile Administration",
             "L List  A Add  C Alter  D Delete  P Reset pw  R Revoke  E Resume",
             [("USERID", "User ID  . . . .", 8, ""), ("NAME", "Name . . . . . .", 20, ""),
              ("PASSWORD", "Password . . . .", 8, ""),
              ("ATTR", "Attributes . . .", 30, "")],
             _racf_user_cmd),
    "GROUP": ("RACF Group Profile Administration",
              "L List  A Add  D Delete  CO Connect user  RE Remove user",
              [("GROUP", "Group  . . . . .", 8, ""), ("USERID", "User ID  . . . .", 8, "")],
              _racf_group_cmd),
    "DSD": ("RACF Data Set Profile Administration",
            "L List  A Add  C Alter  P Permit",
            [("PROFILE", "Profile  . . . .", 44, ""), ("UACC", "UACC . . . . . .", 8, "NONE"),
             ("ID", "Permit ID  . . .", 8, ""), ("ACCESS", "Access . . . . .", 8, "READ")],
            _racf_dsd_cmd),
    "GENRES": ("RACF General Resource Administration",
               "L List  A Define  C Alter  P Permit",
               [("CLASS", "Class  . . . . .", 8, ""), ("PROFILE", "Profile  . . . .", 40, ""),
                ("UACC", "UACC . . . . . .", 8, "NONE"), ("ID", "Permit ID  . . .", 8, ""),
                ("ACCESS", "Access . . . . .", 8, "READ")],
               _racf_genres_cmd),
    "SEARCH": ("RACF Search",
               "Enter a class (USER GROUP DATASET FACILITY ...) and optional mask",
               [("CLASS", "Class  . . . . .", 8, "USER"), ("MASK", "Mask . . . . . .", 20, "")],
               _racf_search_cmd),
}

_UTIL_OPTIONS = [
    ("1", "Library", "Compress or print data set; print index listing"),
    ("2", "Data Set", "Allocate, rename, delete, catalog, uncatalog"),
    ("3", "Move/Copy", "Move or copy members or data sets"),
    ("4", "Dslist", "Print or display (to process) list of data sets"),
    ("5", "Reset", "Reset statistics for members of ISPF library"),
]


class Ispf3270Session(PanelSession):
    def __init__(self, state, peer_addr: str = "", userid: str = "IBMUSER"):
        self.state = state
        self.peer_addr = peer_addr or ""
        self.userid = (userid or "IBMUSER").upper()
        self._tso = TsoCommandProcessor(state, self.userid)
        self._screen = _PRIMARY
        self._message = ""
        # context
        self.cmd_lines: List[str] = []
        self.cmd_history: List[str] = []   # commands entered (retrieve list)
        self.cmd_out_lines: List[str] = []  # last command output (output panel)
        self._cmdout_top: int = 0
        self._pending_cmd: str = ""        # value to pre-fill the command line (retrieve)
        self._retrieve_rows: dict = {}     # screen-row -> command, for cursor retrieve
        self.dsl_prefix = self.userid
        self.dsl_rows: list = []
        self.dsl_scroll: Optional[ScrollList] = None
        self.mem_ds = None
        self.mem_names: List[str] = []
        self.mem_scroll: Optional[ScrollList] = None
        self.browse_title = ""
        self.browse_lines: List[str] = []
        self.browse_scroll: Optional[ScrollList] = None
        self.rss_scroll: Optional[ScrollList] = None
        self.rss_return = _PRIMARY
        self.rss_mode = "LIST"
        self.rss_title = "CTI RSS FEEDS"
        self.rss_lines: list = []
        self._rss_links: list = []
        self.browse_return = _DSLIST
        self.editor = None
        self.editor_return = _DSLIST
        self._edit_spec = ""
        self._edit_is_new = False
        self.subapp = None  # nested SDSF/DB2I launched from the primary menu
        self._racf_view = "MENU"
        self._racf_output: List[str] = []
        self._racf_outscroll: Optional[ScrollList] = None
        self._endv_scroll: Optional[ScrollList] = None
        self._endvfg_fields: dict = {}
        self._endvfg_scroll: Optional[ScrollList] = None
        self._ims_scroll: Optional[ScrollList] = None
        self._racf_fld: dict = {}
        self._lp_mode = "FG"
        self._lp_output: List[str] = []
        self._lp_scroll: Optional[ScrollList] = None
        self._lp_src = ""

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        return self._primary_panel()

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if self.subapp is not None:
            screen = self.subapp.handle(pi)
            if screen is None:  # nested app ended -> back to launch context
                self.subapp = None
                self._screen = getattr(self, "_subapp_return", _PRIMARY)
                self._subapp_return = _PRIMARY
                return self._current_panel()
            return screen
        if self.editor is not None:
            screen = self.editor.handle(pi)
            if screen is None:  # editor ended -> return to originating list
                self.editor = None
                self._screen = self.editor_return
                return self._dslist_panel() if self.editor_return == _DSLIST else self._members_panel()
            return screen
        # Global jump: =x from any panel
        jumped = self._maybe_jump(pi)
        if jumped is not None:
            return jumped
        # PA2 = Reshow (redisplay current panel); PA1 = Attention (also redisplay)
        if pi.key in ("PA1", "PA2"):
            return self._current_panel()
        method = {
            _PRIMARY: self._h_primary, _SETTINGS: self._h_settings,
            _COMMAND: self._h_command, _CMDOUT: self._h_cmdout, _EDIT_ENTRY: self._h_edit_entry, _UTIL: self._h_util,
            _DSL_ENTRY: self._h_dsl_entry, _DSLIST: self._h_dslist,
            _MEMBERS: self._h_members, _BROWSE: self._h_browse,
            _RSSREAD: self._h_rssread,
            _LYNX: self._h_lynx,
            _OUTLIST: self._h_outlist,
            _DSUTIL: self._h_dsutil, _MOVECOPY: self._h_movecopy,
            _DSALLOC: self._h_alloc,
            _RACF: self._h_racf, _ZSEC: self._h_zsec,
            _ENDV: self._h_endv,
            _IMSP: self._h_ims,
            _MGMT: self._h_mgmt,
            _ENDVFG: self._h_endvfg,
            _LANGPROC: self._h_langproc,
        }.get(self._screen)
        return method(pi) if method else None

    # --------------------------------------------------------------- jump
    def _current_panel(self) -> ScreenBuffer:
        return {
            _PRIMARY: self._primary_panel, _SETTINGS: self._settings_panel,
            _COMMAND: self._command_panel, _CMDOUT: self._cmdout_panel, _EDIT_ENTRY: self._edit_entry_panel, _UTIL: self._util_panel,
            _DSL_ENTRY: self._dsl_entry_panel, _DSLIST: self._dslist_panel,
            _MEMBERS: self._members_panel, _BROWSE: self._browse_panel,
            _RSSREAD: self._rssread_panel,
            _LYNX: self._lynx_panel,
            _OUTLIST: self._outlist_panel,
            _DSUTIL: self._dsutil_panel, _MOVECOPY: self._movecopy_panel,
            _DSALLOC: self._alloc_panel,
            _RACF: self._racf_panel, _ZSEC: self._zsec_panel,
            _ENDV: self._endv_panel,
            _IMSP: self._ims_panel,
            _MGMT: self._mgmt_panel,
            _ENDVFG: self._endvfg_panel,
            _LANGPROC: self._langproc_panel,
        }.get(self._screen, self._primary_panel)()

    def _maybe_jump(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        # command-line jump appears in OPTION or COMMAND fields
        raw = pi.stripped("OPTION") or pi.stripped("COMMAND") or pi.stripped("CMD")
        if not raw.startswith("="):
            return None
        target = raw[1:].strip().upper()
        self._message = ""
        return self._dispatch_option(target.split(".")[0], rest=target)

    def _dispatch_option(self, opt: str, rest: str = "") -> Optional[ScreenBuffer]:
        opt = opt.upper()
        if opt in ("X", ""):
            return None if opt == "X" else self._primary_panel()
        if opt == "0":
            self._screen = _SETTINGS
            return self._settings_panel()
        if opt in ("1", "2"):
            # View/Edit: from primary, prompt via DSLIST entry (then B/E)
            self._screen = _DSL_ENTRY
            return self._dsl_entry_panel(intent=("VIEW" if opt == "1" else "EDIT"))
        if opt == "3":
            sub = rest.split(".", 1)[1].strip() if "." in rest else ""
            return self._enter_util_sub(sub)
        if opt == "6":
            self._screen = _COMMAND
            return self._command_panel()
        if opt in ("RSS", "CTI", "RSSREAD"):  # ISPF RSS reader (CTI feeds)
            return self._rss_open_reader(return_to=_PRIMARY)
        if opt == "S":  # SDSF
            from gibson.apps.sdsf3270 import Sdsf3270Session
            self.subapp = Sdsf3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
            return self.subapp.initial_screen()
        if opt == "8":  # Outlist Utility - display/delete/print held job output
            self._screen = _OUTLIST
            return self._outlist_panel()
        if opt in ("12", "DB2", "L DB2", "LDB2"):  # DB2I primary option menu
            from gibson.apps.db2i3270 import Db2i3270Session
            self.subapp = Db2i3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
            return self.subapp.initial_screen()
        if opt in ("DSN", "L DSN", "LDSN"):  # DB2I DSN command processor
            from gibson.apps.db2i3270 import Db2i3270Session
            self.subapp = Db2i3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
            return self.subapp._enter_dsn()
        if opt == "R":  # RACF security administration panels
            self._screen = _RACF
            self._racf_view = "MENU"
            self._racf_output = []
            return self._racf_panel()
        if opt in ("M", "MGMT", "MANAGEMENT"):  # Management sub-menu
            self._screen = _MGMT
            sub = rest.split(".", 1)[1].strip().upper() if "." in rest else ""
            if sub:
                match = ({n: fn for n, _nm, _d, fn in self._MGMT_MENU}.get(sub)
                         or {nm.upper(): fn for _n, nm, _d, fn in self._MGMT_MENU}.get(sub))
                if match is not None:
                    return match(self)
            return self._mgmt_panel()
        if opt in ("ZSEC", "ZSECURE"):
            return self._open_zsec()
        if opt in ("E", "ENDEVOR", "NDVR"):  # CA Endevor SCM primary options
            return self._open_endevor()
        if opt in ("I", "IMS", "IMSCONN"):  # IMS Connect / OTMA security lab
            self._screen = _IMSP
            self._ims_scroll = None
            self._ims_run("IMS")               # render the IMS Connect primary panel
            return self._ims_panel()
        if opt in ("SV", "SYSVIEW", "SYSV"):  # CA SYSVIEW full-screen monitor
            return self._open_sysview()
        if opt in ("EZ", "EZRECON", "RECON"):  # EZRecon recon toolkit
            return self._open_ezrecon()
        if opt in ("4", "5"):  # Foreground / Batch language processing
            self._screen = _LANGPROC
            self._lp_mode = "FG" if opt == "4" else "BATCH"
            self._lp_output = []
            self._lp_scroll = None
            return self._langproc_panel()
        self._message = f"INVALID OPTION '{opt}'"
        self._screen = _PRIMARY
        return self._primary_panel()

    # ------------------------------------------------------------ PRIMARY
    def _primary_panel(self) -> ScreenBuffer:
        import datetime
        p = Panel(title="ISPF Primary Option Menu", cursor="OPTION")
        p.add(Label(2, 1, "Menu  Utilities  Compilers  Options  Status  Help", colors.BLUE))
        p.add(Label(4, 2, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 14, 20, colour=_TURQ))
        row = 6
        for num, name, _desc in _PRIMARY_OPTIONS:
            desc = _PRIMARY_SHORT.get(num, _desc)
            p.add(Label(row, 4, f"{num:<2} {name:<12} {desc}", colors.TURQUOISE))
            row += 1
        # Right-hand information panel (User ID / Time / Terminal / ...).
        info = [
            ("User ID . :", self.userid),
            ("Time. . . :", datetime.datetime.now().strftime("%H:%M")),
            ("Terminal. :", "3278"),
            ("Screen. . :", "1"),
            ("Language. :", "ENGLISH"),
            ("Appl ID . :", "ISR"),
            ("TSO logon :", "ISPFPROC"),
            ("TSO prefix:", self.userid),
            ("System ID :", "S0W1"),
            ("MVS acct. :", "ACCT#"),
            ("Release . :", "ISPF 7.5"),
        ]
        for i, (label, value) in enumerate(info):
            p.add(Label(6 + i, 52, label, colors.GREEN))
            p.add(Label(6 + i, 64, value, colors.WHITE))
        p.add(Label(row + 1, 4, "Enter X to Terminate using log/list defaults", colors.BLUE))
        p.pfkeys = _PF_MENU
        if self._message:
            p.message = self._message
        return p.render()

    def _h_primary(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            return None
        opt = pi.stripped("OPTION").upper()
        if not opt:
            return self._primary_panel()
        # support "3.4" entered directly
        head = opt.split(".")[0]
        return self._dispatch_option(head, rest=opt)

    # ----------------------------------------------------------- SETTINGS
    def _settings_panel(self) -> ScreenBuffer:
        p = Panel(title="ISPF Settings", cursor="OPT")
        p.add(Label(3, 2, "Options", colors.WHITE))
        for i, opt in enumerate([
            "Enter \"/\" to select option",
            "_ Command line at bottom",
            "/ Panel display CUA mode",
            "/ Long message in pop-up",
            "_ Tab to action bar choices",
        ]):
            p.add(Label(5 + i, 4, opt, colors.TURQUOISE))
        p.add(Label(12, 2, "Terminal Characteristics", colors.WHITE))
        p.add(Label(13, 4, "Screen format . . 2  (1=Data, 2=Std, 3=Max, 4=Part)", colors.TURQUOISE))
        p.add(Label(14, 4, "Terminal type . . 3278", colors.TURQUOISE))
        p.add(Field("OPT", 13, 22, 2, colour=_TURQ))
        p.pfkeys = _PF_SIMPLE
        return p.render()

    def _h_settings(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15") or pi.key == "ENTER":
            self._screen = _PRIMARY
            return self._primary_panel()
        return self._settings_panel()

    # ------------------------------------------------------------ COMMAND
    _RETR_TOP_ROW = 10
    _RETR_HEIGHT = 13

    def _command_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 2, "Menu  List  Mode  Functions  Utilities  Help", colors.WHITE)
        s.put(3, 31, "ISPF Command Shell", _TURQ)
        s.put(4, 1, "Enter TSO commands below:", colors.GREEN)
        s.put(6, 1, "===>", colors.WHITE)
        s.add_field("CMD", 6, 6, 72, value=self._pending_cmd, colour=_TURQ, role="command")
        self._pending_cmd = ""
        s.put(8, 1, "Place cursor on choice and press enter to Retrieve command", colors.GREEN)
        # retrieve list: command history, most recent at the bottom (z/OS order)
        self._retrieve_rows = {}
        hist = self.cmd_history[-self._RETR_HEIGHT:]
        for i, c in enumerate(hist):
            row = self._RETR_TOP_ROW + i
            s.put(row, 1, ("=> " + c)[:79], _TURQ)
            self._retrieve_rows[row] = c
        _put_pfkeys(s, _PF_SIMPLE)
        s.set_cursor(6, 6)
        return s

    def _cmdout_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        scroll = ScrollList(self.cmd_out_lines or ["READY"], height=20, top=self._cmdout_top)
        scroll.render_into(s, 1, left=1, width=79, colour=colors.GREEN)
        self._cmdout_top = scroll.top
        s.put(22, 1, scroll.position_label.ljust(20), colors.BLUE)
        s.put(23, 1, "***", colors.WHITE)
        s.put(24, 1, "F3=Return  ENTER=Return  F7=Backward  F8=Forward", colors.BLUE)
        s.set_cursor(23, 5)
        return s

    def _h_cmdout(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            scroll = ScrollList(self.cmd_out_lines or ["READY"], height=20, top=self._cmdout_top)
            scroll.scroll(pi.key)
            self._cmdout_top = scroll.top
            return self._cmdout_panel()
        self._screen = _COMMAND
        return self._command_panel()

    def _h_command(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        cmd = pi.stripped("CMD")
        if not cmd:
            # ENTER on an empty command line: retrieve the command under the cursor
            row = (pi.cursor or (None, None))[0]
            if row in self._retrieve_rows:
                self._pending_cmd = self._retrieve_rows[row]
            return self._command_panel()
        self.cmd_history.append(cmd)
        if len(self.cmd_history) > 60:
            self.cmd_history = self.cmd_history[-60:]
        try:
            out = self._tso.run(cmd)
        except Exception as exc:
            out = f"IKJ56500I {exc}"
        if isinstance(out, str) and out.startswith("GIBSON-INTERACTIVE:"):
            target = out.split(":", 1)[1].strip().upper()
            out = (f"{target} is an interactive command - enter it at the "
                   f"TSO READY prompt (=X then {target}), not the ISPF shell.")
        # show the command output on its own TSO output panel (authentic option 6)
        self.cmd_out_lines = ["READY", cmd] + [l.rstrip() for l in text_to_lines(out)] + ["READY"]
        self._cmdout_top = max(0, len(self.cmd_out_lines) - 20)
        self._screen = _CMDOUT
        return self._cmdout_panel()

    # --------------------------------------------------------------- UTIL
    def _util_panel(self) -> ScreenBuffer:
        p = Panel(title="Utility Selection Menu", cursor="OPTION")
        p.add(Label(4, 2, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 14, 8, colour=_TURQ))
        row = 6
        for num, name, desc in _UTIL_OPTIONS:
            p.add(Label(row, 4, f"{num}  {name:<10} {desc}", colors.TURQUOISE))
            row += 1
        p.pfkeys = _PF_SIMPLE
        if self._message:
            p.message = self._message
        return p.render()

    def _enter_util_sub(self, sub: str) -> Optional[ScreenBuffer]:
        """Route a 3.x utility selection to its panel."""
        sub = (sub or "").strip().upper()
        if sub in ("2", "DS", "DATASET"):
            self._screen = _DSUTIL
            return self._dsutil_panel()
        if sub in ("3", "MC", "MOVE", "COPY"):
            self._screen = _MOVECOPY
            return self._movecopy_panel()
        if sub in ("4", "DSLIST", "DSLIST"):
            self._screen = _DSL_ENTRY
            return self._dsl_entry_panel()
        if sub in ("1", "LIBRARY"):
            self._screen = _UTIL
            self._message = "Library compress/print is a no-op in this lab system."
            return self._util_panel()
        if sub in ("5", "RESET"):
            self._screen = _UTIL
            self._message = "ISRZ000  Statistics reset (no-op in this lab system)."
            return self._util_panel()
        self._screen = _UTIL
        return self._util_panel()

    def _h_util(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        opt = pi.stripped("OPTION")
        if not opt:
            return self._util_panel()
        return self._enter_util_sub(opt)

    # ------------------------------------------------------ 3.2 DATA SET
    def _dsutil_panel(self) -> ScreenBuffer:
        p = Panel(title="Data Set Utility", cursor="OPTION")
        p.add(Label(2, 1, "Menu  RefList  Utilities  Help", colors.BLUE))
        p.add(Label(4, 1, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 13, 4, colour=_TURQ))
        p.add(Label(6, 4, "A Allocate new data set      C Catalog data set", colors.TURQUOISE))
        p.add(Label(7, 4, "R Rename entire data set     U Uncatalog data set", colors.TURQUOISE))
        p.add(Label(8, 4, "D Delete entire data set     S Short data set information", colors.TURQUOISE))
        p.add(Label(9, 4, "blank Data set information", colors.TURQUOISE))
        p.add(Label(11, 1, "ISPF Library:", colors.GREEN))
        p.add(Label(12, 4, "Project . . .", colors.GREEN))
        p.add(Field("PROJECT", 12, 18, 8,
                    value=getattr(self, "_dsutil_proj", self.userid), colour=_TURQ))
        p.add(Label(13, 4, "Group . . . .", colors.GREEN))
        p.add(Field("GROUP", 13, 18, 8, value=getattr(self, "_dsutil_group", ""), colour=_TURQ))
        p.add(Label(14, 4, "Type  . . . .", colors.GREEN))
        p.add(Field("TYPE", 14, 18, 8, value=getattr(self, "_dsutil_type", ""), colour=_TURQ))
        p.add(Label(16, 1, "Other Partitioned, Sequential or VSAM Data Set:", colors.GREEN))
        p.add(Label(17, 4, "Data Set Name . . .", colors.GREEN))
        p.add(Field("DSNAME", 17, 24, 44, value=getattr(self, "_dsutil_dsn", ""), colour=_TURQ))
        p.add(Label(18, 4, "Volume Serial . . .", colors.GREEN))
        p.add(Field("VOLSER", 18, 24, 6, value=getattr(self, "_dsutil_vol", ""), colour=_TURQ))
        p.add(Label(19, 6, "(If not cataloged, required for option \"C\")", colors.BLUE))
        p.add(Label(21, 4, "New Name (for rename) . .", colors.GREEN))
        p.add(Field("NEWNAME", 21, 30, 44, colour=_TURQ))
        p.pfkeys = _PF_SIMPLE
        if self._message:
            p.message = self._message
        return p.render()

    def _dsutil_resolve_dsn(self, pi: PanelInput) -> str:
        """Real ISPF 3.2: use the Other Data Set Name if given, else build the
        name from the ISPF Library Project.Group.Type fields."""
        other = pi.stripped("DSNAME")
        if other:
            return other
        parts = [x for x in (pi.stripped("PROJECT"), pi.stripped("GROUP"),
                             pi.stripped("TYPE")) if x]
        return ".".join(parts)

    def _h_dsutil(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _UTIL
            return self._util_panel()
        self._dsutil_proj = pi.stripped("PROJECT")
        self._dsutil_group = pi.stripped("GROUP")
        self._dsutil_type = pi.stripped("TYPE")
        self._dsutil_vol = pi.stripped("VOLSER")
        self._dsutil_dsn = pi.stripped("DSNAME")
        opt = (pi.stripped("OPTION") or "").upper()   # blank = data set information
        dsn = self._dsutil_resolve_dsn(pi)
        ds = self.state.datasets
        if not dsn:
            self._message = "ENTER A DATA SET NAME OR ISPF LIBRARY"
            return self._dsutil_panel()
        if opt == "A":                                # -> Allocate New Data Set panel
            self._alloc_dsn = dsn.upper()
            self._screen = _DSALLOC
            return self._alloc_panel(reset=True)
        try:
            if opt in ("", "S"):
                self._message = self._dataset_info(dsn)
            elif opt == "D":
                self._message = ds.delete(self.userid, dsn)
            elif opt == "C":
                self._message = ds.catalog(self.userid, dsn)
            elif opt == "U":
                self._message = ds.uncatalog(self.userid, dsn)
            elif opt == "R":
                newname = pi.stripped("NEWNAME")
                if not newname:
                    self._message = "ENTER A NEW NAME FOR RENAME"
                else:
                    self._rename_dataset(dsn, newname)
                    self._message = f"DATA SET RENAMED TO {newname.upper()}"
            else:
                self._message = f"INVALID OPTION '{opt}'"
        except FileNotFoundError:
            self._message = f"IDC3012I ENTRY {dsn.upper()} NOT FOUND"
        except PermissionError as exc:
            self._message = f"ICH408I ACCESS DENIED - {exc}"
        except Exception as exc:
            self._message = f"UTILITY ERROR: {exc}"
        return self._dsutil_panel()

    # ------------------------------------------- 3.2 A  ALLOCATE NEW DATA SET
    _ALLOC_DEFAULTS = {"VOLSER": "", "DEVTYPE": "", "MGMTCLAS": "", "STORCLAS": "",
                       "DATACLAS": "", "SPCU": "TRACKS", "AVGREC": "", "PRIQTY": "1",
                       "SECQTY": "1", "DIRBLK": "0", "RECFM": "FB", "LRECL": "80",
                       "BLKSIZE": "0", "DSNTYPE": "PDS"}

    def _alloc_panel(self, reset: bool = False) -> ScreenBuffer:
        if reset:
            self._alloc_fields = dict(self._ALLOC_DEFAULTS)
        f = getattr(self, "_alloc_fields", dict(self._ALLOC_DEFAULTS))
        p = Panel(title="Allocate New Data Set", cursor="VOLSER")
        p.add(Label(2, 1, "Menu  RefList  Utilities  Help", colors.BLUE))
        p.add(Label(4, 1, "Command ===>", colors.GREEN))
        p.add(Field("CMD", 4, 14, 30, colour=_TURQ))
        p.add(Label(6, 1, "Data Set Name . . . :", colors.GREEN))
        p.add(Label(6, 23, getattr(self, "_alloc_dsn", "")[:50], colors.TURQUOISE))
        rows = [
            (8, "Management class . . .", "MGMTCLAS", 8, "(Blank for default management class)"),
            (9, "Storage class  . . . .", "STORCLAS", 8, "(Blank for default storage class)"),
            (10, "Volume serial . . . .", "VOLSER", 6, "(Blank for system default volume)"),
            (11, "Device type . . . . .", "DEVTYPE", 8, "(Generic unit or device address)"),
            (12, "Data class . . . . . .", "DATACLAS", 8, "(Blank for default data class)"),
            (13, "Space units . . . . .", "SPCU", 7, "(BLKS TRKS CYLS KB MB BYTES RECORDS)"),
            (14, "Average record unit .", "AVGREC", 1, "(M, K, or U)"),
            (15, "Primary quantity  . .", "PRIQTY", 8, "(In above units)"),
            (16, "Secondary quantity  .", "SECQTY", 8, "(In above units)"),
            (17, "Directory blocks  . .", "DIRBLK", 8, "(Zero for sequential data set)"),
            (18, "Record format . . . .", "RECFM", 5, ""),
            (19, "Record length . . . .", "LRECL", 6, ""),
            (20, "Block size  . . . . .", "BLKSIZE", 6, ""),
            (21, "Data set name type  .", "DSNTYPE", 8, "(LIBRARY PDS LARGE BASIC or blank)"),
        ]
        numeric = {"PRIQTY", "SECQTY", "DIRBLK", "LRECL", "BLKSIZE"}
        for row, label, name, length, hint in rows:
            p.add(Label(row, 2, label, colors.GREEN))
            p.add(Field(name, row, 24, length, value=f.get(name, ""),
                        colour=_TURQ, numeric=(name in numeric)))
            if hint:
                p.add(Label(row, 24 + length + 2, hint, colors.BLUE))
        p.pfkeys = _PF_SIMPLE
        if self._message:
            p.message = self._message
        return p.render()

    _VALID_RECFM = {"F", "FB", "FBA", "FBM", "FA", "FM", "V", "VB", "VBA", "VBM",
                    "VA", "VM", "U", "VS", "VBS"}
    _VALID_SPCU = {"TRACKS", "TRKS", "TRK", "CYLS", "CYL", "CYLINDERS", "BLKS",
                   "BLOCKS", "KB", "MB", "BYTES", "RECORDS"}

    def _h_alloc(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15", "PF12"):         # cancel -> back, no allocation
            self._screen = _DSUTIL
            self._message = "ALLOCATE CANCELLED" if pi.key == "PF12" else ""
            return self._dsutil_panel()
        f = {k: pi.stripped(k) for k in self._ALLOC_DEFAULTS}
        self._alloc_fields = f                        # retain for redraw on error
        recfm = (f["RECFM"] or "FB").upper()
        if recfm not in self._VALID_RECFM:
            self._message = f"INVALID RECORD FORMAT '{recfm}'"
            return self._alloc_panel()
        spcu = (f["SPCU"] or "TRACKS").upper()
        if spcu not in self._VALID_SPCU:
            self._message = f"INVALID SPACE UNITS '{spcu}'"
            return self._alloc_panel()
        try:
            vals = {}
            for name, default in (("LRECL", 80), ("BLKSIZE", 0), ("PRIQTY", 1),
                                  ("SECQTY", 1), ("DIRBLK", 0)):
                raw = f[name] or str(default)
                if not raw.isdigit():
                    raise ValueError(f"{name} MUST BE NUMERIC")
                vals[name] = int(raw)
        except ValueError as exc:
            self._message = str(exc)
            return self._alloc_panel()
        dsntype = (f["DSNTYPE"] or "").upper()
        org = "PO" if (vals["DIRBLK"] > 0 or dsntype in ("LIBRARY", "PDS", "PDSE")) else "PS"
        try:
            info = self.state.datasets.allocate(
                self.userid, self._alloc_dsn, org=org, recfm=recfm, lrecl=vals["LRECL"],
                blksize=vals["BLKSIZE"], volume=(f["VOLSER"] or None), space_units=spcu,
                primary=vals["PRIQTY"], secondary=vals["SECQTY"], dirblks=vals["DIRBLK"],
                device=(f["DEVTYPE"] or None), mgmtclas=(f["MGMTCLAS"] or None),
                storclas=(f["STORCLAS"] or None), dataclas=(f["DATACLAS"] or None),
                dsntype=(dsntype or None))
        except PermissionError as exc:
            self._message = f"ICH408I ACCESS DENIED - {exc}"
            return self._alloc_panel()
        except Exception as exc:
            self._message = f"ALLOCATION FAILED: {exc}"
            return self._alloc_panel()
        self._screen = _DSUTIL
        self._dsutil_dsn = info.name
        self._message = f"DATA SET {info.name} ALLOCATED ({info.org})"
        return self._dsutil_panel()

    def _rename_dataset(self, dsn: str, newname: str) -> None:
        ds = self.state.datasets
        base, member = ds.split_name(dsn)
        meta = ds.meta(self.userid, base) or {}
        org = meta.get("ORG", "PO" if member else "PS")
        if member:
            content = ds.read(self.userid, dsn)
            ds.allocate(self.userid, f"{base}({newname})", org="PO")
            ds.write(self.userid, f"{base}({newname})", content)
            ds.delete(self.userid, dsn)
            return
        members = []
        try:
            members = ds.members(self.userid, base)
        except Exception:
            members = []
        ds.allocate(self.userid, newname, org=org,
                    recfm=meta.get("RECFM", "FB"), lrecl=int(meta.get("LRECL", 80)))
        if members:
            for m in members:
                ds.allocate(self.userid, f"{newname}({m})", org="PO")
                ds.write(self.userid, f"{newname}({m})", ds.read(self.userid, f"{base}({m})"))
        else:
            ds.write(self.userid, newname, ds.read(self.userid, base))
        ds.delete(self.userid, base)

    def _dataset_info(self, dsn: str) -> str:
        ds = self.state.datasets
        meta = ds.meta(self.userid, dsn) or {}
        base, _ = ds.split_name(dsn)
        org = meta.get("ORG", "?")
        return (f"DSORG={org} RECFM={meta.get('RECFM','FB')} "
                f"LRECL={meta.get('LRECL',80)} VOL={meta.get('VOLUME','WORK01')} "
                f"CATALOGED={meta.get('CATALOGED', True)}")

    # ------------------------------------------------------ 3.3 MOVE/COPY
    def _movecopy_panel(self) -> ScreenBuffer:
        p = Panel(title="Move/Copy Utility", cursor="OPTION")
        p.add(Label(2, 1, "Menu  RefList  Utilities  Help", colors.BLUE))
        p.add(Label(4, 2, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 14, 4, colour=_TURQ))
        p.add(Label(6, 4, "C Copy data set or member   M Move data set or member", colors.TURQUOISE))
        p.add(Label(8, 2, "From Data Set . . .", colors.GREEN))
        p.add(Field("FROM", 8, 22, 44, value=getattr(self, "_mc_from", ""), colour=_TURQ))
        p.add(Label(10, 2, "To   Data Set . . .", colors.GREEN))
        p.add(Field("TO", 10, 22, 44, value=getattr(self, "_mc_to", ""), colour=_TURQ))
        p.add(Label(12, 3, "Use name(member) to copy a single member; a bare PDS copies all.",
                    colors.GREEN))
        p.pfkeys = _PF_SIMPLE
        if self._message:
            p.message = self._message
        return p.render()

    def _h_movecopy(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _UTIL
            return self._util_panel()
        opt = (pi.stripped("OPTION") or "C").upper()
        src = pi.stripped("FROM")
        dst = pi.stripped("TO")
        self._mc_from, self._mc_to = src, dst
        if not src or not dst:
            self._message = "ENTER BOTH FROM AND TO DATA SET NAMES"
            return self._movecopy_panel()
        try:
            n = self._copy_dataset(src, dst)
            if opt == "M":
                self.state.datasets.delete(self.userid, self.state.datasets.split_name(src)[0]
                                           if self.state.datasets.split_name(src)[1] is None else src)
                self._message = f"MOVED {n} MEMBER(S)/RECORD SET FROM {src.upper()} TO {dst.upper()}"
            else:
                self._message = f"COPIED {n} MEMBER(S)/RECORD SET FROM {src.upper()} TO {dst.upper()}"
        except FileNotFoundError:
            self._message = f"IDC3012I ENTRY {src.upper()} NOT FOUND"
        except PermissionError as exc:
            self._message = f"ICH408I ACCESS DENIED - {exc}"
        except Exception as exc:
            self._message = f"MOVE/COPY ERROR: {exc}"
        return self._movecopy_panel()

    def _copy_dataset(self, src: str, dst: str) -> int:
        ds = self.state.datasets
        sbase, smember = ds.split_name(src)
        dbase, dmember = ds.split_name(dst)
        if smember:  # single member -> member or sequential
            content = ds.read(self.userid, src)
            target = dst if dmember else f"{dbase}({smember})"
            ds.allocate(self.userid, target, org="PO")
            ds.write(self.userid, target, content)
            return 1
        # whole dataset
        try:
            members = ds.members(self.userid, sbase)
        except Exception:
            members = []
        if members:
            for m in members:
                ds.allocate(self.userid, f"{dbase}({m})", org="PO")
                ds.write(self.userid, f"{dbase}({m})", ds.read(self.userid, f"{sbase}({m})"))
            return len(members)
        ds.allocate(self.userid, dbase, org="PS")
        ds.write(self.userid, dbase, ds.read(self.userid, sbase))
        return 1


    # ---------------------------------------------------------- DSL ENTRY
    def _dsl_entry_panel(self, intent: str = "") -> ScreenBuffer:
        self._dsl_intent = intent
        p = Panel(title="Data Set List Utility", cursor="DSLEVEL")
        p.add(Label(2, 1, "Menu  RefList  RefMode  Utilities  Help", colors.BLUE))
        p.add(Label(4, 2, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 14, 8, colour=_TURQ))
        p.add(Label(6, 3, "Dsname Level . . .", colors.TURQUOISE))
        p.add(Field("DSLEVEL", 6, 23, 44, value=self.dsl_prefix, colour=_TURQ))
        p.add(Label(7, 3, "Volume serial  . .", colors.TURQUOISE))
        p.add(Field("VOLUME", 7, 23, 6, colour=_TURQ))
        p.add(Label(9, 3, "Enter a Dsname Level and press ENTER to list data sets.", colors.GREEN))
        p.pfkeys = _PF_SCROLL
        if self._message:
            p.message = self._message
        return p.render()

    def _h_dsl_entry(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        level = pi.stripped("DSLEVEL").upper() or self.userid
        self.dsl_prefix = level
        try:
            rows = self.state.datasets.listcat(self.userid, level)
            rows = [r for r in rows if not str(getattr(r, "path", "")).endswith(".meta")]
        except Exception as exc:
            self._message = f"LISTCAT FAILED: {exc}"
            return self._dsl_entry_panel()
        self.dsl_rows = rows
        if not rows:
            self._message = "NO DATA SETS FOUND"
            return self._dsl_entry_panel()
        self._screen = _DSLIST
        self.dsl_scroll = ScrollList([self._dsl_row_text(i, r) for i, r in enumerate(rows, 1)], height=_LIST_ROWS)
        return self._dslist_panel()

    # ------------------------------------------------------------- DSLIST
    def _dsl_row_text(self, n: int, r) -> str:
        org = getattr(r, "org", "")
        vol = getattr(r, "volume", "")
        return f"{n:>4} {getattr(r,'name',str(r)):<44} {org:<3} {vol:<6}"

    def _dslist_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"DSLIST - Data Sets Matching {self.dsl_prefix}"[:79], colors.BLUE)
        s.put(2, 1, (self.dsl_scroll.position_label if self.dsl_scroll else "Row 0 of 0").ljust(20), colors.BLUE)
        s.put(3, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 3, 14, 50, colour=_TURQ, role="command")
        s.put(3, 66, "Scroll ===> PAGE", colors.BLUE)
        if self._message:
            s.put(4, 1, ("==> " + self._message)[:79], colors.YELLOW)
        else:
            s.put(4, 1, "Enter line command at left:  B Browse  V View  E Edit  M Members  I Info", colors.TURQUOISE)
        s.put(5, 1, "  Cmd  Name                                         Org Volume", colors.BLUE)
        visible = self.dsl_scroll.visible() if self.dsl_scroll else []
        top = self.dsl_scroll.top if self.dsl_scroll else 0
        for i, rowtext in enumerate(visible):
            r = 6 + i
            absidx = top + i  # 0-based into dsl_rows
            s.add_field(f"LC{absidx:04d}", r, 2, 4, colour=_TURQ, role="line_command")
            row = self.dsl_rows[absidx] if absidx < len(self.dsl_rows) else None
            name = getattr(row, "name", "") if row is not None else ""
            org = getattr(row, "org", "") if row is not None else ""
            vol = getattr(row, "volume", "") if row is not None else ""
            if not name:  # fall back to the formatted text (skip leading number)
                name = rowtext.split(None, 1)[1].strip() if " " in rowtext else rowtext.strip()
            # editable name lets the user append (MEMBER) before an E line command
            s.add_field(f"DSN{absidx:04d}", r, 7, 46, value=name[:46], colour=colors.GREEN, role="field")
            s.put(r, 54, f"{org:<3} {vol:<6}"[:24], colors.GREEN)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 14)
        return s

    def _h_dslist(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _DSL_ENTRY
            return self._dsl_entry_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self.dsl_scroll:
                self.dsl_scroll.scroll(pi.key)
            return self._dslist_panel()
        cmd = pi.stripped("COMMAND").upper()
        if _scroll_primary(self.dsl_scroll, cmd):
            return self._dslist_panel()
        if cmd.startswith("LOCATE ") or cmd.startswith("L "):
            key = cmd.split(None, 1)[1] if " " in cmd else ""
            if self.dsl_scroll and self.dsl_scroll.locate(key.lower()):
                return self._dslist_panel()
            self._message = "LOCATE: not found"
            return self._dslist_panel()
        # line commands: find first non-blank LC field
        for name, val in pi.fields.items():
            if name.startswith("LC") and val.strip():
                idx = int(name[2:])
                if 0 <= idx < len(self.dsl_rows):
                    edited = pi.stripped(f"DSN{idx:04d}")
                    return self._apply_line_command(val.strip().upper(), self.dsl_rows[idx], edited)
        return self._dslist_panel()

    def _apply_line_command(self, action: str, row, edited_name: str = "") -> ScreenBuffer:
        action = action[0] if action else ""
        org = getattr(row, "org", "")
        name = getattr(row, "name", "")
        # The user may have appended (MEMBER) to the editable name to create/edit
        # a specific member directly from the data set list.
        member = ""
        en = (edited_name or "").strip().upper()
        if en and "(" in en and en.endswith(")"):
            base, member = en[:-1].split("(", 1)
            base = base.strip()
            member = member.strip()
            if base:
                name = base
        if action == "E" and member:
            spec = f"{name}({member})"
            self._edit_is_new = not self._member_exists(name, member)
            self._edit_spec = spec
            self.editor_return = _DSLIST
            self._screen = _EDIT_ENTRY
            return self._edit_entry_panel()
        if action == "M" or (action in ("S", "") and org == "PO"):
            if org != "PO":
                self._message = "NOT A PARTITIONED DATA SET"
                return self._dslist_panel()
            return self._open_members(row)
        if action == "E":
            if org == "PO":
                return self._open_members(row)  # choose a member to edit
            self.editor_return = _DSLIST
            return self._open_editor(name)
        if action in ("B", "V", "S"):
            if org == "PO":
                return self._open_members(row)  # must pick a member first
            text = self._read_dataset(name)
            self.browse_return = _DSLIST
            return self._open_browse(name, text)
        if action == "I":
            self._message = f"{name}  ORG={org}  VOL={getattr(row,'volume','')}  RECFM={getattr(row,'recfm','')}  LRECL={getattr(row,'lrecl','')}"
            return self._dslist_panel()
        self._message = f"UNKNOWN LINE COMMAND '{action}'"
        return self._dslist_panel()

    # ------------------------------------------------------------ MEMBERS
    def _open_members(self, row) -> ScreenBuffer:
        self.mem_ds = row
        try:
            path = getattr(row, "path", None)
            names = sorted(p.name.upper() for p in path.iterdir()
                           if p.is_file() and not p.name.endswith(".meta")) if path else []
        except Exception:
            names = []
        self.mem_names = names
        self.mem_scroll = ScrollList(
            [f"{n:>4} {nm:<8}" for n, nm in enumerate(names, 1)], height=_LIST_ROWS)
        self._screen = _MEMBERS
        if not names:
            self._message = "NO MEMBERS"
        return self._members_panel()

    def _members_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        dsn = getattr(self.mem_ds, "name", "")
        s.put(1, 1, f"MEMBER LIST  {dsn}"[:79], colors.BLUE)
        s.put(2, 1, (self.mem_scroll.position_label if self.mem_scroll else "Row 0 of 0").ljust(20), colors.BLUE)
        s.put(3, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 3, 14, 50, colour=_TURQ, role="command")
        s.put(5, 1, "  Cmd  Name", colors.BLUE)
        visible = self.mem_scroll.visible() if self.mem_scroll else []
        top = self.mem_scroll.top if self.mem_scroll else 0
        for i, rowtext in enumerate(visible):
            r = 6 + i
            absidx = top + i
            s.add_field(f"LC{absidx:04d}", r, 2, 4, colour=_TURQ, role="line_command")
            s.put(r, 7, rowtext[:60], colors.GREEN)
        if self._message:
            s.put(4, 1, ("==> " + self._message)[:79], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 14)
        return s

    def _h_members(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _DSLIST
            return self._dslist_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self.mem_scroll:
                self.mem_scroll.scroll(pi.key)
            return self._members_panel()
        cmd = pi.stripped("COMMAND").upper()
        if cmd.startswith("L ") or cmd.startswith("LOCATE "):
            key = cmd.split(None, 1)[1] if " " in cmd else ""
            if self.mem_scroll and self.mem_scroll.locate(key.lower()):
                return self._members_panel()
            self._message = "LOCATE: not found"
            return self._members_panel()
        for name, val in pi.fields.items():
            if name.startswith("LC") and val.strip():
                idx = int(name[2:])
                if 0 <= idx < len(self.mem_names):
                    member = self.mem_names[idx]
                    dsn = getattr(self.mem_ds, "name", "")
                    spec = f"{dsn}({member})"
                    if val.strip().upper().startswith("E"):
                        self.editor_return = _MEMBERS
                        return self._open_editor(spec)
                    text = self._read_dataset(spec)
                    self.browse_return = _MEMBERS
                    return self._open_browse(spec, text)
        return self._members_panel()

    # ------------------------------------------------------------- BROWSE
    def _open_editor(self, spec: str, new: bool = False):
        from gibson.apps.ispf3270.editor import Ispf3270Editor
        text = "" if new else self._read_dataset(spec)
        self.editor = Ispf3270Editor(self.state, self.userid, spec, text, peer_addr=self.peer_addr)
        return self.editor.initial_screen()

    def _member_exists(self, dataset: str, member: str) -> bool:
        try:
            path = self.state.datasets.ds_path(self.userid, dataset)
            return (path / member.upper()).exists()
        except Exception:
            return False

    def _edit_entry_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 2, "Menu  RefList  RefMode  Utilities  Workstation  Help", colors.WHITE)
        s.put(3, 31, "EDIT Entry Panel", _TURQ)
        if self._edit_is_new:
            s.put(4, 55, "New member", colors.YELLOW)
        s.put(6, 1, "Object Name:", colors.GREEN)
        s.put(7, 1, ("'" + self._edit_spec + "'")[:79], _TURQ)
        s.put(8, 3, "Initial Macro  . .", colors.GREEN)
        s.add_field("IMACRO", 8, 22, 8, colour=_TURQ, role="field")
        s.put(9, 3, "PDSE Generation. .", colors.GREEN)
        s.add_field("PDSEGEN", 9, 22, 8, colour=_TURQ, role="field")
        s.put(10, 3, "Line Command Table", colors.GREEN)
        s.add_field("LCTAB", 10, 22, 8, colour=_TURQ, role="field")
        s.put(11, 3, "Profile Name . . .", colors.GREEN)
        s.add_field("PROFILE", 11, 22, 8, colour=_TURQ, role="field")
        s.put(11, 33, "(Blank defaults to Type)", colors.GREEN)
        s.put(12, 3, "Format Name  . . .", colors.GREEN)
        s.add_field("FORMAT", 12, 22, 8, colour=_TURQ, role="field")
        s.put(13, 3, "Panel Name . . . .", colors.GREEN)
        s.add_field("PANEL", 13, 22, 8, colour=_TURQ, role="field")
        s.put(13, 33, "(Leave blank for default)", colors.GREEN)
        s.put(15, 1, "Press ENTER to edit, or END/PF3 to cancel.", colors.TURQUOISE)
        _put_pfkeys(s, _PF_SIMPLE)
        s.set_cursor(8, 22)
        return s

    def _h_edit_entry(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        if pi.key in ("PF3", "PF15"):
            self._screen = _DSLIST
            return self._dslist_panel()
        spec = self._edit_spec
        new = self._edit_is_new
        self._screen = _DSLIST   # editor_return controls where the editor lands
        return self._open_editor(spec, new=new)

    def _read_dataset(self, spec: str) -> str:
        try:
            return self.state.datasets.read(self.userid, spec)
        except Exception as exc:
            return f"** UNABLE TO READ {spec}: {exc} **"

    # ------------------------------------------------------------ OUTLIST
    def _held_jobs(self) -> list:
        """Held / completed output jobs visible to this user (newest first)."""
        from gibson.core.jes import JobStatus
        jes = getattr(self.state, "jes", None)
        jobs = list(getattr(jes, "jobs", {}).values()) if jes else []
        keep = {JobStatus.HELD, JobStatus.OUTPUT, JobStatus.FAILED}
        mine = [j for j in jobs if j.status in keep]
        # most recently submitted first
        return sorted(mine, key=lambda j: getattr(j, "jobid", ""), reverse=True)

    def _outlist_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "Outlist Utility", colors.BLUE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 4, colour=_TURQ, role="option")
        s.put(5, 2, "L  List held job output       Jobname ===>", colors.TURQUOISE)
        s.add_field("JOBNAME", 5, 45, 8, colour=_TURQ)
        s.put(6, 2, "D  Delete held job output     Class . ===>", colors.TURQUOISE)
        s.add_field("CLASS", 6, 45, 1, colour=_TURQ)
        s.put(7, 2, "P  Print held job output", colors.TURQUOISE)
        jobs = self._held_jobs()
        s.put(9, 1, "  JOBNAME   JOBID      C  STATUS    RECORDS", colors.WHITE)
        s.put(10, 1, "  --------  ---------  -  --------  -------", colors.WHITE)
        row = 11
        for j in jobs[:11]:
            line = (f"  {j.jobname:<8.8}  {j.jobid:<9.9}  {j.message_class:<1.1}  "
                    f"{str(j.status.value if hasattr(j.status,'value') else j.status):<8.8}  "
                    f"{j.records:>7}")
            s.put(row, 1, line[:79], colors.GREEN)
            row += 1
        if not jobs:
            s.put(11, 3, "No held output for this user.", colors.YELLOW)
        if self._message:
            s.put(22, 1, ("==> " + self._message)[:79], colors.YELLOW)
        _put_pfkeys(s, _PF_SIMPLE)
        s.set_cursor(3, 13)
        return s

    def _h_outlist(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        opt = (pi.stripped("OPTION") or "L").upper()
        jobname = pi.stripped("JOBNAME").upper()
        jobs = self._held_jobs()
        if jobname:
            jobs = [j for j in jobs if j.jobname.upper() == jobname]
        if opt == "D":
            jes = getattr(self.state, "jes", None)
            removed = 0
            for j in list(jobs):
                if jes and j.jobid in getattr(jes, "jobs", {}):
                    del jes.jobs[j.jobid]
                    removed += 1
            self._message = f"{removed} JOB(S) DELETED" if removed else "NO MATCHING HELD OUTPUT"
            return self._outlist_panel()
        if opt == "P":
            self._message = (f"{len(jobs)} JOB(S) QUEUED FOR PRINT" if jobs
                             else "NO MATCHING HELD OUTPUT")
            return self._outlist_panel()
        # L (default): display the selected job's spool, or a roster of all held
        if not jobs:
            self._message = "NO MATCHING HELD OUTPUT"
            return self._outlist_panel()
        if jobname or len(jobs) == 1:
            j = jobs[0]
            text = "".join(f"********************************* {sf.ddname} "
                           f"*********************************\n{sf.content}\n"
                           for sf in j.spool) or "(no spool data)\n"
            self.browse_return = _OUTLIST
            return self._open_browse(f"{j.jobname} {j.jobid}", text)
        roster = "JOBNAME   JOBID      CLASS  STATUS    RECORDS\n" + "\n".join(
            f"{j.jobname:<8}  {j.jobid:<9}  {j.message_class:<5}  "
            f"{(j.status.value if hasattr(j.status,'value') else j.status):<8}  {j.records:>7}"
            for j in jobs)
        self.browse_return = _OUTLIST
        return self._open_browse("HELD OUTPUT", roster)

    # ------------------------------------------------------- RACF / zSecure
    def _racf_run(self, cmd: str) -> List[str]:
        """Delegate to the real RACF/TSO engine (same path -> same SMF80)."""
        try:
            out = self._tso.run(cmd)
        except Exception as exc:  # never crash the panel on a bad command
            out = f"COMMAND FAILED: {exc}"
        lines = [f"COMMAND ===> {cmd}", ""] + (out or "").splitlines()
        self._racf_outscroll = ScrollList(lines, height=11)
        return lines

    def _racf_menu_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 25, "RACF - SERVICES OPTION MENU", colors.WHITE)
        s.put(3, 1, "OPTION  ===>", colors.GREEN)
        s.add_field("OPTION", 3, 14, 4, colour=_TURQ, role="option")
        s.put(5, 1, "SELECT ONE OF THE FOLLOWING:", colors.BLUE)
        row = 7
        for num, name in _RACF_MENU:
            s.put(row, 4, f"{num:>2}  {name}"[:79], colors.TURQUOISE)
            row += 1
        s.put(row + 1, 4, "99  EXIT", colors.TURQUOISE)
        s.put(row + 3, 1,
              "Actions echo the equivalent RACF command and write SMF type-80.",
              colors.GREEN)
        if self._message:
            s.put(22, 1, ("==> " + self._message)[:79], colors.YELLOW)
        s.put(24, 1, "PF1=HELP  PF3=END  PF12=CANCEL", colors.BLUE)
        s.set_cursor(3, 14)
        return s

    def _racf_panel(self) -> ScreenBuffer:
        if self._racf_view == "MENU":
            return self._racf_menu_panel()
        if self._racf_view == "SETR":
            s = ScreenBuffer()
            s.extended_attributes = True
            s.put(1, 1, "RACF SETROPTS - System Options", colors.BLUE)
            s.put(2, 62, (self._racf_outscroll.position_label if self._racf_outscroll else "").rjust(17), colors.BLUE)
            if self._racf_outscroll:
                self._racf_outscroll.render_into(s, 4, left=1, width=79, colour=colors.GREEN)
            _put_pfkeys(s, _PF_SCROLL)
            s.set_cursor(2, 1)
            return s
        title, legend, fields, _builder = _RACF_VIEWS[self._racf_view]
        saved = self._racf_fld.get(self._racf_view, {})
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, title, colors.BLUE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 4, colour=_TURQ, role="option")
        s.put(4, 1, legend[:79], colors.TURQUOISE)
        row = 6
        for fname, label, width, default in fields:
            s.put(row, 3, label, colors.GREEN)
            s.add_field(fname, row, 21, width, value=saved.get(fname, default), colour=_TURQ)
            row += 1
        out_top = row + 1
        s.put(out_top, 1, "Result:", colors.WHITE)
        s.put(out_top, 62, (self._racf_outscroll.position_label if self._racf_outscroll else "").rjust(17), colors.BLUE)
        if self._racf_outscroll:
            self._racf_outscroll.render_into(s, out_top + 1, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(out_top, 12, self._message[:48], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 13)
        return s

    def _h_racf(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            if self._racf_view == "MENU":
                self._screen = _PRIMARY
                return self._primary_panel()
            self._racf_view = "MENU"
            self._racf_output = []
            self._racf_outscroll = None
            return self._racf_panel()
        if pi.key in ("PF7", "PF8") and self._racf_outscroll:
            self._racf_outscroll.scroll(pi.key)
            return self._racf_panel()
        opt = pi.stripped("OPTION").upper()
        if self._racf_view == "MENU":
            if opt in ("99", "X", "EXIT", "END"):
                self._screen = _PRIMARY
                self._message = ""
                return self._primary_panel()
            if opt == "5":
                self._racf_view = "SETR"
                self._racf_output = self._racf_run("SETROPTS LIST")
                return self._racf_panel()
            viewmap = {"1": "DSD", "2": "GENRES", "3": "GROUP", "4": "USER"}
            if opt in viewmap:
                self._racf_view = viewmap[opt]
                self._racf_output = []
                self._racf_outscroll = None
                return self._racf_panel()
            if opt in ("S", "SEARCH"):  # search retained as a RACF shortcut
                self._racf_view = "SEARCH"
                self._racf_output = []
                self._racf_outscroll = None
                return self._racf_panel()
            if opt == "6":
                self._message = "IRRR014I RRSF IS NOT ACTIVE ON THIS SYSTEM"
                return self._racf_panel()
            if opt == "7":
                self._message = "RACDCERT - USE TSO: RACDCERT LIST / LISTRING"
                return self._racf_panel()
            if opt:
                self._message = f"INVALID OPTION '{opt}'"
            return self._racf_panel()
        if self._racf_view == "SETR":
            return self._racf_panel()
        # action view
        _t, _l, fields, builder = _RACF_VIEWS[self._racf_view]
        fld = {fn: pi.stripped(fn) for fn, _lbl, _w, _d in fields}
        self._racf_fld[self._racf_view] = fld
        cmd = builder(opt or "L", fld)
        if not cmd:
            self._message = "ENTER REQUIRED FIELD(S) / VALID ACTION CODE"
        else:
            self._racf_output = self._racf_run(cmd)
        return self._racf_panel()

    # ----------------------------------------------- M MANAGEMENT sub-menu
    def _open_zsec(self) -> ScreenBuffer:
        self._screen = _ZSEC
        self._racf_output = []
        return self._zsec_panel()

    def _open_endevor(self) -> ScreenBuffer:
        self._screen = _ENDV
        self._endv_scroll = None
        self._endv_run("ENDEVOR")
        return self._endv_panel()

    def _open_sysview(self) -> ScreenBuffer:
        from gibson.apps.sysview3270 import Sysview3270Session
        self._subapp_return = _MGMT
        self.subapp = Sysview3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
        return self.subapp.initial_screen()

    def _open_ezrecon(self) -> ScreenBuffer:
        from gibson.apps.ezrecon3270 import EzRecon3270Session
        self._subapp_return = _MGMT
        self.subapp = EzRecon3270Session(self.state, peer_addr=self.peer_addr, userid=self.userid)
        return self.subapp.initial_screen()

    def _open_rss(self) -> ScreenBuffer:
        return self._rss_open_reader(return_to=_MGMT)

    def _open_lynx(self) -> ScreenBuffer:
        return self._lynx_open(return_to=_MGMT)

    _MGMT_MENU = [
        ("1", "zSecure", "IBM Security zSecure Admin and Audit for RACF", _open_zsec),
        ("2", "SMP/E", "SMP/E software maintenance dialogs", _open_zsec),
        ("3", "SYSVIEW", "CA SYSVIEW Performance and Operations Monitor", _open_sysview),
        ("4", "Endevor", "CA Endevor SCM software change management", _open_endevor),
        ("5", "EZRecon", "EZRecon reconnaissance and assessment toolkit", _open_ezrecon),
        ("6", "RSS", "CTI RSS reader - security news feeds (PF7/PF8 scroll)", _open_rss),
        ("7", "Lynx", "Lynx text web browser rendered in ISPF (PF7/PF8 scroll)", _open_lynx),
    ]

    def _mgmt_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "Menu  Options  Info  Commands  Setup", colors.BLUE)
        s.put(2, 30, "Management Services", colors.WHITE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 8, colour=_TURQ, role="option")
        s.put(5, 4, "Select a management application:", colors.WHITE)
        row = 7
        for num, name, desc, _fn in self._MGMT_MENU:
            s.put(row, 4, num, colors.WHITE)
            s.put(row, 8, f"{name:<10}", _TURQ)
            s.put(row, 20, desc[:56], colors.GREEN)
            row += 1
        if self._message:
            s.put(row + 1, 4, self._message[:74], colors.YELLOW)
        s.put(22, 1, "F1=Help  F3=Exit", colors.BLUE)
        s.set_cursor(3, 13)
        return s

    def _h_mgmt(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        opt = pi.stripped("OPTION").upper().split(".")[0]
        if not opt:
            return self._mgmt_panel()
        match = {n: fn for n, _nm, _d, fn in self._MGMT_MENU}.get(opt)
        # also accept the application name/alias
        if match is None:
            byname = {nm.upper(): fn for _n, nm, _d, fn in self._MGMT_MENU}
            match = byname.get(opt)
        if match is not None:
            return match(self)
        self._message = f"INVALID OPTION '{opt}'"
        return self._mgmt_panel()

    def _zsec_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "Menu  Options  Info  Commands  Setup", colors.BLUE)
        s.put(2, 1, "IBM Security zSecure Admin and Audit for RACF  -  V3.1.0", colors.WHITE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 4, colour=_TURQ, role="option")
        row = 5
        for num, name, desc, _topic in _ZSEC_MENU:
            s.put(row, 4, f"{num:<5}{name:<22.22} {desc}"[:79], colors.TURQUOISE)
            row += 1
        out_top = row + 1
        s.put(out_top, 1, "Report:", colors.WHITE)
        s.put(out_top, 62, (self._racf_outscroll.position_label if self._racf_outscroll else "").rjust(17), colors.BLUE)
        if self._racf_outscroll:
            self._racf_outscroll.render_into(s, out_top + 1, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(out_top, 12, self._message[:48], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 13)
        return s

    def _h_zsec(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _MGMT
            return self._mgmt_panel()
        if pi.key in ("PF7", "PF8") and self._racf_outscroll:
            self._racf_outscroll.scroll(pi.key)
            return self._zsec_panel()
        opt = pi.stripped("OPTION").upper()
        topic = {n: t for n, _nm, _d, t in _ZSEC_MENU}.get(opt)
        if topic:
            self._racf_output = self._racf_run(f"ZSEC {topic}")
        elif opt:
            self._message = f"INVALID OPTION '{opt}'"
        return self._zsec_panel()

    # ------------------------------------------------------ E ENDEVOR (CA SCM)
    def _endv_run(self, cmd: str) -> None:
        """Drive the CA Endevor engine (same path as the TSO ENDEVOR command)."""
        from gibson.apps.endevor import endevor_command
        try:
            out = endevor_command(self.state, self.userid, cmd)
        except Exception as exc:  # never crash the panel on a bad request
            out = f"COMMAND FAILED: {exc}"
        if out is None:
            out = f"C1G0000E  UNRECOGNISED ENDEVOR REQUEST: {cmd}"
        self._endv_scroll = ScrollList((out or "").splitlines(), height=18)

    def _endv_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "Menu  Utilities  Display  Foreground  Package  Help", colors.BLUE)
        s.put(2, 1, "CA Endevor SCM  -  Primary Options", colors.WHITE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 60, colour=_TURQ, role="option")
        out_top = 5
        s.put(out_top - 1, 62,
              (self._endv_scroll.position_label if self._endv_scroll else "").rjust(17), colors.BLUE)
        if self._endv_scroll:
            for i, row in enumerate(self._endv_scroll.visible()):
                s.put(out_top + i, 1, row[:79], _endv_line_colour(row))
        if self._message:
            s.put(4, 1, self._message[:78], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 13)
        return s

    def _h_endv(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _MGMT
            return self._mgmt_panel()
        if pi.key in ("PF7", "PF8") and self._endv_scroll:
            self._endv_scroll.scroll(pi.key)
            return self._endv_panel()
        opt = pi.stripped("OPTION").strip()
        if opt.upper() in ("2", "FG", "FOREGROUND"):
            # Option 2 FOREGROUND -> the fielded element-action data-entry panel.
            self._screen = _ENDVFG
            self._endvfg_scroll = None
            return self._endvfg_panel()
        if opt:
            # Bare C1 menu numbers map to element-action verbs; anything else is a
            # verb/spec (DISPLAY / BROWSE sys.sub.typ.elm / RETRIEVE / ADD /
            # PACKAGE ...) handed straight to the engine.
            num = {"0": "MENU", "1": "DISPLAY", "3": "MENU",
                   "4": "PACKAGE", "5": "PACKAGE", "6": "MENU"}.get(opt.upper())
            self._endv_run(f"ENDEVOR {num if num else opt}")
        return self._endv_panel()

    # ---------------------------------------------- E.2  ENDEVOR FOREGROUND PANEL
    _ENDVFG_DEFAULTS = {"ACTION": "DISPLAY", "ENV": "PROD", "SYSTEM": "", "SUBSYS": "",
                        "TYPE": "", "ELEMENT": "", "STAGE": "P", "CCID": "", "COMMENT": ""}

    def _endvfg_panel(self) -> ScreenBuffer:
        if not self._endvfg_fields:
            self._endvfg_fields = dict(self._ENDVFG_DEFAULTS)
        f = self._endvfg_fields
        p = Panel(title="Endevor Foreground - Element Actions", cursor="SYSTEM")
        p.add(Label(2, 1, "Menu  Display  Retrieve  Add  Options  Help", colors.BLUE))
        p.add(Label(4, 1, "Option ===>", colors.GREEN))
        p.add(Field("CMD", 4, 14, 24, colour=_TURQ))
        p.add(Label(6, 2, "Action  . . . :", colors.GREEN))
        p.add(Field("ACTION", 6, 18, 9, value=f.get("ACTION", ""), colour=_TURQ))
        p.add(Label(6, 30, "(DISPLAY BROWSE ADD GENERATE MOVE DELETE SIGNOUT)", colors.BLUE))
        rows = [
            (8,  "Environment  :", "ENV", 8, ""),
            (9,  "System . . . :", "SYSTEM", 8, ""),
            (10, "Subsystem  . :", "SUBSYS", 8, ""),
            (11, "Type . . . . :", "TYPE", 8, "(COBOL COPYBOOK JCL ...)"),
            (12, "Element  . . :", "ELEMENT", 10, ""),
            (13, "Stage  . . . :", "STAGE", 1, "(D=Dev T=Test Q=QA P=Prod E=Emer)"),
            (14, "CCID . . . . :", "CCID", 12, "(change control id)"),
            (15, "Comment  . . :", "COMMENT", 40, ""),
        ]
        for row, label, name, length, hint in rows:
            p.add(Label(row, 2, label, colors.GREEN))
            p.add(Field(name, row, 18, length, value=f.get(name, ""), colour=_TURQ))
            if hint:
                p.add(Label(row, 18 + length + 2, hint, colors.BLUE))
        sb = p.render()
        out_top = 17
        sb.put(out_top, 1, "Result:", colors.WHITE)
        if self._endvfg_scroll:
            sb.put(out_top, 62, self._endvfg_scroll.position_label.rjust(17), colors.BLUE)
            self._endvfg_scroll.render_into(sb, out_top + 1, left=1, width=79, colour=colors.GREEN)
        if self._message:
            sb.put(out_top, 12, self._message[:48], colors.YELLOW)
        _put_pfkeys(sb, _PF_SCROLL)
        return sb

    def _h_endvfg(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _ENDV
            return self._endv_panel()
        if pi.key in ("PF7", "PF8") and self._endvfg_scroll:
            self._endvfg_scroll.scroll(pi.key)
            return self._endvfg_panel()
        f = self._endvfg_fields or dict(self._ENDVFG_DEFAULTS)
        for name in self._ENDVFG_DEFAULTS:
            v = pi.stripped(name).strip()
            if v or name not in ("ACTION", "ENV", "STAGE"):
                f[name] = v
        self._endvfg_fields = f
        action = (f.get("ACTION") or "DISPLAY").upper()
        f["ACTION"] = action
        sysn, sub = f.get("SYSTEM", "").upper(), f.get("SUBSYS", "").upper()
        typ, elem = f.get("TYPE", "").upper(), f.get("ELEMENT", "").upper()
        from gibson.apps.endevor import endevor_command
        if action in ("DISPLAY", "LIST", "DIS"):
            spec = ".".join(x for x in (sysn, sub) if x)
            cmd = f"ENDEVOR DISPLAY {spec}".strip()
        else:
            if not (sysn and sub and typ and elem):
                self._message = "SYSTEM/SUBSYS/TYPE/ELEMENT REQUIRED FOR THIS ACTION"
                return self._endvfg_panel()
            cmd = f"ENDEVOR {action} {sysn}.{sub}.{typ}.{elem}"
        try:
            out = endevor_command(self.state, self.userid, cmd) or "C1G0000E  NO RESPONSE"
        except Exception as exc:  # noqa: BLE001
            out = f"COMMAND FAILED: {exc}"
        self._endvfg_scroll = ScrollList([f"ACTION: {cmd}", ""] + out.splitlines(), height=6)
        return self._endvfg_panel()

    # ------------------------------------------------------ I  IMS CONNECT/OTMA
    def _ims_run(self, cmd: str) -> None:
        from gibson.apps.ims import ims_command
        try:
            out = ims_command(self.state, self.userid, cmd)
        except Exception as exc:  # never crash the panel
            out = f"COMMAND FAILED: {exc}"
        if out is None:
            out = f"DFS1292E  UNRECOGNISED IMS REQUEST: {cmd}"
        self._ims_scroll = ScrollList((out or "").splitlines(), height=18)

    def _ims_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, "Menu  Connect  OTMA  Security  Help", colors.BLUE)
        s.put(2, 1, "IMS Connect / OTMA  -  Security Lab", colors.WHITE)
        s.put(3, 1, "Option ===>", colors.GREEN)
        s.add_field("OPTION", 3, 13, 60, colour=_TURQ, role="option")
        out_top = 5
        s.put(out_top - 1, 62,
              (self._ims_scroll.position_label if self._ims_scroll else "").rjust(17), colors.BLUE)
        if self._ims_scroll:
            self._ims_scroll.render_into(s, out_top, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(4, 1, self._message[:78], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(3, 13)
        return s

    def _h_ims(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        if pi.key in ("PF7", "PF8") and self._ims_scroll:
            self._ims_scroll.scroll(pi.key)
            return self._ims_panel()
        opt = pi.stripped("OPTION").strip()
        if opt:
            # Bare option text is handed to the engine; prefix IMS if the user
            # omitted it (so "SUBMIT PART" and "IMS SUBMIT PART" both work).
            req = opt if opt.upper().startswith("IMS") else f"IMS {opt}"
            self._ims_run(req)
        return self._ims_panel()

    # ------------------------------------------------ 4/5 LANGUAGE PROCESSING
    def _langproc_panel(self) -> ScreenBuffer:
        fg = self._lp_mode == "FG"
        title = "Foreground" if fg else "Batch"
        p = Panel(title=f"{title} Language Processing", cursor="SOURCE")
        p.add(Label(2, 1, "Menu  Utilities  Compilers  Help", colors.BLUE))
        p.add(Label(4, 2, "Option ===>", colors.GREEN))
        p.add(Field("OPTION", 4, 14, 8, colour=_TURQ))
        p.add(Label(6, 3, "Source Data Set . .", colors.GREEN))
        p.add(Field("SOURCE", 6, 23, 44, value=self._lp_src, colour=_TURQ))
        p.add(Label(7, 3, "Language  . . . . .", colors.GREEN))
        p.add(Field("LANG", 7, 23, 10, value="COBOL", colour=_TURQ))
        if fg:
            p.add(Label(9, 3, "Press ENTER to compile and run in the foreground.", colors.GREEN))
        else:
            p.add(Label(9, 3, "Press ENTER to generate JCL and submit a compile job.", colors.GREEN))
        out_top = 11
        sb = p.render()
        sb.put(out_top, 1, "Result:", colors.WHITE)
        if self._lp_scroll:
            sb.put(out_top, 62, self._lp_scroll.position_label.rjust(17), colors.BLUE)
            self._lp_scroll.render_into(sb, out_top + 1, left=1, width=79, colour=colors.GREEN)
        if self._message:
            sb.put(out_top, 12, self._message[:48], colors.YELLOW)
        return sb

    def _h_langproc(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = _PRIMARY
            return self._primary_panel()
        if pi.key in ("PF7", "PF8") and self._lp_scroll:
            self._lp_scroll.scroll(pi.key)
            return self._langproc_panel()
        src = pi.stripped("SOURCE")
        self._lp_src = src
        if not src:
            self._message = "ENTER A SOURCE DATA SET"
            return self._langproc_panel()
        try:
            source = self.state.datasets.read(self.userid, src)
        except Exception:
            self._message = f"SOURCE {src.upper()} NOT FOUND"
            return self._langproc_panel()
        if self._lp_mode == "FG":
            lines = self._compile_foreground(source)
        else:
            lines = self._submit_batch_compile(src)
        self._lp_output = lines
        self._lp_scroll = ScrollList(lines, height=10)
        return self._langproc_panel()

    def _compile_foreground(self, source: str) -> List[str]:
        from gibson.languages.cobol import CobolSimulator
        res = CobolSimulator().compile(source)
        lines = [f"COMPILE RC={res.rc:04d}", ""]
        lines += (res.listing or "").splitlines()[:40]
        if res.display_lines:
            lines += ["", "----- PROGRAM OUTPUT (DISPLAY) -----"]
            lines += list(res.display_lines)
        if res.rc == 0:
            lines += ["", f"***  {self._lp_src.upper()} COMPILED AND RAN - RC=0  ***"]
        else:
            lines += ["", f"***  COMPILE FAILED - RC={res.rc}  ***"]
        return lines

    def _submit_batch_compile(self, src: str) -> List[str]:
        from gibson.apps.tso import TsoCommandProcessor
        jcl = (
            f"//{self.userid[:7]}C JOB (ACCT),'COMPILE',CLASS=A,MSGCLASS=A\n"
            f"//COB     EXEC PGM=IGYCRCTL,PARM='OBJECT,LIST'\n"
            f"//SYSIN    DD DSN={src.upper()},DISP=SHR\n"
            f"//SYSPRINT DD SYSOUT=*\n"
            f"//SYSLIN   DD DSN={self.userid}.OBJ,DISP=(NEW,CATLG)\n"
        )
        try:
            tso = TsoCommandProcessor(self.state, self.userid)
            self.state.datasets.allocate(self.userid, f"{self.userid}.COMPILE.JCL", org="PS")
            self.state.datasets.write(self.userid, f"{self.userid}.COMPILE.JCL", jcl)
            msg = tso.run(f"SUBMIT '{self.userid}.COMPILE.JCL'")
        except Exception as exc:
            return [f"SUBMIT FAILED: {exc}"]
        return ["Generated and submitted compile JCL:", ""] + jcl.splitlines() + ["", msg]

    def _open_browse(self, title: str, text: str) -> ScreenBuffer:
        self.browse_title = title
        self.browse_lines = [l.rstrip("\n") for l in text_to_lines(text)]
        self.browse_scroll = ScrollList(self.browse_lines, height=_BROWSE_ROWS)
        self._screen = _BROWSE
        return self._browse_panel()

    def _browse_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"BROWSE  {self.browse_title}"[:60], colors.BLUE)
        s.put(1, 62, (self.browse_scroll.position_label if self.browse_scroll else "").rjust(17), colors.BLUE)
        s.put(2, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 2, 14, 50, colour=_TURQ, role="command")
        s.put(2, 63, "Scroll ===> PAGE", colors.BLUE)
        if self.browse_scroll:
            self.browse_scroll.render_into(s, 4, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(3, 1, ("==> " + self._message)[:79], colors.YELLOW)
        _put_pfkeys(s, _PF_SCROLL)
        s.set_cursor(2, 14)
        return s

    def _h_browse(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = self.browse_return
            if self.browse_return == _OUTLIST:
                return self._outlist_panel()
            return self._dslist_panel() if self.browse_return == _DSLIST else self._members_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self.browse_scroll:
                self.browse_scroll.scroll(pi.key)
            return self._browse_panel()
        cmd = pi.stripped("COMMAND")
        up = cmd.upper()
        if _scroll_primary(self.browse_scroll, up):
            return self._browse_panel()
        if up.startswith("F ") or up.startswith("FIND ") or up == "RFIND" or pi.key == "PF5":
            term = (cmd.split(None, 1)[1] if " " in cmd else getattr(self, "_last_find", "")).strip()
            self._last_find = term
            if term and self._browse_find(term):
                self._message = f"FOUND '{term}'"
            else:
                self._message = f"'{term}' NOT FOUND" if term else "ENTER FIND STRING"
            return self._browse_panel()
        if up.startswith("L ") or up.startswith("LOCATE "):
            num = up.split(None, 1)[1] if " " in up else ""
            if num.isdigit() and self.browse_scroll:
                self.browse_scroll.top = max(0, min(int(num) - 1, len(self.browse_lines) - 1))
            return self._browse_panel()
        if up in ("M", "TOP", "MAX UP") and self.browse_scroll:
            self.browse_scroll.to_top(); return self._browse_panel()
        if up in ("MAX", "BOTTOM") and self.browse_scroll:
            self.browse_scroll.to_bottom(); return self._browse_panel()
        return self._browse_panel()

    # ----------------------------------------------------------- RSS reader
    def _rss_open_reader(self, return_to=None) -> ScreenBuffer:
        """Enter the ISPF RSS reader (option RSS).  Lists the cached CTI feed
        items in a scrollable pane; F7/F8 page, a number opens that article."""
        self.rss_return = return_to or _PRIMARY
        self.rss_mode = "LIST"
        self.rss_title = "CTI RSS FEEDS"
        self._rss_refresh_list()
        self._screen = _RSSREAD
        return self._rssread_panel()

    def _rss_refresh_list(self, live: bool = False) -> None:
        lines = ["NUM  FEED                 PUBLISHED         TITLE",
                 "---  -------------------- ----------------  " + "-" * 30]
        self._rss_links = []
        try:
            from gibson.apps import cti_rss
            cti_rss.ensure_rss_datasets(self.state, self.userid)
            if live:
                cti_rss.fetch_all(self.state, self.userid)
            items = cti_rss._cached_items(self.state, self.userid)
        except Exception as exc:
            items = []
            lines.append(f"RSS--E  {type(exc).__name__}: {str(exc)[:50]}")
        for i, it in enumerate(items, 1):
            feed = str(it.get("feed", ""))[:20]
            pub = str(it.get("published", ""))[:16]
            title = str(it.get("title", ""))[:34]
            lines.append(f"{i:<3}  {feed:<20} {pub:<16}  {title}")
            self._rss_links.append(it)
        if not items:
            lines.append("")
            lines.append("No cached items.  Type REFRESH (or PF6) to fetch the latest feeds,")
            lines.append("then enter an item number to open the article.")
        self.rss_lines = lines
        self.rss_scroll = ScrollList(lines, height=_BROWSE_ROWS, top=0)

    def _rss_open_article(self, num: int) -> None:
        from gibson.apps import cti_rss
        # Clean, ISPF-ready render (no ANSI escapes, no "--More--" pager, EBCDIC-
        # safe, word-wrapped) so PF7/PF8 page the article correctly.
        body = cti_rss.render_article_lines(self.state, self.userid, num, width=78)
        self.rss_mode = "ARTICLE"
        item = self._rss_links[num - 1] if 0 < num <= len(self._rss_links) else {}
        self.rss_title = ("ARTICLE: " + str(item.get("title", "")))[:58]
        self.rss_lines = body
        self.rss_scroll = ScrollList(body, height=_BROWSE_ROWS, top=0)

    def _rssread_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        s.put(1, 1, f"RSS  {self.rss_title}"[:60], colors.BLUE)
        s.put(1, 62, (self.rss_scroll.position_label if self.rss_scroll else "").rjust(17), colors.BLUE)
        s.put(2, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 2, 14, 50, colour=_TURQ, role="command")
        s.put(2, 63, "Scroll ===> PAGE", colors.BLUE)
        if self.rss_scroll:
            self.rss_scroll.render_into(s, 4, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(3, 1, ("==> " + self._message)[:79], colors.YELLOW)
        hint = ("F3=Exit  F6=Refresh  F7=Up  F8=Down   #=open article" if self.rss_mode == "LIST"
                else "F3=Back  F7=Up  F8=Down  F10/F11=Left/Right")
        _put_pfkeys(s, "F1=Help  F2=Split  " + hint + "  F9=Swap\nF12=Cancel")
        s.set_cursor(2, 14)
        return s

    def _h_rssread(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            if self.rss_mode == "ARTICLE":          # article -> back to list
                self.rss_mode = "LIST"
                self._rss_refresh_list()
                return self._rssread_panel()
            self._screen = getattr(self, "rss_return", _PRIMARY)
            return self._current_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self.rss_scroll:
                self.rss_scroll.scroll(pi.key)
            return self._rssread_panel()
        cmd = pi.stripped("COMMAND")
        up = cmd.upper()
        if pi.key == "PF6" or up in ("REFRESH", "REF", "FETCH"):
            self.rss_mode = "LIST"
            self._rss_refresh_list(live=True)
            self._message = "FEEDS REFRESHED"
            return self._rssread_panel()
        if _scroll_primary(self.rss_scroll, up):
            return self._rssread_panel()
        if self.rss_mode == "LIST" and (up.isdigit() or up.startswith("O ") or up.startswith("OPEN ")):
            num = up if up.isdigit() else up.split(None, 1)[1]
            if num.isdigit() and 1 <= int(num) <= len(self._rss_links):
                try:
                    self._rss_open_article(int(num))
                except Exception as exc:
                    self._message = f"OPEN FAILED: {type(exc).__name__}"
                return self._rssread_panel()
            self._message = "ENTER A VALID ITEM NUMBER"
            return self._rssread_panel()
        return self._rssread_panel()

    # ----------------------------------------------------------- Lynx browser
    def _lynx_open(self, return_to=None, url: str = "") -> ScreenBuffer:
        """Enter the ISPF Lynx text browser.  Type a URL on the command line and
        press ENTER to render the page; PF7/PF8 scroll."""
        self.lynx_return = return_to or _PRIMARY
        self.lynx_url = url or getattr(self, "lynx_url", "")
        self.lynx_lines = [
            "LYNX  -  text web browser (rendered in ISPF)",
            "-" * 78,
            "",
            "Type a URL on the Command line and press ENTER, for example:",
            "  http://sighberbank.com",
            "  https://www.bleepingcomputer.com",
            "",
            "PF7/PF8 scroll the page.  PF3 returns.  Only http:// and https:// URLs",
            "are fetched; the same in-simulator hosts the OMVS Lynx tool can reach.",
        ]
        self.lynx_scroll = ScrollList(self.lynx_lines, height=_BROWSE_ROWS, top=0)
        self._screen = _LYNX
        if url:
            self._lynx_fetch(url)
        return self._lynx_panel()

    def _lynx_fetch(self, url: str) -> None:
        from gibson.tools.html_text_browser import render_clean_lines
        self.lynx_url = url
        self.lynx_lines = render_clean_lines(url, width=78, state=self.state)
        self.lynx_scroll = ScrollList(self.lynx_lines, height=_BROWSE_ROWS, top=0)

    def _lynx_panel(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        title = ("LYNX  " + (self.lynx_url or "Enter a URL"))[:60]
        s.put(1, 1, title, colors.BLUE)
        s.put(1, 62, (self.lynx_scroll.position_label if self.lynx_scroll else "").rjust(17), colors.BLUE)
        s.put(2, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 2, 14, 48, colour=_TURQ, role="command")
        s.put(2, 63, "Scroll ===> PAGE", colors.BLUE)
        if self.lynx_scroll:
            self.lynx_scroll.render_into(s, 4, left=1, width=79, colour=colors.GREEN)
        if self._message:
            s.put(3, 1, ("==> " + self._message)[:79], colors.YELLOW)
        _put_pfkeys(s, "F1=Help  F2=Split  F3=Exit  F7=Up  F8=Down  "
                       "GO <url>=fetch  F9=Swap\nF12=Cancel")
        s.set_cursor(2, 14)
        return s

    def _h_lynx(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        if pi.key in ("PF3", "PF15"):
            self._screen = getattr(self, "lynx_return", _PRIMARY)
            return self._current_panel()
        if pi.key in ("PF7", "PF8", "PF10", "PF11"):
            if self.lynx_scroll:
                self.lynx_scroll.scroll(pi.key)
            return self._lynx_panel()
        cmd = pi.stripped("COMMAND").strip()
        up = cmd.upper()
        if _scroll_primary(self.lynx_scroll, up):
            return self._lynx_panel()
        # GO <url>, or a bare URL, fetches the page
        target = ""
        if up.startswith("GO ") or up.startswith("OPEN "):
            target = cmd.split(None, 1)[1].strip()
        elif cmd.lower().startswith(("http://", "https://")):
            target = cmd
        if target:
            try:
                self._lynx_fetch(target)
                self._message = "PAGE LOADED"
            except Exception as exc:
                self._message = f"FETCH FAILED: {type(exc).__name__}"
            return self._lynx_panel()
        if cmd:
            self._message = "ENTER A URL (http:// or https://) OR GO <url>"
        return self._lynx_panel()

    def _browse_find(self, term: str) -> bool:
        if not self.browse_scroll:
            return False
        start = self.browse_scroll.top + 1
        low = term.lower()
        for i in range(start, len(self.browse_lines)):
            if low in self.browse_lines[i].lower():
                self.browse_scroll.top = i
                return True
        for i in range(0, start):  # wrap
            if low in self.browse_lines[i].lower():
                self.browse_scroll.top = i
                return True
        return False
