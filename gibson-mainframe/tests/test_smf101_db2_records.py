from gibson.core.state import GibsonState
from gibson.core.smf.records.type100_101_102 import db2_accounting, db2_audit
from gibson.core.smf.writer import get_smf_writer


def test_db2_accounting_and_audit_records():
    st = GibsonState.create()
    db2_accounting(st, userid="IBMUSER", sql_verb="SELECT", table_name="CARDS", rows_returned=10, correlation_id="DB2C")
    db2_audit(st, userid="IBMUSER", sql_verb="SELECT", table_name="CARDS", suspicious_payload_class="SQLI", correlation_id="DB2C")
    assert get_smf_writer(st).query(record_type=101)
    assert get_smf_writer(st).query(record_type=102)
