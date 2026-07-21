from gibson.core.state import GibsonState
from gibson.core.smf.records.type7 import data_lost
from gibson.core.smf.writer import get_smf_writer


def test_smf7_data_lost_training_record():
    st = GibsonState.create()
    data_lost(st, count_lost=5, affected_record_types="80,110")
    row = get_smf_writer(st).query(record_type=7)[0].to_flat_fields()
    assert row["COUNT_LOST"] == "5"
    assert row["AFFECTED_RECORD_TYPES"] == "80,110"
