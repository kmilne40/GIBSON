from gibson.core.state import GibsonState
from gibson.core.smf.records.type92 import uss_file
from gibson.core.smf.writer import get_smf_writer


def test_uss_file_record():
    st = GibsonState.create()
    uss_file(st, userid="IBMUSER", path="/u/ibmuser/tool.py", operation="EXEC", program="PYTHON", bytes_count=512, correlation_id="USS1")
    row = get_smf_writer(st).query(record_type=92)[0].to_flat_fields()
    assert row["PATH"] == "/u/ibmuser/tool.py"
    assert row["OPERATION"] == "EXEC"
