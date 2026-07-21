# pyspf_tui.py
# ISPF-ish TUI with Authentic 3270 Colors and Integrated Editor Logic
# Merges functionality of the user's 'editor.py' into the 'pyspf' framework.

from __future__ import annotations
import os, json, subprocess, datetime
from enum import Enum
from typing import Callable, List, Tuple, Optional, Dict

# Storage root (override with PYSPF_DATA_ROOT)
DATA_ROOT = os.environ.get("PYSPF_DATA_ROOT", "~/mfsim/f")

# -----------------------------------------------------------------------------
# 3270 Color Emulation (ANSI)
# -----------------------------------------------------------------------------
class IBMColor:
    BLUE      = "\x1b[34m"       # Instructions / Headers / Low Priority
    GREEN     = "\x1b[32m"       # Normal Input fields / Data
    TURQUOISE = "\x1b[36m"       # Field Descriptors / Column Headers
    RED       = "\x1b[31m"       # Error messages / Warnings / Important Inputs
    WHITE     = "\x1b[37;1m"     # High Intensity / Selected Fields / Command Line
    YELLOW    = "\x1b[33m"       # Highlighted Data / Markers
    RESET     = "\x1b[0m"        # Reset to terminal default

    # Standard Helpers
    HLINE     = BLUE + ("─" * 79) + RESET

# ANSI helpers
ESC = "\x1b"
CLR = ESC + "[2J" + ESC + "[H"

ACTION_BAR = f"{IBMColor.BLUE}Menu  Utilities  Compilers  Options  Status  Help{IBMColor.RESET}"

class Screen(Enum):
    PRIMARY = 1
    UTILITIES = 2
    DATASET_UTILITY = 3
    MOVE_COPY = 4
    DSLIST = 5
    OUTLIST = 6
    SDSF = 7
    COMMAND = 8

