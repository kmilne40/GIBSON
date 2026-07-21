from pathlib import Path
import tempfile, shutil

from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.apps.master_console import MasterConsoleController
from gibson.core import v26_features
from gibson.apps.editor import EditorModel, EditorCommandProcessor


def make_state(mode='secure'):
    root = Path(tempfile.mkdtemp())
    cfg = GibsonConfig(sim_root=root, files_root=root/'f', commands_dir=root/'f'/'commands', transfer_root=root/'transfers', gacf_path=root/'GACF.DB', security_mode=mode)
    st = GibsonState.create(cfg)
    return st, root


def test_guest_sys1_none_enforced_nonwarning_and_warning_allowed():
    st, root = make_state('secure')
    try:
        # Non-warning SYS1 dataset denies GUEST read and update.
        for intent in ('READ', 'UPDATE'):
            try:
                st.datasets.security.authorize('GUEST', 'SYS1.PROCLIB', intent)
                assert False, 'GUEST should have ACCESS(NONE) to SYS1.PROCLIB'
            except PermissionError as exc:
                assert 'ICH408I' in str(exc)
        # The training WARNING profile permits access but records warnings.
        assert st.dynamic_racf._find_profile('DATASET', 'SYS1.PARMLIB').warning is True
        st.datasets.security.authorize('GUEST', 'SYS1.PARMLIB', 'UPDATE')
        assert any('WARNING MODE' in text for _sev, text in st.drain_console_events())
    finally:
        shutil.rmtree(root)


def test_split_console_removed_but_standard_console_service_still_works():
    st, root = make_state('secure')
    try:
        proc = TsoCommandProcessor(st, 'IBMUSER')
        assert 'NOT AVAILABLE' in proc.run('SPLITCON ON')
        ctl = MasterConsoleController(st, 'IBMUSER')
        assert 'NOT AVAILABLE' in ctl.execute('D SPLITCON').text
        out = ctl.execute('S FTPD').text
        assert 'STARTED' in out or 'ALREADY ACTIVE' in out or 'FTPD' in out
    finally:
        shutil.rmtree(root)


def test_ispf_right_panel_and_extra_software_commands():
    right = v26_features.ispf_right_panel('IBMUSER')
    plain = '\n'.join(right)
    assert 'User ID' in plain and 'IBMUSER' in plain
    assert 'Terminal' in plain and '3278' in plain
    assert 'System ID' in plain and 'S0W1' in plain
    assert 'Release' in plain and 'ISPF 7.5' in plain
    # HH:MM only, regardless of colour escape wrappers.
    assert ':' in plain
    st, root = make_state('secure')
    try:
        proc = TsoCommandProcessor(st, 'IBMUSER')
        assert 'ZSECURE MAIN MENU' in proc.run('ZSECURE')
        assert 'SMP/E MAIN MENU' in proc.run('SMPE')
        assert 'SYSMOD STATUS' in proc.run('SMPE LIST SYSMODS')
    finally:
        shutil.rmtree(root)


def test_port_scan_per_port_probe_alerts_console_dashboard_and_zsecure():
    st, root = make_state('secure')
    try:
        for port in (2023, 2111, 50000, 8443):
            st.note_port_touch('203.0.113.10', port, 'TEST')
        assert any(a.get('event_type') == 'PORT_SCAN' for a in st.recent_dashboard_alerts(10))
        assert any('PORT SCAN' in text for _sev, text in st.drain_console_events())
        proc = TsoCommandProcessor(st, 'IBMUSER')
        assert 'PORT_SCAN' in proc.run('D SECURITY')
        assert 'PORT_SCAN' in proc.run('ZSEC ALERTS')
    finally:
        shutil.rmtree(root)


def test_editor_long_line_not_split_at_midpoint():
    model = EditorModel([''], recfm='FB', lrecl=80)
    proc = EditorCommandProcessor(model)
    line70 = 'A' * 70
    assert proc.execute('TEXT 1 ' + line70) == 'LINE UPDATED'
    assert model.lines[0] == line70
    line80 = 'B' * 80
    proc.execute('TEXT 1 ' + line80)
    assert model.lines[0] == line80
    line90 = 'C' * 90
    proc.execute('TEXT 1 ' + line90)
    assert model.lines[0] == line90[:80]
