from __future__ import annotations

import http.client
import socket
import threading
import time
from pathlib import Path

from gibson.apps.tso import TsoCommandProcessor
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.services.ftp import GibsonFtpAdapter
from gibson.services.rest_gateway import serve_rest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def make_state(tmp_path: Path, *, rest_port: int | None = None) -> GibsonState:
    sim_root = tmp_path / "mfsim"
    cfg = GibsonConfig(
        host="127.0.0.1",
        port=_free_port(),
        uss_port=_free_port(),
        ftp_port=_free_port(),
        rest_port=rest_port or _free_port(),
        db2_tcp_port=_free_port(),
        db2_ws_port=_free_port(),
        dashboard_port=_free_port(),
        sim_root=sim_root,
        files_root=sim_root / "f",
        commands_dir=sim_root / "f" / "commands",
        gacf_path=sim_root / "GACF.DB",
    )
    cfg.ensure()
    cfg.gacf_path.write_text(
        "IBMUSER:SYS1:SPECIAL:OMVS\nSARCHER:sarchpw:NONE:OMVS\nGUEST:GUEST:NONE:OMVS\n",
        encoding="utf-8",
    )
    return GibsonState.create(cfg)


def test_state_seeds_user_training_libraries(tmp_path):
    st = make_state(tmp_path)
    assert st.datasets.read("IBMUSER", "IBMUSER.SQL.LAB(WHOADM)").startswith("SELECT USERID")
    assert "TSHOCKER" in st.datasets.read("IBMUSER", "IBMUSER.JCL.LAB(TSHOCK)")
    assert "HELLO IT IS" in st.datasets.read("IBMUSER", "IBMUSER.PDS.CODE(TIME)")


def test_rexx_lab_exec_returns_time_and_rvary_output(tmp_path):
    st = make_state(tmp_path)
    out = TsoCommandProcessor(st, "IBMUSER").run("EX 'IBMUSER.PDS.CODE(TIME)'")
    assert "HELLO IT IS" in out
    assert "RACF" in out or "RVARY" in out


def test_rexx_ushell_style_listener_starts_training_shell(tmp_path):
    st = make_state(tmp_path)
    st.datasets.write("IBMUSER", "IBMUSER.USHELL.REXX", "/* REXX */\nMATT_DAEMON:\ncall SOCKET('BIND')\n")
    out = TsoCommandProcessor(st, "IBMUSER").run("EX 'IBMUSER.USHELL.REXX' '40023'")
    assert "LISTENER SIMULATION STARTED ON PORT" in out
    port = int(out.split("PORT", 1)[1].splitlines()[0].strip())
    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
        banner = s.recv(4096).decode("utf-8", errors="ignore")
        assert "training shell" in banner.lower()
        s.sendall(b"help\n")
        time.sleep(0.1)
        data = s.recv(8192).decode("utf-8", errors="ignore")
        assert "sysinfo" in data.lower() and "racf" in data.lower()


def test_surrogat_submit_runs_job_as_target_user(tmp_path):
    st = make_state(tmp_path)
    tso = TsoCommandProcessor(st, "SARCHER")
    out = tso.run("SUBMIT 'IBMUSER.JCL.LAB(SURRJOB)'")
    assert "SUBMITTED" in out
    job = st.jes.list_jobs(owner="IBMUSER")[-1]
    assert job.owner == "IBMUSER"
    assert job.submitter == "SARCHER"
    msglog = next(sf.content for sf in job.spool if sf.ddname == "JESMSGLG")
    assert "USING SURROGAT ACCESS" in msglog


def test_ftp_sql_upload_creates_output_dataset_and_sdsf_job(tmp_path):
    st = make_state(tmp_path)
    adapter = GibsonFtpAdapter(st)
    reply = adapter.stor_sql("IBMUSER", "WHOADM.SQL", b"SELECT USERID, AUTHORITY FROM SYSIBM.SYSUSERAUTH WHERE AUTHORITY = 'SYSADM';")
    assert "JOBWHO_HAS_SYSADM.txt" in reply
    assert "DBAUSER1" in st.datasets.read("IBMUSER", "JOBWHO_HAS_SYSADM.txt")
    job = st.jes.list_jobs(owner="IBMUSER")[-1]
    assert any(sf.ddname == "SYSOUT" for sf in job.spool)


def test_ftp_jes_upload_creates_training_shell_job(tmp_path):
    st = make_state(tmp_path)
    adapter = GibsonFtpAdapter(st)
    jcl = st.datasets.read("IBMUSER", "IBMUSER.JCL.LAB(TSHOCK)")
    reply = adapter.stor_jes("IBMUSER", "TSHOCK.JCL", jcl.encode("utf-8"), tso_runner=TsoCommandProcessor(st, "IBMUSER").run)
    assert "tshocker_port=" in reply
    port = int(reply.split("tshocker_port=", 1)[1])
    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
        banner = s.recv(4096).decode("utf-8", errors="ignore")
        assert "training shell" in banner.lower()


def test_rest_gateway_serves_banking_lab_and_query_api(tmp_path):
    st = make_state(tmp_path, rest_port=_free_port())
    t = threading.Thread(target=serve_rest, args=(st,), daemon=True)
    t.start()
    deadline = time.time() + 4
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", st.config.rest_port, timeout=0.5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", errors="ignore")
            conn.close()
            assert resp.status == 200
            assert "Banking lab" in body or "banking application" in body.lower()
            assert "POST /query" in body
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise AssertionError("REST gateway did not start")

    conn = http.client.HTTPConnection("127.0.0.1", st.config.rest_port, timeout=1)
    conn.request("POST", "/query", body='{"user":"IBMUSER","password":"SYS1","sql":"SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1;"}', headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="ignore")
    conn.close()
    assert resp.status == 200
    assert "GIBSONDB2" in data

    conn = http.client.HTTPConnection("127.0.0.1", st.config.rest_port, timeout=1)
    conn.request("GET", "/bank/account?user=GUEST&id=10001")
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", errors="ignore")
    conn.close()
    assert resp.status == 200
    assert "IDOR training branch triggered" in body
