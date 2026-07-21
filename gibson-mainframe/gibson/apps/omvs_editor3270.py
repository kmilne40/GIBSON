"""Full-screen 3270 editor for the OMVS shell (oedit / vi / view / edit).

A faithful-enough ISPF EDIT primitive rendered as a real 3270 panel: a line-number
prefix area, an editable content area, a primary command line and a bottom-of-data
marker.  Used in OMVS3270 mode where a line-mode `vi` cannot work.

Supported:
* Direct overtyping of content lines.
* Prefix (line) commands: I / In (insert), D / Dn (delete), R / Rn (repeat).
* Primary commands: SAVE, CANCEL, END (PF3 = save+exit), TOP, BOTTOM/BOT,
  FIND text, CHANGE old new [ALL], RESET.
* Scrolling: PF7 (up) / PF8 (down).
* view / obrowse open read-only (BROWSE).
"""
from __future__ import annotations

from typing import Callable, Optional

from gibson.render.screen3270 import ScreenBuffer
from gibson.render import colors

try:
    _TURQ = colors.TURQUOISE
except Exception:  # pragma: no cover
    _TURQ = colors.GREEN


class Omvs3270Editor:
    def __init__(self, path: str, text: str, *, readonly: bool = False,
                 save_cb: Optional[Callable[[str], None]] = None,
                 rows: int = 24, cols: int = 80, recfm: str = "VB", lrecl: int = 255):
        self.path = path
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "" and len(self.lines) > 1:
            self.lines.pop()           # drop trailing empty from final newline
        if not self.lines:
            self.lines = [""]
        self.readonly = readonly
        self.save_cb = save_cb
        self.rows = rows
        self.cols = cols
        self.recfm = recfm
        self.lrecl = lrecl
        self.top = 0
        self.message = ""
        self.ended = False
        self.saved = False
        self.body_rows = rows - 4      # title, cmd line, ... pfkey row, bottom marker
        self._pending = ""             # last FIND target for RFIND

    # ----------------------------------------------------------------- render
    def render(self) -> ScreenBuffer:
        s = ScreenBuffer(rows=self.rows)
        s.extended_attributes = True
        mode = "BROWSE" if self.readonly else "EDIT  "
        s.put(1, 1, mode, colors.WHITE)
        s.put(1, 8, self.path[:48], colors.YELLOW)
        s.put(1, 60, f"Columns 00001 {self.lrecl:05d}"[:19], colors.BLUE)
        s.put(2, 1, "Command ===>", colors.WHITE)
        s.add_field("CMD", 2, 14, 51, colour=_TURQ, role="command")
        s.put(2, 66, "Scroll ===> PAGE", colors.BLUE)

        n = len(self.lines)
        r = 3
        last = min(n, self.top + self.body_rows)
        content_width = min(self.cols - 9, self.lrecl)
        for i in range(self.top, last):
            num = f"{(i + 1) * 100:06d}"
            pcol = colors.BLUE if not self.readonly else colors.WHITE
            if self.readonly:
                s.put(r, 1, num, pcol)
                s.put(r, 8, self.lines[i][:content_width], colors.GREEN)
            else:
                s.add_field(f"P{i}", r, 1, 6, value=num, colour=pcol, role="input")
                s.add_field(f"L{i}", r, 8, content_width, value=self.lines[i][:content_width],
                            colour=colors.GREEN, role="input")
            r += 1
            if r > self.rows - 1:
                break
        if last >= n and r <= self.rows - 1:
            s.put(r, 1, "****** " + "*" * 30 + " Bottom of Data " + "*" * 26, colors.BLUE)

        pf = ("PF1=Help PF3=End/Save PF7=Up PF8=Down   prefix: I D R   "
              "cmd: SAVE CANCEL FIND CHANGE")
        if self.readonly:
            pf = "PF1=Help PF3=End PF7=Up PF8=Down   BROWSE (read-only)"
        s.put(self.rows, 1, pf[:79], colors.BLUE)
        if self.message:
            s.put(1, 32, self.message[:46], colors.RED)
        s.set_cursor(3, 8)
        return s

    # ----------------------------------------------------------------- handle
    def handle(self, pi) -> Optional[ScreenBuffer]:
        """Process one interaction. Sets self.ended=True when the editor should
        close (caller then inspects self.saved)."""
        self.message = ""
        n = len(self.lines)
        visible = range(self.top, min(n, self.top + self.body_rows))

        # 1) capture content edits (overtyping)
        if not self.readonly:
            for i in list(visible):
                k = f"L{i}"
                if k in pi.fields:
                    self.lines[i] = (pi.fields.get(k, "") or "").rstrip()

        # 2) prefix line commands
        if not self.readonly:
            cmds = []
            for i in list(visible):
                raw = (pi.fields.get(f"P{i}", "") or "").strip().upper()
                num = f"{(i + 1) * 100:06d}"
                if raw and raw != num and not raw.isdigit():
                    cmds.append((i, raw))
            # apply from bottom up so indices stay valid
            for i, raw in sorted(cmds, reverse=True):
                self._apply_prefix(i, raw)

        # 3) primary command
        cmd = pi.stripped("CMD")
        end_after = self._apply_primary(cmd)

        # 4) PF keys
        if pi.key in ("PF3", "PF15"):
            if not self.readonly and self.save_cb:
                self._save()
            self.ended = True
            return None
        if pi.key in ("PF7", "PF18"):
            self.top = max(0, self.top - self.body_rows)
        elif pi.key in ("PF8", "PF19"):
            if self.top + self.body_rows < len(self.lines):
                self.top = min(len(self.lines) - 1, self.top + self.body_rows)
        if end_after:
            self.ended = True
            return None
        return self.render()

    # --------------------------------------------------------------- prefix
    def _apply_prefix(self, i: int, raw: str) -> None:
        letter = raw[0]
        rest = raw[1:].strip()
        count = 1
        if rest.isdigit():
            count = max(1, min(int(rest), 200))
        if letter == "I":          # insert blank line(s) after this line
            for _ in range(count):
                self.lines.insert(i + 1, "")
            self.message = f"{count} line(s) inserted"
        elif letter == "D":        # delete count lines from here
            del self.lines[i:i + count]
            if not self.lines:
                self.lines = [""]
            self.message = f"{count} line(s) deleted"
        elif letter == "R":        # repeat this line count times
            for _ in range(count):
                self.lines.insert(i + 1, self.lines[i])
            self.message = f"{count} line(s) repeated"

    # --------------------------------------------------------------- primary
    def _apply_primary(self, cmd: str) -> bool:
        if not cmd:
            return False
        up = cmd.upper()
        verb, _, arg = up.partition(" ")
        arg = cmd.partition(" ")[2].strip()
        if verb in ("SAVE",):
            self._save()
            return False
        if verb in ("END",):
            if not self.readonly:
                self._save()
            return True
        if verb in ("CANCEL", "CAN"):
            self.saved = False
            self.message = "Edits discarded"
            return True
        if verb in ("TOP",):
            self.top = 0
            return False
        if verb in ("BOTTOM", "BOT"):
            self.top = max(0, len(self.lines) - self.body_rows)
            return False
        if verb in ("RESET", "RES"):
            self.message = "Reset"
            return False
        if verb in ("FIND", "F"):
            return self._find(arg)
        if verb in ("CHANGE", "C"):
            return self._change(arg)
        self.message = f"Unknown command: {verb}"
        return False

    def _find(self, arg: str) -> bool:
        target = arg.strip().strip("'\"")
        if not target:
            self.message = "FIND requires an argument"
            return False
        start = self.top + 1
        for idx in range(start, len(self.lines)) :
            if target.lower() in self.lines[idx].lower():
                self.top = idx
                self.message = f"FOUND '{target}'"
                return False
        # wrap from top
        for idx in range(0, start):
            if target.lower() in self.lines[idx].lower():
                self.top = idx
                self.message = f"FOUND '{target}' (wrapped)"
                return False
        self.message = f"'{target}' not found"
        return False

    def _change(self, arg: str) -> bool:
        if self.readonly:
            self.message = "Cannot CHANGE in BROWSE"
            return False
        parts = arg.split()
        all_flag = False
        if parts and parts[-1].upper() == "ALL":
            all_flag = True
            parts = parts[:-1]
        if len(parts) < 2:
            self.message = "CHANGE old new [ALL]"
            return False
        old = parts[0].strip("'\"")
        new = parts[1].strip("'\"")
        changed = 0
        rng = range(len(self.lines)) if all_flag else range(self.top, len(self.lines))
        for idx in rng:
            if old in self.lines[idx]:
                if all_flag:
                    changed += self.lines[idx].count(old)
                    self.lines[idx] = self.lines[idx].replace(old, new)
                else:
                    self.lines[idx] = self.lines[idx].replace(old, new, 1)
                    self.top = idx
                    changed = 1
                    break
        self.message = f"{changed} change(s) made" if changed else f"'{old}' not found"
        return False

    # ----------------------------------------------------------------- save
    def _save(self) -> None:
        if self.readonly or not self.save_cb:
            return
        try:
            self.save_cb("\n".join(self.lines) + "\n")
            self.saved = True
            self.message = "Saved"
        except Exception as exc:  # noqa: BLE001
            self.message = f"Save failed: {exc}"
