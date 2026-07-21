import subprocess
import sys
from pathlib import Path

import pytest

from gibson.cli import build_state
from gibson.core.security_mode import SECURE, VULN
from gibson.apps.tso import TsoCommandProcessor


class Args:
    secure=False; vuln=False; gacf=None; sim_root=None; host=None; port=None; ftp_port=None; uss_port=None; tn3270_port=None; rest_port=None; db2_tcp_port=None; db2_ws_port=None


def test_cli_build_state_secure_and_vuln_modes():
    a=Args(); a.secure=True
    st=build_state(a)
    assert st.config.security_mode == SECURE
    assert st.config.port == 1023
    assert st.config.dashboard_port == 8443
    b=Args(); b.vuln=True
    st2=build_state(b)
    assert st2.config.security_mode == VULN
    assert st2.config.port == 2023


def test_cli_modes_conflict_fails_closed():
    a=Args(); a.secure=True; a.vuln=True
    with pytest.raises(SystemExit):
        build_state(a)


def test_gibsonctl_secure_vuln_are_advertised_and_forwarded():
    root = Path(__file__).resolve().parents[1]
    help_out = subprocess.check_output(['bash', 'gibsonctl.sh', '--help'], cwd=root, text=True)
    assert 'start --secure' in help_out
    assert 'start --vuln' in help_out
    secure = subprocess.check_output(['bash', 'gibsonctl.sh', 'start', '--secure', '--dry-run'], cwd=root, text=True)
    assert '--secure' in secure
    assert 'DRY-RUN' in secure
    vuln = subprocess.check_output(['bash', 'gibsonctl.sh', 'start', '--vuln', '--dry-run'], cwd=root, text=True)
    assert '--vuln' in vuln
    conflict = subprocess.run(['bash', 'gibsonctl.sh', 'start', '--secure', '--vuln', '--dry-run'], cwd=root, text=True, capture_output=True)
    assert conflict.returncode == 2
    assert 'mutually exclusive' in conflict.stdout


def test_rexx_invocation_executes_safe_execio_and_say():
    a=Args(); st=build_state(a)
    st.datasets.allocate('IBMUSER', 'IBMUSER.REXX.TEST(HELLO)', org='PO')
    st.datasets.write('IBMUSER', 'IBMUSER.REXX.TEST(HELLO)', "/* REXX */\nPARSE ARG TARGET\nSAY 'HELLO' SYSVAR('SYSUID')\nLINES.1='ALPHA'\nLINES.0=1\nEXECIO * DISKW TARGET (STEM LINES.\n")
    out=TsoCommandProcessor(st,'IBMUSER').run("EX 'IBMUSER.REXX.TEST(HELLO)' 'IBMUSER.REXX.OUT'")
    assert 'HELLO IBMUSER' in out
    assert st.datasets.read('IBMUSER','IBMUSER.REXX.OUT').strip() == 'ALPHA'


def test_jcl_submit_iefbr14_and_cobol_compile_simulation_visible_in_spool():
    a=Args(); st=build_state(a)
    jcl="""//COBOLJ JOB (ACCT),'COBOL',CLASS=A,MSGCLASS=A
//COBC    EXEC PGM=IGYCRCTL
//SYSIN   DD *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO FROM COBOL'.
/*
//BR14    EXEC PGM=IEFBR14
"""
    st.datasets.allocate('IBMUSER','IBMUSER.JCL.TEST(COBOLJ)', org='PO')
    st.datasets.write('IBMUSER','IBMUSER.JCL.TEST(COBOLJ)', jcl)
    out=TsoCommandProcessor(st,'IBMUSER').run("SUBMIT 'IBMUSER.JCL.TEST(COBOLJ)'")
    assert 'SUBMITTED' in out
    jobs=st.jes.list_jobs('IBMUSER')
    job=jobs[-1]
    spool='\n'.join(sf.content for sf in job.spool)
    assert 'IGYCRCTL COBOL COMPILER SIMULATION' in spool
    assert 'HELLO FROM COBOL' in spool
    assert 'IEFBR14' in spool
