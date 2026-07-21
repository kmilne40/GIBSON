from pathlib import Path

from gibson.apps.master_console import MasterConsoleUI
from gibson.apps.welcome.routes import render_page
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.core.security_event_bus import emit_smf110
from gibson.services import telnet_server
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path | None = None) -> GibsonState:
    if tmp_path is None:
        tmp_path = Path('/tmp/gibson-v6-test')
    cfg = GibsonConfig(
        sim_root=tmp_path,
        files_root=tmp_path / 'f',
        commands_dir=tmp_path / 'f' / 'commands',
        gacf_path=tmp_path / 'GACF.DB',
    )
    cfg.ensure()
    cfg.gacf_path.write_text('IBMUSER:SYS1:SPECIAL:OMVS\n', encoding='utf-8')
    return GibsonState.create(cfg)


def test_gibson_sentry_branding_and_routes(tmp_path):
    st = make_state(tmp_path)
    for path in ['/cti', '/cti/dashboard', '/cti/events', '/cti/rss', '/cti/m4m/navigator']:
        code, ctype, body = render_page(path, st)
        assert code == 200
        assert 'GIBSON SENTRY' in body
        assert 'GIBSON SENTINEL' not in body
    assert 'RSS Feed' in render_page('/cti/rss', st)[2]


def test_rss_page_uses_config_and_safety(tmp_path):
    st = make_state(tmp_path)
    code, _, body = render_page('/cti/rss', st)
    assert code == 200
    assert 'Configured Feeds' in body
    assert 'KrebsOnSecurity' in body or 'KREBSONSECURITY' in body
    assert 'Only HTTP/HTTPS feeds are accepted' in body


def test_event_detail_and_m4m_layer(tmp_path):
    st = make_state(tmp_path)
    ev = emit_smf110(st, event='DVCA_PIN_BRUTE_SUCCESS', user='IBMUSER', channel='CICS', result='SUCCESS', transaction='DVCA', detail='PIN brute force training')
    body = render_page('/cti/events', st)[2]
    assert 'DVCA_PIN_BRUTE_SUCCESS' in body
    assert 'T1110' in body
    detail = render_page('/cti/events/' + ev.event_id, st)[2]
    assert 'SMF-style Evidence' in detail
    assert 'Network / IDS Evidence' in detail
    layer = render_page('/cti/m4m/layer.json', st)[2]
    assert 'Gibson Mainframe Training Layer' in layer
    assert 'T1110' in layer


def test_m4m_navigator_page(tmp_path):
    st = make_state(tmp_path)
    body = render_page('/cti/m4m/navigator', st)[2]
    assert 'M4M Navigator' in body
    assert 'matrix' in body
    assert 'Reconnaissance' in body


def test_master_console_event_colour_is_yellow_not_blue(tmp_path):
    st = make_state(tmp_path)
    ui = MasterConsoleUI(st)
    rendered = ui._format_event('INFO', 'IEE600I SRCIP=198.51.100.66 SERVICE=CTI')
    assert '\x1b[33m' in rendered
    assert '\x1b[34m' not in rendered and '\x1b[44m' not in rendered


def test_tso_console_plain_source_and_racfblocker_still_fixed(tmp_path):
    src = telnet_server.GibsonTelnetSession._plain_console_snapshot.__code__.co_consts
    joined = '\n'.join(str(x) for x in src)
    assert 'GIBSON CONSOLE' in joined
    assert 'PROCESSOR BLOCK ACTIVITY' not in joined
    st = make_state(tmp_path)
    out = TsoCommandProcessor(st, 'IBMUSER').run('NETSTAT HOME')
    assert 'RACF - SERVICES OPTION MENU' not in out
    assert 'EZZ2350I' in out or 'NETSTAT' in out
