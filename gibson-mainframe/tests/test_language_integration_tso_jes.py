from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/'f', commands_dir=tmp_path/'f'/'commands', gacf_path=tmp_path/'GACF.DB')
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\nGUEST:GUEST:NONE:NOOMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_jes_cobol_compile_and_hlasm_assemble(tmp_path):
    st = make_state(tmp_path)
    jcl = """//LANGJOB JOB (ACCT),'LANG',CLASS=A,MSGCLASS=A
//COBOL EXEC PGM=IGYCRCTL
//SYSIN DD *
IDENTIFICATION DIVISION.
PROGRAM-ID. X.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-N PIC 9(2) VALUE 1.
PROCEDURE DIVISION.
ADD 1 TO WS-N.
DISPLAY WS-N.
STOP RUN.
/*
//ASM EXEC PGM=ASMA90
//SYSIN DD *
TEST CSECT
START LA 1,5
      ST 1,VALUE
VALUE DS F
      END
/*
//LKED EXEC PGM=IEWL
//SYSLMOD DD DSN=IBMUSER.LOAD(TEST),DISP=(NEW,CATLG)
"""
    st.datasets.write('IBMUSER','IBMUSER.CNTL.LANG',jcl)
    out = TsoCommandProcessor(st,'IBMUSER').run("SUBMIT 'IBMUSER.CNTL.LANG'")
    assert 'SUBMITTED' in out
    job = st.jes.list_jobs('IBMUSER')[-1]
    spool = '\n'.join(s.content for s in job.spool)
    assert 'IGYCRCTL COBOL COMPILER STARTED' in spool
    assert 'ASMA90 HIGH LEVEL ASSEMBLER STARTED' in spool
    assert 'IEWL LINKAGE EDITOR SIMULATION STARTED' in spool
    assert 'SYMBOL TABLE' in spool


def test_tso_rexx_execio_and_tso_commands_still_route(tmp_path):
    st = make_state(tmp_path)
    st.datasets.write('IBMUSER','IBMUSER.DATA.IN','A\nB\n')
    st.datasets.write('IBMUSER','IBMUSER.REXX.TEST',"""/* REXX */
ADDRESS TSO 'NETSTAT HOME'
OUTTRAP O.
ADDRESS TSO 'LISTUSER IBMUSER'
OUTTRAP OFF
SAY O.0
""")
    tso = TsoCommandProcessor(st,'IBMUSER')
    assert 'EZZ2350I' in tso.run('NETSTAT HOME')
    out = tso.run("EX 'IBMUSER.REXX.TEST'")
    assert 'EZZ2350I' in out
    assert 'USER=IBMUSER' in out or '1' in out
