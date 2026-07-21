from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import shutil
from datetime import datetime
from gibson.core import v26_features
import re

from gibson.core.datasets import DatasetInfo
from gibson.core.state import GibsonState
from gibson.render import colors
from gibson.render.input import SocketInputDriver, read_panel_command, panel_input_value
from gibson.render.screen3270 import ScreenBuffer
from gibson.apps.editor import InteractiveEditor
from gibson.apps.db2_sim import Db2Simulator, SYSTEM_INFO


@dataclass
class IspfMessage:
    text: str = ""


def _pad(text: str, n: int = 79) -> str:
    return text[:n].ljust(n)


class IspfApp:
    """ISPF/PDF z/OS 2.5-style panels for Gibson.

    The simulator is still a telnet/ANSI application, not a true 3270 data
    stream.  To make 3.4 usable over TCP, line commands are rendered in the left
    command column and are entered at Command ===> as `E 1`, `B 2`, `V 3`, etc.
    That is the reliable raw-telnet equivalent of typing a line command in the
    field to the left of a data set.
    """

    # DSLIST ANSI rendering uses human-visible one-based coordinates because
    # SocketInputDriver.read_line_at() sends ANSI coordinates directly. Keep
    # these constants as the single source for command placement.
    DSLIST_COMMAND_ROW = 3
    DSLIST_COMMAND_COL = 13
    DSLIST_MESSAGE_ROW = 4
    DSLIST_LIST_START_ROW = 6
    DSLIST_WIDTH = 79

    def __init__(self, state: GibsonState, userid: str, tso_runner: Callable[[str], str]):
        self.state = state
        self.userid = userid.upper()
        self.tso_runner = tso_runner
        self.message = ""

    # ---------------- generic helpers ----------------
    def _ds(self, name: str) -> str:
        ds = name.strip().strip("'").upper()
        if not ds:
            return ""
        if ds.startswith(self.userid + "."):
            return ds
        return self.userid + "." + ds

    def _read(self, dsname: str) -> str:
        return self.state.datasets.read(self.userid, dsname)

    def _write(self, dsname: str, text: str) -> None:
        self.state.datasets.write(self.userid, dsname, text)

    def _auth_denial(self, dsname: str, access: str = "UPDATE") -> str:
        return (f"ISPF EDIT - DATA SET NOT OPENED\n"
                f"ICH408I USER({self.userid}) DATASET({dsname.upper()}) CL(DATASET) INSUFFICIENT ACCESS AUTHORITY\n"
                f"ISPF317I USER NOT AUTHORIZED TO EDIT DATA SET\n"
                f"EDIT NOT ALLOWED - REQUIRED ACCESS {access.upper()}")

    def _can_dataset_access(self, dsname: str, intent: str) -> tuple[bool, str]:
        try:
            if self.state.datasets.security is not None:
                self.state.datasets.security.authorize(self.userid, dsname, intent)
            return True, ""
        except PermissionError:
            needed = "UPDATE" if intent.upper() in {"UPDATE", "WRITE", "ALLOCATE"} else intent.upper()
            return False, self._auth_denial(dsname, needed)

    def _fit_visible(self, text: str, width: int = 79) -> str:
        return text[:width].ljust(width)

    def _dslist_title(self, prefix: str, row_text: str) -> str:
        right = row_text[:18]
        left_width = max(1, self.DSLIST_WIDTH - len(right))
        left = f"DSLIST - Data Sets Matching {prefix}"[:left_width]
        return left.ljust(left_width) + right

    def _send_pause(self, driver: SocketInputDriver, prompt: str = "Command ===>") -> None:
        driver.read_line_at(4, 13)

    def _dataset_info(self, dsname: str) -> Optional[DatasetInfo]:
        rows = [r for r in self.state.datasets.listcat(self.userid) if r.name == dsname]
        return rows[0] if rows else None

    def _edit_dataset_spec(self, driver: SocketInputDriver, send: Callable[[str], None], raw_spec: str, mode: str = "EDIT") -> str:
        spec = self._ds(raw_spec)
        dataset, member = self.state.datasets.split_name(spec)
        row = self._dataset_info(dataset)
        if row is None:
            return "DATA SET NOT FOUND"
        if mode.upper() == "EDIT":
            ok, denial = self._can_dataset_access(spec, "UPDATE")
            if not ok:
                return denial
        elif mode.upper() in {"VIEW", "BROWSE"}:
            ok, denial = self._can_dataset_access(spec, "READ")
            if not ok:
                return denial.replace("EDIT", mode.upper())
        if member and row.org != "PO":
            return "NOT A PARTITIONED DATA SET"
        if member:
            try:
                text = self._read(spec)
            except Exception:
                self.state.datasets.allocate(self.userid, spec, org="PO", recfm=row.recfm, lrecl=row.lrecl)
                text = ""
        else:
            if row.org == "PO":
                return self._member_list(driver, send, row, default_action="E" if mode == "EDIT" else mode[:1])
            try:
                text = self._read(spec)
            except Exception:
                text = ""
        InteractiveEditor(
            spec,
            text,
            mode=mode,
            recfm=row.recfm,
            lrecl=row.lrecl,
            save_callback=lambda t, d=spec: self._write(d, t),
            submitter=self._submit_jcl_text,
        ).run(driver, send)
        return ""


    def build_dsliste_panel(self, prefix: str = "") -> ScreenBuffer:
        """Build an ISPF 3.4 Data Set List Utility field registry panel."""
        s = ScreenBuffer()
        s.put(1, 1, "Menu  RefList  RefMode  Utilities  Help", colors.BLUE)
        s.put(2, 1, "Data Set List Utility".center(79), colors.WHITE)
        s.put(4, 1, "Option ===>", colors.BLUE)
        s.add_field("OPTION", 4, 13, 8, value="", protected=False, color=colors.RED, role="option", tab_order=1)
        s.put(6, 3, "Dsname Level . . .", colors.TURQUOISE)
        s.add_field("DSNAME_LEVEL", 6, 23, 44, value=prefix or self.userid, protected=False, color=colors.RED, role="dataset", tab_order=2)
        s.put(7, 3, "Volume serial . . .", colors.TURQUOISE)
        s.add_field("VOLUME_SERIAL", 7, 23, 6, value="", protected=False, color=colors.RED, role="option", tab_order=3)
        s.put(9, 3, "Data set list options", colors.WHITE)
        s.put(10, 5, "Initial View . . . VOLUME    Enter / to select option", colors.TURQUOISE)
        s.put(11, 5, "Confirm Delete . . YES", colors.TURQUOISE)
        s.put(12, 5, "Display Catalog Name NO", colors.TURQUOISE)
        s.put(24, 1, "F1=Help F2=Split F3=Exit F7=Backward F8=Forward F9=Swap F10=Actions F12=Cancel", colors.BLUE)
        s.set_cursor_field("OPTION")
        return s

    def build_dslist_result_panel(self, prefix: str, rows: list, page: int = 0, page_size: int = 13) -> ScreenBuffer:
        """Build a fielded DSLIST result panel with line-command fields."""
        s = ScreenBuffer()
        start = page * page_size
        visible = rows[start:start+page_size]
        row_text = f"Row {start+1 if rows else 0} of {len(rows)}"
        s.put(1, 1, "Menu  Functions  Confirm  Utilities  Help", colors.BLUE)
        s.put(2, 1, self._dslist_title(prefix, row_text), colors.BLUE)
        s.put(3, 1, "Command ===>", colors.BLUE)
        s.add_field("COMMAND", 3, 13, 44, value="", protected=False, color=colors.RED, role="command", tab_order=1)
        s.put(3, 58, "Scroll ===>", colors.BLUE)
        s.add_field("SCROLL", 3, 70, 5, value="PAGE", protected=False, color=colors.WHITE, role="scroll", tab_order=2)
        s.put(5, 1, "Command - Enter '/' to select action                  Message           Volume", colors.BLUE)
        tab = 3
        for n, r in enumerate(visible, start + 1):
            row = 6 + (n - start - 1)
            s.add_field(f"LINECMD.{n:06d}", row, 1, 4, value="", protected=False, color=colors.TURQUOISE, role="line_command", tab_order=tab); tab += 1
            s.put(row, 6, f"{n:>3} {getattr(r,'name',str(r)):<45}"[:55], colors.GREEN)
        s.put(22, 1, "***************************** END OF DATA SET LIST *****************************", colors.BLUE)
        s.put(24, 1, "Line commands: E Edit  S Select/Info  B Browse  V View  M Members  D Delete  R Rename", colors.BLUE)
        s.set_cursor_field("COMMAND")
        return s

    def panel_heading(self, title: str, command: str = "OPTION", scroll: bool = False) -> List[str]:
        right = "Scroll ===> PAGE" if scroll else ""
        return [
            colors.CLEAR + colors.ACTION_BAR,
            colors.BLUE + _pad("-" * 79) + colors.RESET,
            colors.WHITE + _pad(title.center(79)) + colors.RESET,
            colors.BLUE + f"{command:<7} ===>" + colors.RED + " " + colors.BLUE + (" " * 43) + (right if scroll else "") + colors.RESET,
        ]

    def footer(self) -> str:
        return colors.BLUE + "F1=Help  F3=Exit  F7=Up  F8=Down  F10=Actions  F12=Cancel" + colors.RESET

    def msgline(self, msg: Optional[str] = None) -> str:
        m = self.message if msg is None else msg
        return (colors.RED + _pad(m) + colors.RESET) if m else colors.TURQUOISE + _pad("") + colors.RESET

    def _handle_jump(self, option: str, driver: SocketInputDriver, send: Callable[[str], None], sdsf_loop: Optional[Callable[[str], None]] = None) -> bool:
        if not self.state.config.ispf_global_jump:
            return False
        opt = (option or "").strip().upper()
        if not opt.startswith("="):
            return False
        target = opt[1:]
        if target in ("", "MENU", "ISR"):
            return True
        if target in ("6", "COMMAND") or target.startswith("6,") or target.startswith("6."):
            if target not in ("6", "COMMAND"):
                sub = target[2:].strip().upper()
                self.message = f"JUMPED TO OPTION 6 ({sub})"
            self.panel_6(driver, send)
            return True
        if target in ("3.2", "32"):
            self.panel_32(driver, send)
            return True
        if target in ("3.3", "33"):
            self.panel_33(driver, send)
            return True
        if target in ("3.4", "34"):
            self.panel_34(driver, send)
            return True
        if target in ("5", "BATCH"):
            self.panel_batch(driver, send)
            return True
        if target in ("12", "DB2"):
            self.panel_db2i(driver, send)
            return True
        if target in ("12.1",):
            self.panel_db2i(driver, send, initial="1")
            return True
        if target in ("R", "RACF", "M.5"):
            self.panel_management(driver, send, initial="5")
            return True
        if target in ("M", "MGMT", "MANAGEMENT"):
            self.panel_management(driver, send)
            return True
        if target.startswith("S") and sdsf_loop is not None:
            panel = "MENU"
            if "." in target:
                panel = target.split(".", 1)[1] or "MENU"
            sdsf_loop(panel)
            return True
        self.message = f"INVALID JUMP ={target}"
        return True

    # ---------------- primary / utilities ----------------
    def primary_menu(self) -> str:
        lines = self.panel_heading("ISPF Primary Option Menu")
        lines += [
            self.msgline(),
            f" {colors.WHITE}0{colors.TURQUOISE}  Settings      Terminal/user parameters        {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[0]}",
            f" {colors.WHITE}1{colors.TURQUOISE}  View          Display data/listings           {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[1]}",
            f" {colors.WHITE}2{colors.TURQUOISE}  Edit          Create/change source            {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[2]}",
            f" {colors.WHITE}3{colors.TURQUOISE}  Utilities     Utility functions               {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[3]}",
            f" {colors.WHITE}5{colors.TURQUOISE}  Batch         Submit batch job                {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[4]}",
            f" {colors.WHITE}6{colors.TURQUOISE}  Command       TSO commands/REXX               {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[5]}",
            f" {colors.WHITE}8{colors.TURQUOISE}  Outlist       Held job output                 {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[6]}",
            f" {colors.WHITE}S{colors.TURQUOISE}  SDSF          System display/search           {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[7]}",
            f" {colors.WHITE}12{colors.TURQUOISE} DB2           DB2I menu / SPUFI               {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[8]}",
            f" {colors.WHITE}R{colors.TURQUOISE}  RACF          Security admin panels           {colors.BLUE}{v26_features.ispf_right_panel(self.userid)[9]}",
            f" {colors.WHITE}M{colors.TURQUOISE}  Management    zSecure/SMP/E tools             {v26_features.ispf_right_panel(self.userid)[10]}",
            "",
            f" {colors.BLUE}Enter {colors.WHITE}X{colors.BLUE} to Terminate using log/list defaults{colors.RESET}",
        ]
        return "\n".join(lines) + "\n"

    def utility_menu(self) -> str:
        lines = self.panel_heading("Utility Selection Menu")
        lines += [
            self.msgline(),
            f"  {colors.WHITE}1{colors.TURQUOISE}  Library     - Compress or print data set. Print, rename, delete members",
            f"  {colors.WHITE}2{colors.TURQUOISE}  Data Set    - Allocate, rename, delete, catalog, uncatalog, information",
            f"  {colors.WHITE}3{colors.TURQUOISE}  Move/Copy   - Move, copy, or promote members or data sets",
            f"  {colors.WHITE}4{colors.TURQUOISE}  Dslist      - Print or display list of data set names",
            f"  {colors.WHITE}8{colors.TURQUOISE}  Outlist     - Display, delete, or print held job output",
            "",
            self.footer(),
        ]
        return "\n".join(lines) + "\n"

    def run(self, driver: SocketInputDriver, send: Callable[[str], None], sdsf_loop: Callable[[str], None]) -> None:
        while True:
            send(self.primary_menu())
            res = driver.read_line_at(4, 13)
            choice = panel_input_value(res, context='ISPF').command.strip().upper()
            self.message = ""
            if self._handle_jump(choice, driver, send, sdsf_loop):
                continue
            if choice.startswith("="):
                choice = choice[1:]
            if choice in ("X", "EXIT", "F3", "PF3"):
                return
            if choice in ("0", "SETTINGS"):
                self.panel_settings(driver, send)
            elif choice in ("1", "VIEW"):
                self.panel_view_edit(driver, send, "VIEW")
            elif choice in ("2", "EDIT"):
                self.panel_view_edit(driver, send, "EDIT")
            elif choice == "3":
                self.utilities_loop(driver, send, sdsf_loop)
            elif choice == "3.2":
                self.panel_32(driver, send)
            elif choice == "3.3":
                self.panel_33(driver, send)
            elif choice == "3.4":
                self.panel_34(driver, send)
            elif choice in ("5", "BATCH"):
                self.panel_batch(driver, send)
            elif choice in ("6", "COMMAND"):
                self.panel_6(driver, send)
            elif choice in ("8", "OUTLIST"):
                sdsf_loop("O")
            elif choice == "S" or choice.startswith("S.") or choice.startswith("S;"):
                initial = "MENU"
                if choice.startswith("S."):
                    initial = choice.split(".", 1)[1].split(";", 1)[0] or "MENU"
                elif choice.startswith("S;"):
                    initial = choice.split(";", 1)[1].split(";", 1)[0] or "MENU"
                sdsf_loop(initial.upper())
            elif choice in ("12", "12.1", "DB2"):
                self.panel_db2i(driver, send, initial="1" if choice == "12.1" else "MENU")
            elif choice in ("R", "RACF"):
                self.panel_racf(driver, send)
            elif choice in ("M", "M.5", "MGMT", "MANAGEMENT", "EXTRA", "SOFTWARE"):
                self.panel_management(driver, send, initial="5" if choice == "M.5" else "MENU")
            else:
                self.message = "INVALID OPTION"

    def utilities_loop(self, driver: SocketInputDriver, send: Callable[[str], None], sdsf_loop: Callable[[str], None]) -> None:
        while True:
            send(self.utility_menu())
            res = driver.read_line_at(4, 13)
            opt = panel_input_value(res, context='ISPF').command.strip().upper()
            self.message = ""
            if self._handle_jump(opt, driver, send, sdsf_loop):
                continue
            if opt.startswith("="):
                opt = opt[1:]
            if opt in ("F3", "PF3", "X", "EXIT", "END"):
                return
            if opt == "1":
                self.panel_library(driver, send)
            elif opt == "2":
                self.panel_32(driver, send)
            elif opt == "3":
                self.panel_33(driver, send)
            elif opt == "4":
                self.panel_34(driver, send)
            elif opt == "8":
                sdsf_loop("O")
            else:
                self.message = "OPTION NOT AVAILABLE"


    def panel_settings(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        lines = self.panel_heading("ISPF Settings")
        lines += [
            self.msgline(),
            f" Terminal type . . . : 3278",
            f" Screen size . . . . : 24 X 80",
            f" Language . . . . . : ENGLISH",
            f" Command delimiter . : ;",
            f" Message level . . . : SHORT",
            f" Confirm delete . . : YES",
            f" Prefix . . . . . . : {self.userid}",
            "",
            "PF1=Help PF3=Exit PF7=Up PF8=Down PF12=Cancel",
        ]
        send("\n".join(lines) + "\n")
        self._send_pause(driver)

    def panel_library(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        lines = self.panel_heading("Library Utility")
        lines += [self.msgline(), "Supported commands: C Compress  P Print  R Rename member  D Delete member", "", self.footer()]
        send("\n".join(lines) + "\n")
        ds = driver.read_line(colors.TURQUOISE + "Data Set Name ===>" + colors.RED + " ").text.strip().upper()
        if ds:
            try:
                row = next((r for r in self.state.datasets.listcat(self.userid, self._ds(ds)) if r.name == self._ds(ds)), None)
                if row and row.org == "PO":
                    self._member_list(driver, send, row, default_action="B")
                else:
                    self._info_panel(driver, send, self._ds(ds))
            except Exception as e:
                self.message = f"LIBRARY UTILITY FAILED: {e}"

    # ---------------- View/Edit entry ----------------
    def panel_view_edit(self, driver: SocketInputDriver, send: Callable[[str], None], mode: str) -> None:
        lines = self.panel_heading(f"{mode.title()} Entry Panel")
        lines += [
            "",
            colors.TURQUOISE + "ISPF Library:" + colors.RESET,
            colors.TURQUOISE + "   Project . . ." + colors.RESET,
            colors.TURQUOISE + "   Group . . . ." + colors.RESET,
            colors.TURQUOISE + "   Type  . . . ." + colors.RESET,
            colors.TURQUOISE + "   Member  . . ." + colors.RESET,
            "",
            colors.TURQUOISE + "Other Partitioned, Sequential or VSAM Data Set:" + colors.RESET,
        ]
        send("\n".join(lines) + "\n")
        ds = driver.read_line(colors.TURQUOISE + "   Data Set Name . . ." + colors.RED + " ").text.strip().upper()
        if not ds:
            self.message = "DATA SET NAME REQUIRED"
            return
        fq = self._ds(ds)
        try:
            text = self._read(fq)
        except Exception:
            text = ""
            if mode == "EDIT":
                self.state.datasets.allocate(self.userid, fq, org="PS")
            else:
                self.message = "DATA SET NOT FOUND"
                return
        InteractiveEditor(fq, text, mode=mode, save_callback=lambda t, d=fq: self._write(d, t), submitter=self._submit_jcl_text).run(driver, send)

    # ---------------- Option 3.2 ----------------
    def panel_32(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        while True:
            lines = self.panel_heading("Data Set Utility")
            lines += [
                self.msgline(),
                f" {colors.WHITE}A{colors.TURQUOISE} Allocate new data set                 {colors.WHITE}C{colors.TURQUOISE} Catalog data set",
                f" {colors.WHITE}R{colors.TURQUOISE} Rename entire data set              {colors.WHITE}U{colors.TURQUOISE} Uncatalog data set",
                f" {colors.WHITE}D{colors.TURQUOISE} Delete entire data set              {colors.WHITE}S{colors.TURQUOISE} Short data set information",
                f" {colors.WHITE}I{colors.TURQUOISE} Data set information                {colors.WHITE}V{colors.TURQUOISE} VSAM utilities",
                "",
                colors.TURQUOISE + "For ISPF Library or Other Partitioned or Sequential Data Set:" + colors.RESET,
                colors.TURQUOISE + "   Data Set Name . . . . . . . . . . . ." + colors.RESET,
                "",
                self.footer(),
            ]
            send("\n".join(lines) + "\n")
            opt = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
            if self._handle_jump(opt, driver, send):
                continue
            if opt in ("F3", "PF3", "X", "EXIT", "END"):
                return
            self.message = ""
            if opt == "A":
                self._allocate_panel(driver, send)
            elif opt in ("D", "R", "I", "S", "C", "U"):
                ds = driver.read_line(colors.TURQUOISE + "Data Set Name ===>" + colors.RED + " ").text.strip().upper()
                if not ds:
                    self.message = "DATA SET NAME REQUIRED"
                    continue
                if opt == "D":
                    self._delete_ds(driver, self._ds(ds))
                elif opt == "R":
                    self._rename_ds(driver, self._ds(ds))
                elif opt in ("I", "S"):
                    self._info_panel(driver, send, self._ds(ds))
                elif opt == "C":
                    self.message = self.state.datasets.catalog(self.userid, self._ds(ds))
                elif opt == "U":
                    self.message = self.state.datasets.uncatalog(self.userid, self._ds(ds))
            else:
                self.message = "INVALID OPTION"

    def _allocate_panel(self, driver: SocketInputDriver, send: Callable[[str], None], preset_name: str = "") -> None:
        lines = self.panel_heading("Allocate New Data Set")
        lines += [
            colors.TURQUOISE + "Data Set Name  . . . . . . ." + colors.RESET,
            colors.TURQUOISE + "Management class . . . . . ." + colors.RESET,
            colors.TURQUOISE + "Storage class  . . . . . . ." + colors.RESET,
            colors.TURQUOISE + "Data class . . . . . . . . ." + colors.RESET,
            colors.TURQUOISE + "Volume serial . . . . . . . . WORK01" + colors.RESET,
            colors.TURQUOISE + "Device type . . . . . . . . . 3390" + colors.RESET,
            colors.TURQUOISE + "Space units . . . . . . . . . TRKS" + colors.RESET,
            colors.TURQUOISE + "Primary quantity  . . . . . . 1" + colors.RESET,
            colors.TURQUOISE + "Secondary quantity  . . . . . 1" + colors.RESET,
            colors.TURQUOISE + "Directory blocks . . . . . . . 0" + colors.RESET,
            colors.TURQUOISE + "Record format . . . . . . . . FB" + colors.RESET,
            colors.TURQUOISE + "Record length . . . . . . . . 80" + colors.RESET,
            colors.TURQUOISE + "Block size  . . . . . . . . . 6160" + colors.RESET,
            colors.TURQUOISE + "Data set organization . . . . PS/PO/PDSE" + colors.RESET,
            colors.TURQUOISE + "Replace existing? . . . . . . NO" + colors.RESET,
            colors.TURQUOISE + "Catalog? . . . . . . . . . . YES" + colors.RESET,
            colors.TURQUOISE + "Initial member . . . . . . ." + colors.RESET,
        ]
        send("\n".join(lines) + "\n")
        def _read_default(prompt: str, default: str = "") -> str:
            try:
                return driver.read_line(prompt).text.strip()
            except Exception:
                return default
        name = preset_name or _read_default(colors.TURQUOISE + "Data Set Name ===>" + colors.RED + " ").upper()
        if not name:
            self.message = "DATA SET NAME REQUIRED"
            return
        mgmt = _read_default(colors.TURQUOISE + "Management class ===>" + colors.RED + " ").upper()
        stor = _read_default(colors.TURQUOISE + "Storage class ===>" + colors.RED + " ").upper()
        data = _read_default(colors.TURQUOISE + "Data class ===>" + colors.RED + " ").upper()
        vol = _read_default(colors.TURQUOISE + "Volume serial ===>" + colors.RED + " WORK01 ", "WORK01").upper() or "WORK01"
        device = _read_default(colors.TURQUOISE + "Device type ===>" + colors.RED + " 3390 ", "3390").upper() or "3390"
        units = _read_default(colors.TURQUOISE + "Space units ===>" + colors.RED + " TRKS ", "TRKS").upper() or "TRKS"
        primary = _read_default(colors.TURQUOISE + "Primary quantity ===>" + colors.RED + " 1 ", "1") or "1"
        secondary = _read_default(colors.TURQUOISE + "Secondary quantity ===>" + colors.RED + " 1 ", "1") or "1"
        dirblks = _read_default(colors.TURQUOISE + "Directory blocks ===>" + colors.RED + " 0 ", "0") or "0"
        recfm = _read_default(colors.TURQUOISE + "Record format ===>" + colors.RED + " FB ", "FB").upper() or "FB"
        lrecl_s = _read_default(colors.TURQUOISE + "Record length ===>" + colors.RED + " 80 ", "80") or "80"
        blksize_s = _read_default(colors.TURQUOISE + "Block size ===>" + colors.RED + " 6160 ", "6160") or "6160"
        org_in = _read_default(colors.TURQUOISE + "Data set organization ===>" + colors.RED + " PS ", "PS").upper() or "PS"
        # Compatibility: older tests/drivers supplied the allocation type as the
        # second field, before the v30.288 storage-management prompts existed.
        # Treat a storage-management field that looks like a DSORG as the DSORG
        # so existing scripted ISPF 3.2 flows keep working.
        if mgmt in {"PO", "PDS", "PDSE", "LIBRARY", "PS"} and org_in == "PS":
            org_in = mgmt
        replace = _read_default(colors.TURQUOISE + "Replace existing? ===>" + colors.RED + " NO ", "NO").upper() or "NO"
        catalog = _read_default(colors.TURQUOISE + "Catalog? ===>" + colors.RED + " YES ", "YES").upper() or "YES"
        member = _read_default(colors.TURQUOISE + "Initial member ===>" + colors.RED + " ").upper()
        # Backward-compatible compact test/operator entry: name, type, dirblks, recfm, lrecl.
        # Older Gibson panels asked for fewer fields. Preserve that contract so
        # automation and training scripts do not need to answer newer SMS prompts.
        compact_org = ""
        if mgmt in {"LIBRARY", "PDSE", "PDS", "PO", "PS"} or (stor.isdigit() and data in {"F", "FB", "VB", "VBA", "U"} and vol.isdigit()):
            compact_org = mgmt if mgmt in {"LIBRARY", "PDSE", "PDS", "PO", "PS"} else "PS"
            dirblks = stor or "0"
            recfm = data or recfm
            lrecl_s = vol or lrecl_s
            org_in = compact_org
            vol = "WORK01"
        try:
            lrecl = int(lrecl_s); blksize = int(blksize_s); dir_count = int(dirblks) if str(dirblks).isdigit() else 0
        except ValueError:
            self.message = "INVALID NUMERIC ALLOCATION VALUE"; return
        org = "PO" if org_in in {"PO", "PDS", "PDSE", "LIBRARY"} or dir_count > 0 else "PS"
        full = self._ds(name)
        if self.state.datasets.ds_path(self.userid, full).exists() and replace not in {"Y", "YES"}:
            self.message = "DATA SET ALREADY EXISTS - SPECIFY REPLACE YES"; return
        self.state.datasets.allocate(self.userid, full, org=org, recfm=recfm, lrecl=lrecl)
        path = self.state.datasets.ds_path(self.userid, full)
        self.state.datasets._write_meta(path, org=org, recfm=recfm, lrecl=lrecl, blksize=blksize, volume=vol, cataloged=(catalog in {"Y","YES"}), owner=self.userid, mgmtclas=mgmt, storclas=stor, dataclas=data, space_units=units, primary=primary, secondary=secondary, dirblks=str(dir_count), device=device)
        if org == "PO" and member:
            self.state.datasets.write(self.userid, f"{full}({member})", "")
        alloc_kind = "PDSE/LIBRARY" if org_in in {"LIBRARY", "PDSE"} else ("PDS" if org == "PO" else "PS")
        self.message = f"DATA SET ALLOCATED AS {alloc_kind}"

    def _delete_ds(self, driver: SocketInputDriver, ds: str) -> None:
        confirm = driver.read_line(colors.RED + f"DELETE {ds}. ENTER confirms, CANCEL aborts ===>" + colors.RED + " ").text.strip().upper()
        if confirm == "CANCEL":
            self.message = "DELETE CANCELLED"
        else:
            self.message = self.state.datasets.delete(self.userid, ds)

    def _rename_ds(self, driver: SocketInputDriver, ds: str) -> None:
        new = driver.read_line(colors.TURQUOISE + "New Data Set Name ===>" + colors.RED + " ").text.strip().upper()
        if not new:
            self.message = "NEW NAME REQUIRED"; return
        try:
            oldp = self.state.datasets.ds_path(self.userid, ds)
            newp = self.state.datasets.ds_path(self.userid, self._ds(new))
            newp.parent.mkdir(parents=True, exist_ok=True)
            oldp.rename(newp)
            mp_old = self.state.datasets.meta_path(oldp)
            if mp_old.exists():
                mp_old.rename(self.state.datasets.meta_path(newp))
            self.message = "DATA SET RENAMED"
        except Exception as e:
            self.message = f"RENAME FAILED: {e}"

    def _info_panel(self, driver: SocketInputDriver, send: Callable[[str], None], ds: str) -> None:
        rows = [r for r in self.state.datasets.listcat(self.userid) if r.name == ds]
        if not rows:
            self.message = "DATA SET NOT FOUND"
            return
        r = rows[0]
        lines = self.panel_heading("Data Set Information", command="COMMAND")
        lines += [
            "",
            f" Data Set Name . . . : {colors.WHITE}{r.name}{colors.RESET}",
            f" General Data:        {colors.TURQUOISE}Volume serial . . . :{colors.WHITE} {r.volume}",
            f"                      {colors.TURQUOISE}Device type . . . . :{colors.WHITE} 3390",
            f"                      {colors.TURQUOISE}Organization  . . . :{colors.WHITE} {r.org}",
            f"                      {colors.TURQUOISE}Record format . . . :{colors.WHITE} {r.recfm}",
            f"                      {colors.TURQUOISE}Record length . . . :{colors.WHITE} {r.lrecl}",
            f"                      {colors.TURQUOISE}Block size  . . . . :{colors.WHITE} {r.blksize}",
            "",
            self.footer(),
        ]
        send("\n".join(lines) + "\n")
        self._send_pause(driver)

    # ---------------- Option 3.3 ----------------
    def panel_33(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        while True:
            lines = self.panel_heading("Move/Copy Utility")
            lines += [
                self.msgline(),
                f" {colors.WHITE}C{colors.TURQUOISE} Copy data set or member       {colors.WHITE}M{colors.TURQUOISE} Move data set or member",
                "",
                colors.TURQUOISE + "FROM ISPF Library or Other Partitioned or Sequential Data Set:" + colors.RESET,
                colors.TURQUOISE + "   Data Set Name . . . ." + colors.RESET,
                colors.TURQUOISE + "   Member . . . . . . ." + colors.RESET,
                "",
                colors.TURQUOISE + "TO ISPF Library or Other Partitioned or Sequential Data Set:" + colors.RESET,
                colors.TURQUOISE + "   Data Set Name . . . ." + colors.RESET,
                colors.TURQUOISE + "   Member . . . . . . ." + colors.RESET,
                "",
                self.footer(),
            ]
            send("\n".join(lines) + "\n")
            opt = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
            self.message = ""
            if self._handle_jump(opt, driver, send):
                continue
            if opt in ("F3", "PF3", "X", "EXIT", "END"):
                return
            if opt not in ("C", "M"):
                self.message = "ENTER C OR M"
                continue
            src = driver.read_line(colors.TURQUOISE + "From Data Set Name ===>" + colors.RED + " ").text.strip().upper()
            smem = driver.read_line(colors.TURQUOISE + "From Member ===>" + colors.RED + " ").text.strip().upper()
            dst = driver.read_line(colors.TURQUOISE + "To Data Set Name   ===>" + colors.RED + " ").text.strip().upper()
            dmem = driver.read_line(colors.TURQUOISE + "To Member ===>" + colors.RED + " ").text.strip().upper()
            try:
                sds = self._ds(src) + (f"({smem})" if smem else "")
                dds = self._ds(dst) + (f"({dmem or smem})" if (dmem or smem) else "")
                text = self._read(sds)
                self._write(dds, text)
                if opt == "M":
                    self.state.datasets.delete(self.userid, sds)
                self.message = "DATA SET COPIED" if opt == "C" else "DATA SET MOVED"
            except Exception as e:
                self.message = f"MOVE/COPY FAILED: {e}"

    # ---------------- Option 3.4 ----------------
    def panel_34(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        lines = self.panel_heading("Data Set List Utility")
        lines += [
            self.msgline(),
            colors.TURQUOISE + "Option  ===> blank - Display data set list" + colors.RESET,
            "",
            colors.TURQUOISE + "Enter one or both of the parameters below:" + colors.RESET,
            colors.TURQUOISE + "   Dsname Level . . ." + colors.RESET,
            colors.TURQUOISE + "   Volume serial  . ." + colors.RESET,
            "",
            colors.TURQUOISE + "Data set list options:" + colors.RESET,
            colors.TURQUOISE + "   Initial View . . . VOLUME    Enter / to select option" + colors.RESET,
            colors.TURQUOISE + "   Confirm Delete . . YES" + colors.RESET,
            colors.TURQUOISE + "   Display Catalog Name NO" + colors.RESET,
            "",
            self.footer(),
        ]
        send("\n".join(lines) + "\n")
        pref = driver.read_line(colors.TURQUOISE + "Dsname Level ===>" + colors.RED + " ").text.strip().upper()
        # In ISPF 3.4 the Dsname Level field is a listing prefix / HLQ selector.
        # It must not be auto-qualified with the current TSO prefix.
        prefix = pref.strip().strip("'") if pref else self.userid + "."
        self.dslist_loop(driver, send, prefix)

    def dslist_loop(self, driver: SocketInputDriver, send: Callable[[str], None], prefix: str) -> None:
        page = 0
        page_size = 13
        msg = ""
        last_action = "S"
        while True:
            rows = self.state.datasets.listcat(self.userid, prefix)
            rows = [r for r in rows if not r.path.name.endswith(".meta")]
            if not rows:
                msg = msg or "NO DATA SETS FOUND"
            max_page = max(0, (len(rows) - 1) // page_size)
            page = max(0, min(page, max_page))
            start = page * page_size
            visible = rows[start:start + page_size]
            row_text = f"Row {start+1 if rows else 0} of {len(rows)}"
            lines = [colors.CLEAR + colors.ACTION_BAR,
                     colors.BLUE + self._dslist_title(prefix, row_text) + colors.RESET,
                     colors.BLUE + "Command ===>" + colors.RED + " " + colors.BLUE + " " * 43 + "Scroll ===>" + colors.WHITE + " PAGE" + colors.RESET]
            lines.append(colors.RED + _pad(msg) + colors.RESET if msg else colors.TURQUOISE + "Enter line command at left.  TCP entry: E 1, S 1, B 1, V 1, / 1" + colors.RESET)
            lines.append(colors.BLUE + "Command - Enter '/' to select action                  Message           Volume" + colors.RESET)
            lines.append(colors.BLUE + "-------------------------------------------------------------------------------" + colors.RESET)
            for n, r in enumerate(visible, start + 1):
                prompt = "*PO" if r.org == "PO" else ""
                lines.append(colors.TURQUOISE + "____" + colors.RESET + " " + colors.GREEN + f"{n:>3} {r.name:<45}" + colors.WHITE + f"{prompt:<16}{r.volume:<6}" + colors.RESET)
            if start + page_size >= len(rows):
                lines.append(colors.BLUE + "***************************** END OF DATA SET LIST *****************************" + colors.RESET)
            while len(lines) < 23:
                lines.append("")
            lines.append(colors.BLUE + "Line commands: E Edit  S Select/Info  B Browse  V View  M Members  D Delete  R Rename" + colors.RESET)
            send("\n".join(lines) + "\n")
            # The command field is on the rendered ``Command ===>`` row.
            # Keep both the raw typed text (needed for line commands such as
            # ``E 1`` and allocation/dataset syntax) and the logical command
            # (needed for PF-key actions such as PF3/PF7/PF8).  A previous
            # PF-key cleanup dropped ``raw`` and read from the message row,
            # which caused normal DSLIST commands to raise NameError and made
            # user input overwrite panel text.
            res = driver.read_line_at(self.DSLIST_COMMAND_ROW, self.DSLIST_COMMAND_COL)
            panel = panel_input_value(res, context='ISPF')
            raw = (getattr(panel, 'text', '') or getattr(panel, 'command', '') or '').strip()
            u = (getattr(panel, 'command', '') or raw).strip().upper()
            msg = ""
            if u in ("F3", "PF3", "X", "EXIT", "END"):
                return
            if u in ("F7", "PF7", "UP"):
                page = max(0, page - 1); continue
            if u in ("F8", "PF8", "DOWN"):
                page = min(max_page, page + 1); continue
            if not raw:
                continue
            m_alloc = re.match(r"^(A|ALLOC|ALLOCATE|NEW|CREATE|C)\s+(.+)$", raw, re.I)
            if m_alloc and not m_alloc.group(2).strip().isdigit():
                self._allocate_panel(driver, send, preset_name=m_alloc.group(2).strip())
                msg = self.message
                continue
            if "(" in raw and raw.rstrip().endswith(")"):
                msg = self._edit_dataset_spec(driver, send, raw, mode="EDIT")
                continue
            if u in ("R", "REFRESH"):
                continue
            if u.startswith("SORT"):
                rows.sort(key=lambda x: x.name)
                continue
            action, idx, err = self._parse_dslist_command(raw, rows, last_action)
            if err:
                msg = err
                continue
            assert action and idx is not None
            last_action = action
            msg = self._dslist_action(driver, send, action, rows[idx])

    def _parse_dslist_command(self, raw: str, rows: List[DatasetInfo], last_action: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        parts = raw.strip().upper().split()
        if not parts:
            return None, None, None
        if parts[0] == "=":
            parts[0] = last_action
        if len(parts) == 1:
            # Permit `E` then prompt in calling context? Here return error for clarity.
            return None, None, "ENTER LINE COMMAND AND ROW NUMBER, FOR EXAMPLE: E 1"
        action = parts[0]
        target = parts[1]
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(rows):
                return action, idx, None
            return None, None, "ROW NOT FOUND"
        # Match exact or suffix DSN.
        for i, row in enumerate(rows):
            if row.name == target or row.name.endswith("." + target):
                return action, i, None
        return None, None, "DATA SET NOT FOUND"

    def _dslist_action(self, driver: SocketInputDriver, send: Callable[[str], None], action: str, row: DatasetInfo) -> str:
        a = action.upper()
        ds = row.name
        if a == "/":
            return self._action_menu(driver, send, row)
        if a in ("S", "SELECT"):
            # On a PDS, S enters a member list. On PS, show short information.
            if row.org == "PO":
                return self._member_list(driver, send, row, default_action="B")
            self._info_panel(driver, send, ds)
            return ""
        if a in ("E", "EDIT"):
            ok, denial = self._can_dataset_access(ds, "UPDATE")
            if not ok:
                return denial
            if row.org == "PO":
                return self._member_list(driver, send, row, default_action="E")
            try:
                text = self._read(ds)
            except Exception:
                text = ""
            InteractiveEditor(ds, text, mode="EDIT", recfm=row.recfm, lrecl=row.lrecl,
                              save_callback=lambda t, d=ds: self._write(d, t),
                              submitter=self._submit_jcl_text).run(driver, send)
            return ""
        if a in ("B", "BROWSE"):
            ok, denial = self._can_dataset_access(ds, "READ")
            if not ok:
                return denial.replace("EDIT", "BROWSE")
            if row.org == "PO":
                return self._member_list(driver, send, row, default_action="B")
            InteractiveEditor(ds, self._read(ds), mode="BROWSE", recfm=row.recfm, lrecl=row.lrecl).run(driver, send)
            return ""
        if a in ("V", "VIEW"):
            ok, denial = self._can_dataset_access(ds, "READ")
            if not ok:
                return denial.replace("EDIT", "VIEW")
            if row.org == "PO":
                return self._member_list(driver, send, row, default_action="V")
            InteractiveEditor(ds, self._read(ds), mode="VIEW", recfm=row.recfm, lrecl=row.lrecl).run(driver, send)
            return ""
        if a in ("M", "MEM", "MEMBERS"):
            return self._member_list(driver, send, row, default_action="B")
        if a in ("I", "INFO"):
            self._info_panel(driver, send, ds)
            return ""
        if a in ("D", "DELETE"):
            self._delete_ds(driver, ds)
            return self.message
        if a in ("R", "RENAME"):
            self._rename_ds(driver, ds)
            return self.message
        if a in ("C", "CAT"):
            return self.state.datasets.catalog(self.userid, ds)
        if a == "U":
            return self.state.datasets.uncatalog(self.userid, ds)
        return "UNSUPPORTED LINE COMMAND"

    def _action_menu(self, driver: SocketInputDriver, send: Callable[[str], None], row: DatasetInfo) -> str:
        lines = [colors.CLEAR,
                 colors.BLUE + "+----------------------- Data Set List Actions -----------------------+" + colors.RESET,
                 f" Data Set: {row.name}",
                 "",
                 "  1  Edit              2  View              3  Browse",
                 "  4  Member List       5  Delete            6  Rename",
                 "  7  Information       8  Catalog           9  Uncatalog",
                 "  A  Allocate/Create new data set",
                 colors.BLUE + "+---------------------------------------------------------------------+" + colors.RESET]
        send("\n".join(lines) + "\n")
        pick = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
        mapping = {"1":"E", "2":"V", "3":"B", "4":"M", "5":"D", "6":"R", "7":"I", "8":"C", "9":"U", "A":"A"}
        choice = mapping.get(pick, pick)
        if choice == "A":
            self._allocate_panel(driver, send)
            return self.message
        return self._dslist_action(driver, send, choice, row)

    def _member_list(self, driver: SocketInputDriver, send: Callable[[str], None], row: DatasetInfo, default_action: str = "B") -> str:
        if row.org != "PO" or not row.path.is_dir():
            return "NOT A PARTITIONED DATA SET"
        msg = ""
        while True:
            members = sorted(p for p in row.path.iterdir() if p.is_file() and not p.name.endswith(".meta"))
            lines = [colors.CLEAR + colors.ACTION_BAR,
                     colors.BLUE + f"Member List  {row.name:<47} Row 1 of {len(members)}" + colors.RESET,
                     colors.BLUE + "Command ===>" + colors.RED + " " + colors.BLUE + " " * 43 + "Scroll ===>" + colors.WHITE + " PAGE" + colors.RESET,
                     colors.RED + _pad(msg) + colors.RESET if msg else colors.TURQUOISE + "Enter E, B, V, S, D, R to left of member.  TCP entry: E 1" + colors.RESET,
                     colors.BLUE + "Name     Prompt       Size  Created     Changed            ID" + colors.RESET,
                     colors.BLUE + "-------------------------------------------------------------------------------" + colors.RESET]
            for n, p in enumerate(members, 1):
                lines.append(colors.TURQUOISE + "____" + colors.RESET + " " + colors.GREEN + f"{n:>3} {p.name.upper():<8}             {p.stat().st_size:>5}" + colors.RESET)
            if not members:
                lines.append(colors.BLUE + "******************************* NO MEMBERS *************************************" + colors.RESET)
            while len(lines) < 23:
                lines.append("")
            lines.append(colors.BLUE + "Line commands: E Edit  S Select  B Browse  V View  D Delete  R Rename" + colors.RESET)
            send("\n".join(lines) + "\n")
            res = driver.read_line_at(3, 13)
            u = panel_input_value(res, context='ISPF').command.strip().upper()
            msg = ""
            if u in ("F3", "PF3", "X", "EXIT", "END"):
                return ""
            parts = u.split()
            if len(parts) >= 2 and not parts[1].isdigit():
                action, mem = parts[0], parts[1].upper()
                if action in {"E", "EDIT", "S", "SELECT", "A", "CREATE", "NEW", "I"}:
                    if not re.fullmatch(r"[A-Z0-9#$@]{1,8}", mem):
                        msg = "INVALID MEMBER NAME"; continue
                    mdsn = row.name + f"({mem})"
                    ok, denial = self._can_dataset_access(mdsn, "UPDATE")
                    if not ok:
                        msg = denial.splitlines()[-1]; continue
                    p = row.path / mem
                    if not p.exists():
                        ans = driver.read_line(colors.TURQUOISE + f"Member {mem} does not exist. Create? Y/N ===>" + colors.RED + " ").text.strip().upper()
                        if ans not in {"Y", "YES"}:
                            msg = "CREATE CANCELLED"; continue
                        p.touch()
                    InteractiveEditor(mdsn, p.read_text(encoding="utf-8", errors="ignore"), mode="EDIT", save_callback=lambda t, path=p, d=mdsn: self._write(d, t), submitter=self._submit_jcl_text).run(driver, send)
                    continue
            if len(parts) == 1 and parts[0].isdigit():
                parts = [default_action, parts[0]]
            if len(parts) < 2 or not parts[1].isdigit():
                msg = "ENTER LINE COMMAND AND MEMBER NUMBER, FOR EXAMPLE: E 1"
                continue
            action, n = parts[0], int(parts[1])
            if not (1 <= n <= len(members)):
                msg = "MEMBER NOT FOUND"
                continue
            p = members[n - 1]
            mdsn = row.name + f"({p.name.upper()})"
            if action in ("E", "EDIT"):
                ok, denial = self._can_dataset_access(mdsn, "UPDATE")
                if not ok:
                    msg = denial.splitlines()[-1]; continue
                InteractiveEditor(mdsn, p.read_text(encoding="utf-8", errors="ignore"), mode="EDIT",
                                  save_callback=lambda t, d=mdsn: self._write(d, t),
                                  submitter=self._submit_jcl_text).run(driver, send)
            elif action in ("B", "BROWSE", "S", "SELECT"):
                ok, denial = self._can_dataset_access(mdsn, "READ")
                if not ok:
                    msg = denial.splitlines()[-1]; continue
                InteractiveEditor(mdsn, p.read_text(encoding="utf-8", errors="ignore"), mode="BROWSE").run(driver, send)
            elif action in ("V", "VIEW"):
                ok, denial = self._can_dataset_access(mdsn, "READ")
                if not ok:
                    msg = denial.splitlines()[-1]; continue
                InteractiveEditor(mdsn, p.read_text(encoding="utf-8", errors="ignore"), mode="VIEW").run(driver, send)
            elif action in ("D", "DELETE"):
                confirm = driver.read_line(colors.RED + f"DELETE {mdsn}. ENTER confirms, CANCEL aborts ===>" + colors.RED + " ").text.strip().upper()
                if confirm != "CANCEL":
                    p.unlink(missing_ok=True)
            elif action in ("R", "RENAME"):
                new = driver.read_line(colors.TURQUOISE + "New member name ===>" + colors.RED + " ").text.strip().upper()
                if new:
                    p.rename(p.with_name(new))

    # ---------------- Option 6 / Batch ----------------
    def panel_6(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        while True:
            lines = self.panel_heading("ISPF Command Shell", command="COMMAND")
            lines += [self.msgline(), colors.TURQUOISE + "Enter TSO command, CLIST, or REXX EXEC below." + colors.RESET, "", self.footer()]
            send("\n".join(lines) + "\n")
            res = driver.read_line_at(4, 13)
            cmd = panel_input_value(res, context='ISPF').command.strip()
            if self._handle_jump(cmd, driver, send):
                continue
            if cmd.upper() in ("F3", "PF3", "END", "EXIT", "X"):
                return
            if not cmd:
                continue
            out = self.tso_runner(res.text.strip())
            send(colors.CLEAR + out.rstrip("\n") + "\n")
            self._send_pause(driver)

    # ---------------- Option 12 / DB2I ----------------
    def run_db2i_spufi(self, sql: str, output_ds: str = "") -> str:
        result = Db2Simulator(self.state).format_spufi(sql, self.userid)
        if output_ds.strip():
            self._write(self._ds(output_ds), result)
        return result

    def panel_db2i(self, driver: SocketInputDriver, send: Callable[[str], None], initial: str = "MENU") -> None:
        option = (initial or "MENU").strip().upper()
        while True:
            if option in {"MENU", ""}:
                lines = self.panel_heading(f"DB2I PRIMARY OPTION MENU          SSID: {SYSTEM_INFO['SUBSYSTEM']}")
                lines += [
                    self.msgline(),
                    f" {colors.WHITE}1{colors.TURQUOISE}  SPUFI         Execute SQL statements from an input data set",
                    f" {colors.WHITE}2{colors.TURQUOISE}  DCLGEN        Generate declarations (display-only)",
                    f" {colors.WHITE}5{colors.TURQUOISE}  COMMANDS      Db2 commands and DISPLAY GROUP",
                    f" {colors.WHITE}7{colors.TURQUOISE}  CATALOG       Catalog queries for SYSIBM tables",
                    f" {colors.WHITE}X{colors.TURQUOISE}  Exit          Return to ISPF primary menu",
                    "",
                    self.footer(),
                ]
                send("\n".join(lines) + "\n")
                choice = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
            else:
                choice = option

            option = "MENU"
            if self._handle_jump(choice, driver, send):
                continue
            if choice in {"X", "EXIT", "END", "F3", "PF3", ""}:
                return
            self.message = ""
            if choice == "1":
                self.panel_spufi(driver, send)
            elif choice == "2":
                send(colors.CLEAR + self.panel_heading("DB2I DCLGEN")[0] + "\n" + colors.WHITE + "DSNT418I DCLGEN SUPPORT IS DISPLAY-ONLY IN GIBSON. USE SPUFI/CATALOG FOR ADMIN TASKS.\n" + colors.RESET)
                self._send_pause(driver)
            elif choice == "5":
                self.panel_db2_commands(driver, send)
            elif choice == "7":
                self.panel_db2_catalog(driver, send)
            else:
                self.message = "INVALID DB2 OPTION"

    def panel_spufi(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        while True:
            lines = self.panel_heading("SPUFI")
            lines += [
                self.msgline(),
                colors.TURQUOISE + "  INPUT DATA SET NAME . . . . . . . . . ." + colors.RESET,
                colors.TURQUOISE + "  OUTPUT DATA SET NAME  . . . . . . . . ." + colors.RESET,
                colors.TURQUOISE + "  EDIT INPUT  . . . . . . . . . . . . . ." + colors.RESET,
                colors.TURQUOISE + "  EXECUTE SQL FROM THE INPUT DATA SET AND OPTIONALLY SAVE OUTPUT." + colors.RESET,
                "",
                self.footer(),
            ]
            send("\n".join(lines) + "\n")
            in_ds = driver.read_line(colors.TURQUOISE + "INPUT  ===>" + colors.RED + " ").text.strip().upper()
            if in_ds.upper() in {"F3", "PF3", "X", "EXIT", "END"}:
                return
            out_ds = driver.read_line(colors.TURQUOISE + "OUTPUT ===>" + colors.RED + " ").text.strip().upper()
            edit_in = driver.read_line(colors.TURQUOISE + "EDIT INPUT (YES/NO) ===>" + colors.RED + " ").text.strip().upper() or "NO"
            if not in_ds:
                self.message = "INPUT DATA SET NAME REQUIRED"
                continue
            fq_in = self._ds(in_ds)
            try:
                sql = self._read(fq_in)
            except Exception:
                sql = "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1;"
                self.state.datasets.allocate(self.userid, fq_in, org="PS")
                self._write(fq_in, sql)
            if edit_in in {"Y", "YES"}:
                InteractiveEditor(fq_in, sql, mode="EDIT", save_callback=lambda t, d=fq_in: self._write(d, t)).run(driver, send)
                sql = self._read(fq_in)
            result = self.run_db2i_spufi(sql, out_ds)
            send(colors.CLEAR + result + "\n")
            self._send_pause(driver)
            return

    def panel_db2_commands(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        while True:
            lines = self.panel_heading("DB2 COMMANDS")
            lines += [self.msgline(), colors.TURQUOISE + "ENTER DISPLAY GROUP, -DISPLAY GROUP, OR SQL (SELECT ...)" + colors.RESET, "", self.footer()]
            send("\n".join(lines) + "\n")
            cmd = read_panel_command(driver, 4, 13, context='ISPF').command.strip()
            if self._handle_jump(cmd, driver, send):
                continue
            if cmd.upper() in {"F3", "PF3", "X", "EXIT", "END", ""}:
                return
            if cmd.strip().upper() in {"DISPLAY GROUP", "-DISPLAY GROUP"}:
                out = Db2Simulator(self.state).display_group()
            else:
                out = self.run_db2i_spufi(cmd)
            send(colors.CLEAR + out + "\n")
            self._send_pause(driver)

    def panel_db2_catalog(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        lines = self.panel_heading("DB2 CATALOG QUICK QUERY")
        lines += [self.msgline(), colors.TURQUOISE + "SELECT FROM SYSIBM.SYSTABLES / SYSCOLUMNS / SYSUSERAUTH" + colors.RESET, "", self.footer()]
        send("\n".join(lines) + "\n")
        obj = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
        if self._handle_jump(obj, driver, send):
            return
        if obj in {"F3", "PF3", "X", "EXIT", "END", ""}:
            return
        mapping = {
            "SYSTABLES": "SELECT NAME,CREATOR,DBNAME,TSNAME FROM SYSIBM.SYSTABLES;",
            "SYSCOLUMNS": "SELECT TBNAME,NAME,COLTYPE,LENGTH FROM SYSIBM.SYSCOLUMNS;",
            "SYSUSERAUTH": "SELECT USERID,AUTHORITY,OMVS FROM SYSIBM.SYSUSERAUTH;",
            "SYSUSERS": "SELECT USERID,AUTHORITY,OMVS FROM SYSIBM.SYSUSERS;",
        }
        sql = mapping.get(obj, obj if obj.startswith("SELECT ") else f"SELECT NAME,CREATOR,DBNAME,TSNAME FROM SYSIBM.SYSTABLES WHERE NAME='{obj}';")
        send(colors.CLEAR + self.run_db2i_spufi(sql) + "\n")
        self._send_pause(driver)

    # ---------------- Management / RACF ----------------
    def _extra_submenu(self, driver: SocketInputDriver, send: Callable[[str], None], app: str) -> None:
        """Interactive Extra Software submenus for zSecure, SMP/E, and RSS."""
        app_u = app.upper()
        while True:
            if app_u == "ZSEC":
                menu_cmd = "ZSEC"; mapping = {"1":"ZSEC EVENTS", "2":"ZSEC RACF", "3":"ZSEC ACCESS", "4":"ZSEC COMPLIANCE", "5":"ZSEC ALERTS", "6":"ZSEC SMF", "7":"ZSEC REPORTS", "8":"ZSEC APF", "9":"ZSEC SETTINGS"}
            elif app_u == "SMPE":
                menu_cmd = "SMPE"; mapping = {"1":"SMPE CSI", "2":"SMPE ZONES", "3":"SMPE LIST SYSMODS", "4":"SMPE RECEIVE", "5":"SMPE APPLY CHECK", "6":"SMPE ACCEPT CHECK", "7":"SMPE REPORT", "8":"SMPE HOLDDATA", "9":"SMPE SETTINGS"}
            elif app_u == "SYSVIEW":
                menu_cmd = "SYSVIEW"; mapping = {"1":"SYSVIEW SYSTEM", "2":"SYSVIEW JOBS", "3":"SYSVIEW CICS", "4":"SYSVIEW DB2", "5":"SYSVIEW TCPIP", "6":"SYSVIEW USS", "7":"SYSVIEW STORAGE", "8":"SYSVIEW ALERTS", "9":"SYSVIEW LOG", "A":"SYSVIEW RSS", "B":"SYSVIEW DATASETS", "C":"SYSVIEW DATASETS", "D":"SYSVIEW REFRESH"}
            else:
                menu_cmd = "RSS"; mapping = {"1":"RSS LIST", "2":"RSS SHOW", "3":"RSS FETCH", "4":"RSS REFRESH", "5":"RSS ADD TRAINING https://example.invalid/training.xml", "6":"RSS DELETE TRAINING", "7":"RSS CONFIG", "8":"RSS EXPORT RSS.CTI.RSS.REPORT"}
            out = v26_features.dispatch_tso(self.state, self.userid, menu_cmd) or "APPLICATION NOT AVAILABLE"
            send(colors.CLEAR + out.rstrip("\n") + "\n")
            cmd = read_panel_command(driver, 4, 13, context='ISPF').command.strip()
            uc = cmd.upper()
            if uc in {"X", "EXIT", "END", "F3", "PF3", ""}:
                return
            run_cmd = mapping.get(uc, cmd)
            out = v26_features.dispatch_tso(self.state, self.userid, run_cmd) or "INVALID EXTRA SOFTWARE OPTION"
            send(colors.CLEAR + out.rstrip("\n") + "\n")
            self._send_pause(driver)

    def panel_management(self, driver: SocketInputDriver, send: Callable[[str], None], initial: str = "MENU") -> None:
        option = (initial or "MENU").strip().upper()
        while True:
            if option in {"MENU", ""}:
                lines = self.panel_heading("Management Option Menu - Extra Software")
                lines += [
                    self.msgline(),
                    f" {colors.WHITE}1{colors.TURQUOISE}  zSecure      Security and compliance analysis",
                    f" {colors.WHITE}2{colors.TURQUOISE}  SMP/E        Software installation and maintenance",
                    f" {colors.WHITE}3{colors.TURQUOISE}  RSS          CTI/RSS feed reader",
                    f" {colors.WHITE}4{colors.TURQUOISE}  SYSVIEW      Performance and operations monitor",
                    f" {colors.WHITE}5{colors.TURQUOISE}  RACF         View and update RACF settings",
                    f" {colors.WHITE}X{colors.TURQUOISE}  Exit         Return to ISPF primary menu",
                    "",
                    self.footer(),
                ]
                send("\n".join(lines) + "\n")
                choice = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
            else:
                choice = option
            option = "MENU"
            if self._handle_jump(choice, driver, send):
                continue
            if choice in {"X", "EXIT", "END", "F3", "PF3", ""}:
                return
            self.message = ""
            if choice in {"1", "Z", "ZSEC", "ZSECURE", "CKR"}:
                self._extra_submenu(driver, send, "ZSEC")
            elif choice in {"2", "SMP", "SMPE", "SMP/E"}:
                self._extra_submenu(driver, send, "SMPE")
            elif choice in {"3", "RSS"}:
                self._extra_submenu(driver, send, "RSS")
            elif choice in {"4", "SYSVIEW", "SYSV"}:
                self._extra_submenu(driver, send, "SYSVIEW")
            elif choice == "5":
                self.panel_racf(driver, send)
            else:
                out = v26_features.dispatch_tso(self.state, self.userid, choice)
                if out:
                    send(colors.CLEAR + out.rstrip("\n") + "\n")
                    self._send_pause(driver)
                else:
                    self.message = "INVALID EXTRA SOFTWARE OPTION"

    def panel_racf(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        examples = {
            "1": "LISTUSER IBMUSER ALL",
            "2": "LISTGRP SYS1",
            "3": "RLIST DATASET IBMUSER.** ALL",
            "4": "SEARCH CLASS(FACILITY) FILTER(*)",
            "5": "RLIST CICS RSS.* ALL",
            "6": "RLIST DSNR DB2A.* ALL",
            "7": "RLIST STARTED ** ALL",
            "8": "SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)",
            "9": "RLIST PTKTDATA RSS ALL",
            "A": "MFA STATUS",
            "B": "RACDCERT CERTAUTH LIST",
            "C": "SETROPTS LIST",
            "D": "ZSEC SMF80",
            "E": "SEARCH CLASS(DATASET) FILTER(*)",
        }
        while True:
            lines = self.panel_heading("RACF ADMINISTRATION - RSS SECURITY SERVICES")
            lines += [
                self.msgline(),
                colors.TURQUOISE + "SELECT OPTION OR ENTER RACF COMMAND ON COMMAND ===>" + colors.RESET,
                "",
                f" {colors.WHITE}1{colors.TURQUOISE}  User administration        ADDUSER ALTUSER DELUSER LISTUSER",
                f" {colors.WHITE}2{colors.TURQUOISE}  Group administration       ADDGROUP ALTGROUP LISTGRP CONNECT",
                f" {colors.WHITE}3{colors.TURQUOISE}  Dataset profiles           ADDSD ALTDSD LISTDSD PERMIT",
                f" {colors.WHITE}4{colors.TURQUOISE}  General resources          RDEFINE RALTER RLIST PERMIT",
                f" {colors.WHITE}5{colors.TURQUOISE}  CICS resource security     TCICSTRN/GCICSTRN/FACILITY",
                f" {colors.WHITE}6{colors.TURQUOISE}  DB2 resource security      DSNR and subsystem profiles",
                f" {colors.WHITE}7{colors.TURQUOISE}  Started task profiles      STARTED class mapping",
                f" {colors.WHITE}8{colors.TURQUOISE}  SURROGAT/delegation        Batch submit authority",
                f" {colors.WHITE}9{colors.TURQUOISE}  PassTicket/PTKTDATA        APPLID and replay settings",
                f" {colors.WHITE}A{colors.TURQUOISE}  MFA administration         User token and IPL MFA state",
                f" {colors.WHITE}B{colors.TURQUOISE}  Digital certificates       RACDCERT / DIGTCERT / rings",
                f" {colors.WHITE}C{colors.TURQUOISE}  SETROPTS options           CLASSACT RACLIST PASSWORD MFA",
                f" {colors.WHITE}D{colors.TURQUOISE}  Audit / SMF options        SMF80 and audit review",
                f" {colors.WHITE}E{colors.TURQUOISE}  Search/list profiles       SEARCH and RLIST shortcuts",
                f" {colors.WHITE}F{colors.TURQUOISE}  Command shell              Enter RACF command directly",
                "",
                colors.TURQUOISE + "Examples: ADDUSER TRAINEE PASSWORD(PASS123) DFLTGRP(STUDENT) | ALTUSER TRAINEE OMVS(UID(10077))" + colors.RESET,
                "",
                self.footer(),
            ]
            send("\n".join(lines) + "\n")
            cmd = read_panel_command(driver, 4, 13, context='ISPF').command.strip()
            if self._handle_jump(cmd, driver, send):
                continue
            uc = cmd.upper()
            if uc in {"X", "EXIT", "END", "F3", "PF3", ""}:
                return
            if uc in examples:
                out = self.tso_runner(examples[uc])
            else:
                out = self.tso_runner(cmd)
            send(colors.CLEAR + out.rstrip("\n") + "\n")
            self._send_pause(driver)

    def panel_batch(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        lines = self.panel_heading("Submit Job")
        lines += ["", colors.TURQUOISE + "JCL Data Set Name . . ." + colors.RESET]
        send("\n".join(lines) + "\n")
        ds = driver.read_line(colors.TURQUOISE + "JCL Data Set Name ===>" + colors.RED + " ").text.strip().upper()
        self.message = self.tso_runner(f"SUBMIT '{self._ds(ds)}'") if ds else "JCL DATA SET REQUIRED"

    def _submit_jcl_text(self, jcl: str) -> str:
        job = self.state.jes.submit(jcl, self.userid, runner=self.tso_runner)
        return f"JOB {job.jobid} SUBMITTED"

    # Backward-compatible non-interactive helpers.
    def option6_command(self, command: str) -> str:
        return self.tso_runner(command)

    def edit_dataset_once(self, dsname: str, command: str) -> str:
        from gibson.apps.editor import EditorModel, EditorCommandProcessor
        try:
            text = self.state.datasets.read(self.userid, dsname)
        except Exception:
            text = ""
        model = EditorModel(text.splitlines(), recfm="FB", lrecl=80)
        proc = EditorCommandProcessor(model)
        msg = proc.execute(command)
        if command.upper() == "SAVE":
            self.state.datasets.write(self.userid, dsname, model.text())
            msg = "DATA SAVED"
        return msg

# Production-grade ISPF M.3/R/M.4 panel routing. These overrides make the
# interactive panels call the stateful engines rather than static examples.
_ISPF_ORIG_EXTRA_SUBMENU_PROD = IspfApp._extra_submenu
_ISPF_ORIG_PANEL_RACF_PROD = IspfApp.panel_racf

def _ispf_prod_extra_submenu(self, driver, send, app: str) -> None:
    app_u = (app or '').upper()
    from gibson.core import v26_features
    if app_u == 'RSS':
        menu = '\n'.join(['RSS CTI/RSS FEED READER','1  List configured feeds','2  Fetch / refresh feeds','3  Show cached headlines','4  Add feed','5  Delete feed','6  Export report','7  Edit feed dataset','8  Last run status','X  Exit'])
        mapping={'1':'RSS LIST','2':'RSS FETCH','3':'RSS SHOW','4':'RSS ADD TRAINING https://example.invalid/training.xml','5':'RSS DELETE TRAINING','6':'RSS EXPORT RSS.CTI.RSS.REPORT','7':'RSS CONFIG','8':'RSS CONFIG'}
    elif app_u == 'SYSVIEW':
        menu = v26_features.dispatch_tso(self.state, self.userid, 'SYSVIEW') or 'SYSVIEW unavailable'
        mapping={'1':'SYSVIEW SYSTEM','2':'SYSVIEW JOBS','3':'SYSVIEW CICS','4':'SYSVIEW DB2','5':'SYSVIEW TCPIP','6':'SYSVIEW USS','7':'SYSVIEW STORAGE','8':'SYSVIEW ALERTS','9':'SYSVIEW RSS','A':'SYSVIEW DATASETS','B':'SYSVIEW RSS','C':'SYSVIEW DATASETS','D':'SYSVIEW REFRESH'}
    elif app_u == 'ZSEC':
        menu = v26_features.dispatch_tso(self.state, self.userid, 'ZSEC') or 'zSecure unavailable'
        mapping={'1':'ZSEC RACF','2':'ZSEC PRIVILEGE','3':'ZSEC UID0','4':'ZSEC RACFDS','5':'ZSEC ACCESS','6':'ZSEC CICS','7':'ZSEC DB2','8':'ZSEC SERVAUTH','9':'ZSEC PASSTICKET','A':'ZSEC MFA','B':'ZSEC ICSF','C':'ZSEC RACDCERT','D':'ZSEC STARTED','E':'ZSEC SURROGAT','F':'ZSEC JES','G':'ZSEC EVENTS','H':'ZSEC COMPLIANCE','I':'ZSEC DRIFT','J':'ZSEC REPORTS'}
    else:
        return _ISPF_ORIG_EXTRA_SUBMENU_PROD(self, driver, send, app)
    while True:
        send(colors.CLEAR + menu.rstrip('\n') + '\n' + self.footer() + '\n')
        choice = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
        if choice in {'X','EXIT','END','F3','PF3',''}:
            return
        if self._handle_jump(choice, driver, send):
            continue
        run_cmd = mapping.get(choice, choice)
        out = v26_features.dispatch_tso(self.state, self.userid, run_cmd) or 'INVALID OPTION'
        send(colors.CLEAR + out.rstrip('\n') + '\n')
        self._send_pause(driver)

def _ispf_prod_panel_racf(self, driver, send) -> None:
    from gibson.core import v26_features
    while True:
        out = v26_features.dispatch_tso(self.state, self.userid, 'RACFADMIN MENU') or 'RACF ADMIN unavailable'
        send(colors.CLEAR + out.rstrip('\n') + '\n' + self.footer() + '\n')
        cmd = read_panel_command(driver, 4, 13, context='ISPF').command.strip()
        uc = cmd.upper()
        if uc in {'X','EXIT','END','F3','PF3',''}:
            return
        if self._handle_jump(cmd, driver, send):
            continue
        # Numeric options open the same command shell with deterministic examples.
        examples={'1':'LISTUSER IBMUSER','2':'LISTGRP *','3':'LISTDSD','4':'RLIST FACILITY *','9':'PTKTDATA','A':'MFA','B':'RACDCERT','C':'SETROPTS LIST'}
        run = examples.get(uc, cmd)
        out = v26_features.dispatch_tso(self.state, self.userid, 'RACFADMIN ' + run) or 'INVALID RACF ADMIN OPTION'
        send(colors.CLEAR + out.rstrip('\n') + '\n')
        self._send_pause(driver)

IspfApp._extra_submenu = _ispf_prod_extra_submenu
IspfApp.panel_racf = _ispf_prod_panel_racf

# Fully interactive RSS operations panels v2: RSS M.3, SYSVIEW M.4, zSecure M.1, RACF R.
def _ispf_read_cmd(self, driver, row=4):
    try:
        return read_panel_command(driver, row, 13, context='ISPF').command.strip()
    except Exception:
        return (driver.read_line('COMMAND ===> ').text or '').strip()

def _ispf_prod_v2_extra_submenu(self, driver, send, app: str) -> None:
    from gibson.core import v26_features
    app_u = (app or '').upper()
    while True:
        if app_u == 'RSS':
            from gibson.apps.cti_rss import render_panel
            send(colors.CLEAR + render_panel() + '\n' + self.footer() + '\n')
            choice = _ispf_read_cmd(self, driver).upper()
            if choice in {'X','EXIT','END','F3','PF3',''}: return
            if self._handle_jump(choice, driver, send): continue
            if choice == '1': run_cmd = 'RSS LIST'
            elif choice == '2': run_cmd = 'RSS FETCH'
            elif choice == '3': run_cmd = 'RSS SHOW'
            elif choice == '4':
                name = _ispf_read_cmd(self, driver, 6) or 'TRAINING'
                url = _ispf_read_cmd(self, driver, 7) or 'https://example.com/feed.xml'
                run_cmd = f'RSS ADD {name} {url}'
            elif choice == '5':
                name = _ispf_read_cmd(self, driver, 6) or 'TRAINING'
                run_cmd = f'RSS DELETE {name}'
            elif choice == '6':
                dsn = _ispf_read_cmd(self, driver, 6) or 'RSS.CTI.RSS.REPORT'
                run_cmd = f'RSS EXPORT {dsn}'
            elif choice == '7': run_cmd = 'RSS CONFIG'
            elif choice == '8': run_cmd = 'RSS STATUS'
            else: run_cmd = choice if choice.upper().startswith('RSS') else 'RSS ' + choice
        elif app_u == 'SYSVIEW':
            menu = v26_features.dispatch_tso(self.state, self.userid, 'SYSVIEW') or 'SYSVIEW unavailable'
            send(colors.CLEAR + menu.rstrip('\n') + '\n' + self.footer() + '\n')
            choice = _ispf_read_cmd(self, driver).upper()
            if choice in {'X','EXIT','END','F3','PF3',''}: return
            if self._handle_jump(choice, driver, send): continue
            mapping={'1':'SYSVIEW SYSTEM','2':'SYSVIEW JOBS','3':'SYSVIEW CICS','4':'SYSVIEW DB2','5':'SYSVIEW TCPIP','6':'SYSVIEW USS','7':'SYSVIEW STORAGE','8':'SYSVIEW ALERTS','9':'SYSVIEW RSS','A':'SYSVIEW DATASETS','B':'SYSVIEW RSS','C':'SYSVIEW DATASETS','D':'SYSVIEW REFRESH'}
            run_cmd = mapping.get(choice, choice if choice.startswith('SYSVIEW') else 'SYSVIEW ' + choice)
        elif app_u == 'ZSEC':
            menu = v26_features.dispatch_tso(self.state, self.userid, 'ZSEC') or 'zSecure unavailable'
            send(colors.CLEAR + menu.rstrip('\n') + '\n' + self.footer() + '\n')
            choice = _ispf_read_cmd(self, driver).upper()
            if choice in {'X','EXIT','END','F3','PF3',''}: return
            if self._handle_jump(choice, driver, send): continue
            mapping={'1':'ZSEC RACF','2':'ZSEC PRIVILEGE','3':'ZSEC UID0','4':'ZSEC RACFDS','5':'ZSEC ACCESS','6':'ZSEC CICS','7':'ZSEC DB2','8':'ZSEC SERVAUTH','9':'ZSEC PASSTICKET','A':'ZSEC MFA','B':'ZSEC ICSF','C':'ZSEC RACDCERT','D':'ZSEC STARTED','E':'ZSEC SURROGAT','F':'ZSEC JES','G':'ZSEC EVENTS','H':'ZSEC COMPLIANCE','I':'ZSEC DRIFT','J':'ZSEC REPORTS'}
            run_cmd = mapping.get(choice, choice if choice.startswith('ZSEC') else 'ZSEC ' + choice)
        else:
            return _ISPF_ORIG_EXTRA_SUBMENU_PROD(self, driver, send, app)
        out = v26_features.dispatch_tso(self.state, self.userid, run_cmd) or 'INVALID OPTION'
        send(colors.CLEAR + out.rstrip('\n') + '\n')
        self._send_pause(driver)

def _ispf_prod_v2_panel_racf(self, driver, send) -> None:
    from gibson.core import v26_features
    while True:
        out = v26_features.dispatch_tso(self.state, self.userid, 'RACFADMIN MENU') or 'RACF ADMIN unavailable'
        send(colors.CLEAR + out.rstrip('\n') + '\n' + self.footer() + '\n')
        choice = _ispf_read_cmd(self, driver).strip()
        uc = choice.upper()
        if uc in {'X','EXIT','END','F3','PF3',''}: return
        if self._handle_jump(choice, driver, send): continue
        if uc in {'1','USER','USERS'}:
            send(colors.CLEAR + 'RACF USER ADMINISTRATION\nCommands: ADD LIST ALT DEL REVOKE RESUME CONNECT REMOVE\nUSERID ===>\nACTION ===>\n' + self.footer() + '\n')
            userid = _ispf_read_cmd(self, driver, 4).upper() or 'TRAINEE'
            action = (_ispf_read_cmd(self, driver, 5).upper() or 'LIST')
            if action.startswith('ADD'):
                run = f'RACFADMIN ADDUSER {userid} NAME(Training User) DFLTGRP(STUDENT) PASSWORD(PASS123)'
            elif action.startswith('ALT'):
                run = f'RACFADMIN ALTUSER {userid} OMVS(UID(10077))'
            elif action.startswith('DEL'):
                run = f'RACFADMIN DELUSER {userid}'
            elif action.startswith('REVOKE'):
                run = f'RACFADMIN ALTUSER {userid} REVOKE'
            elif action.startswith('RESUME'):
                run = f'RACFADMIN ALTUSER {userid} RESUME'
            else:
                run = f'RACFADMIN LISTUSER {userid}'
        elif uc in {'2','GROUP'}: run='RACFADMIN LISTGRP *'
        elif uc in {'3','DATASET'}: run='RACFADMIN LISTDSD'
        elif uc in {'4','RESOURCE'}: run='RACFADMIN RLIST FACILITY *'
        elif uc in {'9','PTKTDATA'}: run='RACFADMIN PTKTDATA'
        elif uc in {'A','MFA'}: run='RACFADMIN MFA'
        elif uc in {'B','RACDCERT'}: run='RACFADMIN RACDCERT'
        elif uc in {'C','SETROPTS'}: run='RACFADMIN SETROPTS LIST'
        else: run = 'RACFADMIN ' + choice
        out = v26_features.dispatch_tso(self.state, self.userid, run) or 'INVALID RACF ADMIN OPTION'
        send(colors.CLEAR + out.rstrip('\n') + '\n')
        self._send_pause(driver)

IspfApp._extra_submenu = _ispf_prod_v2_extra_submenu
IspfApp.panel_racf = _ispf_prod_v2_panel_racf

# NMAP M.10 panel integration.  This overrides the management panel to add a
# first-class NMAP submenu while preserving the existing zSecure/SMP/E/RSS/
# SYSVIEW/RACF behaviours.
_ISPF_PANEL_MGMT_BEFORE_NMAP = IspfApp.panel_management

def _ispf_panel_management_with_nmap(self, driver, send, initial: str = "MENU") -> None:
    from gibson.core import v26_features
    option = (initial or "MENU").strip().upper()
    while True:
        if option in {"MENU", ""}:
            lines = self.panel_heading("Management Option Menu - Extra Software")
            lines += [
                self.msgline(),
                f" {colors.WHITE}1{colors.TURQUOISE}  zSecure      Security and compliance analysis",
                f" {colors.WHITE}2{colors.TURQUOISE}  SMP/E        Software installation and maintenance",
                f" {colors.WHITE}3{colors.TURQUOISE}  RSS          CTI/RSS feed reader",
                f" {colors.WHITE}4{colors.TURQUOISE}  SYSVIEW      Performance and operations monitor",
                f" {colors.WHITE}5{colors.TURQUOISE}  RACF         View and update RACF settings",
                f" {colors.WHITE}10{colors.TURQUOISE} NMAP         Gibson NSE-style mainframe enumeration",
                f" {colors.WHITE}M.10{colors.TURQUOISE} NMAP        Same as option 10",
                f" {colors.WHITE}X{colors.TURQUOISE}  Exit         Return to ISPF primary menu",
                "",
                self.footer(),
            ]
            send("\n".join(lines) + "\n")
            choice = read_panel_command(driver, 4, 13, context='ISPF').command.strip().upper()
        else:
            choice = option
        option = "MENU"
        if self._handle_jump(choice, driver, send):
            continue
        if choice in {"X", "EXIT", "END", "F3", "PF3", ""}:
            return
        if choice in {"10", "M.10", "NMAP"}:
            while True:
                out = v26_features.dispatch_tso(self.state, self.userid, 'NMAP MENU') or 'NMAP unavailable'
                send(colors.CLEAR + out.rstrip('\n') + '\n' + self.footer() + '\n')
                sel = (_ispf_read_cmd(self, driver) if '_ispf_read_cmd' in globals() else read_panel_command(driver,4,13,context='ISPF').command).strip().upper()
                if sel in {'X','EXIT','END','F3','PF3',''}:
                    break
                run = 'NMAP ' + sel
                out = v26_features.dispatch_tso(self.state, self.userid, run) or 'INVALID NMAP OPTION'
                send(colors.CLEAR + out.rstrip('\n') + '\n')
                self._send_pause(driver)
            continue
        if choice in {"1", "Z", "ZSEC", "ZSECURE", "CKR"}:
            self._extra_submenu(driver, send, "ZSEC")
        elif choice in {"2", "SMP", "SMPE", "SMP/E"}:
            self._extra_submenu(driver, send, "SMPE")
        elif choice in {"3", "RSS"}:
            self._extra_submenu(driver, send, "RSS")
        elif choice in {"4", "SYSVIEW", "SYSV"}:
            self._extra_submenu(driver, send, "SYSVIEW")
        elif choice == "5":
            self.panel_racf(driver, send)
        else:
            out = v26_features.dispatch_tso(self.state, self.userid, choice)
            if out:
                send(colors.CLEAR + out.rstrip('\n') + '\n')
                self._send_pause(driver)
            else:
                self.message = "INVALID MANAGEMENT OPTION"

IspfApp.panel_management = _ispf_panel_management_with_nmap

# CICS_UI_OMVS_LOGGING: remove NMAP from ISPF M menu only; OMVS nmap remains available.
try:
    IspfApp.panel_management = _ISPF_PANEL_MGMT_BEFORE_NMAP
except Exception:
    pass


# Gibson RACF Services Option Menu v2: final override.  This intentionally
# makes the primary ISPF RACF target the IBM-style RACF Services hierarchy,
# not the custom Gibson FIBS administration shortcut panel.
def _gibson_racf_services_panel_v2(self, driver, send) -> None:
    from gibson.apps.racf_services.menu import racf_services_command, render_racf_services_menu
    current = 'RACFSERV'
    while True:
        try:
            out = racf_services_command(self.state, self.userid, current)
        except Exception as exc:
            out = render_racf_services_menu() + f'\n\nRACF PANEL ERROR RCF0007 - {type(exc).__name__}: {exc}'
        if not out:
            out = render_racf_services_menu() + '\n\nRACF PANEL ERROR RCF0008 - EMPTY PANEL RESPONSE' 
        send(colors.CLEAR + out.rstrip('\n') + '\n' + self.footer() + '\n')
        choice = _ispf_read_cmd(self, driver).strip()
        uc = choice.upper()
        if uc in {'X','EXIT','END','F3','PF3',''}:
            return
        if self._handle_jump(choice, driver, send):
            continue
        if current.upper().startswith('RACFUSER'):
            current = 'RACFUSER ' + choice
        elif current.upper().startswith('RACFSYS'):
            current = 'RACFSYS ' + choice
        elif uc in {'4','USER','USERS'}:
            current = 'RACFUSER'
        elif uc in {'5','SYSTEM','SETROPTS'}:
            current = 'RACFSYS'
        else:
            current = 'RACFSERV ' + choice

IspfApp.panel_racf = _gibson_racf_services_panel_v2
