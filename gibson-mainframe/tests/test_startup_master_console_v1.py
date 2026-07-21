from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTL = ROOT / "gibsonctl.sh"
CURSES = ROOT / "gibson" / "apps" / "master_console_curses.py"


def test_gibsonctl_start_master_flags_are_supported():
    text = CTL.read_text()
    assert "--no-master) MASTER_LAUNCH=\"none\"" in text
    assert "--master-plain) MASTER_LAUNCH=\"plain\"" in text
    assert "--master-curses) MASTER_LAUNCH=\"curses\"" in text
    assert "launch_master_after_start" in text


def test_start_uses_background_services_before_console():
    text = CTL.read_text()
    assert "setsid \"$PYTHON_BIN\" -m \"$MODULE_CMD\"" in text
    assert "--pid-file \"$MAIN_PID\"" in text
    assert "GIBSON services will continue running after the console exits" in text


def test_non_interactive_start_suppresses_curses():
    text = CTL.read_text()
    assert "is_interactive_terminal" in text
    assert "GIBMCS001W Interactive terminal unavailable" in text
    assert "TERM" in text and "dumb" in text


def test_console_title_and_colour_roles():
    text = CURSES.read_text()
    assert "GIBSON MASTER CONSOLE" in text
    assert '"command"' in text
    assert '"binary_yellow"' in text
    assert '"binary_white"' in text
    assert "curses.COLOR_RED" in text
    assert "curses.COLOR_GREEN" in text


def test_command_text_uses_command_colour_role():
    text = CURSES.read_text()
    assert 'self.colors.get("command"' in text


def test_binary_colour_changes_during_processing():
    text = CURSES.read_text()
    assert 'binary_white' in text
    assert 'binary_yellow' in text
    assert 'if active and (int(time.time() * 4) % 2 == 0)' in text
