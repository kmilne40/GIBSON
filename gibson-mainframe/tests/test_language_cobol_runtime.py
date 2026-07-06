from gibson.languages.cobol import CobolSimulator


def test_cobol_working_storage_move_display_if_perform():
    src = """
IDENTIFICATION DIVISION.
PROGRAM-ID. DEMO.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-NAME PIC X(20) VALUE 'GIBSON'.
01 WS-COUNT PIC 9(4) VALUE 0.
PROCEDURE DIVISION.
MOVE 'HELLO' TO WS-NAME.
ADD 1 TO WS-COUNT.
IF WS-COUNT > 0 DISPLAY WS-NAME ELSE DISPLAY 'BAD'.
PERFORM SHOW-IT 2 TIMES.
STOP RUN.
SHOW-IT.
DISPLAY WS-COUNT.
"""
    res = CobolSimulator().compile(src)
    assert res.rc == 0
    assert "DATA MAP" in res.listing
    assert "WS-NAME" in res.listing
    assert res.display_lines[:3] == ["HELLO", "1", "1"]


def test_cobol_exec_cics_sql_recognised():
    src = """
IDENTIFICATION DIVISION.
PROGRAM-ID. X.
PROCEDURE DIVISION.
EXEC CICS SEND MAP('A') END-EXEC.
EXEC SQL SELECT * FROM SYSIBM.SYSDUMMY1 END-EXEC.
STOP RUN.
"""
    res = CobolSimulator().compile(src)
    assert "EXEC CICS" in res.listing
    assert "EXEC SQL" in res.listing
