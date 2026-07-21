from __future__ import annotations

from pathlib import Path

from gibson.apps.ispf import IspfApp
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render.input import InputResult


class ScriptedDriver:
    def __init__(self, *items: str):
        self.items = list(items)

    def _next(self) -> InputResult:
        if self.items:
            return InputResult(self.items.pop(0))
        return InputResult("F3")

    def read_line_at(self, row: int, col: int, hidden: bool = False) -> InputResult:
        return self._next()

    def read_line(self, prompt: str = "", hidden: bool = False, mask: bool = False) -> InputResult:
        return self._next()


def _state(tmp_path: Path) -> GibsonState:
    sim_root = tmp_path / "mfsim"
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=0,
        uss_port=0,
        ftp_port=0,
        rest_port=0,
        db2_tcp_port=0,
        db2_ws_port=0,
        dashboard_port=0,
        sim_root=sim_root,
        files_root=sim_root / "f",
        commands_dir=sim_root / "f" / "commands",
        gacf_path=sim_root / "GACF.DB",
    )
    return GibsonState.create(cfg)


def _app(st: GibsonState) -> IspfApp:
    return IspfApp(st, "IBMUSER", lambda c: TsoCommandProcessor(st, "IBMUSER").run(c))


def test_db2i_menu_option_5_opens_commands_panel(tmp_path):
    st = _state(tmp_path)
    app = _app(st)
    out: list[str] = []
    app.panel_db2i(ScriptedDriver("5", "DISPLAY GROUP", "", "F3", "X"), out.append)
    joined = "".join(out)
    assert "DB2 COMMANDS" in joined
    assert "DISPLAY GROUP REPORT" in joined
    assert "INVALID DB2 OPTION" not in joined
    assert app.message != "INVALID DB2 OPTION"


def test_db2i_menu_option_1_opens_spufi_and_executes_sql(tmp_path):
    st = _state(tmp_path)
    app = _app(st)
    out: list[str] = []
    app.panel_db2i(ScriptedDriver("1", "SQLIN", "", "NO", "", "X"), out.append)
    joined = "".join(out)
    assert "SPUFI" in joined
    assert "CURRENT SERVER" in joined
    assert "GIBSONDB2" in joined
    assert "INVALID DB2 OPTION" not in joined


def test_db2i_direct_initial_option_1_no_unbound_choice(tmp_path):
    st = _state(tmp_path)
    app = _app(st)
    out: list[str] = []
    app.panel_db2i(ScriptedDriver("SQLIN", "", "NO", ""), out.append, initial="1")
    joined = "".join(out)
    assert "CURRENT SERVER" in joined
    assert "GIBSONDB2" in joined
    assert app.message != "INVALID DB2 OPTION"


def test_management_menu_exit_does_not_report_invalid_option(tmp_path):
    st = _state(tmp_path)
    app = _app(st)
    out: list[str] = []
    app.panel_management(ScriptedDriver("X"), out.append)
    assert "Management Option Menu" in "".join(out)
    assert app.message != "INVALID MANAGEMENT OPTION"
