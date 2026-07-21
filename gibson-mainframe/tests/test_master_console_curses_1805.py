from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from gibson.apps.master_console import MasterConsoleController
from gibson.apps.master_console_curses import (
    BinaryAnimator,
    MIN_COLS,
    MIN_ROWS,
    calculate_layout,
    clip_text,
    format_bar,
    wrap_text,
)
from gibson.cli import build_state

ROOT = Path(__file__).resolve().parents[1]
CURSES = ROOT / "gibson" / "apps" / "master_console_curses.py"


def _state(tmp_path: Path):
    args = Namespace(
        gacf=None,
        sim_root=str(tmp_path / "sim"),
        secure=False,
        vuln=True,
        split_console=False,
        logon_panel=False,
        host=None,
        port=None,
        ftp_port=None,
        uss_port=None,
        tn3270_port=None,
        rest_port=None,
        db2_tcp_port=None,
        db2_ws_port=None,
        no_web_terminal=True,
        with_web_terminal=False,
        web_terminal_port=None,
    )
    return build_state(args)


def test_layout_windows_do_not_overlap():
    layout = calculate_layout(40, 120)
    assert set(layout) == {"header", "log", "status", "command"}
    assert layout["header"].bottom <= layout["log"].y
    assert layout["header"].bottom <= layout["status"].y
    assert layout["log"].right == layout["status"].x
    assert layout["log"].bottom <= layout["command"].y
    assert layout["status"].bottom <= layout["command"].y
    assert layout["command"].bottom == 40


def test_small_layout_returns_empty():
    assert calculate_layout(MIN_ROWS - 1, MIN_COLS) == {}
    assert calculate_layout(MIN_ROWS, MIN_COLS - 1) == {}


def test_text_clipping_and_wrapping_stay_inside_width():
    line = "ICH408I " + "SYS1.PARMLIB " * 20
    wrapped = wrap_text(line, 32)
    assert wrapped
    assert all(len(part) <= 32 for part in wrapped)
    assert len(clip_text(line, 16)) <= 16


def test_format_bar_clips_percent():
    assert "100%" in format_bar("CPU", 155, 30)
    assert "  0%" in format_bar("CPU", -5, 30)


def test_binary_animation_moves_when_active_and_fits():
    anim = BinaryAnimator(seed=1)
    idle = anim.frame(24, 3, active=False)
    active = anim.frame(24, 3, active=True)
    assert idle != active
    assert len(active) == 3
    assert all(len(row) <= 24 for row in active)


def test_master_console_core_commands(tmp_path):
    controller = MasterConsoleController(_state(tmp_path))
    assert "GIBSON MASTER CONSOLE COMMANDS" in controller.execute("HELP").text
    assert "IPLINFO DISPLAY" in controller.execute("D IPLINFO").text
    assert "ACTIVITY DISPLAY" in controller.execute("D A,L").text
    assert "DASD ACTIVITY" in controller.execute("DASD").text
    assert "SECURITY RARE SUMMARY" in controller.execute("D SECURITY,RARE").text


def test_unknown_command_returns_text_no_traceback(tmp_path):
    controller = MasterConsoleController(_state(tmp_path))
    text = controller.execute("THISCOMMANDDOESNOTEXIST").text
    assert "Traceback" not in text
    assert text.strip()


def test_curses_renderer_is_event_driven_not_constant_full_redraw():
    text = CURSES.read_text()
    assert "time.sleep(" not in text
    assert "self._draw(stdscr, layout, active)" not in text
    assert "_refresh_dirty_panes" in text
    assert "_dirty_log" in text
    assert "_dirty_command" in text
    assert "_maybe_step_animation" in text


def test_curses_renderer_does_not_erase_screen_every_loop():
    text = CURSES.read_text()
    loop_body = text[text.index("    def _main") : text.index("    def _layout_signature")]
    assert "stdscr.erase()" not in loop_body
    assert "curses.doupdate()" not in loop_body
