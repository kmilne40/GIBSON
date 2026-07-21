"""Workstream C - ibmmainframer.com gap-fillers.

C1: functional IDCAMS/VSAM (DEFINE CLUSTER, REPRO load, PRINT, LISTCAT) and a
    real DFSORT (reads SORTIN, applies SYSIN SORT FIELDS, writes SORTOUT).
C2: ISPF option 4 (Foreground compile-and-run) and option 5 (Batch compile
    submit) wired to the COBOL compiler / JES.
"""
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.render.screen3270 import ScreenBuffer
from gibson.net.datastream3270 import parse_3270_input_frame
from gibson.render.panels import panel_input_from_event, KEY_TO_AID
from gibson.apps.ispf3270.ispf_session import Ispf3270Session


def _state():
    st = GibsonState.create(); st.racf.load()
    return st


def _run_job(st, tp, jcl):
    st.datasets.allocate("IBMUSER", "IBMUSER.RUN.JCL", org="PS")
    st.datasets.write("IBMUSER", "IBMUSER.RUN.JCL", jcl)
    tp.run("SUBMIT 'IBMUSER.RUN.JCL'")
    job = list(st.jes.jobs.values())[-1]
    return "\n".join(s.content for s in job.spool)


def _inbound(s, key="ENTER", **fv):
    fr = bytes([KEY_TO_AID.get(key, 0x7D)]) + ScreenBuffer.encode_baddr(0)
    for n, t in fv.items():
        f = [x for x in s.fields if x.name == n][0]
        fr += bytes([0x11]) + ScreenBuffer.encode_baddr(f.address + 1) + t.encode("cp037")
    return panel_input_from_event(parse_3270_input_frame(fr, screen_registry=s))


def _W(s):
    return s.to_3270().decode("cp037", "ignore").upper()


_DEFINE_REPRO = """//VSAMJOB JOB (ACCT),'VSAM',CLASS=A,MSGCLASS=A
//STEP1 EXEC PGM=IDCAMS
//INPUT DD *
0001 ALICE
0003 CAROL
0002 BOB
/*
//SYSPRINT DD SYSOUT=*
//SYSIN DD *
  DEFINE CLUSTER (NAME(IBMUSER.CUST.KSDS) INDEXED KEYS(6 0) RECORDSIZE(80 80))
  REPRO INFILE(INPUT) OUTDATASET(IBMUSER.CUST.KSDS)
  PRINT INDATASET(IBMUSER.CUST.KSDS)
  LISTCAT
/*
"""


def _sort_job(fields, dsn):
    return f"""//SJOB JOB (ACCT),'S',CLASS=A,MSGCLASS=A
//STEP1 EXEC PGM=SORT
//SORTIN DD *
0003 CAROL
0001 ALICE
0002 BOB
/*
//SORTOUT DD DSN={dsn},DISP=(NEW,CATLG)
//SYSIN DD *
  SORT FIELDS={fields}
/*
"""


# --- C1: IDCAMS / VSAM ---------------------------------------------------
def test_c1_define_cluster_creates_vsam():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    out = _run_job(st, tp, _DEFINE_REPRO)
    assert "IBMUSER.CUST.KSDS DEFINED" in out
    assert "VSAM KSDS CLUSTER" in out
    assert [i.org for i in st.datasets.listcat("IBMUSER") if i.name == "IBMUSER.CUST.KSDS"] == ["VS"]


def test_c1_repro_loads_records():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    out = _run_job(st, tp, _DEFINE_REPRO)
    assert "NUMBER OF RECORDS PROCESSED WAS 3" in out
    assert "ALICE" in st.datasets.read("IBMUSER", "IBMUSER.CUST.KSDS")


def test_c1_print_and_listcat():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    out = _run_job(st, tp, _DEFINE_REPRO)
    assert "ALICE" in out and "RECORD 00000001" in out
    assert "CLUSTER  IBMUSER.CUST.KSDS" in out


def test_c1_idcams_delete():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    _run_job(st, tp, _DEFINE_REPRO)
    jcl = """//DELJOB JOB (ACCT),'DEL',CLASS=A,MSGCLASS=A
//STEP1 EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN DD *
  DELETE IBMUSER.CUST.KSDS
/*
"""
    out = _run_job(st, tp, jcl)
    assert "DELETED" in out
    assert all(i.name != "IBMUSER.CUST.KSDS" for i in st.datasets.listcat("IBMUSER"))


# --- C1: DFSORT ----------------------------------------------------------
def test_c1_sort_ascending():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    _run_job(st, tp, _sort_job("(1,4,CH,A)", "IBMUSER.ASC"))
    rows = [l.split()[0] for l in st.datasets.read("IBMUSER", "IBMUSER.ASC").splitlines()]
    assert rows == ["0001", "0002", "0003"]


def test_c1_sort_descending_numeric():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    _run_job(st, tp, _sort_job("(1,4,ZD,D)", "IBMUSER.DESC"))
    rows = [l.split()[0] for l in st.datasets.read("IBMUSER", "IBMUSER.DESC").splitlines()]
    assert rows == ["0003", "0002", "0001"]


def test_c1_sort_fields_copy():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    _run_job(st, tp, _sort_job("=COPY", "IBMUSER.COPY"))
    rows = [l.split()[0] for l in st.datasets.read("IBMUSER", "IBMUSER.COPY").splitlines()]
    assert rows == ["0003", "0001", "0002"]            # unchanged order


def test_c1_sort_reports_counts():
    st = _state(); tp = TsoCommandProcessor(st, "IBMUSER")
    out = _run_job(st, tp, _sort_job("(1,4,CH,A)", "IBMUSER.ASC2"))
    assert "IN: 3, OUT: 3" in out and "END OF DFSORT" in out


# --- C2: ISPF 4 / 5 ------------------------------------------------------
_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO FROM GIBSON'.
           STOP RUN.
"""


def _ispf_with_cobol():
    st = _state()
    st.datasets.allocate("IBMUSER", "IBMUSER.COBOL(HELLO)", org="PO")
    st.datasets.write("IBMUSER", "IBMUSER.COBOL(HELLO)", _COBOL)
    a = Ispf3270Session(st, userid="IBMUSER")
    return st, a, a.initial_screen()


def test_c2_opt4_foreground_compiles():
    st, a, m = _ispf_with_cobol()
    fg = a.handle(_inbound(m, OPTION="4"))
    assert "FOREGROUND LANGUAGE PROCESSING" in _W(fg)
    out = _W(a.handle(_inbound(fg, SOURCE="IBMUSER.COBOL(HELLO)")))
    assert "RC=0000" in out or "COMPILED AND RAN" in out


def test_c2_opt4_missing_source():
    st, a, m = _ispf_with_cobol()
    fg = a.handle(_inbound(m, OPTION="4"))
    out = _W(a.handle(_inbound(fg, SOURCE="IBMUSER.NOPE(X)")))
    assert "NOT FOUND" in out


def test_c2_opt5_batch_submits_job():
    st, a, m = _ispf_with_cobol()
    ba = a.handle(_inbound(m, OPTION="5"))
    assert "BATCH LANGUAGE PROCESSING" in _W(ba)
    before = len(st.jes.jobs)
    out = _W(a.handle(_inbound(ba, SOURCE="IBMUSER.COBOL(HELLO)")))
    assert "SUBMITTED" in out and "IGYCRCTL" in out
    assert len(st.jes.jobs) == before + 1


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"all {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
