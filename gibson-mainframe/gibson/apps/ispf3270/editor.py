"""M5 - ISPF Editor in authentic EBCDIC 3270.

Driven by the ISPF session (option 2 Edit / line command ``E``).  Implements the
edit session in passes:

  Pass 1  display, scroll, in-place data edit, SAVE / CANCEL / END, CAPS
  Pass 2  prefix line commands  I D R (with counts), DD block delete,
          C/CC + M/MM copy/move with A/B destination
  Pass 3  FIND / CHANGE / EXCLUDE (NEXT / FIRST / ALL)
  Pass 4  SUBMIT (to JES via the existing submit path)

Storage is reused (``state.datasets.read`` / ``write``).  The crux -- the prefix
area -- exploits the 3270 rule that only *modified* fields are returned: any
prefix field that comes back carries a user-typed command; the count is parsed
as ``[1-9]\\d?`` so residual line-number digits are ignored.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from gibson.render import colors
from gibson.render.screen3270 import ScreenBuffer
from gibson.render.panels import PanelInput, ScrollList

_TURQ = getattr(colors, "TURQUOISE", colors.GREEN)
_DATA_ROWS = 18              # visible data lines (rows 5..22)
_DATA_COL = 9                # data field starts here (after 6-char prefix + attr)
_DATA_WIDTH = 71             # cols 9..79
_FIRST_ROW = 5

_BLOCKS = ("DD", "CC", "MM", "XX", "RR")
_SINGLE_RE = re.compile(r"^([A-Z])([1-9]\d?)?")


class Ispf3270Editor:
    def __init__(self, state, userid: str, dsname: str, text: str, peer_addr: str = "", readonly: bool = False):
        self.state = state
        self.userid = (userid or "IBMUSER").upper()
        self.dsname = dsname
        self.peer_addr = peer_addr
        self.readonly = readonly
        self.lines: List[str] = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()  # trailing newline -> no phantom blank line
        # Per-line numbering state: loaded lines are numbered; lines created by
        # i/r/copy are "new" and show the ISPF '''''' prefix until renumbered
        # (which happens on SAVE, or via the RENUM/NUMBER command).
        self.numbered: List[bool] = [True] * len(self.lines)
        self.top = 0
        self.caps = False
        self.changed = False
        self.excluded: set = set()
        self._message = ""
        self._last_find = ""
        self._last_change: Optional[Tuple[str, str, bool]] = None  # for F6=RCHANGE
        self._cursor_target = None
        self.hoff = 0  # horizontal scroll offset (F10=Left / F11=Right)
        # A CC/MM block can be marked in one Enter and the A/B destination given
        # in a later Enter - real ISPF remembers the pending block between
        # submissions.  (kind 'C'|'M', sorted list of marked line indices).
        self._pending_block: Optional[Tuple[str, List[int]]] = None

    # ----------------------------------------------------------------- API
    def initial_screen(self) -> ScreenBuffer:
        return self._render()

    def _num_at(self, idx: int) -> bool:
        return self.numbered[idx] if 0 <= idx < len(self.numbered) else True

    def _renumber(self, on: bool = True) -> None:
        """RENUM/NUMBER -> all lines numbered; UNNUM -> all '''''' (new)."""
        self.numbered = [on] * len(self.lines)

    def handle(self, pi: PanelInput) -> Optional[ScreenBuffer]:
        self._message = ""
        # 1) apply in-place data edits (only modified data fields return)
        self._apply_data_edits(pi)
        # top-of-data prefix: insert the first line(s) (works on an empty member)
        top_cmd = self._clean_prefix(pi.fields.get("LPTOP", "") or "", "******")
        if top_cmd:
            verb, cnt = self._parse_prefix(top_cmd)
            if verb == "I":
                n = cnt or 1
                for _ in range(n):
                    self.lines.insert(0, "")
                    self.numbered.insert(0, False)  # new lines show ''''''
                self.changed = True
                self.top = 0
                self._cursor_target = "LD00000"
                return self._render()
            if verb:
                self._message = "Only I (insert) is valid on Top of Data"
                return self._render()
        # 2) apply prefix line commands (only modified prefix fields return)
        handled_prefix, pmsg = self._apply_prefix(pi)
        if pmsg:
            self._message = pmsg

        key = pi.key
        cmd = pi.stripped("COMMAND")
        up = cmd.upper()

        # scroll keys
        if key in ("PF7", "PF8", "PF10", "PF11"):
            self._scroll(key)
            return self._render()
        if key in ("PF3", "PF15"):
            # END -> save (unless readonly) then exit
            if not self.readonly:
                self._save()
            return None
        if key in ("PA2", "PA1"):  # Reshow / Attention -> redisplay
            return self._render()
        if key in ("PF12", "PF24"):  # CANCEL - exit without saving
            return None
        if key == "PF4":  # EXPAND (field expansion not modelled here)
            self._message = "EXPAND is not available for this field"
            return self._render()
        if key in ("PF2", "PF9"):  # SPLIT / SWAP - split screen (Workstream E)
            self._message = "Split screen is not available yet"
            return self._render()

        # primary commands
        if up in ("CANCEL", "CAN"):
            return None
        if up in ("SAVE",):
            self._save(); return self._render()
        if up in ("END",):
            if not self.readonly:
                self._save()
            return None
        if up in ("CAPS ON", "CAPS"):
            self.caps = True; self._message = "CAPS ON"; return self._render()
        if up == "CAPS OFF":
            self.caps = False; self._message = "CAPS OFF"; return self._render()
        if up in ("NUMBER", "NUMBER ON", "RENUM", "NUM"):
            self._renumber(True); self._message = "LINES RENUMBERED"; return self._render()
        if up in ("UNNUM", "NUMBER OFF", "UNNUMBER"):
            self._renumber(False); self._message = "LINES UNNUMBERED"; return self._render()
        if up in ("TOP", "M") :
            self.top = 0; return self._render()
        if up in ("BOTTOM", "BOT", "MAX"):
            self.top = max(0, len(self.lines) - _DATA_ROWS); return self._render()
        if up.startswith("L ") or up.startswith("LOCATE "):
            num = up.split(None, 1)[1]
            if num.isdigit():
                self.top = max(0, min(int(num) - 1, max(0, len(self.lines) - 1)))
            return self._render()
        if up.startswith(("F ", "FIND ")) or up == "RFIND" or key == "PF5":
            return self._do_find(cmd)
        if up.startswith(("C ", "CHANGE ", "CHG ")):
            return self._do_change(cmd)
        if up == "RCHANGE" or key == "PF6":
            return self._repeat_change()
        if up.startswith(("X ", "EXCLUDE ")) or up in ("XALL", "EXCLUDEALL"):
            parts = cmd.split(None, 2)
            term = (parts[1].strip().strip("'\"") if len(parts) >= 2 else "")
            allflag = up in ("XALL", "EXCLUDEALL") or (len(parts) >= 3 and parts[2].upper() == "ALL")
            if not term:
                self._message = "ENTER AN EXCLUDE STRING"
                return self._render()
            low = term.lower(); n = 0
            for i in range(len(self.lines)):
                if low in self.lines[i].lower():
                    self.excluded.add(i); n += 1
                    if not allflag:
                        break
            self._message = f"{n} LINE(S) EXCLUDED"
            return self._render()
        if up in ("RESET", "RES"):
            self.excluded = set()
            self._message = "RESET COMPLETE"
            return self._render()
        if up in ("SUB", "SUBMIT"):
            return self._do_submit()
        if handled_prefix or not cmd:
            return self._render()
        self._message = f"INVALID COMMAND: {cmd}"
        return self._render()

    # -------------------------------------------------------- data edits
    def _apply_data_edits(self, pi: PanelInput) -> None:
        for name, val in pi.fields.items():
            if not name.startswith("LD"):
                continue
            try:
                idx = int(name[2:])
            except ValueError:
                continue
            if 0 <= idx < len(self.lines):
                new = val if self.hoff else val.rstrip()
                if self.caps:
                    new = new.upper()
                if self.hoff:
                    # the visible field is a window [hoff : hoff+width] of the
                    # full record; splice the edit back into the full line.
                    original = self.lines[idx]
                    left = original[:self.hoff]
                    right = original[self.hoff + _DATA_WIDTH:]
                    if right:
                        new = (left + new.ljust(_DATA_WIDTH) + right).rstrip()
                    else:
                        new = (left + new).rstrip()
                if new != self.lines[idx]:
                    self.lines[idx] = new
                    self.changed = True

    # ------------------------------------------------------ prefix cmds
    def _parse_prefix(self, val: str) -> Tuple[str, Optional[int]]:
        s = (val or "").strip().upper()
        if not s:
            return "", None
        if s[:2] in _BLOCKS:
            return s[:2], None
        m = _SINGLE_RE.match(s)
        if not m:
            return "", None
        return m.group(1), (int(m.group(2)) if m.group(2) else None)

    def _orig_prefix(self, idx: int) -> str:
        """The prefix string this line was rendered with (line number or '''''')."""
        return f"{((idx + 1) * 100) % 1000000:06d}" if self._num_at(idx) else "''''''"

    def _clean_prefix(self, val: str, orig: str) -> str:
        """Strip line-number residue left when a command is overtyped onto a
        pre-filled prefix field.

        The prefix area is pre-filled with the 6-digit line number; typing a
        short command like ``I2`` over the start leaves ``I20100``.  Without
        this, the count regex would read ``20`` and insert 20 lines.  We strip
        the longest trailing run that matches the original prefix, so ``I2``
        parses as command ``I`` count ``2``.
        """
        val = val or ""
        if not val.strip() or val == orig:
            return ""
        for cut in range(len(orig), 0, -1):
            if val.endswith(orig[-cut:]):
                head = val[: len(val) - cut]
                if head[:1].isalpha():
                    return head.strip()
                break
        return val.strip()

    def _apply_prefix(self, pi: PanelInput) -> Tuple[bool, str]:
        items: Dict[int, Tuple[str, Optional[int]]] = {}
        for name, val in pi.fields.items():
            if not name.startswith("LP"):
                continue
            try:
                idx = int(name[2:])
            except ValueError:
                continue
            cmd, cnt = self._parse_prefix(self._clean_prefix(val, self._orig_prefix(idx)))
            if cmd:
                items[idx] = (cmd, cnt)
        if not items:
            return False, ""
        if self.readonly:
            return True, "DATA SET IS READ-ONLY"

        # destination (A/B/O) for copy/move
        dest = None
        dest_kind = None
        for i, (c, _n) in items.items():
            if c in ("A", "B", "O"):
                dest, dest_kind = i, c

        cc = sorted(i for i, (c, _n) in items.items() if c == "CC")
        mm = sorted(i for i, (c, _n) in items.items() if c == "MM")
        c_single = [(i, n) for i, (c, n) in items.items() if c == "C"]
        m_single = [(i, n) for i, (c, n) in items.items() if c == "M"]

        if (cc or mm or c_single or m_single) or (
                dest is not None and self._pending_block is not None):
            # Merge this Enter's CC/MM markers with any previously-marked block,
            # so "mark CC...CC, Enter, then A, Enter" works like real ISPF.
            pend_kind, pend_marks = (self._pending_block or (None, []))
            c_marks = sorted(set(cc) | (set(pend_marks) if pend_kind == "C" else set()))
            m_marks = sorted(set(mm) | (set(pend_marks) if pend_kind == "M" else set()))
            move = False
            src = None
            if len(c_marks) >= 2:
                src = list(range(c_marks[0], c_marks[-1] + 1))
            elif len(m_marks) >= 2:
                src = list(range(m_marks[0], m_marks[-1] + 1)); move = True
            elif c_single:
                i, n = c_single[0]; src = list(range(i, i + (n or 1)))
            elif m_single:
                i, n = m_single[0]; src = list(range(i, i + (n or 1))); move = True
            elif len(c_marks) == 1:
                self._pending_block = ("C", c_marks)
                return True, "CC PENDING - MARK THE OTHER END OR ENTER A/B"
            elif len(m_marks) == 1:
                self._pending_block = ("M", m_marks)
                return True, "MM PENDING - MARK THE OTHER END OR ENTER A/B"
            else:
                return True, "INCOMPLETE BLOCK COMMAND"
            if dest is None:
                # Block fully marked but no destination yet: remember it.
                self._pending_block = ("M" if move else "C", src)
                return True, "PENDING COPY/MOVE - SPECIFY A OR B DESTINATION"
            block = [self.lines[k] for k in src if 0 <= k < len(self.lines)]
            # copied lines become new ('''''') ; moved lines keep their numbering
            block_num = [(False if not move else self._num_at(k))
                         for k in src if 0 <= k < len(self.lines)]
            srcset = set(src) if move else set()
            newlines: List[str] = []
            newnum: List[bool] = []
            for k, line in enumerate(self.lines):
                if k == dest and dest_kind == "B":
                    newlines.extend(block); newnum.extend(block_num)
                if k not in srcset:
                    newlines.append(line); newnum.append(self._num_at(k))
                if k == dest and dest_kind in ("A", "O"):
                    newlines.extend(block); newnum.extend(block_num)
            self.lines = newlines
            self.numbered = newnum
            self.excluded = set()
            self.changed = True
            self._pending_block = None
            return True, "BLOCK MOVED" if move else "BLOCK COPIED"

        # exclude / show (X, Xn, XX block, S to reveal)
        xx = sorted(i for i, (c, _n) in items.items() if c == "XX")
        xset = set()
        if len(xx) >= 2:
            xset.update(range(xx[0], xx[-1] + 1))
        for i, (c, n) in items.items():
            if c == "X":
                xset.update(range(i, i + (n or 1)))
        show = set()
        for i, (c, n) in items.items():
            if c == "S":
                show.update(range(i, i + (n or 1)))
        if xset or show:
            self.excluded |= {i for i in xset if 0 <= i < len(self.lines)}
            self.excluded -= show
            return True, ""

        # delete (D, Dn, DD)
        delete = set()
        dd = sorted(i for i, (c, _n) in items.items() if c == "DD")
        if len(dd) >= 2:
            delete.update(range(dd[0], dd[-1] + 1))
        for i, (c, n) in items.items():
            if c == "D":
                delete.update(range(i, i + (n or 1)))
        inserts = {i: (n or 1) for i, (c, n) in items.items() if c == "I"}
        repeats = {i: (n or 1) for i, (c, n) in items.items() if c == "R"}

        if delete or inserts or repeats:
            newlines = []
            newnum: List[bool] = []
            for k, line in enumerate(self.lines):
                if k in delete:
                    continue
                newlines.append(line); newnum.append(self._num_at(k))
                if k in repeats:
                    newlines.extend([line] * repeats[k])
                    newnum.extend([False] * repeats[k])  # repeated lines are new
                if k in inserts:
                    newlines.extend([""] * inserts[k])
                    newnum.extend([False] * inserts[k])  # inserted lines are new
            self.lines = newlines
            self.numbered = newnum
            self.excluded = set()  # indices shifted - clear stale excludes
            self.changed = True
            return True, ""
        return True, "UNKNOWN LINE COMMAND"

    # -------------------------------------------------------- find/change
    def _do_find(self, cmd: str) -> ScreenBuffer:
        parts = cmd.split(None, 1)
        term = parts[1].strip().strip("'\"") if len(parts) > 1 else self._last_find
        self._last_find = term
        if not term:
            self._message = "ENTER A FIND STRING"
            return self._render()
        low = term.lower()
        start = self.top + 1
        order = list(range(start, len(self.lines))) + list(range(0, start))
        for i in order:
            if low in self.lines[i].lower():
                self.top = i
                self._message = f"FOUND  '{term}'  on line {i+1}"
                return self._render()
        self._message = f"'{term}' NOT FOUND"
        return self._render()

    def _do_change(self, cmd: str) -> ScreenBuffer:
        # CHANGE str1 str2 [ALL|NEXT|FIRST]
        toks = cmd.split()
        if len(toks) < 3:
            self._message = "FORMAT: CHANGE oldstring newstring [ALL]"
            return self._render()
        old = toks[1].strip("'\"")
        new = toks[2].strip("'\"")
        allflag = len(toks) > 3 and toks[3].upper() == "ALL"
        self._last_change = (old, new, allflag)
        return self._change(old, new, allflag)

    def _repeat_change(self) -> ScreenBuffer:
        if not self._last_change:
            self._message = "NO PREVIOUS CHANGE TO REPEAT"
            return self._render()
        old, new, allflag = self._last_change
        return self._change(old, new, allflag)

    def _change(self, old: str, new: str, allflag: bool) -> ScreenBuffer:
        count = 0
        if allflag:
            for i, line in enumerate(self.lines):
                if old in line:
                    count += line.count(old)
                    self.lines[i] = line.replace(old, new)
            if count:
                self.changed = True
            self._message = f"{count} CHANGE(S) MADE" if count else f"'{old}' NOT FOUND"
        else:
            start = self.top
            order = list(range(start, len(self.lines))) + list(range(0, start))
            for i in order:
                if old in self.lines[i]:
                    self.lines[i] = self.lines[i].replace(old, new, 1)
                    self.top = i
                    self.changed = True
                    self._message = f"1 CHANGE MADE on line {i+1}"
                    break
            else:
                self._message = f"'{old}' NOT FOUND"
        return self._render()

    # -------------------------------------------------------------- save
    def _save(self) -> None:
        if self.readonly:
            self._message = "DATA SET IS READ-ONLY - NOT SAVED"
            return
        try:
            self.state.datasets.write(self.userid, self.dsname, "\n".join(self.lines) + "\n")
            self.changed = False
            self._renumber(True)  # saved lines acquire sequence numbers ('''''' -> numbered)
            self._message = f"{self.dsname} SAVED"
        except Exception as exc:
            self._message = f"SAVE FAILED: {exc}"

    def _do_submit(self) -> ScreenBuffer:
        text = "\n".join(self.lines) + "\n"
        try:
            if hasattr(self.state, "submit_job"):
                res = self.state.submit_job(text, self.userid)
            else:
                from gibson.apps.tso import TsoCommandProcessor
                self.state.datasets.write(self.userid, self.dsname, text)
                res = TsoCommandProcessor(self.state, self.userid).run(f"SUBMIT '{self.dsname}'")
            self._message = (str(res).strip().splitlines() or ["JOB SUBMITTED"])[0][:70]
        except Exception as exc:
            self._message = f"SUBMIT FAILED: {exc}"
        return self._render()

    # ------------------------------------------------------------ scroll
    def _scroll(self, key: str) -> None:
        if key == "PF8":
            if self.top + _DATA_ROWS < len(self.lines):
                self.top = min(self.top + _DATA_ROWS, max(0, len(self.lines) - 1))
        elif key == "PF7":
            self.top = max(0, self.top - _DATA_ROWS)
        elif key == "PF11":  # Right
            longest = max((len(l) for l in self.lines), default=0)
            if self.hoff + _DATA_WIDTH < longest:
                self.hoff += _DATA_WIDTH
        elif key == "PF10":  # Left
            self.hoff = max(0, self.hoff - _DATA_WIDTH)

    # ------------------------------------------------------------ render
    def _render(self) -> ScreenBuffer:
        s = ScreenBuffer()
        s.extended_attributes = True
        mode = "VIEW" if self.readonly else "EDIT"
        s.put(1, 1, f"{mode}  {self.dsname:<40} Columns {self.hoff + 1:05d} {self.hoff + _DATA_WIDTH + 1:05d}"[:79], colors.BLUE)
        s.put(2, 1, "Command ===>", colors.WHITE)
        s.add_field("COMMAND", 2, 14, 50, colour=_TURQ, role="command")
        s.put(2, 66, "Scroll ===> PAGE", colors.BLUE)
        # top-of-data marker.  Its 6-col prefix is an input field so a line
        # command (e.g. I / In) can insert the first line(s) even when the
        # member is empty - matching real ISPF.
        if self.top == 0:
            s.add_field("LPTOP", 3, 1, 6, value="******", colour=colors.BLUE, role="line_command", tab_order=0)
            s.put(3, 8, "********************** Top of Data ***********************************"[:72], colors.BLUE)
        else:
            s.put(3, 1, "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", colors.BLUE)
        if self._message:
            s.put(4, 1, ("==MSG> " + self._message)[:79], colors.YELLOW)

        end = min(self.top + _DATA_ROWS, len(self.lines))
        row = _FIRST_ROW
        idx = self.top
        last_idx = self.top
        tab = 1
        while idx < len(self.lines) and row < _FIRST_ROW + _DATA_ROWS:
            if idx in self.excluded:
                j = idx
                while j < len(self.lines) and j in self.excluded:
                    j += 1
                count = j - idx
                s.put(row, 1, f"- - - - - - - - - - - - - - -  {count} Line(s) Not Displayed"[:79], _TURQ)
                idx = j
            else:
                # numbered lines show a 6-digit sequence number; new lines (just
                # inserted / repeated / copied) show the ISPF '''''' prefix until
                # they are renumbered on SAVE or via RENUM.
                prefix = f"{((idx + 1) * 100) % 1000000:06d}" if self._num_at(idx) else "''''''"
                s.add_field(f"LP{idx:05d}", row, 1, 6, value=prefix, colour=colors.BLUE,
                            role="line_command", tab_order=tab)
                s.add_field(f"LD{idx:05d}", row, _DATA_COL, _DATA_WIDTH,
                            value=self.lines[idx][self.hoff:self.hoff + _DATA_WIDTH], colour=colors.GREEN,
                            role="data", tab_order=tab + 1)
                tab += 2
                idx += 1
            row += 1
            last_idx = idx
        if last_idx >= len(self.lines) and row <= 23:
            s.put(row, 1, "****** **************************** Bottom of Data ****************************"[:79], colors.BLUE)

        legend = ("F1=Help F2=Split F3=Exit F4=Expand F5=Rfind F6=Rchange "
                  "F7=Up F8=Down F9=Swap F10=Left F11=Right F12=Cancel")
        if self.readonly:
            legend = ("F1=Help F2=Split F3=Exit F5=Rfind F7=Up F8=Down "
                      "F9=Swap F10=Left F11=Right F12=Cancel")
        s.put(24, 1, legend[:79], colors.BLUE)
        target = getattr(self, "_cursor_target", None)
        if target and any(f.name == target for f in s.fields):
            tf = [f for f in s.fields if f.name == target][0]
            s.set_cursor(tf.row, tf.col)
        else:
            s.set_cursor(2, 14)
        self._cursor_target = None
        return s
