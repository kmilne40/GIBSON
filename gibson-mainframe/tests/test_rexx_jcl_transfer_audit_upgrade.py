from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path

from gibson.apps.banking_lab import get_banking_lab
from gibson.apps.ispf import IspfApp
from gibson.apps.sdsf import SdsfApp
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.healthcheck import get_healthchecker
from gibson.core.passticket import get_passticket_service
from gibson.core.transfers import get_transfer_manager
from gibson.render.input import InputResult
from gibson.services.rest_gateway import serve_rest
from gibson.services.telnet_server import GibsonTelnetSession

from tests.test_ftp_jes_rexx_rest_lab_upgrade import make_state, _free_port
from tests.test_banking_tn3270_web_lab import _wait_for_rest


class DummyConn:
    def sendall(self, _data):
        return None


def _post_json(port: int, path: str, payload: dict) -> tuple[int, dict | str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", errors="ignore")
    conn.close()
    try:
        return resp.status, json.loads(body)
    except Exception:
        return resp.status, body


def test_rexx_extended_control_flow_and_execio_roundtrip(tmp_path: Path):
    st = make_state(tmp_path)
    script = """/* REXX */
PARSE ARG TARGET
COUNT = 2 + 3
IF COUNT = 5 THEN SAY 'COUNT OK'
LINES.0 = 2
LINES.1 = 'ALPHA'
LINES.2 = 'BETA'
EXECIO * DISKW TARGET (STEM LINES.
READ.0 = 0
EXECIO * DISKR TARGET (STEM READ.
DO I = 1 TO READ.0
  SAY READ.I
END
EXIT
"""
    st.datasets.allocate("IBMUSER", "IBMUSER.PDS.CODE(EXTREXX)", org="PO")
    st.datasets.write("IBMUSER", "IBMUSER.PDS.CODE(EXTREXX)", script)
    out = TsoCommandProcessor(st, "IBMUSER").run("EX 'IBMUSER.PDS.CODE(EXTREXX)' 'IBMUSER.TEST.OUT'")
    assert "COUNT OK" in out
    assert "ALPHA" in out and "BETA" in out
    assert st.datasets.read("IBMUSER", "IBMUSER.TEST.OUT") == "ALPHA\nBETA"


def test_jcl_extended_proc_if_and_output_dataset(tmp_path: Path):
    st = make_state(tmp_path)
    jcl = """//PROCJOB  JOB (ACCT),'PROC',CLASS=A,MSGCLASS=A,USER=IBMUSER
//COPYPROC PROC OUT=IBMUSER.PROC.OUT
//PSTEP    EXEC PGM=IEBGENER
//SYSUT1   DD *
PROC LINE 1
PROC LINE 2
/*
//SYSUT2   DD DSN=&OUT,DISP=(NEW,CATLG)
//         PEND
//RUNPROC  EXEC COPYPROC,OUT=IBMUSER.PROC.OUT
// IF (RUNPROC.RC = 0) THEN
//BR14     EXEC PGM=IEFBR14
// ENDIF
"""
    job = st.jes.submit(jcl, "IBMUSER", runner=TsoCommandProcessor(st, "IBMUSER").run)
    assert job.rc == 0
    assert st.datasets.read("IBMUSER", "IBMUSER.PROC.OUT") == "PROC LINE 1\nPROC LINE 2"
    sysmsg = next(sf.content for sf in job.spool if sf.ddname == "JESYSMSG")
    assert "IEFBR14" in sysmsg or "RUNPROC" in sysmsg


def test_transmit_and_receive_restore_dataset(tmp_path: Path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "IBMUSER")
    st.datasets.allocate("IBMUSER", "IBMUSER.SECRET.TEXT", org="PS")
    st.datasets.write("IBMUSER", "IBMUSER.SECRET.TEXT", "TOP SECRET")
    out = tso.run("TRANSMIT SARCHER DA(IBMUSER.SECRET.TEXT) OUTDSN(IBMUSER.XMIT.SECRET)")
    assert "TRANSMIT CREATED" in out
    recv = TsoCommandProcessor(st, "SARCHER").run("RECEIVE INDSN('IBMUSER.XMIT.SECRET') DA(SARCHER.RESTORED.TEXT)")
    assert "RECEIVE COMPLETE" in recv
    assert st.datasets.read("SARCHER", "SARCHER.RESTORED.TEXT") == "TOP SECRET"


def test_rest_indfile_upload_and_download_roundtrip(tmp_path: Path):
    st = make_state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    _wait_for_rest(st)

    status, body = _post_json(st.config.rest_port, "/indfile/upload", {"user": "IBMUSER", "target": "IBMUSER.UPLOAD.PS", "content": "HELLO IND$FILE"})
    assert status == 200
    assert body["target"] == "IBMUSER.UPLOAD.PS"
    assert st.datasets.read("IBMUSER", "IBMUSER.UPLOAD.PS") == "HELLO IND$FILE"

    conn = http.client.HTTPConnection("127.0.0.1", st.config.rest_port, timeout=2)
    conn.request("GET", "/indfile/download?user=IBMUSER&dataset=IBMUSER.UPLOAD.PS")
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="ignore")
    conn.close()
    assert resp.status == 200
    assert data == "HELLO IND$FILE"
    assert any(evt["TARGET"] == "IBMUSER.UPLOAD.PS" and evt["DIRECTION"] == "GET" for evt in st.indfile_history)


