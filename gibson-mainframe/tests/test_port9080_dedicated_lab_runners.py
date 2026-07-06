from __future__ import annotations
import pytest
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.fibs_training.lab_catalog import list_labs
from gibson.apps.fibs_training.lab_runner import run_lab, secure_compare, _RUNNERS


def _state():
    return GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=Path('/tmp/gibson-test'), security_mode='vuln'))


@pytest.mark.parametrize('slug', [lab.slug for lab in list_labs()])
def test_every_lab_has_dedicated_runner_and_structured_vulnerable_secure_results(slug):
    assert slug in _RUNNERS
    state = _state()
    res = run_lab(state, slug, '1001', 'teller', trace_id=f'TRACE-{slug}')
    assert res['lab'] == slug
    assert res['trace_id'] == f'TRACE-{slug}'
    assert res['request'] and res['response']
    assert res['trace_events']
    assert res['evidence_id']
    assert 'secure_comparison' in res
    sec = secure_compare(state, slug, '1001', 'teller', trace_id=f'TRACE-{slug}-SEC')
    assert sec['lab'] == slug
    assert sec['trace_id'] == f'TRACE-{slug}-SEC'
    assert sec['request'] and sec['response'] and sec['trace_events']


def test_unique_evidence_content_for_selected_labs():
    state = _state()
    checks = {
        'idor': 'authorization',
        'mass-assignment': 'restricted_fields',
        'weak-auth': 'accepted',
        'verbose-errors': 'backend_detail_logged',
        'business-logic': 'rule',
        'method-override': 'effective_method',
        'excessive-data': 'field_count',
    }
    for slug, key in checks.items():
        res = run_lab(state, slug, '1001', 'teller', trace_id='TRACE-'+slug)
        assert key in res['response'] or key in str(res['response'])
