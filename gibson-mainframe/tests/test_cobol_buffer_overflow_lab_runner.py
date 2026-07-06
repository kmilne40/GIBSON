from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.fibs_training.lab_catalog import get_lab
from gibson.apps.fibs_training.lab_runner import run_lab, secure_compare


def test_cobol_bo_lab_exists_and_runs():
    lab = get_lab('cobol-buffer-overflow')
    assert lab is not None
    assert 'buffer overflow' in lab.beginner_explanation.lower()
    state = GibsonState.create(GibsonConfig())
    result = run_lab(state, 'cobol-buffer-overflow', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY', 'ALICE')
    assert result['response']['result'] == 'AUTH_FLAG_OVERWRITE'
    assert any(ev.get('component') == 'COBOL' for ev in result['trace_events'])
    assert any('SMF80' in str(ev) or ev.get('smf_type') == '80' for ev in result['smf_events'])


def test_cobol_bo_secure_compare_blocks():
    state = GibsonState.create(GibsonConfig())
    result = secure_compare(state, 'cobol-buffer-overflow', '1234567890ABCDEF', 'ALICE')
    assert result['response']['result'] == 'BLOCKED_SECURE'
