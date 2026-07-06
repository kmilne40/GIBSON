from gibson.core.state import GibsonState
from gibson.core.smf.records.type119 import tcpip
from gibson.core.smf.writer import get_smf_writer


def test_tn3270_or_ftp_network_record_has_forensic_fields():
    st = GibsonState.create()
    tcpip(st, userid="IBMUSER", application="FTP", remote_ip="198.51.100.66", remote_port=21, local_port=2023, bytes_in=120, bytes_out=400, correlation_id="NET1")
    rows = [r.to_flat_fields() for r in get_smf_writer(st).query(record_type=119)]
    assert rows[0]["APPLICATION"] == "FTP"
    assert rows[0]["REMOTE_IP"] == "198.51.100.66"
    assert rows[0]["CORRELATION_ID"] == "NET1"
