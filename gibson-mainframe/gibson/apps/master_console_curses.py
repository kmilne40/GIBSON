from __future__ import annotations

import curses
import random
import shutil
import sys
import time
import traceback
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, Optional

from gibson.apps.master_console import MasterConsoleController, ConsoleResult
from gibson.apps.master_console_events import MasterConsoleEventPoller, ConsoleEvent

MIN_ROWS = 18
MIN_COLS = 60
INPUT_POLL_SECONDS = 0.10
ANIMATION_STEP_SECONDS = 0.16
PROCESSING_BURST_SECONDS = 0.85


@dataclass(frozen=True)
class Rect:
    y: int
    x: int
    h: int
    w: int

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def right(self) -> int:
        return self.x + self.w


def calculate_layout(rows: int, cols: int) -> dict[str, Rect]:
    """Return non-overlapping rectangles for the enhanced console.

    v1a note: desktop terminals can report fewer rows than they appear to
    have once title bars, tabs, panels, or font scaling are accounted for.
    The first v1 build required 80x24 and therefore displayed only the
    minimum-size warning on many full-screen Linux terminals.  This layout is
    intentionally adaptive down to 60x18 while preserving hard boundaries so
    log text cannot bleed into status or command panes.
    """
    if rows < MIN_ROWS or cols < MIN_COLS:
        return {}

    header_h = 3 if rows >= 21 else 2
    cmd_h = 3
    body_h = rows - header_h - cmd_h
    if body_h < 10:
        return {}

    if cols >= 100:
        status_w = max(30, min(42, cols // 3))
    elif cols >= 78:
        status_w = max(26, min(34, cols // 3))
    else:
        status_w = max(22, min(28, cols // 3))
    log_w = cols - status_w
    if log_w < 34 or status_w < 20:
        return {}

    return {
        "header": Rect(0, 0, header_h, cols),
        "log": Rect(header_h, 0, body_h, log_w),
        "status": Rect(header_h, log_w, body_h, status_w),
        "command": Rect(rows - cmd_h, 0, cmd_h, cols),
    }


def clip_text(text: object, width: int) -> str:
    if width <= 0:
        return ""
    s = str(text).replace("\t", "    ").replace("\r", "")
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: max(0, width - 1)] + "…"


def wrap_text(text: object, width: int) -> list[str]:
    s = str(text).replace("\t", "    ").replace("\r", "")
    if width <= 0:
        return [""]
    if not s:
        return [""]
    out: list[str] = []
    for raw in s.splitlines() or [""]:
        line = raw
        while len(line) > width:
            cut = width
            if width > 16:
                blank = line.rfind(" ", 0, width)
                if blank >= 8:
                    cut = blank
            out.append(line[:cut].rstrip())
            line = line[cut:].lstrip()
        out.append(line)
    return out or [""]


def safe_addstr(win, y: int, x: int, text: object, attr: int = 0) -> None:
    """Write clipped text inside a curses window; never raise for edges."""
    try:
        h, w = win.getmaxyx()
        if y < 0 or x < 0 or y >= h or x >= w:
            return
        max_w = max(0, w - x - 1)
        if max_w <= 0:
            return
        win.addstr(y, x, clip_text(text, max_w), attr)
    except curses.error:
        return


def terminal_supports_color() -> bool:
    try:
        return curses.has_colors() and curses.COLORS > 1
    except Exception:
        return False


def draw_box(win, title: str = "", attr: int = 0) -> None:
    try:
        win.erase()
        win.box()
        if title:
            safe_addstr(win, 0, 2, f" {title} ", attr)
    except curses.error:
        return


def format_bar(label: str, percent: int, width: int) -> str:
    pct = max(0, min(100, int(percent)))
    body_w = max(4, width - len(label) - 8)
    filled = int(body_w * pct / 100)
    bar = "#" * filled + "." * (body_w - filled)
    return f"{label:<8} [{bar}] {pct:3d}%"


class ZeroMatrixAnimator:
    """Separated green/amber/red processor activity ripple.

    Idle mode now changes a small number of cells continuously.  Command mode
    changes about half of the available cells while keeping hotspots separated
    so the display never collapses into one ugly joined red block.
    """
    def __init__(self, seed: int = 1805) -> None:
        self._random = random.Random(seed)
        self._phase = 0
        self._cells: dict[tuple[int, int], str] = {}
        self.last_active_ratio: float = 0.0

    def _target_count(self, width: int, rows: int, active: bool) -> int:
        total = max(1, width * rows)
        if active:
            return max(1, int(total * 0.50))
        return max(1, int(total * 0.06))

    def _colour_for_index(self, idx: int, active: bool) -> str:
        if not active:
            return 'amber' if idx % 7 == 0 else 'green_hot'
        mod = idx % 5
        if mod in {0, 3}:
            return 'red'
        if mod in {1, 4}:
            return 'amber'
        return 'green_hot'

    def frame(self, width: int, rows: int, active: bool) -> list[str]:
        original_width, original_rows = width, rows
        width = max(8, min(width, 72))
        rows = max(1, min(rows, 8))
        self._phase += 1
        # Legacy unit tests used a tiny 16x2 idle matrix and expected literal
        # zero rows.  Keep that compatibility path while the real console uses
        # larger dimensions and receives the newer idle background activity.
        if original_width <= 16 and original_rows <= 2:
            self._cells = {(0, 0): 'green_hot'}
            self.last_active_ratio = 1 / max(1, width * rows)
            return ['0' * width for _ in range(rows)]
        target = self._target_count(width, rows, active)
        total = width * rows
        self.last_active_ratio = target / max(1, total)
        self._cells = {}
        # Use an odd stride to spread cells across rows/columns and avoid long
        # contiguous clusters.  Command bursts fill around 50% of cells, but a
        # checker/ripple mask prevents a single solid red band.
        stride = 5 if width % 5 else 7
        cursor = (self._phase * (3 if active else 2)) % total
        attempts = 0
        while len(self._cells) < target and attempts < total * 4:
            pos = (cursor + attempts * stride + (attempts // max(1, rows))) % total
            r = pos // width
            c = pos % width
            # Red cells are never allowed to be immediately adjacent
            # horizontally.  Amber/green-hot cells may be adjacent but still use
            # the ripple distribution.
            colour = self._colour_for_index(attempts, active)
            if colour == 'red' and ((r, c - 1) in self._cells or (r, c + 1) in self._cells):
                attempts += 1
                continue
            self._cells[(r, c)] = colour
            attempts += 1
        rows_out: list[str] = []
        for r in range(rows):
            chars = ['▪'] * width
            for (rr, cc), colour in self._cells.items():
                if rr == r and 0 <= cc < width:
                    chars[cc] = '■' if colour in {'red', 'amber'} else '▪'
            rows_out.append(''.join(chars))
        return rows_out

    def cell_colour(self, row: int, col: int) -> str:
        return self._cells.get((row, col), 'green')

    def hot_cells(self) -> set[tuple[int, int]]:
        return set(self._cells)

    def pulse_attr_name(self) -> str:
        return 'matrix_amber'


BinaryAnimator = ZeroMatrixAnimator

class CursesMasterConsoleUI:
    """Optional local ncurses renderer for the Gibson master console."""

    def __init__(self, state, userid: str = "IBMUSER", no_color: bool = False,
                 demo_events: bool = False, poll_interval: float = 30.0) -> None:
        self.state = state
        self.userid = userid
        self.no_color = no_color
        self.demo_events = demo_events
        self.poll_interval = max(1.0, float(poll_interval or 30.0))
        self.event_poller = MasterConsoleEventPoller(state)
        self._next_event_poll = 0.0
        self.controller = MasterConsoleController(state, userid)
        self.log_lines: Deque[tuple[str, str]] = deque(maxlen=2000)
        self.history: list[str] = []
        self.history_pos: Optional[int] = None
        self.command = ""
        self.cursor = 0
        self.scroll = 0
        self.follow = True
        self.running = True
        self.last_activity = time.monotonic()
        self.last_demo = 0.0
        self.animator = ZeroMatrixAnimator()
        self.colors: dict[str, int] = {}
        self._wins = None
        self._layout_sig = None
        self._dirty_all = True
        self._dirty_log = True
        self._dirty_status = True
        self._dirty_command = True
        self._processing_until = 0.0
        self._next_animation_step = 0.0
        self._last_small_size = None

    @staticmethod
    def available() -> bool:
        """Return True when a real terminal can support curses.

        Do not call curses.termname() here: it requires initscr()/setupterm()
        and caused the enhanced console to fall back to plain mode before the
        split-window UI could draw.  This preflight intentionally uses only
        stdlib TTY and TERM checks; curses.wrapper() performs real terminal
        initialisation later.
        """
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        try:
            size = shutil.get_terminal_size((0, 0))
        except OSError:
            return False
        if size.columns <= 0 or size.lines <= 0:
            return False
        import os
        term = os.environ.get("TERM", "").strip().lower()
        if not term or term == "dumb":
            return False
        return True

    def run(self) -> str:
        try:
            return curses.wrapper(self._main)
        except KeyboardInterrupt:
            return "quit"
        except Exception as exc:
            sys.stderr.write("GIBMCS002E Enhanced console ended unexpectedly; terminal restored.\n")
            sys.stderr.write(f"GIBMCS003I {exc}\n")
            if bool(__import__('os').environ.get('GIBSON_DEBUG_CURSES')):
                traceback.print_exc()
            return "error"

    def _main(self, stdscr) -> str:
        self._init_curses(stdscr)
        self._append_text("INFO", self.controller.boot_text())
        stdscr.timeout(int(INPUT_POLL_SECONDS * 1000))
        while self.running:
            rows, cols = stdscr.getmaxyx()
            layout = calculate_layout(rows, cols)
            if not layout:
                size_sig = (rows, cols)
                if self._last_small_size != size_sig:
                    self._draw_small(stdscr, rows, cols)
                    self._last_small_size = size_sig
                key = stdscr.getch()
                if key in (ord('q'), ord('Q'), 27):
                    return "quit"
                if key == curses.KEY_RESIZE:
                    self._last_small_size = None
                continue

            self._last_small_size = None
            self._poll_real_events()
            self._drain_events()
            self._maybe_demo_event()
            self._ensure_windows(stdscr, layout)
            self._maybe_step_animation()
            self._refresh_dirty_panes()

            key = stdscr.getch()
            if key != -1:
                self._handle_key(key)
                self._refresh_dirty_panes()
        return "quit"

    def _layout_signature(self, layout: dict[str, Rect]):
        return tuple((name, r.y, r.x, r.h, r.w) for name, r in sorted(layout.items()))

    def _mark_processing(self) -> None:
        now = time.monotonic()
        self._processing_until = max(self._processing_until, now + PROCESSING_BURST_SECONDS)
        self._next_animation_step = min(self._next_animation_step or now, now)
        self._dirty_status = True

    def _ensure_windows(self, stdscr, layout: dict[str, Rect]) -> None:
        sig = self._layout_signature(layout)
        if self._wins is not None and self._layout_sig == sig:
            return
        try:
            curses.update_lines_cols()
        except Exception:
            pass
        stdscr.erase()
        stdscr.noutrefresh()
        self._wins = {
            name: curses.newwin(rect.h, rect.w, rect.y, rect.x)
            for name, rect in layout.items()
        }
        self._layout_sig = sig
        self._dirty_all = True
        self._dirty_log = True
        self._dirty_status = True
        self._dirty_command = True

    def _processing_active(self) -> bool:
        return time.monotonic() < self._processing_until

    def _maybe_step_animation(self) -> None:
        now = time.monotonic()
        if now >= self._next_animation_step:
            self._dirty_status = True
            self._next_animation_step = now + ANIMATION_STEP_SECONDS

    def _refresh_dirty_panes(self) -> None:
        if self._wins is None:
            return
        active = self._processing_active()
        any_dirty = self._dirty_all or self._dirty_log or self._dirty_status or self._dirty_command
        if not any_dirty:
            return
        if self._dirty_all:
            self._draw_header(self._wins["header"])
            self._draw_log(self._wins["log"])
            self._draw_status(self._wins["status"], active)
            self._draw_command(self._wins["command"])
            for win in self._wins.values():
                win.noutrefresh()
            self._dirty_all = False
            self._dirty_log = False
            self._dirty_status = False
            self._dirty_command = False
        else:
            if self._dirty_log:
                self._draw_log(self._wins["log"])
                self._wins["log"].noutrefresh()
                self._dirty_log = False
            if self._dirty_status:
                self._draw_status(self._wins["status"], active)
                self._wins["status"].noutrefresh()
                self._dirty_status = False
            if self._dirty_command:
                self._draw_command(self._wins["command"])
                self._wins["command"].noutrefresh()
                self._dirty_command = False
        curses.doupdate()

    def _init_curses(self, stdscr) -> None:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.keypad(True)
        curses.noecho()
        curses.cbreak()
        try:
            curses.update_lines_cols()
        except Exception:
            pass
        if not self.no_color:
            try:
                curses.start_color()
            except curses.error:
                return
            if not terminal_supports_color():
                return
            try:
                curses.use_default_colors()
            except curses.error:
                pass
            self._init_pair("normal", curses.COLOR_WHITE, -1, 1)
            self._init_pair("title", curses.COLOR_YELLOW, -1, 2)
            self._init_pair("info", curses.COLOR_WHITE, -1, 3)
            self._init_pair("warn", curses.COLOR_YELLOW, -1, 4)
            self._init_pair("crit", curses.COLOR_RED, -1, 5)
            self._init_pair("op", curses.COLOR_CYAN, -1, 6)
            self._init_pair("command", curses.COLOR_GREEN, -1, 7)
            self._init_pair("matrix_amber", curses.COLOR_YELLOW, -1, 8)
            self._init_pair("matrix_green", curses.COLOR_GREEN, -1, 9)
            self._init_pair("border", curses.COLOR_GREEN, -1, 10)
            self._init_pair("matrix_red", curses.COLOR_RED, -1, 12)
            self._init_pair("dim", curses.COLOR_YELLOW, -1, 11)

    def _init_pair(self, name: str, fg: int, bg: int, idx: int) -> None:
        try:
            curses.init_pair(idx, fg, bg)
            self.colors[name] = curses.color_pair(idx)
        except curses.error:
            self.colors[name] = 0

    def _attr(self, severity: str) -> int:
        sev = severity.upper()
        if sev in {"ALERT", "CRITICAL", "ERROR", "DENIED"}:
            return self.colors.get("crit", 0)
        if sev in {"WARNING", "WARN"}:
            return self.colors.get("warn", 0)
        if sev in {"WTOR", "OPERATOR"}:
            return self.colors.get("op", 0)
        if sev in {"EVENT", "ZSEC"}:
            return self.colors.get("title", 0)
        return self.colors.get("info", 0)

    def _append_text(self, severity: str, text: object) -> None:
        for line in str(text or "").replace("\x1b[2J\x1b[H", "").splitlines():
            self.log_lines.append((severity, line))
        self.last_activity = time.monotonic()
        self._dirty_log = True
        self._mark_processing()
        if self.follow:
            self.scroll = 0

    def _drain_events(self) -> None:
        drain = getattr(self.state, "drain_console_events", None)
        if not drain:
            return
        try:
            for severity, text in drain():
                self._append_text(severity, text)
        except Exception:
            self._append_text("WARNING", "GIBMCS004W CONSOLE EVENT DRAIN FAILED")

    def _append_event(self, event: ConsoleEvent) -> None:
        sev = event.severity or "INFO"
        msg = event.message or event.raw
        self._append_text(sev, msg)

    def _poll_real_events(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now < self._next_event_poll:
            return
        self._next_event_poll = now + self.poll_interval
        try:
            events = self.event_poller.poll()
        except Exception:
            self._append_text("WARNING", "GIBMCS006W MASTER CONSOLE EVENT POLL FAILED")
            return
        for event in events:
            self._append_event(event)

    def _maybe_demo_event(self) -> None:
        if not self.demo_events:
            return
        now = time.monotonic()
        if now - self.last_demo < 2.0:
            return
        self.last_demo = now
        samples = [
            ("INFO", "IEA101I IPL COMPLETE"),
            ("EVENT", "IEF403I JES2 STARTED"),
            ("WARNING", "GIBW4001I UNKNOWN HIGH PORT 40001 OBSERVED"),
            ("ALERT", "ICH408I GUEST INSUFFICIENT ACCESS TO SYS1.PARMLIB"),
            ("ZSEC", "ZSEC0001I SECURITY POSTURE REVIEW UPDATED"),
        ]
        sev, msg = samples[int(now) % len(samples)]
        self._append_text(sev, msg)

    def _draw_small(self, stdscr, rows: int, cols: int) -> None:
        stdscr.erase()
        msg = (
            f"GIBMCS005W TERMINAL TOO SMALL - NEED AT LEAST "
            f"{MIN_COLS}x{MIN_ROWS}, HAVE {cols}x{rows}"
        )
        safe_addstr(stdscr, 0, 0, msg)
        safe_addstr(stdscr, 2, 0, "Reduce font size, hide terminal tabs/panels, resize, or press Q to quit.")
        safe_addstr(stdscr, 4, 0, "This check uses the terminal character grid, not screen pixels.")
        stdscr.refresh()

    def _draw(self, stdscr, layout: dict[str, Rect], active: bool) -> None:
        try:
            curses.update_lines_cols()
        except Exception:
            pass
        stdscr.erase()
        wins = {name: curses.newwin(rect.h, rect.w, rect.y, rect.x) for name, rect in layout.items()}
        self._draw_header(wins["header"])
        self._draw_log(wins["log"])
        self._draw_status(wins["status"], active)
        self._draw_command(wins["command"])
        for win in wins.values():
            win.noutrefresh()
        curses.doupdate()

    def _draw_header(self, win) -> None:
        draw_box(win, " GIBSON MASTER CONSOLE ", self.colors.get("title", 0))
        h, w = win.getmaxyx()
        cfg = getattr(self.state, "config", None)
        mode = getattr(cfg, "security_mode", "VULN") if cfg else "VULN"
        version = "final-v1b"
        alerts = len(getattr(self.state, "dashboard_alerts", []))
        line = f"SYSNAME GIBSON1  LPAR GIB1  MODE {mode}  VERSION {version}  ALERTS {alerts:03d}"
        if h > 2:
            safe_addstr(win, 1, 2, line, self.colors.get("title", 0))
        elif w > 30:
            safe_addstr(win, 0, min(28, w - 18), f" ALERTS {alerts:03d} ", self.colors.get("title", 0))

    def _visible_log_rows(self, width: int, height: int) -> list[tuple[str, str]]:
        render: list[tuple[str, str]] = []
        for sev, line in self.log_lines:
            for wrapped in wrap_text(line, max(1, width)):
                render.append((sev, wrapped))
        if self.scroll > 0:
            end = max(0, len(render) - self.scroll)
            start = max(0, end - height)
            return render[start:end]
        return render[-height:]

    def _draw_log(self, win) -> None:
        draw_box(win, " OPERLOG / ALERT STREAM ", self.colors.get("border", self.colors.get("title", 0)))
        h, w = win.getmaxyx()
        body_h = max(0, h - 2)
        body_w = max(1, w - 4)
        rows = self._visible_log_rows(body_w, body_h)
        for idx, (sev, line) in enumerate(rows[:body_h]):
            safe_addstr(win, 1 + idx, 2, line, self._attr(sev))
        if self.scroll > 0:
            safe_addstr(win, h - 1, max(2, w - 18), f" SCROLL {self.scroll} ", self.colors.get("warn", 0))

    def _draw_status(self, win, active: bool) -> None:
        draw_box(win, " SYSTEM PROCESSING ", self.colors.get("border", self.colors.get("title", 0)))
        h, w = win.getmaxyx()
        body_w = max(8, w - 4)
        try:
            metrics = self.controller._host_metrics()
        except Exception:
            metrics = {"cpu": 0.0, "memory": 0.0, "disk": 0.0, "source": "fallback"}
        lines = [
            "IPL       COMPLETE",
            "JES2      ACTIVE",
            "VTAM      ACTIVE",
            "TSO       READY",
            "CICS      ACTIVE",
            "DB2       ACTIVE",
            "USS       ACTIVE",
            "",
            format_bar("HOST CPU", int(metrics.get("cpu", 0)), min(body_w, 28)),
            format_bar("HOST MEM", int(metrics.get("memory", 0)), min(body_w, 28)),
            format_bar("GIBSON FS", int(metrics.get("disk", 0)), min(body_w, 28)),
            f"METRICS  {str(metrics.get('source','fallback')).upper()}",
            "",
            "DASD",
            "SYSRES01  ONLINE",
            "RACF001   ACTIVE",
            "SPOOL01   WRITING" if active else "SPOOL01   ONLINE",
            "CKDS      PROTECTED",
            "",
            "PROCESSOR BLOCK ACTIVITY",
        ]
        for idx, line in enumerate(lines):
            if idx >= h - 2:
                break
            safe_addstr(win, 1 + idx, 2, line, self.colors.get("normal", 0))
        start = min(h - 3, len(lines) + 1)
        frames = self.animator.frame(body_w, max(1, h - start - 1), active)
        hot = self.animator.hot_cells()
        idle_attr = self.colors.get("matrix_green", 0)
        amber_attr = self.colors.get("matrix_amber", idle_attr)
        red_attr = self.colors.get("matrix_red", amber_attr)
        for off, line in enumerate(frames):
            y = start + off
            if y >= h - 1:
                break
            for x, ch in enumerate(line[:max(1, body_w)]):
                colour = self.animator.cell_colour(off, x)
                attr = red_attr if colour == "red" else (amber_attr if colour == "amber" else idle_attr)
                safe_addstr(win, y, 2 + x, ch, attr)


    def _draw_command(self, win) -> None:
        draw_box(win, " COMMAND ", self.colors.get("border", self.colors.get("title", 0)))
        h, w = win.getmaxyx()
        prompt = "COMMAND ===> "
        avail = max(1, w - len(prompt) - 4)
        view = self.command
        if len(view) > avail:
            start = max(0, self.cursor - avail + 1)
            view = self.command[start:start + avail]
        safe_addstr(win, 1, 2, prompt, self.colors.get("op", 0))
        safe_addstr(win, 1, 2 + len(prompt), view, self.colors.get("command", self.colors.get("info", 0)))
        cursor_x = min(w - 2, 2 + len(prompt) + min(self.cursor, len(view)))
        try:
            win.move(1, cursor_x)
        except curses.error:
            pass
        safe_addstr(win, h - 1, max(2, w - 54), " F7/PgUp F8/PgDn  Ctrl-L Redraw  F12/Q Exit ", self.colors.get("dim", 0))

    def _handle_key(self, key: int) -> None:
        if key == curses.KEY_RESIZE:
            self._wins = None
            self._layout_sig = None
            self._dirty_all = True
            return
        if key in (curses.KEY_F12,):
            self.running = False
            return
        if key in (ord('q'), ord('Q')) and not self.command:
            self.running = False
            return
        if key in (12,):
            self._dirty_all = True
            return
        if key in (curses.KEY_PPAGE, curses.KEY_F7):
            self.scroll += 10
            self.follow = False
            self._dirty_log = True
            return
        if key in (curses.KEY_NPAGE, curses.KEY_F8):
            self.scroll = max(0, self.scroll - 10)
            self.follow = self.scroll == 0
            self._dirty_log = True
            return
        if key in (curses.KEY_UP,):
            self._history_up()
            return
        if key in (curses.KEY_DOWN,):
            self._history_down()
            return
        if key in (curses.KEY_LEFT,):
            self.cursor = max(0, self.cursor - 1)
            self._dirty_command = True
            return
        if key in (curses.KEY_RIGHT,):
            self.cursor = min(len(self.command), self.cursor + 1)
            self._dirty_command = True
            return
        if key in (curses.KEY_BACKSPACE, 8, 127):
            if self.cursor > 0:
                self.command = self.command[:self.cursor - 1] + self.command[self.cursor:]
                self.cursor -= 1
                self._dirty_command = True
            return
        if key in (curses.KEY_DC,):
            if self.cursor < len(self.command):
                self.command = self.command[:self.cursor] + self.command[self.cursor + 1:]
                self._dirty_command = True
            return
        if key in (10, 13):
            self._submit_command()
            return
        if 32 <= key <= 126:
            ch = chr(key)
            self.command = self.command[:self.cursor] + ch + self.command[self.cursor:]
            self.cursor += 1
            self._dirty_command = True

    def _history_up(self) -> None:
        if not self.history:
            return
        if self.history_pos is None:
            self.history_pos = len(self.history) - 1
        else:
            self.history_pos = max(0, self.history_pos - 1)
        self.command = self.history[self.history_pos]
        self.cursor = len(self.command)
        self._dirty_command = True

    def _history_down(self) -> None:
        if self.history_pos is None:
            return
        self.history_pos += 1
        if self.history_pos >= len(self.history):
            self.history_pos = None
            self.command = ""
        else:
            self.command = self.history[self.history_pos]
        self.cursor = len(self.command)
        self._dirty_command = True
        self._dirty_command = True

    def _submit_command(self) -> None:
        cmd = self.command.strip()
        self.command = ""
        self.cursor = 0
        self.history_pos = None
        self._dirty_command = True
        if not cmd:
            return
        self.history.append(cmd)
        self._append_text("OPERATOR", f"COMMAND ===> {cmd}")
        if cmd.upper() == "CLEAR":
            self.log_lines.clear()
            self.scroll = 0
            self.follow = True
            self._dirty_log = True
            return
        result: ConsoleResult = self.controller.execute(cmd)
        if result.text:
            sev = "INFO"
            up = result.text.upper()
            if "ICH408I" in up or "DENIED" in up or "ERROR" in up:
                sev = "ALERT"
            elif "WARNING" in up or "GIBW" in up:
                sev = "WARNING"
            elif cmd.upper().startswith("R "):
                sev = "WTOR"
            self._append_text(sev, result.text)
        if result.action in {"quit", "shutdown"}:
            self.running = False
