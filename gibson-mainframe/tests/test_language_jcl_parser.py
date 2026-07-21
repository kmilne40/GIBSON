from gibson.languages.jcl import JclParser


def test_jcl_ast_exec_dd_and_instream():
    jcl = """//JOB1 JOB (ACCT),'X',CLASS=A
//STEP1 EXEC PGM=IEBGENER
//SYSUT1 DD *
HELLO
/*
//SYSUT2 DD DSN=IBMUSER.OUT,DISP=(NEW,CATLG)
//SYSPRINT DD SYSOUT=*
"""
    job = JclParser().parse_job(jcl)
    assert job.name == "JOB1"
    assert job.steps[0].program == "IEBGENER"
    dds = {dd.name: dd for dd in job.steps[0].dds}
    assert dds["SYSUT1"].instream == "HELLO"
    assert dds["SYSUT2"].operands["DSN"] == "IBMUSER.OUT"
