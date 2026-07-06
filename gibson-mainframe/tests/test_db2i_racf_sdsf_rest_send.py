from __future__ import annotations

import http.client
import socket
import threading
import time
from pathlib import Path

from gibson.apps.ispf import IspfApp
from gibson.apps.sdsf import SdsfApp
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.render import colors
from gibson.services.db2_server import serve_db2ws
from gibson.services.rest_gateway import serve_rest
from gibson.services.telnet_server import _colourize_vtam_screen


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _state(tmp_path: Path, *, rest_port: int | None = None, db2_ws_port: int | None = None) -> GibsonState:
    sim_root = tmp_path / "mfsim"
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=_free_port(),
        uss_port=_free_port(),
        ftp_port=_free_port(),
        rest_port=rest_port or _free_port(),
        db2_tcp_port=_free_port(),
        db2_ws_port=db2_ws_port or _free_port(),
        dashboard_port=_free_port(),
        sim_root=sim_root,
        files_root=sim_root / "f",
        commands_dir=sim_root / "f" / "commands",
        gacf_path=sim_root / "GACF.DB",
    )
    return GibsonState.create(cfg)


def test_send_now_delivers_to_connected_user(tmp_path):
    st = _state(tmp_path)
    messages: list[str] = []
    st.sessions.add("IBMUSER", "127.0.0.1", notifier=messages.append)
    proc = TsoCommandProcessor(st, "IBMUSER")
    out = proc.run("SEND 'HELLO NOW' USER(IBMUSER) NOW")
    assert "Message sent immediately to IBMUSER." in out
    assert messages and "HELLO NOW" in messages[-1]


def test_vtam_gibson_word_is_blue():
    screen = "***  GIBSON PRODUCTION LPAR  ***\nLOGON using L TSO\n"
    out = _colourize_vtam_screen(screen)
    assert out.startswith(f"{colors.LIGHT_BLUE}***  GIBSON PRODUCTION LPAR  ***")


def test_ispf_primary_menu_has_db2_and_management(tmp_path):
    st = _state(tmp_path)
    app = IspfApp(st, "IBMUSER", lambda c: TsoCommandProcessor(st, "IBMUSER").run(c))
    menu = app.primary_menu()
    assert "DB2" in menu and "12" in menu
    assert "Management" in menu and "M" in menu


def test_db2i_spufi_executes_and_can_write_output_dataset(tmp_path):
    st = _state(tmp_path)
    app = IspfApp(st, "IBMUSER", lambda c: TsoCommandProcessor(st, "IBMUSER").run(c))
    out = app.run_db2i_spufi("SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1;", output_ds="DB2OUT")
    assert "CURRENT SERVER" in out
    saved = st.datasets.read("IBMUSER", "IBMUSER.DB2OUT")
    assert "GIBSONDB2" in saved


def test_sdsf_smf80_panel_shows_security_records(tmp_path):
    st = _state(tmp_path)
    st.audit.record_smf80("IBMUSER", "USER CREATE", "USER=ALICE", extra={"GROUP": "SYS1", "CLASS": "USER", "RESOURCE": "ALICE", "PROFILE": "ALICE"})
    panel = SdsfApp(st, "IBMUSER").build_panel("SMF80")
    assert panel.title == "SMF TYPE 80 SECURITY LOG"
    assert any(row.cells.get("EVENT", "") == "USER CREATE" for row in panel.rows)
    assert any(row.cells.get("CLASS", "") == "USER" for row in panel.rows)


def test_rest_gateway_fallback_starts_and_answers(tmp_path):
    st = _state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    deadline = time.time() + 4
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", st.config.rest_port, timeout=0.5)
            conn.request("POST", "/query", body='{"user":"IBMUSER","password":"SYS1","sql":"SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1;"}', headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()
            assert resp.status == 200
            assert "GIBSONDB2" in data
            return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("REST gateway did not start listening")


def test_db2_websocket_service_starts_listening(tmp_path):
    st = _state(tmp_path, db2_ws_port=_free_port())
    svc = serve_db2ws(st)
    deadline = time.time() + 4
    try:
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", st.config.db2_ws_port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.1)
        raise AssertionError("DB2 WebSocket listener did not start")
    finally:
        try:
            svc.shutdown()
        except Exception:
            pass
