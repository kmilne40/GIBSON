from __future__ import annotations
import tempfile
from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.fibs_training.lab_catalog import get_lab, list_labs
from gibson.apps.fibs_training.lab_runner import run_lab, secure_compare, reset_lab
from gibson.core.passticket import get_passticket_service
from gibson.apps.racf_admin import racf_admin_command
from gibson.apps.racf_services.menu import racf_services_command
from gibson.apps.zsecure_engine import zsecure_command


def _state():
    return GibsonState.create(GibsonConfig(sim_root=Path(tempfile.mkdtemp())))


def test_identity_lab_catalog_has_passticket_and_mfa():
    labs = {l.slug: l for l in list_labs()}
    assert 'passticket-replay-protection' in labs
    assert 'passticket-hardening' in labs
    assert 'mfa-tso-enforcement' in labs
    assert 'mfa-passticket-bypass' in labs
    assert labs['passticket-replay-protection'].category.startswith('Identity and Access')


def test_passticket_labs_run_secure_reset_and_emit_evidence():
    state = _state()
    for slug in ['passticket-generate-validate','passticket-replay-protection','passticket-applid-mismatch','passticket-overbroad-irrptauth','passticket-debug-leakage','passticket-expiry','passticket-hardening']:
        res = run_lab(state, slug, 'payload', 'teller', trace_id=f'TR-{slug}')
        assert res['lab'] == slug
        assert res['request'] and res['response']
        assert res['trace_events']
        assert any(str(e.get('smf_type')) == '80' for e in res['smf_events'])
        sec = secure_compare(state, slug, 'payload', 'teller')
        assert sec['mode'] == 'secure-compare'
        rst = reset_lab(state, slug, 'teller')
        assert rst['response']['result'] == 'RESET'


def test_passticket_replay_and_mismatch_are_blocked_by_default():
    state = _state()
    replay = run_lab(state, 'passticket-replay-protection', '', 'teller')
    assert replay['response']['replay_blocked'] is True
    mismatch = run_lab(state, 'passticket-applid-mismatch', '', 'teller')
    assert mismatch['response']['mismatch_blocked'] is True
    assert any('PTKT_' in a['event_type'] for a in getattr(state, 'identity_events', []))


def test_mfa_labs_run_and_emit_identity_evidence():
    state = _state()
    for slug in ['mfa-tso-enforcement','mfa-cics-step-up','mfa-service-gap-ftp','mfa-fallback-breakglass','mfa-shared-factor-seed','mfa-passticket-bypass','mfa-fatigue-concept','mfa-audit-review','mfa-hardening']:
        res = run_lab(state, slug, 'payload', 'teller')
        assert res['lab'] == slug
        assert res['response']['status'] == 200
        assert res['trace_events']
    assert any(e['event_type'].startswith('MFA') for e in getattr(state, 'identity_events', []))


def test_passticket_displays_are_live_not_stale_fibs_only():
    state = _state()
    get_passticket_service(state)
    admin = racf_admin_command(state, 'IBMUSER', 'RACFADMIN PTKTDATA')
    assert 'CICS' in admin and 'WEBBANK' in admin and 'FIBS.PTKT.KEY' not in admin
    svc = racf_services_command(state, 'IBMUSER', 'RACFSERV 2')
    assert 'PTKTDATA' in svc and 'TSOGIBS' in svc


def test_zsecure_reports_identity_events():
    state = _state()
    run_lab(state, 'mfa-passticket-bypass', '', 'teller')
    out = zsecure_command(state, 'IBMUSER', 'ZSEC MFA')
    assert out and ('MFA' in out or 'IDENTITY' in out)
