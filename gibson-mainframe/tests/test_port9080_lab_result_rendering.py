from __future__ import annotations
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.fibs_training.lab_catalog import get_lab
from gibson.apps.fibs_training.lab_runner import run_lab
from gibson.apps.fibs_training.lab_rendering import render_lab_detail


def test_result_rendering_populates_request_response_evidence_and_timeline():
    state = GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=Path('/tmp/gibson-render'), security_mode='vuln'))
    lab = get_lab('excessive-data')
    result = run_lab(state, 'excessive-data', '1001', 'teller', trace_id='TRACE-RENDER')
    html = render_lab_detail(lab, 'vulnerable', result)
    assert 'TRACE-RENDER' in html
    assert 'Latest evidence' in html
    assert 'EXCESSIVE_DATA_RETURNED' in html
    assert 'Live mainframe timeline' in html
    assert 'Request / response' in html
