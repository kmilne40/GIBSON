from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/'f', commands_dir=tmp_path/'f'/'commands', gacf_path=tmp_path/'GACF.DB')
    cfg.ensure(); cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_iefbr14_idcams_iebgener_integration(tmp_path):
    st = make_state(tmp_path)
    jcl = """//JCLJOB JOB (ACCT),'JCL',CLASS=A,MSGCLASS=A
//BR14 EXEC PGM=IEFBR14
//NEWDD DD DSN=IBMUSER.JCL.CREATED,DISP=(NEW,CATLG)
//AMS EXEC PGM=IDCAMS
//SYSIN DD *
 DEFINE CLUSTER(NAME(IBMUSER.JCL.IDCAMS))
 LISTCAT
/*
//GEN EXEC PGM=IEBGENER
//SYSUT1 DD *
LINE1
LINE2
/*
//SYSUT2 DD DSN=IBMUSER.JCL.COPY,DISP=(NEW,CATLG)
//SYSPRINT DD SYSOUT=*
"""
    st.datasets.write('IBMUSER','IBMUSER.CNTL.JCL',jcl)
    out = TsoCommandProcessor(st,'IBMUSER').run("SUBMIT 'IBMUSER.CNTL.JCL'")
    assert 'SUBMITTED' in out
    spool='\n'.join(s.content for s in st.jes.list_jobs('IBMUSER')[-1].spool)
    assert 'IBMUSER.JCL.CREATED CATALOGED' in spool
    assert 'IDC0508I DATA SET IBMUSER.JCL.IDCAMS DEFINED' in spool
    assert 'IEB144I THERE ARE 00000002 RECORDS' in spool
    assert st.datasets.read('IBMUSER','IBMUSER.JCL.COPY').splitlines() == ['LINE1','LINE2']
