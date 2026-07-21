from gibson.core.state import GibsonState
from gibson.core.smf.records.type123 import api_request
from gibson.core.smf.records.type100_101_102 import db2_accounting
from gibson.core.smf.formatters import format_timeline


def test_api_sqli_forensic_timeline_links_smf123_and_db2():
    st = GibsonState.create()
    api_request(st, userid="WEBUSER", api_name="FIBS", method="GET", uri="/api/v1/accounts?id=1 OR 1=1", status_code=200, result="WARNING", correlation_id="SQLI1", detail="SQL INJECTION")
    db2_accounting(st, userid="WEBUSER", sql_verb="SELECT", table_name="ACCOUNTS", rows_returned=8, suspicious_payload_class="SQLI", correlation_id="SQLI1", detail="UNSAFE QUERY")
    out = format_timeline(st, "SQLI1")
    assert "API_PROVIDER_REQUEST" in out
    assert "DB2_ACCOUNTING" in out
