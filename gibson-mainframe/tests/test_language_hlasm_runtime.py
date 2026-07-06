from gibson.languages.hlasm import HlasmSimulator


def test_hlasm_parse_and_simulate_basic_program():
    src = """
TEST     CSECT
         USING TEST,15
START    LA 1,5
         ST 1,VALUE
         CLI VALUE,5
         BE DONE
         LA 2,99
DONE     END
VALUE    DS F
"""
    res = HlasmSimulator().assemble(src)
    assert res.rc == 0
    assert "SYMBOL TABLE" in res.listing
    assert "START" in res.symbols
    assert res.registers[1] == 5
