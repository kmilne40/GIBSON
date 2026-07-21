"""End-to-end cicspwn lab: the simulated target responses + blue-team detection.

Exercises the engine the way the real cicspwn tool would drive it over s3270:
region fingerprint (ASSIGN/INQUIRE SYSTEM), CEDA-COPY RACF bypass, file reads,
the SPOOL/JCL code-execution path, the simulated post-exploitation shell, the
runtime password-logon toggle, and the detection timeline.
"""
from __future__ import annotations

from gibson.core.state import GibsonState
from gibson.apps.cics import CicsSimulator
from gibson.apps.cics3270 import Cics3270Session
from gibson.tools.cics_shell import run_cics_shell


def _cics():
    st = GibsonState.create(); st.racf.load()
    c = CicsSimulator(st, "IBMUSER"); c.execute("CESN")
    return st, c


def test_region_fingerprint_assign_inquire():
    st, c = _cics()
    a = c.execute("CECI ASSIGN APPLID(&A) SYSID(&S) USERID(&U) NETNAME(&N) CICSTSLEVEL(&L)")
    for v in ("CICS", "GIB1", "IBMUSER", "LU320", "0720"):
        assert v in a
    i = c.execute("CECI INQUIRE SYSTEM CICSTSLEVEL(&L) APPLID(&A) DFLTUSER(&D) SECURITYMGR(&M)")
    assert "CICSUSER" in i and "EXTERNAL" in i


def test_ceda_copy_racf_bypass():
    st, c = _cics()
    out = c.execute("CEDA COPY TRANS(CEMT) GROUP(DFHTERM) AS(CSPS) TO(GIBSON)")
    assert "COPIED TO CSPS" in out
    # the unprotected alias runs CEMT
    aliased = c.execute("CSPS I FILE")
    assert "FILEA" in aliased or "File(" in aliased
    # alias is marked unprotected in the region
    assert c.region.transactions["CSPS"].attrs["PROTECTED"] == "NO"


def test_file_read_browse_write():
    st, c = _cics()
    r = c.execute("CECI READ FILE(FILEA) RIDFLD(000222)")
    assert "GOODMAN" in r
    b = c.execute("CECI STARTBR FILE(FILEA)")
    assert "BORMAN" in b and "RETURNED 5 RECORD" in b
    c.execute("CECI WRITE FILE(FILEA) FROM('000999 ADDED BY LAB')")
    b2 = c.execute("CECI STARTBR FILE(FILEA)")
    assert "ADDED BY LAB" in b2 and "RETURNED 6 RECORD" in b2


def test_spool_code_execution_and_shell():
    st, c = _cics()
    assert "NORMAL" in c.execute("CECI SPOOLOPEN OUTPUT NODE(LOCAL) USERID(INTRDR)")
    c.execute("CECI SPOOLWRITE TOKEN(X) FROM('//GIBPWN JOB (ACCT),CLASS=A')")
    c.execute("CECI SPOOLWRITE TOKEN(X) FROM('//S1 EXEC PGM=IRXJCL,PARM=REVSHELL')")
    close = c.execute("CECI SPOOLCLOSE TOKEN(X)")
    assert "SUBMITTED TO INTERNAL READER" in close and "simulated shell registered" in close
    assert getattr(st, "cics_pwn_shells", [])
    sh = run_cics_shell(st, ["id"], None, "/")
    assert "CICS region authority" in sh and "SIMULATED" in sh.upper()
    closed = run_cics_shell(st, ["exit"], None, "/")
    assert "closed" in closed.lower()


def test_spool_denied_when_spool_off():
    st, c = _cics()
    c.region.security_options["SPOOL"] = "NO"
    out = c.execute("CECI SPOOLOPEN OUTPUT")
    assert "NOTAUTH" in out and "SPOOL=NO" in out


def test_password_logon_toggle():
    st, c = _cics()
    assert "CURRENTLY OFF" in c.execute("CICS AUTH STATUS")
    assert "NOW ON" in c.execute("CICS AUTH ON")
    assert st.config.realistic_cics_auth is True
    # 3270 session presents a sign-on screen with a Password field
    cs = Cics3270Session(st, peer_addr="203.0.113.9")
    scr = cs.initial_screen()
    txt = scr.to_3270().decode("cp037", "ignore")
    assert "Password" in txt
    assert any(f.name == "PASSWORD" and not f.protected for f in scr.fields)
    assert "NOW OFF" in c.execute("CICS AUTH OFF")
    assert st.config.realistic_cics_auth is False


def test_blue_team_detection_timeline():
    st, c = _cics()
    # run a small attack chain
    c.execute("CECI ASSIGN APPLID(&A)")
    c.execute("CECI INQUIRE SYSTEM CICSTSLEVEL(&L)")
    c.execute("CEDA COPY TRANS(CEMT) GROUP(DFHTERM) AS(CSPS) TO(GIBSON)")
    c.execute("CSPS I FILE")
    c.execute("CECI SPOOLOPEN OUTPUT")
    c.execute("CECI SPOOLWRITE TOKEN(X) FROM('//P JOB')")
    c.execute("CECI SPOOLCLOSE TOKEN(X)")
    det = c.execute("PWNSCAN")
    assert "RACF BYPASS" in det and "CODE EXECUTION" in det
    assert "RECON" in det  # ASSIGN/INQUIRE fingerprint counted


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
    print("all cicspwn lab tests passed")