class ISPFSession:
    def __init__(
        self,
        conn,
        username: str,
        get_jobs: Optional[Callable[[], list]] = None,
        term_size: Optional[Tuple[int, int]] = None,
        tso_runner: Optional[Callable[[str], str]] = None,
    ):
        self.conn = conn
        self.username = (username or "IBMUSER").upper()
        self.get_jobs = get_jobs or (lambda: [])
        self.tso_runner = tso_runner
        self.state = Screen.PRIMARY
        self.term_size = term_size

        self.user_home = os.path.abspath(os.path.join(DATA_ROOT, self.username))
        os.makedirs(self.user_home, exist_ok=True)

        self.gibson_version = "EDITOR-INTEGRATED-1.0"
        self.log_path = os.path.abspath(os.path.join(os.getcwd(), "simulator.log"))
        self._seed_default_dataset()

    # ---------------- I/O ----------------
    def send(self, s: str) -> None:
        try:
            self.conn.sendall(s.encode("utf-8", errors="ignore"))
        except Exception:
            raise SystemExit

    def clear(self) -> None:
        self.send(CLR)

    def _map_fn_key(self, seq: bytes) -> Optional[str]:
        mapping = {
            b"\x1bOP":"F1", b"\x1bOQ":"F2", b"\x1bOR":"F3", b"\x1bOS":"F4",
            b"\x1b[15~":"F5", b"\x1b[17~":"F6", b"\x1b[18~":"F7", b"\x1b[19~":"F8",
            b"\x1b[20~":"F9", b"\x1b[21~":"F10", b"\x1b[23~":"F11", b"\x1b[24~":"F12",
            b"\x1b[A": "UP", b"\x1b[B": "DOWN", b"\x1b[C": "RIGHT", b"\x1b[D": "LEFT",
            b"\x1bOA": "UP", b"\x1bOB": "DOWN", b"\x1bOC": "RIGHT", b"\x1bOD": "LEFT"
        }
        return mapping.get(seq)

    def get_line(self, prompt: str = "") -> str:
        self.send(prompt)
        buf = bytearray()
        while True:
            b = self.conn.recv(1)
            if not b:
                raise SystemExit
            ch = b[0]
            if ch in (10, 13):  # CR/LF
                break
            
            # TAB key (0x09)
            if ch == 9:
                return "TAB"

            if ch == 0x1B:     # ESC: try F-key sequence
                seq = bytearray(b)
                for _ in range(8):
                    nb = self.conn.recv(1)
                    if not nb: break
                    seq.extend(nb)
                    if nb in (b"~",) or (b"A"<=nb<=b"Z") or (b"a"<=nb<=b"z"):
                        break
                key = self._map_fn_key(bytes(seq))
                if key: return key
                continue
            # Handle Backspace (127 or 0x08)
            if ch in (127, 8):
                if len(buf) > 0:
                    buf.pop()
                    # Visual backspace hack: back, space, back
                    self.send("\b \b")
                continue
            
            buf.append(ch)
            # Echo character (green for input)
            self.send(f"{IBMColor.GREEN}{chr(ch)}{IBMColor.RESET}")

        return buf.decode("utf-8", errors="ignore").strip()

    # ------------- Dataset model -------------
    def _seed_default_dataset(self):
        for ds in (f"{self.username}.REXX", f"{self.username}.CNTL", f"{self.username}.JCL",
                   f"{self.username}.ISP.PROF", f"{self.username}.TEXT"):
            p = os.path.join(self.user_home, ds)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not os.path.exists(p):
                try: open(p, "a").close()
                except Exception: pass
                # Create default meta for .TEXT
                if ds.endswith(".TEXT"):
                    self._save_meta(ds, {"RECFM":"FB", "LRECL":80, "BLKSIZE":6160, "ORG":"PS"})

    def _list_ds(self, prefix: Optional[str] = None) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        for root, dirs, files in os.walk(self.user_home):
            rel = os.path.relpath(root, self.user_home)
            if rel == ".": rel = ""
            if rel:
                rows.append((rel.replace(os.sep, ".").upper(), "PO"))
            for f in files:
                r = (rel + "/" + f) if rel else f
                rows.append((r.replace("/", ".").upper(), "PS"))
        if prefix:
            p = prefix.upper()
            rows = [r for r in rows if r[0].startswith(p)]
        rows.sort(key=lambda x: (x[0], x[1]))
        return rows

    def _ensure_ps(self, dsname: str) -> str:
        path = os.path.join(self.user_home, dsname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            open(path, "a").close()
        return path

    def _meta_path(self, dsname: str) -> str:
        return os.path.join(self.user_home, f"{dsname}.meta")

    def _load_meta(self, dsname: str) -> Dict[str, object]:
        mpath = self._meta_path(dsname)
        if os.path.exists(mpath):
            try:
                with open(mpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"RECFM":"VB","LRECL":80,"BLKSIZE":6160,"UNIT":"3390","SPACE_UNIT":"TRK","PRIMARY":1,"SECONDARY":1,"DIRBLKS":0,"VOLUME":"WORK01"}

    def _save_meta(self, dsname: str, meta: Dict[str, object]) -> None:
        try:
            with open(self._meta_path(dsname), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass
    
    def _load_meta_for_path(self, fullpath: str) -> Dict[str, object]:
        # Helper that takes a full path and finds the meta file
        m = fullpath + ".meta"
        if os.path.exists(m):
            try:
                with open(m, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {"RECFM":"VB","LRECL":80,"BLKSIZE":6160,"UNIT":"3390","SPACE_UNIT":"TRK","PRIMARY":1,"SECONDARY":1,"DIRBLKS":0,"VOLUME":"WORK01"}


    def _dslist_dir(self, start_dir: str) -> List[Tuple[str, str, str, Optional[str]]]:
        rows: List[Tuple[str, str, str, Optional[str]]] = []
        try:
            rel_from_user = os.path.relpath(start_dir, self.user_home)
            parent_is_user_root = (rel_from_user == ".")
            for entry in sorted(os.listdir(start_dir)):
                if entry.startswith("."): continue
                ap = os.path.join(start_dir, entry)
                if os.path.isdir(ap):
                    disp = entry.replace(os.sep, ".").upper()
                    rows.append((disp, "PO", ap, None))
                else:
                    if entry.endswith(".meta"): continue
                    if parent_is_user_root:
                        rows.append((entry.upper(), "PS", ap, None))
                    else:
                        po_name = rel_from_user.replace(os.sep, ".").upper()
                        mem = entry.upper()
                        disp = f"{po_name}({mem})"
                        rows.append((disp, "MEM", ap, mem))
        except Exception:
            pass
        return rows

    # ------------- Panels -------------
    def banner(self) -> str:
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'ISPF Primary Option Menu'.center(79)}{IBMColor.RESET}\n\n")
        
        # Authentic 3270-style menu items
        # Green numbers, Turquoise text
        lines = [
            f" {IBMColor.WHITE}0{IBMColor.TURQUOISE}  Settings      Terminal and user parameters            {IBMColor.BLUE}Screen. . . :{IBMColor.WHITE} 1",
            f" {IBMColor.WHITE}1{IBMColor.TURQUOISE}  View          Display source data or listings         {IBMColor.BLUE}Language . .:{IBMColor.WHITE} ENGLISH",
            f" {IBMColor.WHITE}2{IBMColor.TURQUOISE}  Edit          Create or change source data            {IBMColor.BLUE}Appl ID  . .:{IBMColor.WHITE} ISR",
            f" {IBMColor.WHITE}3{IBMColor.TURQUOISE}  Utilities     Perform utility functions               {IBMColor.BLUE}TSO logon. .:{IBMColor.WHITE} {self.username}",
            f" {IBMColor.WHITE}5{IBMColor.TURQUOISE}  Batch         Submit job for language processing      {IBMColor.BLUE}System ID  .:{IBMColor.WHITE} MVSC",
            f" {IBMColor.WHITE}6{IBMColor.TURQUOISE}  Command       Enter TSO or Workstation commands       {IBMColor.BLUE}Release  . .:{IBMColor.WHITE} ISPF 8.1",
            f" {IBMColor.WHITE}M{IBMColor.TURQUOISE}  Additional    More IBM products / tools",
            f" {IBMColor.WHITE}S{IBMColor.TURQUOISE}  SDSF          System Display and Search Facility",
            "",
            f" {IBMColor.BLUE}Enter X to Terminate using log/list defaults{IBMColor.RESET}"
        ]
        for ln in lines:
            self.send(ln + "\n")
        
        return self.get_line(f"{IBMColor.BLUE}Option ===>{IBMColor.RED} ").upper().strip()

    def panel_settings(self):
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'Settings'.center(79)}{IBMColor.RESET}\n\n")
        body = [
            f" {IBMColor.TURQUOISE}USERID . . . . . . :{IBMColor.WHITE} {self.username}",
            f" {IBMColor.TURQUOISE}TERMINAL . . . . . :{IBMColor.WHITE} 3270",
            f" {IBMColor.TURQUOISE}PROMPT  . . . . . .:{IBMColor.WHITE} ON",
            f" {IBMColor.TURQUOISE}PAUSE . . . . . . .:{IBMColor.WHITE} OFF",
            "",
            f"{IBMColor.BLUE}F3=Exit  F1=Help{IBMColor.RESET}"
        ]
        for ln in body: self.send(ln + "\n")
        self.get_line(f"{IBMColor.BLUE}Option ===>{IBMColor.RED} ").upper().strip()
        self.state = Screen.PRIMARY

    def panel_view(self):
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'Browse Data Set'.center(79)}{IBMColor.RESET}\n\n")
        ds = self.get_line(f"{IBMColor.TURQUOISE}Data set name ===>{IBMColor.RED} ").strip().upper()
        if not ds: return
        self._browse_path(os.path.join(self.user_home, ds))

    def panel_utilities(self):
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'Utility Selection Menu'.center(79)}{IBMColor.RESET}\n\n")
        body = [
            f"  {IBMColor.WHITE}2{IBMColor.TURQUOISE}  Data Set     - Data set utility (3.2)",
            f"  {IBMColor.WHITE}3{IBMColor.TURQUOISE}  Move/Copy    - Move, copy members or data sets (3.3)",
            f"  {IBMColor.WHITE}4{IBMColor.TURQUOISE}  Dslist       - Data set list utility (3.4)",
            f"  {IBMColor.WHITE}8{IBMColor.TURQUOISE}  Outlist      - Held job output list (3.8)",
            "",
            f"{IBMColor.BLUE}F3=Exit{IBMColor.RESET}"
        ]
        for ln in body: self.send(ln + "\n")
        cmd = self.get_line(f"{IBMColor.BLUE}Option ===>{IBMColor.RED} ").upper().strip()
        if cmd == "F3": self.state = Screen.PRIMARY
        elif cmd == "2": self.state = Screen.DATASET_UTILITY
        elif cmd == "3": self.state = Screen.MOVE_COPY
        elif cmd == "4": self.state = Screen.DSLIST
        elif cmd == "8": self.state = Screen.OUTLIST

    def _allocate_panel(self):
        self.clear()
        self.send(f"{IBMColor.BLUE}----------------------------- {IBMColor.WHITE}ALLOCATE NEW DATA SET{IBMColor.BLUE} ---------------------------\n\n{IBMColor.RESET}")
        
        name = self.get_line(f"{IBMColor.TURQUOISE} NAME OF NEW DATA SET ==>{IBMColor.RED} ").strip().upper()
        if not name: return None
        
        self.send(f"\n{IBMColor.TURQUOISE}              RECORD FORMAT ==>{IBMColor.GREEN} FB\n")
        self.send(f"{IBMColor.TURQUOISE}      LOGICAL RECORD LENGTH ==>{IBMColor.GREEN} 80\n")
        self.send(f"{IBMColor.TURQUOISE}        PHYSICAL BLOCK SIZE ==>{IBMColor.GREEN} 6160\n\n")
        self.send(f"{IBMColor.TURQUOISE}                     VOLUME ==>{IBMColor.GREEN} WORK01\n")
        self.send(f"{IBMColor.TURQUOISE}                       UNIT ==>{IBMColor.GREEN} 3390\n\n")
        
        # Hardcoding default for simulator simplicity, but preserving flow
        recfm, lrecl, blksize = "FB", 80, 6160
        dirblks = 0
        
        try:
             dirblks_str = self.get_line(f"{IBMColor.TURQUOISE} NUMBER OF DIRECTORY BLOCKS ==>{IBMColor.RED} ").strip()
             dirblks = int(dirblks_str) if dirblks_str else 0
        except: dirblks = 0

        meta = {"RECFM":recfm,"LRECL":lrecl,"BLKSIZE":blksize,"UNIT":"3390","SPACE_UNIT":"TRK",
                "PRIMARY":1,"SECONDARY":1,"DIRBLKS":dirblks,"VOLUME":"WORK01"}
        return name, meta

    def panel_32(self):
        while True:
            self.clear()
            self.send(ACTION_BAR + "\n")
            self.send(IBMColor.HLINE + "\n")
            self.send(f"{IBMColor.WHITE}{'Data Set Utility'.center(79)}{IBMColor.RESET}\n\n")
            body = [
                f"  {IBMColor.WHITE}A{IBMColor.TURQUOISE} - Allocate new data set (creates empty PS or PO)",
                f"  {IBMColor.WHITE}D{IBMColor.TURQUOISE} - Delete data set",
                f"  {IBMColor.WHITE}R{IBMColor.TURQUOISE} - Rename data set",
                f"  {IBMColor.WHITE}I{IBMColor.TURQUOISE} - Information (PS/PO)",
                f"  {IBMColor.WHITE}L{IBMColor.TURQUOISE} - List catalog (by prefix)",
                "",
                f"{IBMColor.BLUE}F3=Exit{IBMColor.RESET}"
            ]
            for ln in body: self.send(ln + "\n")
            cmd = self.get_line(f"{IBMColor.BLUE}Option ===>{IBMColor.RED} ").upper().strip()
            
            if cmd == "F3": self.state = Screen.UTILITIES; return
            
            if cmd == "A":
                alloc = self._allocate_panel()
                if not alloc: continue
                name, meta = alloc
                if meta.get("DIRBLKS", 0) > 0:
                    path = os.path.join(self.user_home, name)
                    os.makedirs(path, exist_ok=True)
                    meta["ORG"] = "PO"
                    self._save_meta(name, meta)
                else:
                    path = self._ensure_ps(name)
                    meta["ORG"] = "PS"
                    self._save_meta(name, meta)
                self.send(f"\n{IBMColor.GREEN}Allocated.{IBMColor.RESET}\n")
                self.get_line("Enter...")
                
            elif cmd == "I":
                name = self.get_line(f"{IBMColor.TURQUOISE} DATA SET NAME ==>{IBMColor.RED} ").strip().upper()
                p = os.path.join(self.user_home, name)
                org = "PO" if os.path.isdir(p) else ("PS" if os.path.exists(p) else "N/A")
                meta = self._load_meta(name)
                self.send(f"\n {IBMColor.WHITE}{name}{IBMColor.RESET}\n")
                self.send(f" {IBMColor.TURQUOISE}Organization:{IBMColor.GREEN} {org}\n")
                self.send(f" {IBMColor.TURQUOISE}RECFM:{IBMColor.GREEN} {meta.get('RECFM','?')}\n")
                self.send(f" {IBMColor.TURQUOISE}LRECL:{IBMColor.GREEN} {meta.get('LRECL',0)}\n")
                self.get_line("\nEnter...")

    def panel_33(self):
        # Stub for Move/Copy
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'Move/Copy Utility'.center(79)}{IBMColor.RESET}\n\n")
        self.send(f"{IBMColor.TURQUOISE}Functionality not fully implemented in this demo.{IBMColor.RESET}\n")
        self.get_line("F3 to Exit...")
        self.state = Screen.UTILITIES

    # ------------- DSLIST (=3.4) with S and D commands -------------
    def panel_34(self):
        pref = self.get_line(f"\n{IBMColor.TURQUOISE}Data set name prefix (blank = user root) ==>{IBMColor.RED} ").strip().upper()
        curdir = self.user_home
        if pref and pref != self.username:
            candidate = os.path.join(self.user_home, pref.replace(".", os.sep))
            if os.path.isdir(candidate):
                curdir = candidate

        page = 18
        idx_offset = 0

        while True:
            rows = self._dslist_dir(curdir)
            total = len(rows)
            idx_offset = max(0, min(idx_offset, max(0, total - page)))

            self.clear()
            self.send(ACTION_BAR + "\n")
            self.send(IBMColor.HLINE + "\n")
            rel = os.path.relpath(curdir, self.user_home)
            shown = f"{self.username}" if rel == "." else f"{self.username}.{rel.replace(os.sep, '.').upper()}"
            title = f"Data Set List — {shown} (items: {total})"
            self.send(f"{IBMColor.WHITE}{title.center(79)}{IBMColor.RESET}\n\n")
            self.send(f"{IBMColor.BLUE}Command ===>{IBMColor.RED} ".ljust(55) + f"{IBMColor.BLUE}Scroll ===>{IBMColor.WHITE} CSR{IBMColor.RESET}\n\n")
            
            # Header
            self.send(f"  {IBMColor.TURQUOISE}#  NAME".ljust(55) + "ORG     VOLUME{IBMColor.RESET}\n")
            self.send(f" {IBMColor.BLUE}--- ---------------------------------------------   ------- ------{IBMColor.RESET}\n")

            page_rows = rows[idx_offset: idx_offset + page]
            for i, (disp, org, _path, _mem) in enumerate(page_rows, 1):
                name = disp[:43]
                self.send(f" {IBMColor.WHITE}{i:>3}{IBMColor.GREEN} {name:<43}   {IBMColor.WHITE}{org:<7} {IBMColor.GREEN}WORK01{IBMColor.RESET}\n")

            self.send("\n")
            self.send(f"{IBMColor.BLUE}Actions: B=Browse, E=Edit, D=Delete, R=Rename, S=Info, F3=Exit{IBMColor.RESET}\n")
            act = self.get_line(f"{IBMColor.BLUE}Action ===>{IBMColor.RED} ").strip().upper()

            if act in ("F3",): self.state = Screen.UTILITIES; return
            if act in ("F7","PF7"): idx_offset = max(0, idx_offset - page); continue
            if act in ("F8","PF8"): idx_offset = min(max(0,total-page), idx_offset + page); continue
            
            if not act: continue

            # If user enters "D" or "S", we need them to select the item number
            pick = self.get_line(f"{IBMColor.TURQUOISE}Item # ===>{IBMColor.RED} ").strip()
            if not pick.isdigit(): continue
            pos = int(pick)
            if pos < 1 or pos > len(page_rows): continue
            disp, org, apath, member = page_rows[pos-1]

            # --- S: DATA SET INFORMATION (DSINFO) ---
            if act == "S":
                self.clear()
                self.send(f"{IBMColor.BLUE}DATA SET INFORMATION\n{IBMColor.RESET}")
                self.send(IBMColor.HLINE + "\n\n")
                
                # Fetch authentic simulated metadata
                meta = self._load_meta_for_path(apath)
                size = os.path.getsize(apath) if os.path.exists(apath) else 0
                now = datetime.datetime.now().strftime("%Y/%m/%d")

                self.send(f"{IBMColor.TURQUOISE}  Data Set Name . . . :{IBMColor.WHITE} {disp}\n")
                self.send(f"{IBMColor.TURQUOISE}  General Data:{IBMColor.RESET}\n")
                self.send(f"{IBMColor.TURQUOISE}   Volume Serial . . . :{IBMColor.WHITE} WORK01\n")
                self.send(f"{IBMColor.TURQUOISE}   Device Type . . . . :{IBMColor.WHITE} 3390\n")
                self.send(f"{IBMColor.TURQUOISE}   Organization  . . . :{IBMColor.WHITE} {org}\n")
                self.send(f"{IBMColor.TURQUOISE}   Record Format . . . :{IBMColor.WHITE} {meta.get('RECFM', '?')}\n")
                self.send(f"{IBMColor.TURQUOISE}   Record Length . . . :{IBMColor.WHITE} {meta.get('LRECL', '?')}\n")
                self.send(f"{IBMColor.TURQUOISE}   Block Size  . . . . :{IBMColor.WHITE} {meta.get('BLKSIZE', '?')}\n")
                self.send(f"{IBMColor.TURQUOISE}   Creation Date . . . :{IBMColor.WHITE} {now}\n")
                self.send(f"{IBMColor.TURQUOISE}   Current Size  . . . :{IBMColor.WHITE} {size} bytes\n")
                
                self.get_line(f"\n{IBMColor.BLUE}Press Enter to return...{IBMColor.RESET}")
                continue

            # --- D: DELETE CONFIRMATION (DSDEL) ---
            if act == "D":
                self.clear()
                self.send(f"{IBMColor.BLUE}DELETE DATA SET — CONFIRMATION\n{IBMColor.RESET}")
                self.send(IBMColor.HLINE + "\n\n")
                self.send(f"{IBMColor.TURQUOISE}Data Set Name . . . :{IBMColor.RED} {disp}\n\n")
                self.send(f"{IBMColor.WHITE}INSTRUCTIONS:{IBMColor.RESET}\n")
                self.send(f"   Press {IBMColor.YELLOW}ENTER{IBMColor.RESET} to confirm delete.\n")
                self.send(f"   Type {IBMColor.YELLOW}CANCEL{IBMColor.RESET} to exit without deleting.\n\n")
                
                confirm = self.get_line(f"{IBMColor.BLUE}Command ===>{IBMColor.RED} ").strip().upper()
                
                if confirm != "CANCEL":
                    try:
                        if org in ("PS", "MEM"):
                            os.remove(apath)
                            m = apath + ".meta"
                            if os.path.exists(m): os.remove(m)
                        else:
                            os.rmdir(apath)
                        self.send(f"\n{IBMColor.WHITE}Dataset deleted.{IBMColor.RESET}\n")
                    except Exception as e:
                        self.send(f"\n{IBMColor.RED}Delete failed: {e}{IBMColor.RESET}\n")
                    self.get_line("Enter...")
                continue

            if act == "E":
                if org in ("PS","MEM"):
                    self._edit_path(apath, disp)
                else:
                    self.send("\nCannot edit directory.\n"); self.get_line("Enter...")
                continue
            
            if act == "B":
                self._browse_path(apath)
                continue

    # ------------- OUTLIST (=3.8) -------------
    def panel_38(self):
        while True:
            self.clear()
            self.send(ACTION_BAR + "\n")
            self.send(IBMColor.HLINE + "\n")
            self.send(f"{IBMColor.WHITE}{'OUTLIST (3.8)'.center(79)}{IBMColor.RESET}\n\n")
            
            jobs = self.get_jobs() or []
            self.send(f"{IBMColor.TURQUOISE} #  JOBNAME  JOBID       QUEUE    STATUS        LINES   SUBMITTED{IBMColor.RESET}\n")
            self.send(f"{IBMColor.BLUE}--- -------- ----------- -------  ------------  -----   -------------------{IBMColor.RESET}\n")
            
            for i, j in enumerate(jobs[:20], 1):
                jobname = str(j.get("jobname","")).upper()[:8].ljust(8)
                jobid   = str(j.get("job_number",""))[:11].ljust(11)
                status  = str(j.get("status","OUTPUT"))[:12].ljust(12)
                lines   = str(j.get("records", j.get("lines","")))[:5].rjust(5)
                self.send(f"{IBMColor.WHITE}{i:>3} {IBMColor.GREEN}{jobname} {jobid} PRTPUN   {status}  {lines}   --{IBMColor.RESET}\n")

            self.send(f"\n{IBMColor.BLUE}F3=Exit   R=Refresh   S=Spool browse{IBMColor.RESET}\n")
            cmd = self.get_line(f"{IBMColor.BLUE}Option ===>{IBMColor.RED} ").strip().upper()
            if cmd == "F3": self.state = Screen.UTILITIES; return

    # ------------- SDSF -------------
    def panel_sdsf(self):
        # Very simple SDSF stub
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'SDSF Primary Option Menu'.center(79)}{IBMColor.RESET}\n\n")
        self.send(f"{IBMColor.TURQUOISE} DA{IBMColor.GREEN} - Display Active Jobs\n")
        self.send(f"{IBMColor.TURQUOISE} ST{IBMColor.GREEN} - Status\n")
        self.send(f"{IBMColor.TURQUOISE} LOG{IBMColor.GREEN} - System Log\n")
        self.get_line("\nF3 to Exit...")
        self.state = Screen.PRIMARY

    # ------------- Command shell -------------
    def panel_cmd(self):
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        self.send(f"{IBMColor.WHITE}{'ISPF Command Shell'.center(79)}{IBMColor.RESET}\n\n")
        while True:
            cmd = self.get_line(f"{IBMColor.BLUE}===>{IBMColor.RED} ")
            if cmd.upper() in ("F3","EXIT"):
                self.state = Screen.PRIMARY; return
            self.send(f"{IBMColor.GREEN}Command '{cmd}' executed (simulated).{IBMColor.RESET}\n")

    # ------------- Browse -------------
    def _browse_path(self, fullpath: str):
        self.clear()
        self.send(ACTION_BAR + "\n")
        self.send(IBMColor.HLINE + "\n")
        dsname = os.path.basename(fullpath)
        self.send(f"{IBMColor.WHITE}VIEW ---- {dsname}".ljust(88) + f"{IBMColor.RESET}\n\n")
        try:
            with open(fullpath, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f.readlines()[:500], 1):
                    line = line.rstrip()
                    self.send(f"{IBMColor.TURQUOISE}{i:06d}{IBMColor.RESET} {IBMColor.GREEN}{line}{IBMColor.RESET}\n")
        except Exception as e:
            self.send(f"\n{IBMColor.RED}Browse failed: {e}{IBMColor.RESET}\n")
        self.get_line("\nF3 to exit...")

    # ------------- THE EDITOR (Integrated from editor.py) -------------
    def _apply_recfm_fb(self, lines: List[str], lrecl: int) -> List[str]:
        if lrecl <= 0: return lines
        fixed: List[str] = []
        for ln in lines:
            raw = ln.rstrip("\n")
            fixed.append(raw[:lrecl].ljust(lrecl))
        return fixed

    def _edit_path(self, fullpath: str, logical_name: str):
        """
        The Integrated Editor.
        Matches the look of the user's 'editor.py' and real ISPF.
        """
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        meta = self._load_meta_for_path(fullpath)
        recfm = meta.get("RECFM", "VB")
        lrecl = int(meta.get("LRECL", 0) or 0)

        # Load file
        if os.path.exists(fullpath):
            try:
                with open(fullpath, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read().splitlines()
                lines = [ln[:lrecl].rstrip() for ln in raw] if (recfm == "FB" and lrecl > 0) else raw
            except Exception:
                lines = []
        else:
            lines = []

        modified = False
        cursor = 0 if lines else 0
        clipboard: List[str] = []
        
        # New State: Toggle between Command Line Focus and Text Body Focus
        edit_mode = False # False = Command Mode (prompt), True = Edit Mode (overwrites line)

        # Internal Helpers
        def find_next(term, start):
            for i in range(start + 1, len(lines)):
                if term.lower() in lines[i].lower(): return i
            return -1

        while True:
            self.clear()
            
            # 1. HEADER
            header_text = f"EDITOR - 1.00   {logical_name}"
            col_info = f"COLUMNS 001 {str(lrecl if lrecl else 80).zfill(3)}"
            self.send(f"{IBMColor.BLUE}{header_text.ljust(45)}{IBMColor.WHITE}{col_info}{IBMColor.RESET}\n")
            
            # 2. COMMAND LINE
            self.send(f"{IBMColor.BLUE}Command ===>{IBMColor.RED} ".ljust(55) + f"{IBMColor.BLUE}Scroll ===>{IBMColor.WHITE} CSR{IBMColor.RESET}\n")
            
            # 3. COMMAND REFERENCE LINE (Added per request)
            self.send(f"{IBMColor.TURQUOISE}Commands: SAVE, END, FIND, I[n], D[n], E, C, P, HELP{IBMColor.RESET}\n")
            
            # 4. TOP OF DATA
            if cursor == 0:
                self.send(f"{IBMColor.BLUE}****** ***************************** {IBMColor.YELLOW}TOP OF DATA{IBMColor.BLUE} ****************************** {IBMColor.RESET}\n")

            # 5. DATA AREA
            # Show 17 lines (simulating the 24-line screen minus headers)
            start = max(0, cursor)
            end = min(len(lines), start + 17)
            
            for i in range(start, end):
                line_content = lines[i]
                # Visuals: Turquoise Line Num, Green Text
                # Highlight current line if in Edit Mode
                if edit_mode and i == cursor:
                    self.send(f"{IBMColor.TURQUOISE}{i+1:06d}{IBMColor.RESET} {IBMColor.WHITE}{line_content}{IBMColor.RESET}\n")
                else:
                    self.send(f"{IBMColor.TURQUOISE}{i+1:06d}{IBMColor.RESET} {IBMColor.GREEN}{line_content}{IBMColor.RESET}\n")

            # 6. BOTTOM OF DATA
            if end >= len(lines):
                 self.send(f"{IBMColor.BLUE}****** **************************** {IBMColor.YELLOW}BOTTOM OF DATA{IBMColor.BLUE} *************************** {IBMColor.RESET}\n")
                 # Pad empty rows to keep prompt at bottom
                 remaining = 17 - (len(lines) - start)
                 for _ in range(remaining): self.send("\n")
            
            # 7. COMMAND INPUT
            if edit_mode:
                # Prompt specific to the line being edited
                prompt_str = f"{IBMColor.TURQUOISE}Edit Line {cursor+1} ===>{IBMColor.WHITE} "
            else:
                prompt_str = f"{IBMColor.BLUE}Command/Line# ===>{IBMColor.RED} "
                
            cmd = self.get_line(prompt_str).strip()
            ucmd = cmd.upper()
            
            # -- NAVIGATION (Arrows/Tab) --
            if ucmd == "TAB":
                edit_mode = not edit_mode
                continue
            
            if ucmd == "UP":
                cursor = max(0, cursor - 1)
                continue
            
            if ucmd == "DOWN":
                cursor = min(len(lines)-1 if lines else 0, cursor + 1)
                continue

            # -- GLOBAL CMDS --
            if ucmd == "HELP":
                self.clear()
                self.send(f"{IBMColor.WHITE}EDITOR HELP{IBMColor.RESET}\n")
                self.send(IBMColor.HLINE + "\n\n")
                self.send(f"{IBMColor.TURQUOISE}Navigation:{IBMColor.RESET}\n")
                self.send(f"  {IBMColor.GREEN}TAB{IBMColor.RESET}        Toggle between Command Mode and Line Edit Mode.\n")
                self.send(f"  {IBMColor.GREEN}UP/DOWN{IBMColor.RESET}    Move the line cursor.\n\n")
                self.send(f"{IBMColor.TURQUOISE}Commands:{IBMColor.RESET}\n")
                self.send(f"  {IBMColor.GREEN}SAVE{IBMColor.RESET}       Save changes to disk.\n")
                self.send(f"  {IBMColor.GREEN}END / F3{IBMColor.RESET}   Exit editor.\n")
                self.send(f"  {IBMColor.GREEN}I[n]{IBMColor.RESET}       Insert [n] blank lines at cursor.\n")
                self.send(f"  {IBMColor.GREEN}D[n]{IBMColor.RESET}       Delete [n] lines at cursor.\n")
                self.send(f"  {IBMColor.GREEN}FIND <txt>{IBMColor.RESET} Search for text forward.\n")
                self.get_line(f"\n{IBMColor.BLUE}Press Enter to return...{IBMColor.RESET}")
                continue

            if ucmd in ("F3", "END"):
                if modified:
                     self.send(f"\n{IBMColor.RED}DATA CHANGED. SAVE or CANCEL?{IBMColor.RESET}\n")
                     q = self.get_line("===> ").upper()
                     if q == "SAVE": ucmd = "SAVE"
                     elif q == "CANCEL": break
                     else: continue
                else:
                    break
            
            if ucmd == "SAVE":
                try:
                    out_lines = self._apply_recfm_fb(lines, lrecl) if (recfm=="FB" and lrecl>0) else lines
                    with open(fullpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(out_lines))
                    modified = False
                    self.send(f"\n{IBMColor.WHITE}File saved.{IBMColor.RESET}\n"); self.get_line("Enter...")
                except Exception as e:
                    self.send(f"\n{IBMColor.RED}Error: {e}{IBMColor.RESET}\n"); self.get_line("Enter...")
                continue
            
            if ucmd in ("F7"):
                cursor = max(0, cursor - 17)
                continue
            if ucmd in ("F8"):
                cursor = min(max(0, len(lines)-17), cursor + 17)
                continue
            if ucmd == "TOP": cursor = 0; continue
            if ucmd == "BOTTOM": cursor = max(0, len(lines) - 17); continue

            # -- EDITING LOGIC --
            
            if edit_mode:
                # In Edit Mode, input overwrites the current line
                if cmd:
                    if cursor < len(lines):
                        lines[cursor] = cmd
                    else:
                        lines.append(cmd)
                    modified = True
                continue
            
            # -- COMMAND MODE LOGIC --

            if ucmd.startswith("FIND ") or ucmd.startswith("F "):
                term = ucmd.split(" ", 1)[1]
                idx = find_next(term, cursor)
                if idx != -1:
                    cursor = idx
                else:
                    self.send(f"\n{IBMColor.RED}Not found.{IBMColor.RESET}\n"); self.get_line("Enter...")
                continue

            if ucmd.startswith("I"): # Insert
                # Insert at CURRENT cursor line
                try: n = int(ucmd[1:]) if len(ucmd)>1 else 1
                except: n = 1
                for _ in range(n): lines.insert(cursor, "")
                modified = True
                continue
            
            if ucmd.startswith("D"): # Delete
                # Delete CURRENT cursor line
                try: n = int(ucmd[1:]) if len(ucmd)>1 else 1
                except: n = 1
                for _ in range(n):
                    if 0 <= cursor < len(lines): del lines[cursor]
                modified = True
                continue

            # Direct Editing fallback (if they type a number)
            if " " in cmd and cmd.split(" ")[0].isdigit():
                parts = cmd.split(" ", 1)
                ln = int(parts[0]) - 1
                new_text = parts[1]
                if 0 <= ln < len(lines):
                    lines[ln] = new_text
                    modified = True
                elif ln == len(lines):
                    lines.append(new_text)
                    modified = True
                continue
            pass


    # ---------------- run loop ----------------
    def run(self):
        try:
            while True:
                if self.state == Screen.PRIMARY:
                    choice = self.banner()
                    if choice == "X": break
                    elif choice == "0": self.panel_settings()
                    elif choice == "1": self.panel_view()
                    elif choice == "2": self._edit_path(os.path.join(self.user_home, f"{self.username}.TEXT"), f"{self.username}.TEXT")
                    elif choice == "3": self.state = Screen.UTILITIES
                    elif choice == "6": self.panel_cmd()
                    elif choice == "S": self.panel_sdsf()
                    else:
                        if choice.startswith("="):
                            tail = choice[1:]
                            self.state = {"3.2":Screen.DATASET_UTILITY,"3.3":Screen.MOVE_COPY,
                                          "3.4":Screen.DSLIST,"3.8":Screen.OUTLIST}.get(tail, self.state)
                        else:
                            pass
                elif self.state == Screen.UTILITIES: self.panel_utilities()
                elif self.state == Screen.DATASET_UTILITY: self.panel_32()
                elif self.state == Screen.MOVE_COPY: self.panel_33()
                elif self.state == Screen.DSLIST: self.panel_34()
                elif self.state == Screen.OUTLIST: self.panel_38()
                else: self.state = Screen.PRIMARY
        except SystemExit:
            return

def run_ispf(conn, username, get_jobs=None, term_size: Optional[Tuple[int,int]] = None, tso_runner: Optional[Callable[[str], str]] = None):
    sess = ISPFSession(conn, username, get_jobs=get_jobs, term_size=term_size, tso_runner=tso_runner)
    sess.run()