def test_console_security_audit_and_secevents_show_recent_logons(tmp_path: Path):
    st = make_state(tmp_path)
    st.config.console_security_audit = True
    lab = get_banking_lab(st)
    snap = lab.login("sec1", "IBMUSER", "SYS1")
    assert snap["authenticated"] is True
    console = st.drain_console_events()
    assert any("ICH70001I IBMUSER LAST ACCESS AT" in text and "LOGON TO WEBBANK RESULT=SUCCESS" in text for _sev, text in console)
    out = TsoCommandProcessor(st, "IBMUSER").run("SECEVENTS")
    assert "TIME     USERID" in out and "IBMUSER" in out and "LOGON" in out


def test_ispf_global_jump_routes_to_expected_panels(tmp_path: Path):
    st = make_state(tmp_path)
    app = IspfApp(st, "IBMUSER", lambda _cmd: "")
    calls: list[str] = []
    app.panel_6 = lambda *_a, **_k: calls.append("6")
    app.panel_34 = lambda *_a, **_k: calls.append("3.4")
    app.panel_management = lambda *_a, **_k: calls.append("M.5")
    dummy = object()
    send = lambda _text: None
    assert app._handle_jump("=6", dummy, send) is True
    assert app._handle_jump("=3.4", dummy, send) is True
    assert app._handle_jump("=M.5", dummy, send) is True
    assert calls == ["6", "3.4", "M.5"]


def test_sdsf_apf_popup_blank_command_line_accepts_free_form_setprog(tmp_path: Path):
    st = make_state(tmp_path)
    session = GibsonTelnetSession(st, DummyConn(), ("127.0.0.1", 23))
    session.userid = "IBMUSER"
    transcript: list[str] = []
    session.send = lambda text: transcript.append(text)

    class Driver:
        def __init__(self):
            self.responses = iter([
                InputResult("/ 1"),
                InputResult("SETPROG APF,ADD,DSNAME=SYS1.TESTAPF,VOLUME=RES001"),
                InputResult("", "F3"),
                InputResult("", "F3"),
                InputResult("", "F3"),
            ])
        def read_line_at(self, _row, _col, hidden: bool = False):
            return next(self.responses, InputResult("", "EOF"))

    session.input = Driver()
    session.sdsf_loop("APF")
    assert "SYS1.TESTAPF" in st.apf_libraries
    combined = "\n".join(transcript)
    assert "SDSF APF POP-UP" in combined
    assert "COMMAND ===> " in combined
    assert "SETPROG APF,ADD" not in combined


def test_healthchecker_ck_panel_and_commands(tmp_path: Path):
    st = make_state(tmp_path)
    hc = get_healthchecker(st)
    rows = hc.rows()
    assert any(row["CHECK"] == "GIBAPF01" for row in rows)
    msg = hc.command("DISPLAY GIBAUD01")
    assert "GIBAUD01" in msg and "FINDING=" in msg
    panel = SdsfApp(st, "IBMUSER").render_panel("CK", 0, "")
    assert "HEALTH CHECKS" in panel
    assert "GIBAPF01" in panel


def test_tso_passticket_logon_helper_accepts_new_ticket(tmp_path: Path):
    st = make_state(tmp_path)
    svc = get_passticket_service(st)
    generated = svc.generate("IBMUSER", "TSO", "IBMUSER")
    assert generated["ok"] is True
    ticket = generated["ticket"]
    session = GibsonTelnetSession(st, DummyConn(), ("127.0.0.1", 23))
    ok, method = session._check_tso_credential("IBMUSER", f"PTKT({ticket})")
    assert ok is True
    assert method == "PASSTICKET"
    assert any(evt.component == "SMF80" and evt.userid == "IBMUSER" and "PASSTICKET" in evt.result for evt in st.audit.events)
