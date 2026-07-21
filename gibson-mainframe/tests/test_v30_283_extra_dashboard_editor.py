from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.core import v26_features
from gibson.apps.editor import EditorModel, EditorCommandProcessor


def state(tmp_path):
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/'f', commands_dir=tmp_path/'f'/'commands', transfer_root=tmp_path/'transfers', gacf_path=tmp_path/'GACF.DB')
    return GibsonState.create(cfg)


def test_zsecure_smpe_rss_commands(tmp_path):
    st=state(tmp_path); p=TsoCommandProcessor(st,'IBMUSER')
    assert 'ZSECURE MAIN MENU' in p.run('ZSEC')
    assert 'ZSECURE ALERTS' in p.run('ZSEC ALERTS') or 'NO ALERTS' in p.run('ZSEC ALERTS')
    assert 'SMP/E MAIN MENU' in p.run('SMPE')
    assert 'SYSMOD' in p.run('SMPE LIST SYSMODS')
    assert 'RSS FEED READER' in p.run('RSS')
    assert 'IBMUSER.RSS.FEED' in p.run('RSS CONFIG')


def test_localhost_portscan_suppressed_remote_alerts(tmp_path):
    st=state(tmp_path); st.config.port_scan_threshold=3; st.config.port_scan_window=30
    for port in [2023,2111,8443]: st.note_port_touch('127.0.0.1', port, service='TEST')
    assert not [a for a in st.recent_dashboard_alerts(10) if a.get('event_type')=='PORT_SCAN']
    for port in [2023,2111,8443]: st.note_port_touch('192.0.2.44', port, service='TEST')
    assert [a for a in st.recent_dashboard_alerts(10) if a.get('event_type')=='PORT_SCAN']


def test_editor_rejects_over_lrecl():
    model=EditorModel([''], recfm='FB', lrecl=80)
    proc=EditorCommandProcessor(model)
    assert proc.execute('1 ' + 'A'*80) == 'LINE UPDATED'
    assert len(model.lines[0]) == 80
    msg=proc.execute('1 ' + 'B'*81)
    assert 'TRUNCATED TO LRECL 80' in str(msg)
    assert model.lines[0] == 'B'*80


def test_ispf_panel_alignment():
    lines=v26_features.ispf_right_panel('IBMUSER')
    plain=[]
    import re
    ansi=re.compile(r'\x1b\[[0-9;]*m')
    for l in lines: plain.append(ansi.sub('', l))
    idx=[p.index(':') for p in plain]
    assert len(set(idx)) == 1
    assert any('Release .' in p and 'ISPF 7.5' in p for p in plain)
