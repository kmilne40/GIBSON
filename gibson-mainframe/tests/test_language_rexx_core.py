from gibson.languages.rexx import RexxInterpreter


def test_rexx_select_parse_functions_and_upper():
    src = """
PARSE ARG A B
UPPER A
SELECT
 WHEN A = 'HELLO' THEN SAY LEFT(A,3) || '-' || WORD('ONE TWO',2)
 OTHERWISE SAY 'BAD'
END
PARSE VALUE 'X Y' WITH C D
SAY C D
"""
    out = RexxInterpreter().run(src, "hello there")
    assert "HEL-TWO" in out
    assert "X Y" in out


def test_rexx_execio_round_trip():
    store = {"IN.DATA": "A\nB\n"}
    def read(dsn): return store[dsn.upper()]
    def write(dsn, text): store[dsn.upper()] = text
    src = """
EXECIO * DISKR 'IN.DATA' (STEM IN. FINIS
SAY IN.0
EXECIO * DISKW 'OUT.DATA' (STEM IN. FINIS
"""
    out = RexxInterpreter(dataset_read=read, dataset_write=write).run(src)
    assert "2" in out
    assert store["OUT.DATA"] == "A\nB"
