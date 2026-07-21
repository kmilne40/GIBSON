from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.core.security_event_bus import emit_smf80, emit_smf102, emit_smf110


def test_security_event_bus_emits_simulated_console_records():
    st = GibsonState.create(GibsonConfig())
    emit_smf80(st, event='IDOR', user='ALICE', channel='WEB9080', resource='CBSA.ACCOUNT.00042', result='SUCCESS')
    emit_smf102(st, event='SQLI_SEARCH', user='ALICE', channel='WEB9080', table='CBSA.ACCOUNT', result='SUCCESS')
    emit_smf110(st, event='FIELD_MUTATION', user='DVCAUSR', channel='HACK3270', transaction='DVCA', program='MCORDERS', result='SUCCESS')
    text = '\n'.join(m for _s, m in st.console_events)
    assert 'SIMULATED SMF80' in text
    assert 'SIMULATED SMF102' in text
    assert 'SIMULATED SMF110' in text
    assert 'CORRID=' in text
    assert len(st.security_training_events) == 3
